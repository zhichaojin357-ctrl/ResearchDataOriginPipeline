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
        (970000001, "Cu W O4", "Copper tungstate", [(4.438, 10000), (2.260, 8000), (1.541, 6000)]),
        (970000002, "Bi O Br", "Bismuth oxybromide", [(3.92, 10000), (2.78, 5000), (1.96, 2500)]),
    ]
    for number, formula, name, peaks in cards:
        sid_offset = len(sid)
        sid.extend(b"\x01" + formula.encode("ascii") + b"\x01" + name.encode("ascii") + b"\x01\x00")
        rid_offset = len(rid)
        # Invented peaks in the observed counted J7 frame; no licensed card bytes.
        rid.extend(b"\x27" + struct.pack("<H", len(peaks)))
        for d_spacing, intensity in peaks:
            rid.extend(struct.pack("<fHbbb", d_spacing, intensity, -1, 2, 3))
        if number != cards[-1][0]:
            rid.extend(b"\x10")
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
        assert [peak["d_spacing_angstrom"] for peak in final_peaks] == pytest.approx([3.92, 2.78, 1.96])
        assert [peak["intensity_raw"] for peak in final_peaks] == [10000, 5000, 2500]
        assert [peak["relative_intensity"] for peak in final_peaks] == pytest.approx([100, 50, 25])
        assert all("hkl" not in peak for peak in final_peaks)


def test_card_relative_intensity_is_invariant_to_scan_window(tmp_path: Path) -> None:
    database_dir = tmp_path / "database"
    _write_jade_database(database_dir)

    with JadeIndex(database_dir) as database:
        whole_card = database.peaks(0, wavelength_angstrom=1.5406, x_min=5, x_max=80)
        cropped_card = database.peaks(0, wavelength_angstrom=1.5406, x_min=30, x_max=70)

    whole_by_theta = {round(float(peak["two_theta_deg"]), 4): peak for peak in whole_card}
    cropped_by_theta = {round(float(peak["two_theta_deg"]), 4): peak for peak in cropped_card}
    assert set(cropped_by_theta).issubset(whole_by_theta)
    for theta, cropped_peak in cropped_by_theta.items():
        assert cropped_peak["relative_intensity"] == pytest.approx(
            whole_by_theta[theta]["relative_intensity"]
        )
    assert [peak["relative_intensity"] for peak in cropped_card] == pytest.approx([80.0, 60.0])


@pytest.mark.parametrize(
    "stem",
    ["", "   ", ".", "..", "ICSD-ALL.xid", "../ICSD-ALL", r"..\ICSD-ALL", "a/b", "name.", "name ", "a:b"],
)
def test_database_stem_must_be_one_safe_filename_stem(tmp_path: Path, stem: str) -> None:
    with pytest.raises(ValueError, match="database stem"):
        XrdPhaseMatchOptions(database_dir=tmp_path, database_stem=stem, card_ids=("97-000-0001",)).validate()
    with pytest.raises(ValueError, match="database stem"):
        JadeIndex(tmp_path, stem)


@pytest.mark.parametrize("stem", ["ICSD ALL", "数据库.版本", "ICSD-ALL_2026"])
def test_database_stem_permits_normal_filename_characters(tmp_path: Path, stem: str) -> None:
    XrdPhaseMatchOptions(database_dir=tmp_path, database_stem=stem, card_ids=("97-000-0001",)).validate()


def test_corrupt_xid_header_count_and_duplicate_ids_are_rejected(tmp_path: Path) -> None:
    for mode in ("header", "count", "duplicate"):
        database_dir = tmp_path / mode
        _write_jade_database(database_dir)
        xid_path = database_dir / "ICSD-ALL.xid"
        xid = bytearray(xid_path.read_bytes())
        if mode == "header":
            xid[:2] = b"XX"
        elif mode == "count":
            struct.pack_into("<I", xid, 8, 99)
        else:
            struct.pack_into("<I", xid, 28, 970000001)
        xid_path.write_bytes(xid)
        with pytest.raises(ValueError):
            JadeIndex(database_dir)


@pytest.mark.parametrize("member", ["sid", "rid"])
def test_corrupt_sid_or_rid_header_is_rejected(tmp_path: Path, member: str) -> None:
    database_dir = tmp_path / member
    _write_jade_database(database_dir)
    path = database_dir / f"ICSD-ALL.{member}"
    payload = bytearray(path.read_bytes())
    payload[:2] = b"XX"
    path.write_bytes(payload)
    with pytest.raises(ValueError, match="SID/RID header"):
        JadeIndex(database_dir)


