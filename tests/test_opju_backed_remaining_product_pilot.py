from __future__ import annotations

import json
from pathlib import Path

from src.cli import main
from src.core.remaining_opju_product_drafts import (
    ReferenceValidationResult,
    RemainingOpjuProductDraftOptions,
    load_remaining_pairings,
    run_remaining_opju_product_drafts,
)


def test_load_remaining_pairings_selects_remaining_types_only(tmp_path: Path) -> None:
    roots = _root_map(tmp_path)
    for root in roots.values():
        root.mkdir(parents=True, exist_ok=True)
    pairing = tmp_path / "pairing.json"
    _write_pairing(
        pairing,
        [
            _pair("BET", ["BET/bet.csv"], "BET/style.opju"),
            _pair("EIS", ["EIS/eis.txt"], "EIS/style.opju"),
            _pair("Raman", ["Raman/raman.txt"], "Raman/style.opju"),
            _pair("Mott-Schottky", ["MS/ms.csv"], "MS/style.opju"),
            _pair("UV-vis DRS / Tauc", ["UV/uv.txt"], "UV/style.opju"),
            _pair("PL", ["PL/pl.txt"], "PL/style.opju"),
            _pair("photocurrent", ["PC/pc.txt"], "PC/style.opju"),
            _pair("FTIR", ["FTIR/a.dpt", "FTIR/b.dpt"], "FTIR/style.opju"),
            _pair("HPLC/LC exported data", ["LC/sample.pdf"], ""),
        ],
    )

    selected = load_remaining_pairings(pairing, roots)

    assert [item.product_key for item in selected] == [
        "EIS",
        "Raman",
        "Mott-Schottky",
        "UV-vis DRS / Tauc",
        "PL",
        "photocurrent",
        "FTIR",
    ]
    assert all(item.product_key != "BET" for item in selected)


