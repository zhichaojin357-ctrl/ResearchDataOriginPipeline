from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.core import template_format_executor as executor
from src.core import template_inputs
from src.origin import style_registry


@pytest.mark.parametrize("mode", ["RGB", "RGBA", "L", "P"])
def test_png_metadata_cleanup_preserves_exact_pixels(tmp_path: Path, mode: str) -> None:
    from PIL import Image, PngImagePlugin

    image = Image.new(mode, (13, 11))
    channels = len(image.getbands())
    pixels = [
        tuple((index * 19 + channel * 53) % 256 for channel in range(channels))
        if channels > 1 else index % 256
        for index in range(13 * 11)
    ]
    image.putdata(pixels)
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("Comment", "private source metadata")
    path = tmp_path / "preview.png"
    image.save(path, pnginfo=metadata, dpi=(96, 96))
    with Image.open(path) as saved:
        expected_mode, expected_size, expected_pixels = saved.mode, saved.size, saved.tobytes()

    assert executor._strip_raster_metadata(path, dpi=600) == ""

    with Image.open(path) as cleaned:
        assert (cleaned.mode, cleaned.size, cleaned.tobytes()) == (
            expected_mode, expected_size, expected_pixels,
        )
        assert "Comment" not in cleaned.info
        assert cleaned.info["dpi"] == pytest.approx((600, 600), abs=0.02)


def test_processed_table_and_binding_refresh_after_owned_transform(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "processed.csv"
    path.write_text("X,Y\n1,2\n", encoding="utf-8")
    product = SimpleNamespace(product_key="BET", processed_data=path)
    reads = 0
    bindings = 0
    original_open = Path.open

    def track_open(source, *args, **kwargs):
        nonlocal reads
        if source == path and (not args or "w" not in str(args[0])):
            reads += 1
        return original_open(source, *args, **kwargs)

    def prepare(_product, _headers, rows, **_kwargs):
        nonlocal bindings
        bindings += 1
        return {"ok": True, "current_y": rows[0][1]}

    monkeypatch.setattr(Path, "open", track_open)
    monkeypatch.setattr(executor, "_prepare_verified_bet_otpu_binding", prepare)
    with template_inputs.template_input_scope():
        for _ in range(2):
            headers, rows = executor._read_processed_csv(path)
            assert executor._prepare_verified_otpu_binding(product, headers, rows)["current_y"] == 2
        assert (reads, bindings) == (1, 1)
        executor._write_processed_csv(path, headers, [[1, 7]])
        headers, rows = executor._read_processed_csv(path)
        assert executor._prepare_verified_otpu_binding(product, headers, rows)["current_y"] == 7
        assert (reads, bindings) == (2, 2)
    executor._read_processed_csv(path)
    assert reads == 3


def test_binding_contract_load_is_scoped_to_one_product(tmp_path: Path, monkeypatch) -> None:
    loads: list[Path] = []

    def load(path):
        loads.append(path)
        return {"BET": object()}

    monkeypatch.setattr(template_inputs, "_load_contracts", load)
    path = tmp_path / "contract.json"
    with template_inputs.template_input_scope():
        first = template_inputs.load_template_binding_contracts(path)
        assert template_inputs.load_template_binding_contracts(path) is first
    with template_inputs.template_input_scope():
        assert template_inputs.load_template_binding_contracts(path) is not first
    assert loads == [path, path]


def test_asset_reads_share_nested_scope_and_end_hash_still_reads_source(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "snapshot.json"
    path.write_text('{"version": 1}', encoding="utf-8")
    reads = 0
    hashes = 0
    original_read = Path.read_text
    original_hash = style_registry.file_sha256

    def read(source, *args, **kwargs):
        nonlocal reads
        reads += source == path
        return original_read(source, *args, **kwargs)

    def digest(source):
        nonlocal hashes
        hashes += source == path
        return original_hash(source)

    monkeypatch.setattr(Path, "read_text", read)
    monkeypatch.setattr(style_registry, "file_sha256", digest)
    with style_registry.origin_style_asset_read_scope():
        initial = style_registry.read_origin_style_json(path)
        initial_hash = style_registry.origin_style_file_sha256(path)
        with style_registry.origin_style_asset_read_scope():
            assert style_registry.read_origin_style_json(path) is initial
            assert style_registry.origin_style_file_sha256(path) == initial_hash
        assert (reads, hashes) == (1, 1)
        path.write_text('{"version": 2}', encoding="utf-8")
        # Production's final source check deliberately calls the uncached hash.
        assert executor.file_sha256(path) != initial_hash
    with style_registry.origin_style_asset_read_scope():
        assert style_registry.read_origin_style_json(path) == {"version": 2}
        assert style_registry.origin_style_file_sha256(path) != initial_hash
    assert (reads, hashes) == (2, 2)


@pytest.mark.parametrize("selected", [{"Text"}, set()])
def test_xps_restores_only_objects_retained_by_current_annotation_policy(monkeypatch, selected) -> None:
    names = ["Text", "Text1", "Text2"]
    objects = {name: SimpleNamespace(Text="") for name in names}
    commands: list[str] = []
    operations = SimpleNamespace(
        app=SimpleNamespace(FindGraphLayer=lambda _name: object()),
        run_labtalk=lambda command: commands.append(command) or SimpleNamespace(ok=True),
    )
    monkeypatch.setattr(executor, "_find_origin_graph_object", lambda _layer, name: objects[name])
    monkeypatch.setattr(executor, "_style_graph_object", lambda *_args, **_kwargs: True)
    snapshot = {"adaptive_native_graph_objects": [{"name": name, "text": name + " current"} for name in names]}

    result = executor._restore_adaptive_xps_native_graph_objects(
        operations, "Graph1", snapshot, expected_names=names, restore_names=selected,
    )

    assert result["applied"] is True
    assert set(result["object_names"]) == selected
    assert len(commands) == 2 * len(selected)
    for name in names:
        assert objects[name].Text == (name + " current" if name in selected else "")


def test_executor_report_displays_actual_route_decisions(tmp_path: Path) -> None:
    result = {
        "summary": {"product_count": 2},
        "products": [
            {"product_key": "FTIR", "origin_style_decision": {"selected_mode": "otpu", "reason_code": "auto_exact_fixed_binding_match"}},
            {"product_key": "EPR", "origin_style_decision": {"selected_mode": "oth-json", "reason_code": "auto_series_cardinality_mismatch_only"}},
        ],
    }
    executor._write_template_format_docs(tmp_path, tmp_path / "run", result)
    report = (tmp_path / "run/reports/template_format_executor_summary.md").read_text(encoding="utf-8")
    payload = json.loads((tmp_path / "run/reports/template_format_executor_summary.json").read_text(encoding="utf-8"))
    assert "FTIR: otpu (auto_exact_fixed_binding_match)" in report
    assert "EPR: oth-json (auto_series_cardinality_mismatch_only)" in report
    assert payload["products"] == result["products"]
    assert "default to an isolated copy" not in payload["policy"]
