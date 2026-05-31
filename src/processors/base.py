from __future__ import annotations

import csv
import re
from pathlib import Path

from src.core.metadata import write_metadata
from src.core.project import claim_policy_path, load_json_compatible_yaml, output_dir
from src.core.table_reader import coerce_numeric_rows, read_table
from src.origin.adapter import export_plot
from src.processors.calculations import build_processed_table, bet_numeric, condition_screening_numeric, epr_numeric, type_specific_results
from src.processors.profiles import SUPPORTED_PROCESSOR_PROFILES


MANUAL_CHECK_ITEMS = {
    "XRD": ["candidate peaks only; no phase or crystal-plane assignment"],
    "UV-vis DRS": ["Eg_candidate and linear interval require confirmation"],
    "EIS": ["no equivalent-circuit fitting or mechanism conclusion"],
    "XPS": ["peak positions/areas are candidates; no valence assignment"],
    "EPR": ["no radical species assignment"],
    "Mott-Schottky": ["flat-band candidate is not CB/VB"],
}


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return cleaned.strip("_") or "dataset"


def process_table_dataset(
    project_root: Path,
    classification: dict,
    source_file: Path,
    *,
    no_origin: bool = True,
    force: bool = True,
    triage: dict | None = None,
) -> dict:
    rows = read_table(source_file)
    numeric = coerce_numeric_rows(rows)
    data_type = classification["inferred_data_type"]
    if not numeric and data_type == "reaction_condition_screening":
        numeric = condition_screening_numeric(rows)
    if data_type == "BET":
        numeric = bet_numeric(rows, numeric)
    if data_type == "EPR":
        numeric = epr_numeric(rows, numeric)
    processor_name = classification["selected_processor"]
    if (
        classification.get("supported_in_phase_1") is False
        or processor_name == "none"
        or data_type == "reference_literature"
    ):
        raise ValueError(f"{data_type} is scan-only and must not be processed as experimental data.")

    source_slug = safe_name(source_file.stem)
    dataset_suffix = _queue_dataset_suffix(triage)
    output_slug = f"{source_slug}_{dataset_suffix}" if dataset_suffix else source_slug
    dataset_id = f"{safe_name(data_type)}_{output_slug}"
    profile = SUPPORTED_PROCESSOR_PROFILES.get(data_type)
    processed_dir = output_dir(project_root, "processed_data", safe_name(data_type))
    metadata_dir = output_dir(project_root, "metadata", safe_name(data_type))
    processed_csv = processed_dir / f"{output_slug}_processed.csv"
    if processed_csv.exists() and not force:
        raise FileExistsError(f"Output already exists; rerun with --force to overwrite: {processed_csv}")

    warnings = []
    key_results = {}
    if not numeric:
        warnings.append("No two-column numeric data could be read.")
        processed_csv.write_text("x,y\n", encoding="utf-8")
        origin_result = None
        status = "fail"
    else:
        numeric = sorted(numeric, key=lambda item: item[0], reverse=data_type in {"XPS", "FTIR"})
        headers, processed_rows = build_processed_table(data_type, numeric, rows)
        with processed_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(headers)
            writer.writerows(processed_rows)
        y_values = [value for _, value in numeric]
        key_results = {
            "point_count": len(numeric),
            "x_min": min(x for x, _ in numeric),
            "x_max": max(x for x, _ in numeric),
            "y_min": min(y_values),
            "y_max": max(y_values),
        }
        key_results.update(type_specific_results(data_type, numeric, rows))
        if data_type == "UV-vis DRS":
            warnings.append("Eg candidate requires configured Tauc interval selection.")
        if data_type == "HPLC/LC exported data" and key_results.get("lc_quantification_blocked_reason"):
            warnings.append(str(key_results["lc_quantification_blocked_reason"]))
        x_title, y_title = _origin_axis_titles(headers)
        if no_origin:
            origin_result = None
            status = "processed_no_origin"
            warnings.append("Origin export skipped by --no-origin.")
        else:
            origin_result = export_plot(
                project_root,
                dataset_id,
                processed_csv,
                x_title,
                y_title,
                data_type=data_type,
                source_file=source_file,
            )
            status = "success" if origin_result.ok else "fail"
            if not origin_result.ok:
                warnings.append(origin_result.message)

    metadata_path = metadata_dir / output_slug / "metadata.json"
    manual_check_items = list(
        profile["manual_check_items"]
        if profile
        else MANUAL_CHECK_ITEMS.get(data_type, ("manual_check_required by Phase 1 policy",))
    )
    forbidden_claims = _forbidden_claims(project_root, data_type, profile)
    plot_type = str(profile["plot_type_hints"][0] if profile else "line")
    return write_metadata(
        project_root=project_root,
        path=metadata_path,
        dataset_id=dataset_id,
        data_type=data_type,
        source_file=source_file,
        processor_name=processor_name,
        processing_status=status,
        plot_type=plot_type,
        origin_file=origin_result.origin_file if origin_result else None,
        figure_tif=origin_result.figure_tif if origin_result else None,
        processed_data=processed_csv,
        preview_png=origin_result.preview_png if origin_result else None,
        manual_check_items=manual_check_items,
        forbidden_claims=forbidden_claims,
        warnings=warnings,
        key_results=key_results,
        triage=triage,
    )


def _forbidden_claims(project_root: Path, data_type: str, profile: dict | None) -> list[str]:
    claims: list[str] = []
    if profile:
        claims.extend(str(item) for item in profile["forbidden_claims"])
    try:
        policy = load_json_compatible_yaml(claim_policy_path(project_root))
    except FileNotFoundError:
        policy = load_json_compatible_yaml(claim_policy_path(Path(__file__).resolve().parents[2]))
    claims.extend(str(item) for item in policy.get("forbidden_claims", []))
    type_policy = policy.get("type_specific", {}).get(data_type, {})
    claims.extend(str(item) for item in type_policy.get("forbidden", []))
    deduped = []
    seen = set()
    for claim in claims:
        if claim not in seen:
            seen.add(claim)
            deduped.append(claim)
    return deduped


def _origin_axis_titles(headers: list[str]) -> tuple[str, str]:
    if len(headers) >= 2:
        return headers[0], headers[1]
    if len(headers) == 1:
        return headers[0], "signal"
    return "x", "y"


def _queue_dataset_suffix(triage: dict | None) -> str:
    if not triage:
        return ""
    queue_id = str(triage.get("queue_id") or "").strip()
    if not queue_id:
        return ""
    return safe_name(queue_id[:8])


def process_supported(project_root: Path, manifest: dict, *, no_origin: bool = True, force: bool = True) -> list[dict]:
    results = []
    for classification in manifest["classifications"]:
        if not classification["supported_in_phase_1"]:
            continue
        for file_name in classification["files"]:
            results.append(
                process_table_dataset(
                    project_root,
                    classification,
                    Path(file_name),
                    no_origin=no_origin,
                    force=force,
                )
            )
    return results
