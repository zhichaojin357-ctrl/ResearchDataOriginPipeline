from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.agilent_dx import (  # noqa: E402
    DX_DECODER_NAME,
    DX_DECODER_VERSION,
    decode_agilent_dx,
)


_METADATA_KEYS = ("vendor", "date", "method", "sample", "vialpos")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the project-native Agilent OpenLab .dx decoder over a real-data "
            "corpus, optionally using rainbow-api only as an external numerical oracle."
        )
    )
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--oracle", choices=("rainbow", "none"), default="rainbow")
    parser.add_argument("--max-issues", type=int, default=100)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    input_root = args.input_root.resolve()
    output_json = args.output_json.resolve()
    _validate_paths(input_root, output_json, force=args.force)
    report = validate_decoder(
        input_root,
        oracle_name=args.oracle,
        max_issues=max(0, args.max_issues),
    )
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"report: {output_json}")
    return 0 if report["passed"] else 1


def validate_decoder(
    input_root: Path,
    *,
    oracle_name: str = "rainbow",
    max_issues: int = 100,
) -> dict[str, Any]:
    paths = sorted(input_root.rglob("*.dx"), key=lambda path: str(path).casefold())
    if not paths:
        raise FileNotFoundError(f"No .dx files found under {input_root}")

    oracle = None
    oracle_version = None
    if oracle_name == "rainbow":
        try:
            import rainbow
        except ImportError as exc:
            raise RuntimeError(
                "rainbow-api is required only for this requested parity check; "
                "the production decoder does not require it"
            ) from exc
        oracle = rainbow
        oracle_version = importlib_metadata.version("rainbow-api")
    elif oracle_name != "none":
        raise ValueError(f"Unsupported decoder oracle: {oracle_name}")

    counts = {
        "dx_total": len(paths),
        "native_decoded": 0,
        "declared_empty_rejected": 0,
        "native_unexpected_failure": 0,
        "oracle_decoded": 0,
        "oracle_expected_empty_failure": 0,
        "oracle_unexpected_failure": 0,
        "paired_decoded": 0,
        "metadata_exact": 0,
        "signal_count_exact": 0,
        "signal_attributes_exact": 0,
        "time_arrays_bitwise_exact": 0,
        "signal_arrays_bitwise_exact": 0,
        "complete_records_bitwise_exact": 0,
    }
    max_abs_time_error = 0.0
    max_abs_signal_error = 0.0
    issues: list[dict[str, Any]] = []

    for path in paths:
        relative = path.relative_to(input_root).as_posix()
        declared_empty = _declares_empty_integrable_signal(path)
        try:
            native = decode_agilent_dx(path)
            counts["native_decoded"] += 1
        except Exception as exc:
            native = None
            if declared_empty:
                counts["declared_empty_rejected"] += 1
            else:
                counts["native_unexpected_failure"] += 1
                _append_issue(
                    issues,
                    max_issues,
                    relative_path=relative,
                    category="native_decode_failure",
                    detail=f"{type(exc).__name__}: {exc}",
                )

        if oracle is None:
            continue
        try:
            reference = oracle.read(str(path))
            counts["oracle_decoded"] += 1
        except Exception as exc:
            reference = None
            if declared_empty:
                counts["oracle_expected_empty_failure"] += 1
            else:
                counts["oracle_unexpected_failure"] += 1
                _append_issue(
                    issues,
                    max_issues,
                    relative_path=relative,
                    category="oracle_decode_failure",
                    detail=f"{type(exc).__name__}: {exc}",
                )

        if native is None or reference is None:
            continue
        counts["paired_decoded"] += 1
        metadata_exact = all(
            str(native.metadata.get(key, "")) == str(reference.metadata.get(key, ""))
            for key in _METADATA_KEYS
        )
        if metadata_exact:
            counts["metadata_exact"] += 1

        signal_count_exact = len(native.datafiles) == len(reference.datafiles)
        if signal_count_exact:
            counts["signal_count_exact"] += 1
        attributes_exact = signal_count_exact
        time_exact = signal_count_exact
        signal_exact = signal_count_exact
        if signal_count_exact:
            for native_signal, reference_signal in zip(
                native.datafiles,
                reference.datafiles,
                strict=True,
            ):
                attributes_exact &= (
                    str(native_signal.name) == str(reference_signal.name)
                    and str(native_signal.detector) == str(reference_signal.detector)
                    and dict(native_signal.metadata or {})
                    == dict(reference_signal.metadata or {})
                )
                native_time = np.asarray(native_signal.xlabels)
                reference_time = np.asarray(reference_signal.xlabels)
                native_values = np.asarray(native_signal.data)
                reference_values = np.asarray(reference_signal.data)
                time_exact &= np.array_equal(native_time, reference_time)
                signal_exact &= np.array_equal(native_values, reference_values)
                if native_time.shape == reference_time.shape and native_time.size:
                    max_abs_time_error = max(
                        max_abs_time_error,
                        float(np.max(np.abs(native_time - reference_time))),
                    )
                if native_values.shape == reference_values.shape and native_values.size:
                    max_abs_signal_error = max(
                        max_abs_signal_error,
                        float(np.max(np.abs(native_values - reference_values))),
                    )

        if attributes_exact:
            counts["signal_attributes_exact"] += 1
        if time_exact:
            counts["time_arrays_bitwise_exact"] += 1
        if signal_exact:
            counts["signal_arrays_bitwise_exact"] += 1
        complete_exact = metadata_exact and attributes_exact and time_exact and signal_exact
        if complete_exact:
            counts["complete_records_bitwise_exact"] += 1
        else:
            _append_issue(
                issues,
                max_issues,
                relative_path=relative,
                category="parity_mismatch",
                detail={
                    "metadata_exact": metadata_exact,
                    "signal_count_exact": signal_count_exact,
                    "signal_attributes_exact": attributes_exact,
                    "time_arrays_bitwise_exact": time_exact,
                    "signal_arrays_bitwise_exact": signal_exact,
                },
            )

    native_complete = (
        counts["native_decoded"] + counts["declared_empty_rejected"] == counts["dx_total"]
        and counts["native_unexpected_failure"] == 0
    )
    if oracle is None:
        parity_passed = True
    else:
        paired = counts["paired_decoded"]
        parity_passed = (
            counts["oracle_unexpected_failure"] == 0
            and paired == counts["native_decoded"]
            and counts["metadata_exact"] == paired
            and counts["signal_count_exact"] == paired
            and counts["signal_attributes_exact"] == paired
            and counts["time_arrays_bitwise_exact"] == paired
            and counts["signal_arrays_bitwise_exact"] == paired
            and counts["complete_records_bitwise_exact"] == paired
        )
    passed = native_complete and parity_passed
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now().astimezone().isoformat(),
        "input_root_name": input_root.name,
        "decoder": {"name": DX_DECODER_NAME, "version": DX_DECODER_VERSION},
        "oracle": {"name": oracle_name, "version": oracle_version},
        "passed": passed,
        "gates": {
            "native_corpus_complete": native_complete,
            "oracle_bitwise_parity": parity_passed,
            "declared_zero-point_signals_are_explicit_failures": True,
        },
        "summary": {
            **counts,
            "max_abs_time_error": max_abs_time_error,
            "max_abs_signal_error": max_abs_signal_error,
            "passed": passed,
        },
        "issues": issues,
        "issue_count_recorded": len(issues),
        "issue_record_limit": max_issues,
    }


