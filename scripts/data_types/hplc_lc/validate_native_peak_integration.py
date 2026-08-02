from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import linear_sum_assignment


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.hplc_analysis import load_hplc_analysis_config  # noqa: E402
from src.core.hplc_openlab import extract_hplc_openlab_dataset  # noqa: E402
from src.core.hplc_peak_integration import (  # noqa: E402
    NATIVE_INTEGRATOR_NAME,
    NATIVE_INTEGRATOR_VERSION,
    integrate_chromatogram,
    match_native_target_peaks,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate project-native HPLC target detection and integration against "
            "available OpenLab .rx rows.  Vendor rows are validation evidence only."
        )
    )
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--since", type=date.fromisoformat, default=date(2026, 7, 17))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    input_root = args.input_root.resolve()
    output_json = args.output_json.resolve()
    _validate_paths(input_root, output_json, force=args.force)
    report = validate_native_integration(input_root, since=args.since)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"report: {output_json}")
    return 0 if report["passed"] else 1


def validate_native_integration(input_root: Path, *, since: date) -> dict[str, Any]:
    config = load_hplc_analysis_config(PROJECT_ROOT)
    dataset = extract_hplc_openlab_dataset(input_root, since)
    train_end = date.fromisoformat(config["native_integration"]["validation_train_end_date"])
    holdout_start = date.fromisoformat(
        config["native_integration"]["validation_holdout_start_date"]
    )
    result_set_splits = _result_set_splits(
        dataset["injections"],
        train_end=train_end,
        holdout_start=holdout_start,
    )
    signal_by_injection = {
        str(column["injection_id"]): column
        for raw_sheet in dataset["raw_sheets"]
        for column in raw_sheet["columns"]
    }
    injection_by_id = {
        str(injection["injection_id"]): injection
        for injection in dataset["injections"]
    }
    vendor_by_injection: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for peak in dataset["peaks"]:
        vendor_by_injection[str(peak["injection_id"])].append(peak)

    all_peak_errors: list[float] = []
    all_peak_absolute_errors: list[float] = []
    target_boundary_errors: dict[str, list[float]] = defaultdict(list)
    boundary_issues: list[dict[str, Any]] = []
    for injection_id, vendor_peaks in vendor_by_injection.items():
        column = signal_by_injection[injection_id]
        time = np.asarray(column["time"], dtype=np.float64)
        signal = np.asarray(column["signal"], dtype=np.float64)
        for peak in vendor_peaks:
            recomputed = _area_from_vendor_boundaries(time, signal, peak)
            vendor_area = float(peak["area"])
            absolute_error = abs(recomputed - vendor_area)
            relative_error = absolute_error / max(abs(vendor_area), 1e-12) * 100.0
            all_peak_errors.append(relative_error)
            all_peak_absolute_errors.append(absolute_error)
            target_key = _target_for_rt(float(peak["retention_time_min"]), config)
            if target_key:
                target_boundary_errors[target_key].append(relative_error)
            if relative_error > 3.0:
                boundary_issues.append(
                    {
                        "injection_id": injection_id,
                        "result_set_id": injection_by_id[injection_id]["result_set_id"],
                        "peak_ordinal": int(peak["peak_ordinal"]),
                        "retention_time_min": float(peak["retention_time_min"]),
                        "vendor_area": vendor_area,
                        "recomputed_area": recomputed,
                        "ape_percent": relative_error,
                    }
                )

    validation_rows: list[dict[str, Any]] = []
    integration_failures: list[dict[str, str]] = []
    all_peak_matches: list[dict[str, Any]] = []
    unmatched_native_peak_count = 0
    unmatched_vendor_peak_count = 0
    for injection_id, injection in injection_by_id.items():
        state = str(injection.get("openlab_processing_state") or "").casefold()
        if state in {"nomethodprovided", "missing_rx", "missing_result"}:
            continue
        column = signal_by_injection[injection_id]
        try:
            integrated = integrate_chromatogram(
                column["time"],
                column["signal"],
                config,
            )
            matched = match_native_target_peaks(
                integrated["peaks"],
                config["targets"],
                ambiguity_margin_min=float(
                    config["quality_thresholds"]["ambiguous_rt_distance_margin_min"]
                ),
                signal_quantifiable=True,
            )
        except Exception as exc:
            integration_failures.append(
                {
                    "injection_id": injection_id,
                    "result_set_id": str(injection["result_set_id"]),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        acquisition_date = date.fromisoformat(str(injection["acquisition_date"]))
        result_set_key = str(injection.get("result_set_id") or f"INJECTION:{injection_id}")
        split = result_set_splits[result_set_key]
        vendor_peaks = vendor_by_injection.get(injection_id, [])
        matched_peaks, unmatched_native, unmatched_vendor = _match_all_peaks(
            integrated["peaks"],
            vendor_peaks,
            maximum_rt_error_min=0.03,
        )
        unmatched_native_peak_count += unmatched_native
        unmatched_vendor_peak_count += unmatched_vendor
        for match in matched_peaks:
            all_peak_matches.append(
                {
                    "split": split,
                    "injection_id": injection_id,
                    "result_set_id": str(injection["result_set_id"]),
                    **match,
                }
            )
        for target_key, target in config["targets"].items():
            nominal = float(target["nominal_rt_min"])
            tolerance = float(target["rt_tolerance_min"])
            candidates = [
                peak
                for peak in vendor_peaks
                if peak.get("retention_time_min") is not None
                and abs(float(peak["retention_time_min"]) - nominal) <= tolerance + 1e-12
            ]
            candidates.sort(
                key=lambda peak: (
                    abs(float(peak["retention_time_min"]) - nominal),
                    int(peak["peak_ordinal"]),
                )
            )
            vendor_peak = candidates[0] if candidates else None
            native_peak = matched[target_key]
            row = {
                "split": split,
                "injection_id": injection_id,
                "result_set_id": str(injection["result_set_id"]),
                "acquisition_date": acquisition_date.isoformat(),
                "target_key": target_key,
                "vendor_detected": vendor_peak is not None,
                "native_detected": native_peak["retention_time_min"] is not None,
                "vendor_peak_ordinal": (
                    int(vendor_peak["peak_ordinal"]) if vendor_peak else None
                ),
                "native_peak_ordinal": native_peak["selected_peak_ordinal"],
                "vendor_rt_min": (
                    float(vendor_peak["retention_time_min"]) if vendor_peak else None
                ),
                "native_rt_min": native_peak["retention_time_min"],
                "vendor_area": float(vendor_peak["area"]) if vendor_peak else None,
                "native_area": native_peak["area"] if vendor_peak else None,
            }
            if vendor_peak and native_peak["retention_time_min"] is not None:
                row["rt_abs_error_min"] = abs(
                    float(native_peak["retention_time_min"])
                    - float(vendor_peak["retention_time_min"])
                )
                row["area_ape_percent"] = abs(
                    float(native_peak["area"]) - float(vendor_peak["area"])
                ) / max(abs(float(vendor_peak["area"])), 1e-12) * 100.0
            else:
                row["rt_abs_error_min"] = None
                row["area_ape_percent"] = None
            validation_rows.append(row)

    metrics = {
        split: _target_metrics(
            [row for row in validation_rows if split == "all" or row["split"] == split],
            config,
        )
        for split in ("train", "holdout", "all")
    }
    all_peak_metrics = {
        split: _all_peak_metrics(
            [
                row
                for row in all_peak_matches
                if split == "all" or row["split"] == split
            ]
        )
        for split in ("train", "holdout", "all")
    }
    boundary_metrics = {
        "all_peaks": _error_metrics(all_peak_errors),
        "all_peaks_absolute_error_mau_s": _error_metrics(all_peak_absolute_errors),
        "targets": {
            key: _error_metrics(target_boundary_errors.get(key, []))
            for key in config["targets"]
        },
    }
    acceptance = config["native_integration"]["acceptance"]
    holdout_gates: dict[str, dict[str, bool]] = {}
    for target_key, values in metrics["holdout"]["targets"].items():
        holdout_gates[target_key] = {
            "positive_cases_present": values["true_positive"] + values["false_negative"] > 0,
            "negative_cases_present": values["true_negative"] + values["false_positive"] > 0,
            "sensitivity": _at_least(
                values["sensitivity"],
                float(acceptance["minimum_target_sensitivity"]),
            ),
            "specificity": _at_least(
                values["specificity"],
                float(acceptance["minimum_target_specificity"]),
            ),
            "rt_p95": _metric_at_most(
                values["rt_abs_error_min"],
                "p95",
                float(acceptance["maximum_rt_p95_min"]),
            ),
            "area_median": _metric_at_most(
                values["area_ape_percent"],
                "median",
                float(acceptance["maximum_area_median_ape_percent"]),
            ),
            "area_p90": _metric_at_most(
                values["area_ape_percent"],
                "p90",
                float(acceptance["maximum_area_p90_ape_percent"]),
            ),
            "area_p95": _metric_at_most(
                values["area_ape_percent"],
                "p95",
                float(acceptance["maximum_area_p95_ape_percent"]),
            ),
        }
    vendor_boundary_gate = (
        _metric_at_most(boundary_metrics["all_peaks"], "median", 0.1)
        and _metric_at_most(boundary_metrics["all_peaks"], "p95", 0.5)
        and _metric_at_most(boundary_metrics["all_peaks"], "max", 3.0)
        and all(
            _metric_at_most(values, "p95", 0.1)
            for values in boundary_metrics["targets"].values()
        )
    )
    passed = (
        not integration_failures
        and vendor_boundary_gate
        and all(all(gates.values()) for gates in holdout_gates.values())
    )
    review_threshold = float(
        config["native_integration"]["validation_area_review_error_percent"]
    )
    area_review = [
        row
        for row in validation_rows
        if row["area_ape_percent"] is not None
        and float(row["area_ape_percent"]) > review_threshold
    ]
    detection_disagreements = [
        row
        for row in validation_rows
        if row["vendor_detected"] != row["native_detected"]
    ]
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now().astimezone().isoformat(),
        "input_root_name": input_root.name,
        "since": since.isoformat(),
        "integrator": {
            "name": NATIVE_INTEGRATOR_NAME,
            "version": NATIVE_INTEGRATOR_VERSION,
            "vendor_method_required": False,
        },
        "validation_design": {
            "vendor_role": "numerical validation oracle only",
            "train": f"acquisition_date <= {train_end.isoformat()}",
            "holdout": f"acquisition_date >= {holdout_start.isoformat()}",
            "split_unit": "complete OpenLab result sets by acquisition date",
            "holdout_blinding": (
                "historical holdout inspected during v1.1 external-rule confirmation; "
                "new result sets are required for a future blind validation claim"
            ),
        },
        "passed": passed,
        "gates": {
            "vendor_boundary_formula": vendor_boundary_gate,
            "holdout_targets": holdout_gates,
            "integration_failure_count_zero": not integration_failures,
        },
        "summary": {
            "selected_injections": dataset["summary"]["selected_injection_count"],
            "vendor_validation_injections": len(
                {
                    row["injection_id"] for row in validation_rows
                }
            ),
            "vendor_peak_rows": len(all_peak_errors),
            "native_integration_failures": len(integration_failures),
            "detection_disagreements": len(detection_disagreements),
            "area_review_items_over_threshold": len(area_review),
            "passed": passed,
        },
        "vendor_boundary_recalculation": boundary_metrics,
        "native_target_validation": metrics,
        "native_all_peak_validation": {
            "matching_rule": "one-to-one minimum RT distance, accepted at <= 0.03 min",
            "matched_peak_count": len(all_peak_matches),
            "unmatched_native_peak_count": unmatched_native_peak_count,
            "unmatched_vendor_peak_count": unmatched_vendor_peak_count,
            "metrics": all_peak_metrics,
        },
        "integration_failures": integration_failures,
        "detection_disagreements": detection_disagreements,
        "area_review_items": area_review,
        "vendor_boundary_issues": boundary_issues,
    }


def _area_from_vendor_boundaries(
    time: np.ndarray,
    signal: np.ndarray,
    peak: dict[str, Any],
) -> float:
    begin = float(peak["begin_time_min"])
    end = float(peak["end_time_min"])
    internal = (time > begin) & (time < end)
    segment_time = np.concatenate(([begin], time[internal], [end]))
    segment_signal = np.interp(segment_time, time, signal)
    baseline = np.interp(
        segment_time,
        (begin, end),
        (float(peak["baseline_start"]), float(peak["baseline_end"])),
    )
    return float(np.trapezoid(segment_signal - baseline, segment_time) * 60.0)


def _target_for_rt(retention_time: float, config: dict[str, Any]) -> str | None:
    candidates = []
    for key, target in config["targets"].items():
        difference = abs(retention_time - float(target["nominal_rt_min"]))
        if difference <= float(target["rt_tolerance_min"]) + 1e-12:
            candidates.append((difference, key))
    return min(candidates)[1] if candidates else None


def _result_set_splits(
    injections: list[dict[str, Any]],
    *,
    train_end: date,
    holdout_start: date,
) -> dict[str, str]:
    grouped: dict[str, set[str]] = defaultdict(set)
    for injection in injections:
        injection_id = str(injection["injection_id"])
        result_set_key = str(
            injection.get("result_set_id") or f"INJECTION:{injection_id}"
        )
        acquisition_date = date.fromisoformat(str(injection["acquisition_date"]))
        split = (
            "train"
            if acquisition_date <= train_end
            else "holdout"
            if acquisition_date >= holdout_start
            else "gap"
        )
        grouped[result_set_key].add(split)
    crossing = {
        result_set_id: sorted(splits)
        for result_set_id, splits in grouped.items()
        if len(splits) != 1
    }
    if crossing:
        raise ValueError(
            "OpenLab result sets cross validation split boundaries: "
            + json.dumps(crossing, ensure_ascii=False, sort_keys=True)
        )
    return {
        result_set_id: next(iter(splits))
        for result_set_id, splits in grouped.items()
    }


def _match_all_peaks(
    native_peaks: list[dict[str, Any]],
    vendor_peaks: list[dict[str, Any]],
    *,
    maximum_rt_error_min: float,
) -> tuple[list[dict[str, Any]], int, int]:
    native = [
        peak
        for peak in native_peaks
        if peak.get("retention_time_min") is not None and peak.get("area") is not None
    ]
    vendor = [
        peak
        for peak in vendor_peaks
        if peak.get("retention_time_min") is not None and peak.get("area") is not None
    ]
    if not native or not vendor:
        return [], len(native), len(vendor)
    costs = np.asarray(
        [
            [
                abs(
                    float(native_peak["retention_time_min"])
                    - float(vendor_peak["retention_time_min"])
                )
                for vendor_peak in vendor
            ]
            for native_peak in native
        ],
        dtype=np.float64,
    )
    native_indices, vendor_indices = linear_sum_assignment(costs)
    matches: list[dict[str, Any]] = []
    for native_index, vendor_index in zip(native_indices, vendor_indices):
        rt_error = float(costs[native_index, vendor_index])
        if rt_error > maximum_rt_error_min:
            continue
        native_peak = native[int(native_index)]
        vendor_peak = vendor[int(vendor_index)]
        vendor_area = float(vendor_peak["area"])
        native_area = float(native_peak["area"])
        matches.append(
            {
                "native_peak_ordinal": int(native_peak["peak_ordinal"]),
                "vendor_peak_ordinal": int(vendor_peak["peak_ordinal"]),
                "native_rt_min": float(native_peak["retention_time_min"]),
                "vendor_rt_min": float(vendor_peak["retention_time_min"]),
                "rt_abs_error_min": rt_error,
                "native_area": native_area,
                "vendor_area": vendor_area,
                "area_ape_percent": abs(native_area - vendor_area)
                / max(abs(vendor_area), 1e-12)
                * 100.0,
            }
        )
    return matches, len(native) - len(matches), len(vendor) - len(matches)


def _all_peak_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "matched_peak_count": len(rows),
        "rt_abs_error_min": _error_metrics(
            [float(row["rt_abs_error_min"]) for row in rows]
        ),
        "area_ape_percent": _error_metrics(
            [float(row["area_ape_percent"]) for row in rows]
        ),
        "area_ape_over_15_percent_count": sum(
            float(row["area_ape_percent"]) > 15.0 for row in rows
        ),
    }


