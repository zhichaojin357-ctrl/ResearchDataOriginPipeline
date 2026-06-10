from __future__ import annotations

import json
from pathlib import Path

from src.cli import main
from src.core.xrd_overlay import (
    XrdOverlayOptions,
    build_xrd_overlay_table,
    parse_xrd_reference_card_peaks,
    run_xrd_overlay,
)


def test_build_xrd_overlay_table_orders_requested_series_and_card(tmp_path: Path) -> None:
    bicu = _write_raw4(tmp_path / "BOBCshuirecwo.txt", [(5.0, 10.0), (6.0, 20.0), (7.0, 15.0)])
    bobc = _write_raw4(tmp_path / "BOBCshuire.txt", [(5.0, 4.0), (6.0, 8.0), (7.0, 6.0)])
    cwo = _write_raw4(tmp_path / "cwo.txt", [(5.0, 2.0), (6.0, 4.0), (7.0, 3.0)])
    card = tmp_path / "CWO PDF#04-009-6293.txt"
    card.write_text("5.0 x 100\n6.0 x 50\n", encoding="utf-8")

    table = build_xrd_overlay_table(bicu, bobc, cwo, card)

    assert table.headers == [
        "two_theta_deg",
        "BiCu-10",
        "BiOBr\\-(0.5)Cl\\-(0.5)",
        "CuWO\\-(4)",
        "CuWO\\-(4) JCPDS card No.04-009-6293",
    ]
    assert table.legend_labels[:3] == ["BiCu-10", "BiOBr\\-(0.5)Cl\\-(0.5)", "CuWO\\-(4)"]
    assert table.origin_ocolors[:3] == [23709421, 33518174, 16814848]
    assert table.rows[0][1] > table.rows[0][2] > table.rows[0][3] > table.rows[0][4]
    assert table.rows[1][4] > 0
    assert table.metadata["reference_card"]["peak_count"] == 2


def test_parse_xrd_reference_card_peaks_accepts_pdf_text_rows(tmp_path: Path) -> None:
    card = tmp_path / "CWO PDF#04-009-6293.txt"
    card.write_text("18.68 3.12 44\nbad row\n23.91 2.22 100\n", encoding="utf-8")

    assert parse_xrd_reference_card_peaks(card) == [(18.68, 44.0), (23.91, 100.0)]


def test_run_xrd_overlay_dry_run_writes_metadata_without_origin(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    bicu = _write_raw4(tmp_path / "BOBCshuirecwo.txt", [(5.0, 10.0), (6.0, 20.0)])
    bobc = _write_raw4(tmp_path / "BOBCshuire.txt", [(5.0, 6.0), (6.0, 12.0)])
    cwo = _write_raw4(tmp_path / "cwo.txt", [(5.0, 4.0), (6.0, 8.0)])
    card = tmp_path / "CWO PDF#04-009-6293.txt"
    card.write_text("5.0 x 100\n6.0 x 50\n", encoding="utf-8")
    reference = tmp_path / "CWO+BOBC+标卡.opju"
    reference.write_bytes(b"opju")

    result = run_xrd_overlay(
        project_root,
        XrdOverlayOptions(
            bicu_source=bicu,
            bobc_source=bobc,
            cwo_source=cwo,
            cwo_card=card,
            reference_opju=reference,
            output_root=project_root / "output",
            with_origin=False,
            timestamp="20260610_120000",
        ),
    )

    assert result["will_launch_origin"] is False
    processed = project_root / result["processed_data"]
    metadata = json.loads((project_root / result["metadata"]).read_text(encoding="utf-8"))
    assert processed.exists()
    assert metadata["manual_check_required"] is True
    assert metadata["origin_status"]["ok"] is False
    assert "BiOBr\\-(0.5)Cl\\-(0.5)" in processed.read_text(encoding="utf-8").splitlines()[0]


def test_run_xrd_overlay_dry_run_does_not_require_reference_opju(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    bicu = _write_raw4(tmp_path / "BOBCshuirecwo.txt", [(5.0, 10.0), (6.0, 20.0)])
    bobc = _write_raw4(tmp_path / "BOBCshuire.txt", [(5.0, 6.0), (6.0, 12.0)])
    cwo = _write_raw4(tmp_path / "cwo.txt", [(5.0, 4.0), (6.0, 8.0)])
    card = tmp_path / "CWO PDF#04-009-6293.txt"
    card.write_text("5.0 x 100\n6.0 x 50\n", encoding="utf-8")

    result = run_xrd_overlay(
        project_root,
        XrdOverlayOptions(
            bicu_source=bicu,
            bobc_source=bobc,
            cwo_source=cwo,
            cwo_card=card,
            reference_opju=tmp_path / "missing_reference.opju",
            output_root=project_root / "output",
            with_origin=False,
            timestamp="20260610_120001",
        ),
    )

    metadata = json.loads((project_root / result["metadata"]).read_text(encoding="utf-8"))
    assert result["will_launch_origin"] is False
    assert metadata["processing_status"] == "processed_no_origin"
    assert metadata["origin_reference_opju"].endswith("missing_reference.opju")


def test_xrd_overlay_cli_parses_required_sources(tmp_path: Path) -> None:
    bicu = _write_raw4(tmp_path / "BOBCshuirecwo.txt", [(5.0, 10.0), (6.0, 20.0)])
    bobc = _write_raw4(tmp_path / "BOBCshuire.txt", [(5.0, 6.0), (6.0, 12.0)])
    cwo = _write_raw4(tmp_path / "cwo.txt", [(5.0, 4.0), (6.0, 8.0)])
    card = tmp_path / "CWO PDF#04-009-6293.txt"
    card.write_text("5.0 x 100\n", encoding="utf-8")
    reference = tmp_path / "CWO+BOBC+标卡.opju"
    reference.write_bytes(b"opju")

    rc = main(
        [
            "xrd-overlay",
            "--bicu-source",
            str(bicu),
            "--bobc-source",
            str(bobc),
            "--cwo-source",
            str(cwo),
            "--cwo-card",
            str(card),
            "--reference-opju",
            str(reference),
            "--output-root",
            str(tmp_path / "out"),
            "--timestamp",
            "20260610_120000",
            "--dry-run",
        ]
    )

    assert rc == 0


def _write_raw4(path: Path, rows: list[tuple[float, float]]) -> Path:
    lines = [";RAW4.00", "[RawHeader]", "Date=06/10/2026", "", "[Data]", "Angle, PSD"]
    lines.extend(f"{x}, {y}" for x, y in rows)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
