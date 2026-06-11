from __future__ import annotations

import json
from pathlib import Path

from src.cli import main
from src.core.opju_product_pilot import ProductContext, TargetPairing
from src.core.v2_exemplar_conformance import (
    UnifiedV2ExemplarConformanceOptions,
    V2_SLUGS,
    V2_TARGET_TYPES,
    V2_TYPE_DIRS,
    run_unified_v2_exemplar_conformance_products,
)


def test_unified_v2_imports_completed_eis_without_refitting(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    pairing_path = tmp_path / "pairing.json"
    pairing_path.write_text("[]", encoding="utf-8")
    output_root = tmp_path / "external"
    first_run = tmp_path / "first_v1"
    remaining_run = tmp_path / "remaining_v1"
    eis_run = _write_completed_eis_run(tmp_path / "completed_eis_v2")
    first_pairings = [_pair(product_key) for product_key in V2_TARGET_TYPES[:5]]
    remaining_pairings = [_pair(product_key) for product_key in V2_TARGET_TYPES[5:]]
    prepare_calls: list[str] = []
    export_calls: list[str] = []

    def fake_prepare(run_root: Path, pairing: TargetPairing) -> tuple[ProductContext, dict[str, object]]:
        if pairing.product_key == "EIS":
            raise AssertionError("EIS must be imported from the completed v2 run, not refitted")
        prepare_calls.append(pairing.product_key)
        slug = V2_SLUGS[pairing.product_key]
        type_root = run_root / V2_TYPE_DIRS[pairing.product_key]
        for directory in ("processed_data", "reference_opju"):
            (type_root / directory).mkdir(parents=True, exist_ok=True)
        processed_data = type_root / "processed_data" / f"{slug}.csv"
        processed_data.write_text("x,y\n0,0\n1,1\n", encoding="utf-8")
        reference_copy = type_root / "reference_opju" / "reference.opju"
        reference_copy.write_text("reference", encoding="utf-8")
        product = ProductContext(
            product_key=pairing.product_key,
            slug=slug,
            pairing=pairing,
            type_root=type_root,
            processed_data=processed_data,
            input_copies=[],
            reference_opju_copy=reference_copy,
            reference_preview_png=type_root / "reference_exports" / f"{slug}_reference_preview.png",
            origin_file=type_root / "origin_files" / f"{slug}.opju",
            figure_tif=type_root / "figures_tif" / f"{slug}.tif",
            preview_png=type_root / "figures_preview" / f"{slug}_preview.png",
            x_label="X",
            y_label="Y",
            graph_title="",
            legend_entries=["Y"],
        )
        return product, {}

    def fake_export(product: ProductContext, _style) -> dict[str, object]:
        export_calls.append(product.product_key)
        for artifact in (product.origin_file, product.figure_tif, product.preview_png, product.reference_preview_png):
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_bytes(f"fake {product.product_key}".encode("utf-8"))
        return {
            "ok": True,
            "message": "fake origin export",
            "conformance": {
                "status": "pass",
                "compared_fields": 4,
                "matched_fields": 4,
                "plot_line_width_origin_units": [30.0],
                "axis_title_bold": True,
            },
        }

    monkeypatch.setattr("src.core.v2_exemplar_conformance.load_target_pairings", lambda _path, _roots: first_pairings)
    monkeypatch.setattr("src.core.v2_exemplar_conformance.load_remaining_pairings", lambda _path, _roots: remaining_pairings)
    monkeypatch.setattr("src.core.v2_exemplar_conformance.prepare_v2_product", fake_prepare)

    result = run_unified_v2_exemplar_conformance_products(
        project_root,
        UnifiedV2ExemplarConformanceOptions(
            pairing_path=pairing_path,
            output_root=output_root,
            with_origin=True,
            timestamp="20260605_150000",
            first_run_root=first_run,
            remaining_run_root=remaining_run,
            eis_v2_run_root=eis_run,
        ),
        root_map={},
        origin_exporter=fake_export,
    )

    assert prepare_calls == [product_key for product_key in V2_TARGET_TYPES if product_key != "EIS"]
    assert export_calls == prepare_calls
    assert result["summary"]["product_count"] == 11
    assert result["summary"]["failure_count"] == 0
    assert result["summary"]["eis_imported"] is True
    run_root = Path(result["run_root"])
    imported_eis_meta = json.loads(
        (run_root / "EIS" / "metadata" / "eis_cleaning_and_fit_metadata.json").read_text(encoding="utf-8")
    )
    assert imported_eis_meta["cleaning"]["ignored_point_count"] == 9
    assert imported_eis_meta["fit"]["parameters"]["n"] == 0.8054177975139813
    assert not Path(imported_eis_meta["fit_curve"]).is_absolute()
    assert run_root / Path(imported_eis_meta["fit_curve"]) == run_root / "EIS" / "processed_data" / "eis_randles_cpe_fit_curve.csv"
    product_metadata = run_root / "EIS" / "metadata" / "EIS_BOBC_exemplar_v2" / "metadata.json"
    assert product_metadata.exists()
    assert not (run_root / "EIS" / "metadata" / "EIS_BOBC_exemplar_v2.json").exists()
    imported_product_meta = json.loads(product_metadata.read_text(encoding="utf-8"))
    assert imported_product_meta["metadata_path"] == "EIS/metadata/EIS_BOBC_exemplar_v2/metadata.json"
    eis_summary = next(item for item in result["products"] if item["product_key"] == "EIS")
    assert eis_summary["metadata"] == "EIS/metadata/EIS_BOBC_exemplar_v2/metadata.json"
    import_report = run_root / "EIS" / "reports" / "EIS_BOBC_exemplar_v2_import_report.md"
    assert "not refitted" in import_report.read_text(encoding="utf-8")
    assert (project_root / "docs" / "UNIFIED_V2_PRODUCT_SUMMARY.md").exists()
    assert (project_root / "docs" / "UNIFIED_V2_PRODUCT_NO_LABEL_AUDIT.md").exists()


def test_cli_unified_v2_passes_eis_run_root(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    pairing = tmp_path / "pairing.json"
    pairing.write_text("[]", encoding="utf-8")
    output_root = tmp_path / "external"
    first_run = tmp_path / "first"
    remaining_run = tmp_path / "remaining"
    eis_run = tmp_path / "eis_v2"
    captured: dict[str, object] = {}

    def fake_run(project: Path, options: UnifiedV2ExemplarConformanceOptions) -> dict[str, object]:
        captured["project"] = project
        captured["options"] = options
        return {
            "run_root": str(output_root / "runs" / "fake"),
            "summary": {"product_count": 11, "failure_count": 0, "eis_imported": True},
            "failures": [],
        }

    monkeypatch.chdir(project_root)
    monkeypatch.setattr("src.cli.run_unified_v2_exemplar_conformance_products", fake_run)

    code = main(
        [
            "unified-v2-exemplar-conformance-all-types",
            "--pairing",
            str(pairing),
            "--output-root",
            str(output_root),
            "--with-origin",
            "--timestamp",
            "20260605_150000",
            "--first-run-root",
            str(first_run),
            "--remaining-run-root",
            str(remaining_run),
            "--eis-v2-run-root",
            str(eis_run),
        ]
    )

    assert code == 0
    assert captured["project"] == project_root
    options = captured["options"]
    assert isinstance(options, UnifiedV2ExemplarConformanceOptions)
    assert options.pairing_path == pairing
    assert options.output_root == output_root
    assert options.with_origin is True
    assert options.timestamp == "20260605_150000"
    assert options.first_run_root == first_run
    assert options.remaining_run_root == remaining_run
    assert options.eis_v2_run_root == eis_run


def _pair(product_key: str) -> TargetPairing:
    return TargetPairing(
        product_key=product_key,
        data_type=product_key,
        xps_subtype="",
        data_root_label="fake",
        data_paths=[Path(f"{product_key}.csv")],
        opju_root_label="fake",
        reference_opju=Path(f"{product_key}.opju"),
        raw={"data_type": product_key},
    )


def _write_completed_eis_run(run_root: Path) -> Path:
    type_root = run_root / "EIS"
    files = {
        "processed_data/raw_eis_data.csv": "frequency_hz,z_real_ohm,minus_z_imag_ohm\n1,1,1\n",
        "processed_data/cleaned_eis_data.csv": "frequency_hz,z_real_ohm,minus_z_imag_ohm\n1,1,1\n",
        "processed_data/ignored_eis_points.csv": "source_index,reason\n63,invalid_negative_z_real\n",
        "processed_data/eis_randles_cpe_fit_curve.csv": "z_real_ohm,minus_z_imag_ohm\n1,1\n",
        "processed_data/EIS_BOBC_exemplar_v2.csv": "cleaned_z_real_kohm,cleaned_minus_z_imag_kohm,fit_z_real_kohm,draft_fit_minus_z_imag_kohm\n1,1,1,1\n",
        "origin_files/EIS_BOBC_exemplar_v2.opju": "opju",
        "figures_tif/EIS_BOBC_exemplar_v2.tif": "tif",
        "figures_preview/EIS_BOBC_exemplar_v2_preview.png": "png",
        "reference_exports/EIS_BOBC_exemplar_v2_reference_preview.png": "ref png",
        "reference_opju/reference.opju": "ref",
        "input_copies/01_EIS-1.txt": "raw",
        "reports/EIS_BOBC_exemplar_v2_report.md": "# EIS source report\n",
    }
    for relative, text in files.items():
        path = type_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    (type_root / "metadata").mkdir(parents=True, exist_ok=True)
    (type_root / "metadata" / "eis_cleaning_and_fit_metadata.json").write_text(
        json.dumps(
            {
                "cleaning": {
                    "raw_point_count": 71,
                    "cleaned_point_count": 62,
                    "ignored_point_count": 9,
                    "ignored_points": [{"source_index": 63, "reason": "invalid_negative_z_real"}],
                },
                "fit": {
                    "method": "least_squares_randles_cpe",
                    "model": "Model A: Rs + (Rct || CPE)",
                    "point_count": 240,
                    "parameters": {
                        "Rs": 8.72681344826923,
                        "Rct": 46525.708925066436,
                        "Q": 0.00013615677344406643,
                        "n": 0.8054177975139813,
                    },
                    "semicircle_classification": "depressed semicircle candidate",
                    "review_policy": "draft fit for visualization/manual review only",
                },
                "raw_data": str(type_root / "processed_data" / "raw_eis_data.csv"),
                "cleaned_data": str(type_root / "processed_data" / "cleaned_eis_data.csv"),
                "ignored_points": str(type_root / "processed_data" / "ignored_eis_points.csv"),
                "fit_curve": str(type_root / "processed_data" / "eis_randles_cpe_fit_curve.csv"),
                "default_fitted_model": "Model A: Rs + (Rct || CPE)",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (type_root / "metadata" / "EIS_BOBC_exemplar_v2.json").write_text(
        json.dumps(
            {
                "product_key": "EIS",
                "processed_data": str(type_root / "processed_data" / "EIS_BOBC_exemplar_v2.csv"),
                "origin_file": str(type_root / "origin_files" / "EIS_BOBC_exemplar_v2.opju"),
                "figure_tif": str(type_root / "figures_tif" / "EIS_BOBC_exemplar_v2.tif"),
                "preview_png": str(type_root / "figures_preview" / "EIS_BOBC_exemplar_v2_preview.png"),
                "origin_status": {
                    "ok": True,
                    "message": "Origin isolated v2 export succeeded",
                    "conformance": {
                        "status": "pass",
                        "compared_fields": 4,
                        "matched_fields": 4,
                        "plot_line_width_origin_units": [30.0],
                        "axis_title_bold": True,
                    },
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return run_root