def test_corrupt_sid_rid_offsets_and_rid_record_size_are_rejected(tmp_path: Path) -> None:
    for mode in ("sid_nonmonotonic", "rid_out_of_bounds", "rid_record_size"):
        database_dir = tmp_path / mode
        _write_jade_database(database_dir)
        xid_path = database_dir / "ICSD-ALL.xid"
        if mode == "sid_nonmonotonic":
            xid = bytearray(xid_path.read_bytes())
            struct.pack_into("<I", xid, 28 + 4, 7)
            xid_path.write_bytes(xid)
        elif mode == "rid_out_of_bounds":
            xid = bytearray(xid_path.read_bytes())
            struct.pack_into("<I", xid, 12 + 8, 10_000)
            xid_path.write_bytes(xid)
        else:
            rid_path = database_dir / "ICSD-ALL.rid"
            rid_path.write_bytes(rid_path.read_bytes() + b"\x00")
        with pytest.raises(ValueError):
            JadeIndex(database_dir)


@pytest.mark.parametrize("mode", ["marker", "count", "zero_count", "separator", "truncated", "headerless"])
def test_corrupt_counted_rid_frames_are_rejected(tmp_path: Path, mode: str) -> None:
    database_dir = tmp_path / "database"
    _write_jade_database(database_dir)
    rid_path = database_dir / "ICSD-ALL.rid"
    rid = bytearray(rid_path.read_bytes())
    if mode == "marker":
        rid[7] = 0
    elif mode in {"count", "zero_count"}:
        struct.pack_into("<H", rid, 8, 4 if mode == "count" else 0)
    elif mode == "separator":
        rid[7 + 3 + 3 * 9] = 0
    elif mode == "truncated":
        rid.pop()
    else:
        rid[7:10] = b"\x00\x00\x00"
    rid_path.write_bytes(rid)
    with pytest.raises(ValueError, match="Jade RID"):
        JadeIndex(database_dir)
    # Failed mmap validation releases the files (also required on Windows).
    rid_path.write_bytes(rid)


@pytest.mark.parametrize("d_spacing", [float("nan"), float("inf"), -1.0, 0.0])
def test_invalid_rid_d_spacing_is_rejected_even_outside_window(tmp_path: Path, d_spacing: float) -> None:
    database_dir = tmp_path / "database"
    _write_jade_database(database_dir)
    rid_path = database_dir / "ICSD-ALL.rid"
    rid = bytearray(rid_path.read_bytes())
    struct.pack_into("<f", rid, 10, d_spacing)
    rid_path.write_bytes(rid)
    with JadeIndex(database_dir) as database:
        with pytest.raises(ValueError, match="Invalid Jade RID d spacing"):
            database.peaks(0, wavelength_angstrom=1.5406, x_min=30, x_max=70)


def test_large_d_spacing_and_zero_intensity_are_valid(tmp_path: Path) -> None:
    database_dir = tmp_path / "database"
    _write_jade_database(database_dir)
    rid_path = database_dir / "ICSD-ALL.rid"
    rid = bytearray(rid_path.read_bytes())
    struct.pack_into("<f", rid, 10, 150.0)
    struct.pack_into("<H", rid, 10 + 9 + 4, 0)
    rid_path.write_bytes(rid)
    with JadeIndex(database_dir) as database:
        peaks = database.peaks(0, wavelength_angstrom=1.5406, x_min=0, x_max=180)
    assert [peak["d_spacing_angstrom"] for peak in peaks] == pytest.approx([150, 1.541])
    assert [peak["relative_intensity"] for peak in peaks] == pytest.approx([100, 60])


def test_rid_peak_count_uses_both_bytes(tmp_path: Path) -> None:
    database_dir = tmp_path / "database"
    _write_jade_database(database_dir)
    xid = (database_dir / "ICSD-ALL.xid").read_bytes()
    final_start = struct.unpack_from("<I", xid, 28 + 8)[0]
    rid_path = database_dir / "ICSD-ALL.rid"
    rid = rid_path.read_bytes()[:final_start]
    count = 300
    rid += b"\x27" + struct.pack("<H", count)
    rid += b"".join(struct.pack("<fHbbb", 2.0 + i / 1000, 10000 - i, 0, 0, 0) for i in range(count))
    rid_path.write_bytes(rid)
    with JadeIndex(database_dir) as database:
        peaks = database.peaks(1, wavelength_angstrom=1.5406, x_min=5, x_max=80)
    assert len(peaks) == count
    assert {peak["intensity_raw"] for peak in peaks} == set(range(9701, 10001))


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
