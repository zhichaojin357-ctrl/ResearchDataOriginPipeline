from __future__ import annotations

from pathlib import Path

from src.cli import main
from src.core.opju_product_pilot import _xps_records_to_offset_table
from src.core.v4_exemplar_conformance import (
    V4_GLOBAL_STYLE_OVERRIDE,
    V4ExemplarConformanceOptions,
    build_v4_v3_options,
    v4_style_readback_acceptance,
)
from src.core.xps_heterojunction import XpsFitRecord


def test_v4_builds_v4_run_scope_and_forced_global_style(tmp_path: Path) -> None:
    pairing = tmp_path / "pairing.json"
    output_root = tmp_path / "external"
    f_root = tmp_path / "f_drive"
    xps_reference = tmp_path / "xps参考图像"

    v3_options = build_v4_v3_options(
        V4ExemplarConformanceOptions(
            pairing_path=pairing,
            output_root=output_root,
            timestamp="20260605_210000",
            f_drive_template_root=f_root,
            xps_reference_template_root=xps_reference,
            with_origin=True,
        )
    )

    assert v3_options.run_scope == "unified_v4_exemplar_conformance_all_types"
    assert v3_options.command_name == "unified-v4-exemplar-conformance-all-types"
    assert v3_options.product_slug_version == "v4"
    assert v3_options.global_style_override == V4_GLOBAL_STYLE_OVERRIDE
    assert v3_options.xps_reference_template_root == xps_reference
    assert v3_options.eis_strict_semicircle_branch is True


def test_cli_unified_v4_passes_required_paths(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    pairing = tmp_path / "pairing.json"
    pairing.write_text("[]", encoding="utf-8")
    output_root = tmp_path / "external"
    f_root = tmp_path / "f_drive"
    xps_reference = tmp_path / "xps参考图像"
    captured: dict[str, object] = {}

    def fake_run(project: Path, options: V4ExemplarConformanceOptions) -> dict[str, object]:
        captured["project"] = project
        captured["options"] = options
        return {
            "run_root": str(output_root / "runs" / "20260605_210000_unified_v4_exemplar_conformance_all_types"),
            "summary": {"product_count": 11, "success_count": 11, "blocked_count": 0, "failed_count": 0},
            "failures": [],
        }

    monkeypatch.chdir(project_root)
    monkeypatch.setattr("src.cli.run_v4_exemplar_conformance_all_types", fake_run)

    code = main(
        [
            "unified-v4-exemplar-conformance-all-types",
            "--pairing",
            str(pairing),
            "--output-root",
            str(output_root),
            "--with-origin",
            "--timestamp",
            "20260605_210000",
            "--f-drive-template-root",
            str(f_root),
            "--xps-reference-template-root",
            str(xps_reference),
        ]
    )

    assert code == 0
    assert captured["project"] == project_root
    options = captured["options"]
    assert isinstance(options, V4ExemplarConformanceOptions)
    assert options.pairing_path == pairing
    assert options.output_root == output_root
    assert options.f_drive_template_root == f_root
    assert options.xps_reference_template_root == xps_reference
    assert options.with_origin is True


def test_v4_style_readback_requires_arial_36_bold_legend_frame_off() -> None:
    passing = {
        "audit_numeric_values": {
            "xb.fsize": 36,
            "yl.fsize": 36,
            "xb.bold": 1,
            "yl.bold": 1,
            "legend.border": 0,
            "legend.frame": 0,
            "legend.fill": 0,
        },
        "audit_string_values": {"xb.font$": "Arial", "yl.font$": "Arial", "legend.font$": "Arial"},
    }
    failing = {
        "audit_numeric_values": {"xb.fsize": 28, "yl.fsize": 36, "xb.bold": 1, "yl.bold": 0, "legend.frame": 1},
        "audit_string_values": {"xb.font$": "Times New Roman", "yl.font$": "Arial"},
    }

    assert v4_style_readback_acceptance(passing).passed is True
    failed = v4_style_readback_acceptance(failing)
    assert failed.passed is False
    assert "axis_title_font_size_36" in failed.failed_checks
    assert "font_family_arial" in failed.failed_checks
    assert "axis_title_bold" in failed.failed_checks
    assert "legend_no_frame" in failed.failed_checks


def test_xps_offset_table_includes_component_columns_for_v4_fill() -> None:
    record = XpsFitRecord(
        sample="BOBC",
        element="Bi",
        region="Bi4f",
        source_file=Path("BOBCfit.xlsx"),
        sheet_name="Bi4f Scan",
        raw_label="Bi4f",
        background_label="Backgnd.",
        envelope_label="Envelope",
        residual_label="Residuals",
        component_labels=["Bi4f Scan A", "Bi4f Scan B"],
        data=[
            {"binding_energy_eV": 160.0, "raw_intensity": 10.0, "envelope": 9.0, "Bi4f Scan A": 4.0, "Bi4f Scan B": 3.0},
            {"binding_energy_eV": 159.0, "raw_intensity": 20.0, "envelope": 18.0, "Bi4f Scan A": 8.0, "Bi4f Scan B": 6.0},
        ],
    )

    headers, rows = _xps_records_to_offset_table([record], include_envelope=True, include_components=True)

    assert headers == [
        "binding_energy_eV",
        "BOBC_measured",
        "BOBC_envelope",
        "BOBC_component_1",
        "BOBC_component_2",
    ]
    assert len(rows[0]) == len(headers)
