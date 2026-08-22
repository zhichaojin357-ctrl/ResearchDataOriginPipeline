from __future__ import annotations

import csv
import json
from pathlib import Path
import struct

import pytest

from src.cli import build_parser
from src.core.xrd_analysis import XrdAnalysisOptions, run_xrd_analysis
from src.core.xrd_jade import JadeIndex, XrdPhaseMatchOptions, match_xrd_phases


def _write_jade_database(database_dir: Path) -> None:
    database_dir.mkdir()
    sid = bytearray(b"J7" + b"\x00" * 5)
    rid = bytearray(b"J7" + b"\x00" * 5)
    records: list[tuple[int, int, int, int]] = []
    cards = [
        (970000001, "Cu W O4", "Copper tungstate", [(4.438, 100), (2.260, 80), (1.541, 60)]),
        (970000002, "Bi O Br", "Bismuth oxybromide", [(3.92, 100), (2.78, 50), (1.96, 25)]),
    ]
    for number, formula, name, peaks in cards:
        sid_offset = len(sid)
        sid.extend(b"\x01" + formula.encode("ascii") + b"\x01" + name.encode("ascii") + b"\x01\x00")
        rid_offset = len(rid)
        for d_spacing, intensity in peaks:
            rid.extend(b"\x00\x00\x00" + struct.pack("<f", d_spacing) + bytes([intensity, 0]))
        records.append((number, sid_offset, rid_offset, number - 970000000))

    xid = bytearray(b"J7" + b"\x00" * 6)
    xid.extend(struct.pack("<I", len(records)))
    for record in records:
        xid.extend(struct.pack("<IIII", *record))
    # Real J7 trailing bytes are intentionally not valid SID/RID terminal offsets.
    xid.extend(b"\x01\x02\x03\x04\x05\x06\x07\x08")
    (database_dir / "ICSD-ALL.xid").write_bytes(xid)
    (database_dir / "ICSD-ALL.sid").write_bytes(sid)
    (database_dir / "ICSD-ALL.rid").write_bytes(rid)


def _sample_points() -> list[tuple[float, float]]:
    return [
        (19.9, 1.0),
        (20.0, 10.0),
        (20.1, 1.0),
        (39.8, 1.0),
        (39.9, 8.0),
        (40.0, 1.0),
        (59.9, 1.0),
        (60.0, 6.0),
        (60.1, 1.0),
    ]


def test_jade_reader_searches_metadata_and_reads_final_record(tmp_path: Path) -> None:
    database_dir = tmp_path / "database"
    _write_jade_database(database_dir)

    with JadeIndex(database_dir) as database:
        assert database.record_count == 2
        assert database.search("CuWO4", limit=10)[0]["card_id"] == "97-000-0001"
        batches = database.search_many(("CuWO4", "Bismuth oxybromide"), limit=10)
        assert [[item["card_id"] for item in batch] for batch in batches] == [
            ["97-000-0001"],
            ["97-000-0002"],
        ]
        final = database.metadata(1)
        assert final["formula"] == "Bi O Br"
        final_peaks = database.peaks(1, wavelength_angstrom=1.5406, x_min=5, x_max=80)
        assert len(final_peaks) == 3


def test_selected_and_full_library_matching_return_candidates(tmp_path: Path) -> None:
    database_dir = tmp_path / "database"
    _write_jade_database(database_dir)
    selected = match_xrd_phases(
        _sample_points(),
        XrdPhaseMatchOptions(database_dir=database_dir, card_ids=("97-000-0001",)),
    )
    assert selected["matches"][0]["card_id"] == "97-000-0001"
    assert selected["matches"][0]["matched_peak_count"] == 3
    assert selected["manual_check_required"] is True

    full = match_xrd_phases(
        _sample_points(),
        XrdPhaseMatchOptions(database_dir=database_dir, full_library_screen=True, result_limit=2),
    )
    assert full["status"] == "full_library_screened_candidates_manual_review_required"
    assert full["matches"][0]["card_id"] == "97-000-0001"


def test_direct_xrd_analysis_uses_registry_and_writes_data_only_outputs(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    database_dir = tmp_path / "database"
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    _write_jade_database(database_dir)
    source_dir.mkdir()
    source = source_dir / "sample.csv"
    source.write_text(
        "two theta,intensity\n" + "\n".join(f"{x},{y}" for x, y in _sample_points()) + "\n",
        encoding="utf-8",
    )

    result = run_xrd_analysis(
        project_root,
        XrdAnalysisOptions(
            source=source,
            database_dir=database_dir,
            output_root=output_root,
            card_ids=("97-000-0001",),
        ),
    )
    assert result["ok"] is True
    assert result["origin_launched"] is False
    assert result["plot_generated"] is False
    assert Path(result["processed_data"]).is_file()
    metadata = json.loads(Path(result["metadata"]).read_text(encoding="utf-8"))
    candidates = json.loads(Path(result["card_match_candidates"]).read_text(encoding="utf-8"))
    with Path(result["processed_data"]).open(encoding="utf-8", newline="") as handle:
        processed_rows = list(csv.DictReader(handle))
    assert metadata["processing_status"] == "processed_no_origin"
    assert metadata["manual_check_required"] is True
    assert metadata["key_results"]["xrd_phase_matching"]["candidate_count"] == 1
    peak_count = candidates["peak_detection"]["candidate_count"]
    assert len(metadata["key_results"]["peak_position_candidates"]) == peak_count
    assert sum(int(row["peak_candidate_flag"]) for row in processed_rows) == peak_count
    assert candidates["matches"][0]["card_id"] == "97-000-0001"
    assert not list(output_root.rglob("*.png"))
    assert not list(output_root.rglob("*.tif"))
    assert not list(output_root.rglob("*.opju"))


def test_binary_raw_is_rejected_before_table_reader(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    database_dir = tmp_path / "database"
    _write_jade_database(database_dir)
    source = tmp_path / "sample.raw"
    source.write_bytes(b"RAW1.01\x00" + b"\x00" * 128)
    with pytest.raises(ValueError, match="same-name TXT/CSV/XY/XLSX"):
        run_xrd_analysis(
            project_root,
            XrdAnalysisOptions(
                source=source,
                database_dir=database_dir,
                output_root=tmp_path / "output",
                card_ids=("97-000-0001",),
            ),
        )


def test_output_root_cannot_overlap_jade_database(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    database_dir = tmp_path / "database"
    _write_jade_database(database_dir)
    source = tmp_path / "sample.csv"
    source.write_text("two theta,intensity\n20,1\n21,2\n22,1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="overlaps protected input path"):
        run_xrd_analysis(
            project_root,
            XrdAnalysisOptions(
                source=source,
                database_dir=database_dir,
                output_root=database_dir / "output",
                card_ids=("97-000-0001",),
            ),
        )


def test_cli_exposes_data_only_xrd_analysis_command() -> None:
    args = build_parser().parse_args(
        [
            "xrd-analyze",
            "--source",
            "sample.txt",
            "--database-dir",
            "database",
            "--card-query",
            "CuWO4",
        ]
    )
    assert args.command == "xrd-analyze"
    assert args.card_query == ["CuWO4"]
    assert args.full_library_screen is False
