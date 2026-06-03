from __future__ import annotations

import argparse
from pathlib import Path

from src.cli import build_parser
from src.core.xps_heterojunction import (
    XpsFitRecord,
    XpsHeterojunctionOptions,
    build_comparison_plan,
)
from src.core.xps_in_situ import InSituRecordStatus, planned_panels


ARTIFACT_SUFFIXES = {".opju", ".tif", ".tiff", ".png", ".pdf", ".xlsx", ".zip"}


def _artifact_paths(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.suffix.lower() in ARTIFACT_SUFFIXES)


def _fit_record(sample: str, element: str, region: str, source_file: Path) -> XpsFitRecord:
    return XpsFitRecord(
        sample=sample,
        element=element,
        region=region,
        source_file=source_file,
        sheet_name=region,
        raw_label="measured",
        background_label="background",
        envelope_label="envelope",
        residual_label="residual",
        component_labels=["Component A"],
        data=[
            {
                "binding_energy_eV": 160.0,
                "raw_intensity": 10.0,
                "background": 1.0,
                "envelope": 9.0,
                "residual": 0.0,
                "component_Component_A": 5.0,
            },
            {
                "binding_energy_eV": 161.0,
                "raw_intensity": 12.0,
                "background": 1.1,
                "envelope": 10.0,
                "residual": 0.1,
                "component_Component_A": 6.0,
            },
        ],
    )


def _subparser(parser: argparse.ArgumentParser, name: str) -> argparse.ArgumentParser:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices[name]
    raise AssertionError("CLI parser has no subparser action")


def test_xps_heterojunction_plan_is_no_artifact_until_execution(tmp_path: Path) -> None:
    output_dir = tmp_path / "run" / "xps_heterojunction"
    records = [
        _fit_record("BOBC", "Bi", "Bi4f", tmp_path / "bobc_bi.synthetic"),
        _fit_record("BC", "Bi", "Bi4f", tmp_path / "bc_bi.synthetic"),
    ]

    plan = build_comparison_plan(records, [], XpsHeterojunctionOptions(output_dir=output_dir, with_origin=False))

    assert [comparison.name for comparison in plan.comparisons] == ["XPS_Bi_BOBC_vs_BC_stacked"]
    assert plan.manual_review == []
    assert not output_dir.exists()
    assert _artifact_paths(tmp_path) == []


def test_xps_heterojunction_missing_counterpart_stays_manual_review_only(tmp_path: Path) -> None:
    output_dir = tmp_path / "run" / "xps_heterojunction"
    records = [_fit_record("BOBC", "Bi", "Bi4f", tmp_path / "bobc_bi.synthetic")]

    plan = build_comparison_plan(records, [], XpsHeterojunctionOptions(output_dir=output_dir, with_origin=False))

    assert plan.comparisons == []
    assert plan.manual_review == [
        {
            "sample": "BC",
            "element": "Bi",
            "reason": "missing_bc_counterpart",
            "comparison": "BOBC vs BC Bi",
        }
    ]
    assert not output_dir.exists()
    assert _artifact_paths(tmp_path) == []


def test_xps_in_situ_panel_planning_is_no_artifact_metadata_only(tmp_path: Path) -> None:
    statuses = [
        InSituRecordStatus("BOBC", "Bi", "Bi4f", True),
        InSituRecordStatus("BC Dark", "Bi", "Bi4f", True),
        InSituRecordStatus("BC Light", "Bi", "Bi4f", True),
        InSituRecordStatus("CWO", "Cu", "Cu2p", True),
        InSituRecordStatus("BC Dark", "Cu", "Cu2p", True),
        InSituRecordStatus("BC Light", "Cu", "Cu2p", False, "missing fitted envelope"),
    ]

    panels, missing = planned_panels(statuses)

    assert [(panel.element, panel.region, panel.reference_sample) for panel in panels] == [("Bi", "Bi4f", "BOBC")]
    assert missing["Cu"] == ["BC Light: missing fitted envelope"]
    assert _artifact_paths(tmp_path) == []


def test_xps_cli_contract_parses_without_processing_or_visual_claims(tmp_path: Path) -> None:
    parser = build_parser()
    xps_parser = _subparser(parser, "xps-heterojunction-stacked")

    args = parser.parse_args(
        [
            "xps-heterojunction-stacked",
            "--bobc",
            str(tmp_path / "bobc_fit.input"),
            "--bc",
            str(tmp_path / "bc_fit.input"),
            "--output-dir",
            str(tmp_path / "run" / "xps"),
            "--dry-run",
        ]
    )
    help_text = xps_parser.format_help().casefold()

    assert args.command == "xps-heterojunction-stacked"
    assert args.dry_run is True
    assert args.with_origin is False
    assert "explicitly launch origin com" in help_text
    assert "visual acceptance" not in help_text
    assert "s-scheme" not in help_text
    assert _artifact_paths(tmp_path) == []
