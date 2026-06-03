from __future__ import annotations

from collections.abc import Sequence

from src.adapters import baseline_adapter, peak_detection_adapter


def is_available() -> bool:
    return baseline_adapter.is_available() and peak_detection_adapter.is_available()


def version_info() -> dict[str, object]:
    return {"baseline": baseline_adapter.version_info(), "peaks": peak_detection_adapter.version_info()}


def capabilities() -> dict[str, object]:
    return {
        "data_types": ["Raman", "PL", "FTIR", "UV-vis DRS"],
        "methods": ["pybaselines ASLS", "scipy candidate peaks"],
        "forbidden_claims": ["no defect assignment", "no recombination conclusion", "no bond assignment"],
    }


def process_or_analyze(x_values: Sequence[float], y_values: Sequence[float]) -> dict[str, object]:
    baseline = baseline_adapter.process_or_analyze(x_values, y_values)
    signal = baseline.get("corrected_signal") or list(y_values)
    peaks = peak_detection_adapter.process_or_analyze(x_values, signal)
    return {
        "ok": bool(peaks.get("candidate_peaks")),
        "baseline": baseline,
        "peaks": peaks,
        "manual_check_required": True,
    }


def smoke_test() -> dict[str, object]:
    result = process_or_analyze([float(i) for i in range(20)], [0, 1, 0, 0.2, 1.5, 0.1, *([0.2] * 14)])
    return {"ok": bool(result["baseline"].get("ok")) and bool(result["peaks"].get("ok")), "result": result}
