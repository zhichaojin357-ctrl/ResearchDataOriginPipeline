from __future__ import annotations

from pathlib import Path

import numpy as np

from src.processors.eis import (
    clean_eis_file,
    draft_fit_eis_randles_cpe,
    eis_plot_rows,
    randles_cpe_impedance,
    select_eis_semicircle_main_branch,
)


def test_eis_cleaning_detects_invalid_low_frequency_tail(tmp_path: Path) -> None:
    source = _write_semicircle_with_bad_tail(tmp_path)

    cleaned = clean_eis_file(source)

    reasons = [item.reason for item in cleaned.ignored_points]
    assert len(cleaned.raw_points) > len(cleaned.cleaned_points)
    assert len(cleaned.ignored_points) >= 3
    assert any("invalid_negative_z_real_unstable_low_frequency_tail" in reason for reason in reasons)
    assert any("sign_flip_negative_minus_z_imag_unstable_low_frequency_tail" in reason for reason in reasons)
    assert any("large_jump_unstable_low_frequency_tail" in reason for reason in reasons)
    assert all(point.z_real_ohm > 0 for point in cleaned.cleaned_points)
    assert all(point.minus_z_imag_ohm >= 0 for point in cleaned.cleaned_points)
    assert cleaned.to_metadata()["raw_point_count"] == len(cleaned.raw_points)
    assert cleaned.to_metadata()["ignored_point_count"] == len(cleaned.ignored_points)


def test_cleaning_preserves_positive_main_branch_until_unstable_tail(tmp_path: Path) -> None:
    source = _write_positive_branch_then_sign_flip_tail(tmp_path)

    cleaned = clean_eis_file(source)

    ignored_indexes = {item.point.source_index for item in cleaned.ignored_points}
    cleaned_indexes = {point.source_index for point in cleaned.cleaned_points}
    assert len(cleaned.raw_points) == 71
    assert len(cleaned.cleaned_points) == 62
    assert len(cleaned.ignored_points) == 9
    assert 45 in cleaned_indexes
    assert 62 in cleaned_indexes
    assert all(index not in ignored_indexes for index in range(1, 63))
    assert all(index in ignored_indexes for index in range(63, 72))


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
    assert len(rows[0]) == 4
    assert any(row[2] is not None and row[3] is not None for row in rows)
    assert len(rows) >= len(fit.points)
    measured_rows = [row for row in rows if row[0] is not None and row[1] is not None]
    assert len(measured_rows) == len(cleaned.cleaned_points)
    assert len(measured_rows) < len(cleaned.raw_points)


def test_plot_intent_keeps_full_fit_curve_independent_from_measured_x(tmp_path: Path) -> None:
    source = _write_positive_branch_then_sign_flip_tail(tmp_path)
    cleaned = clean_eis_file(source)
    fit = draft_fit_eis_randles_cpe(cleaned.cleaned_points)

    rows = eis_plot_rows(cleaned.cleaned_points, fit)

    measured_rows = [row for row in rows if row[0] is not None and row[1] is not None]
    fit_rows = [row for row in rows if row[2] is not None and row[3] is not None]
    assert len(measured_rows) == len(cleaned.cleaned_points)
    assert len(fit_rows) == len(fit.points)
    assert len(fit_rows) > len(measured_rows)
    assert any(row[2] != row[0] for row in rows if row[0] is not None and row[2] is not None)


def test_strict_semicircle_branch_removes_offset_tail_before_fit(tmp_path: Path) -> None:
    source = _write_positive_branch_then_sign_flip_tail(tmp_path)
    cleaned = clean_eis_file(source)

    strict = select_eis_semicircle_main_branch(cleaned, ratio_threshold=1.2)
    fit = draft_fit_eis_randles_cpe(strict.cleaned_points)

    assert len(strict.cleaned_points) < len(cleaned.cleaned_points)
    assert len(strict.ignored_points) > len(cleaned.ignored_points)
    assert any("offset_tail_beyond_semicircle_main_branch" in item.reason for item in strict.ignored_points)
    assert max(point.minus_z_imag_ohm / max(point.z_real_ohm, 1e-9) for point in strict.cleaned_points) <= 1.2
    assert fit.parameters["Rct"] < 1000


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


def _write_positive_branch_then_sign_flip_tail(tmp_path: Path) -> Path:
    path = tmp_path / "eis_positive_branch_sign_flip_tail.txt"
    lines = ["Index;Frequency (Hz);Z' (ohm);-Z'' (ohm)"]
    for index in range(1, 63):
        frequency = 10 ** (5 - (index - 1) / 12)
        z_real = 7.5 + 0.18 * (index ** 2.35)
        minus_z_imag = 1.2 + 0.42 * (index ** 2.45)
        lines.append(f"{index};{frequency:.9g};{z_real:.12g};{minus_z_imag:.12g}")
    tail = [
        (63, 0.063096, -797.945941730502, -8037.65734032442),
        (64, 0.050119, -1279.39554315219, -2223.42394783383),
        (65, 0.039811, 1834.23638043374, -1993.14835825806),
        (66, 0.031623, 1140.73400528289, -1635.91586697007),
        (67, 0.025119, -1469.67650203855, 4008.10086455638),
        (68, 0.019953, 6355.21935680833, -5767.34619478029),
        (69, 0.015849, -4819.04668550351, -6119.663414785),
        (70, 0.012589, -11239.029329854, 4407.73216898586),
        (71, 0.01, -6678.09492619612, -609.949150616819),
    ]
    for index, frequency, z_real, minus_z_imag in tail:
        lines.append(f"{index};{frequency};{z_real};{minus_z_imag}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
