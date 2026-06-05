from __future__ import annotations

from pathlib import Path

import numpy as np

from src.processors.eis import (
    clean_eis_file,
    draft_fit_eis_randles_cpe,
    eis_plot_rows,
    randles_cpe_impedance,
)


def test_eis_cleaning_detects_invalid_low_frequency_tail(tmp_path: Path) -> None:
    source = _write_semicircle_with_bad_tail(tmp_path)

    cleaned = clean_eis_file(source)

    reasons = {item.reason for item in cleaned.ignored_points}
    assert len(cleaned.raw_points) > len(cleaned.cleaned_points)
    assert len(cleaned.ignored_points) >= 3
    assert "invalid_negative_z_real_unstable_low_frequency_tail" in reasons
    assert "sign_flip_negative_minus_z_imag_unstable_low_frequency_tail" in reasons
    assert "large_jump_unstable_low_frequency_tail" in reasons
    assert all(point.z_real_ohm > 0 for point in cleaned.cleaned_points)
    assert all(point.minus_z_imag_ohm >= 0 for point in cleaned.cleaned_points)
    assert cleaned.to_metadata()["raw_point_count"] == len(cleaned.raw_points)
    assert cleaned.to_metadata()["ignored_point_count"] == len(cleaned.ignored_points)


def test_randles_cpe_fit_returns_finite_parameters_and_curve(tmp_path: Path) -> None:
    source = _write_semicircle_with_bad_tail(tmp_path)
    cleaned = clean_eis_file(source)

    fit = draft_fit_eis_randles_cpe(cleaned.cleaned_points)

    assert fit.method == "least_squares_randles_cpe"
    assert set(fit.parameters) == {"Rs", "Rct", "Q", "n"}
    assert fit.parameters["Rs"] > 0
    assert fit.parameters["Rct"] > 0
    assert fit.parameters["Q"] > 0
    assert 0.5 <= fit.parameters["n"] <= 1.0
    assert np.isfinite(fit.residual_sse)
    assert len(fit.points) >= 100
    assert fit.semicircle_classification in {
        "near-ideal semicircle candidate",
        "depressed semicircle candidate",
    }


def test_eis_metadata_avoids_final_circuit_or_mechanism_conclusion(tmp_path: Path) -> None:
    source = _write_semicircle_with_bad_tail(tmp_path)
    cleaned = clean_eis_file(source)
    fit = draft_fit_eis_randles_cpe(cleaned.cleaned_points)

    metadata = fit.to_metadata()

    assert metadata["review_policy"] == "draft fit for visualization/manual review only"
    assert metadata["model"] == "Model A: Rs + (Rct || CPE)"
    assert "no final equivalent-circuit conclusion" in metadata["forbidden_claims_avoided"]
    assert "no electrochemical mechanism conclusion" in metadata["forbidden_claims_avoided"]


def test_plot_intent_includes_cleaned_points_and_fitted_semicircle_curve(tmp_path: Path) -> None:
    source = _write_semicircle_with_bad_tail(tmp_path)
    cleaned = clean_eis_file(source)
    fit = draft_fit_eis_randles_cpe(cleaned.cleaned_points)

    rows = eis_plot_rows(cleaned.cleaned_points, fit)

    assert rows
    assert len(rows[0]) == 3
    assert any(row[2] is not None for row in rows)
    assert len(rows) == len(cleaned.cleaned_points)
    assert len(rows) < len(cleaned.raw_points)


def _write_semicircle_with_bad_tail(tmp_path: Path) -> Path:
    rs, rct, q_value, n_value = 8.0, 55.0, 2.5e-4, 0.92
    freq = np.logspace(5, -0.2, 44)
    z = randles_cpe_impedance(freq, rs, rct, q_value, n_value)
    path = tmp_path / "eis_semicircle_bad_tail.txt"
    lines = ["Index;Frequency (Hz);Z' (ohm);-Z'' (ohm)"]
    for index, (frequency, value) in enumerate(zip(freq, z), start=1):
        lines.append(f"{index};{frequency:.9g};{value.real:.12g};{-value.imag:.12g}")
    tail_start = len(freq) + 1
    lines.extend(
        [
            f"{tail_start};0.04;-20;5",
            f"{tail_start + 1};0.02;120;-35",
            f"{tail_start + 2};0.01;420;260",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