def _target_metrics(rows: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    targets: dict[str, Any] = {}
    for target_key in config["targets"]:
        target_rows = [row for row in rows if row["target_key"] == target_key]
        true_positive = sum(
            row["vendor_detected"] and row["native_detected"] for row in target_rows
        )
        true_negative = sum(
            not row["vendor_detected"] and not row["native_detected"]
            for row in target_rows
        )
        false_positive = sum(
            not row["vendor_detected"] and row["native_detected"] for row in target_rows
        )
        false_negative = sum(
            row["vendor_detected"] and not row["native_detected"] for row in target_rows
        )
        targets[target_key] = {
            "row_count": len(target_rows),
            "true_positive": true_positive,
            "true_negative": true_negative,
            "false_positive": false_positive,
            "false_negative": false_negative,
            "sensitivity": _safe_ratio(true_positive, true_positive + false_negative),
            "specificity": _safe_ratio(true_negative, true_negative + false_positive),
            "rt_abs_error_min": _error_metrics(
                [
                    float(row["rt_abs_error_min"])
                    for row in target_rows
                    if row["rt_abs_error_min"] is not None
                ]
            ),
            "area_ape_percent": _error_metrics(
                [
                    float(row["area_ape_percent"])
                    for row in target_rows
                    if row["area_ape_percent"] is not None
                ]
            ),
        }
    return {"row_count": len(rows), "targets": targets}


def _error_metrics(values: list[float]) -> dict[str, float | int | None]:
    array = np.asarray(values, dtype=np.float64)
    if not len(array):
        return {
            "n": 0,
            "median": None,
            "p90": None,
            "p95": None,
            "p99": None,
            "max": None,
        }
    return {
        "n": int(len(array)),
        "median": float(np.median(array)),
        "p90": float(np.quantile(array, 0.90)),
        "p95": float(np.quantile(array, 0.95)),
        "p99": float(np.quantile(array, 0.99)),
        "max": float(np.max(array)),
    }


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    return float(numerator / denominator) if denominator else None


def _at_least(value: float | None, minimum: float) -> bool:
    return value is not None and float(value) >= minimum


def _metric_at_most(
    metrics: dict[str, float | int | None],
    key: str,
    maximum: float,
) -> bool:
    value = metrics.get(key)
    return int(metrics.get("n") or 0) > 0 and value is not None and float(value) <= maximum


def _validate_paths(input_root: Path, output_json: Path, *, force: bool) -> None:
    if not input_root.is_dir():
        raise NotADirectoryError(input_root)
    if output_json.suffix.casefold() != ".json":
        raise ValueError("--output-json must use a .json suffix")
    if _is_within(output_json, input_root):
        raise ValueError("validation reports must not be written into the raw input tree")
    if _is_within(output_json, PROJECT_ROOT):
        raise ValueError("validation reports must be written outside the project source tree")
    if output_json.exists() and not force:
        raise FileExistsError(f"Output already exists; pass --force to replace it: {output_json}")


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