def _declares_empty_integrable_signal(path: Path) -> bool:
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read("injection.acmd"))
    integrable_counts: list[int] = []
    for signal in root.iter():
        if _local_name(signal.tag) != "Signal":
            continue
        fields = {
            _local_name(child.tag): (child.text or "").strip()
            for child in signal
        }
        if fields.get("IsIntegrable", "").casefold() != "true":
            continue
        try:
            integrable_counts.append(int(fields.get("NumberOfValues", "")))
        except ValueError:
            return False
    return bool(integrable_counts) and all(count <= 0 for count in integrable_counts)


def _append_issue(
    issues: list[dict[str, Any]],
    limit: int,
    *,
    relative_path: str,
    category: str,
    detail: Any,
) -> None:
    if len(issues) < limit:
        issues.append(
            {
                "relative_path": relative_path,
                "category": category,
                "detail": detail,
            }
        )


def _validate_paths(input_root: Path, output_json: Path, *, force: bool) -> None:
    if not input_root.is_dir():
        raise NotADirectoryError(input_root)
    if output_json.suffix.casefold() != ".json":
        raise ValueError("--output-json must use a .json suffix")
    if _is_within(output_json, input_root):
        raise ValueError("validation reports must not be written into the raw input tree")
    if _is_within(output_json, PROJECT_ROOT):
        raise ValueError("validation run products must be written outside the project source tree")
    if output_json.exists() and not force:
        raise FileExistsError(f"Output already exists; pass --force to replace it: {output_json}")


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


if __name__ == "__main__":
    raise SystemExit(main())