def test_run_remaining_product_drafts_generates_safe_products_and_skips_mismatched_mott(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    roots = _root_map(tmp_path)
    for root in roots.values():
        root.mkdir(parents=True, exist_ok=True)

    _write(roots["f_drive_detection"] / "EIS" / "eis.txt", "Index;Frequency (Hz);Z' (ohm);-Z'' (ohm)\n1;1000;7;1\n2;100;8;2\n")
    _write(roots["f_drive_detection"] / "Raman" / "raman.txt", "100 1\n101 2\n")
    _write(roots["f_drive_detection"] / "MS" / "ms.csv", "Potential/V,Z/ohm\n0.1,5\n0.2,6\n")
    _write(roots["f_drive_detection"] / "UV" / "uv.txt", "Data Points\nnm\t%T\n500\t80\n501\t81\n")
    _write(roots["f_drive_detection"] / "PL" / "pl.txt", "Wavelength Counts\n360 1\n361 3\n")
    _write(roots["f_drive_detection"] / "PC" / "pc.txt", "Time/sec Current/A\n0.1 1e-7\n0.2 2e-7\n")
    _write(roots["f_drive_detection"] / "FTIR" / "a.dpt", "4000 1\n3999 2\n")
    _write(roots["f_drive_detection"] / "FTIR" / "b.dpt", "4000 3\n3999 4\n")
    _write(roots["f_drive_detection"] / "LC" / "sample.pdf", "%PDF")
    for ref in (
        roots["f_drive_detection"] / "EIS" / "style.opju",
        roots["f_drive_detection"] / "Raman" / "style.opju",
        roots["f_drive_detection"] / "MS" / "style.opju",
        roots["f_drive_detection"] / "UV" / "style.opju",
        roots["f_drive_detection"] / "PL" / "style.opju",
        roots["f_drive_detection"] / "PC" / "style.opju",
        roots["f_drive_detection"] / "FTIR" / "style.opju",
    ):
        _write(ref, "reference")

    previous_run = tmp_path / "external" / "runs" / "20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet"
    for name in ("BET", "XPS_in_situ", "XPS_non_in_situ", "XRD", "EPR"):
        (previous_run / name).mkdir(parents=True)
    pairing = tmp_path / "pairing.json"
    _write_pairing(
        pairing,
        [
            _pair("BET", ["BET/bet.csv"], "BET/style.opju"),
            _pair("EIS", ["EIS/eis.txt"], "EIS/style.opju"),
            _pair("Raman", ["Raman/raman.txt"], "Raman/style.opju"),
            _pair("Mott-Schottky", ["MS/ms.csv"], "MS/style.opju"),
            _pair("UV-vis DRS / Tauc", ["UV/uv.txt"], "UV/style.opju"),
            _pair("PL", ["PL/pl.txt"], "PL/style.opju"),
            _pair("photocurrent", ["PC/pc.txt"], "PC/style.opju"),
            _pair("FTIR", ["FTIR/a.dpt", "FTIR/b.dpt"], "FTIR/style.opju"),
            _pair("HPLC/LC exported data", ["LC/sample.pdf"], ""),
        ],
    )
    calls: list[str] = []

    def fake_export(product) -> dict[str, object]:
        calls.append(product.product_key)
        for artifact in (product.origin_file, product.figure_tif, product.preview_png, product.reference_preview_png):
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_text(f"fake {product.product_key}", encoding="utf-8")
        return {"ok": True, "message": "fake origin export"}

    result = run_remaining_opju_product_drafts(
        project_root,
        RemainingOpjuProductDraftOptions(
            pairing_path=pairing,
            output_root=tmp_path / "external",
            with_origin=True,
            timestamp="20260604_130000",
            previous_run_root=previous_run,
        ),
        root_map=roots,
        origin_exporter=fake_export,
        reference_validator=lambda _pairing: ReferenceValidationResult(
            False,
            "invalid_mott_exemplar_mismatched_type",
            "fake mismatch",
            {"axis_reads": []},
        ),
    )

    assert result["summary"]["product_count"] == 6
    assert calls == ["EIS", "Raman", "UV-vis DRS / Tauc", "PL", "photocurrent", "FTIR"]
    run_root = Path(result["run_root"])
    assert run_root == tmp_path / "external" / "runs" / "20260604_130000_remaining_opju_product_drafts"
    assert (run_root / "previous_completed_links" / "previous_completed_products.md").exists()
    assert (run_root / "reports" / "deferred_hplc_lc.md").exists()
    skipped = {str(item["data_type"]): str(item["decision"]) for item in result["skipped"]}
    assert skipped["Mott-Schottky"] == "invalid_mott_exemplar_mismatched_type"
    assert skipped["HPLC/LC exported data"] == "deferred_hplc_lc_pdf_only_no_opju"
    assert skipped["reaction_condition_screening"] == "skipped_no_clear_data_pair"
    audit = json.loads((run_root / "reports" / "product_no_label_audit.json").read_text(encoding="utf-8"))
    assert audit["hit_count"] == 0
    final = (run_root / "reports" / "final_summary.md").read_text(encoding="utf-8")
    assert "Selected data" in final
    assert "Forbidden scientific claims avoided" in final
    assert "20260604_231317_real_opju_product_pilot_xps_xrd_epr_bet" in final


def test_cli_remaining_product_drafts_passes_options(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    pairing = tmp_path / "pairing.json"
    _write_pairing(pairing, [])
    output_root = tmp_path / "out"
    previous_run = tmp_path / "previous"
    captured: dict[str, object] = {}

    def fake_run(project: Path, options: RemainingOpjuProductDraftOptions) -> dict[str, object]:
        captured["project"] = project
        captured["options"] = options
        return {
            "run_root": str(output_root / "runs" / "fake"),
            "summary": {"product_count": 1, "skipped_count": 0},
            "failures": [],
        }

    monkeypatch.chdir(project_root)
    monkeypatch.setattr("src.cli.run_remaining_opju_product_drafts", fake_run)

    code = main(
        [
            "remaining-opju-product-drafts",
            "--pairing",
            str(pairing),
            "--output-root",
            str(output_root),
            "--with-origin",
            "--timestamp",
            "20260604_130000",
            "--previous-run-root",
            str(previous_run),
        ]
    )

    assert code == 0
    assert captured["project"] == project_root
    options = captured["options"]
    assert isinstance(options, RemainingOpjuProductDraftOptions)
    assert options.pairing_path == pairing
    assert options.output_root == output_root
    assert options.with_origin is True
    assert options.timestamp == "20260604_130000"
    assert options.previous_run_root == previous_run


def _root_map(tmp_path: Path) -> dict[str, Path]:
    return {
        "f_drive_detection": tmp_path / "f_drive",
        "workspace_xps_data": tmp_path / "workspace" / "XPS",
        "workspace_xps_reference": tmp_path / "xps_reference",
        "workspace_group_data": tmp_path / "workspace",
    }


def _pair(data_type: str, data_paths: list[str], opju_path: str) -> dict[str, object]:
    return {
        "data_type": data_type,
        "xps_subtype": "",
        "selected_data_root_label": "f_drive_detection",
        "selected_data_relative_paths": data_paths,
        "selected_opju_root_label": "f_drive_detection" if opju_path else "",
        "selected_opju_relative_path": opju_path,
        "opju_validation_status": "valid_exemplar" if opju_path else "missing_opju",
    }


def _write_pairing(path: Path, items: list[dict[str, object]]) -> None:
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
