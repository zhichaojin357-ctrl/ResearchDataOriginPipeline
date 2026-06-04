from __future__ import annotations

from pathlib import Path

from src.origin.style_mimic import (
    FORBIDDEN_EXEMPLAR_TEXT_CATEGORIES,
    OpjuStyleSnapshot,
    apply_style_snapshot,
    extract_style_snapshot,
)


def test_extract_style_snapshot_reads_layout_and_plot_style_without_visible_text(tmp_path: Path) -> None:
    reference = tmp_path / "reference.opju"
    reference.write_text("reference", encoding="utf-8")
    fake = _FakeStyleOps()

    snapshot = extract_style_snapshot(fake, reference)

    assert snapshot.status == "extracted"
    assert snapshot.graph_page == "Graph1"
    assert snapshot.graph_pages == ["Graph1"]
    assert snapshot.layout_values["page.width"] == 720
    assert snapshot.layout_values["layer.width"] == 60
    assert snapshot.layer_count == 1
    assert snapshot.audit_numeric_values["legend.x"] == 42
    assert snapshot.audit_numeric_values["title.show"] == 0
    assert snapshot.audit_string_values["xb.font$"] == "Arial"
    assert snapshot.plot_count == 2
    assert snapshot.plot_line_widths == [15.0, 20.0]
    assert snapshot.plot_colors == [2.0, 4.0]
    assert snapshot.copied_visible_text is False
    assert "phase labels" in FORBIDDEN_EXEMPLAR_TEXT_CATEGORIES


def test_apply_style_snapshot_replays_only_numeric_layout_values() -> None:
    fake = _FakeStyleOps()
    snapshot = OpjuStyleSnapshot(
        source_opju="copied.opju",
        status="extracted",
        graph_page="Graph1",
        layout_values={"page.width": 720.0, "layer.left": 23.0, "bad": "not-number"},
    )

    applied = apply_style_snapshot(fake, "ProductGraph", snapshot)

    assert applied is True
    assert any('win -a "ProductGraph"' in script for script in fake.labtalk_scripts)
    assert any("page.width=720.0" in script and "layer.left=23.0" in script for script in fake.labtalk_scripts)
    assert not any("not-number" in script for script in fake.labtalk_scripts)
    assert fake.font_calls == ["ProductGraph"]


def test_apply_style_snapshot_returns_false_without_numeric_layout() -> None:
    fake = _FakeStyleOps()

    applied = apply_style_snapshot(fake, "ProductGraph", OpjuStyleSnapshot("copied.opju", "no_graph_pages"))

    assert applied is False
    assert fake.font_calls == []


class _FakeResult:
    def __init__(self, ok: bool = True, message: str = "ok", payload: dict[str, object] | None = None) -> None:
        self.ok = ok
        self.message = message
        self.payload = payload or {}


class _FakeStyleOps:
    def __init__(self) -> None:
        self.labtalk_scripts: list[str] = []
        self.font_calls: list[str] = []
        self.values = {
            "page.width": 720,
            "page.height": 540,
            "layer.left": 23,
            "layer.top": 10,
            "layer.width": 60,
            "layer.height": 62,
            "layer.x.thickness": 3,
            "layer.y.thickness": 3,
            "layer.x.label.pt": 24,
            "layer.y.label.pt": 24,
            "page.nlayers": 1,
            "layer.x.ticks": 1,
            "layer.y.ticks": 1,
            "layer.x.label.show": 1,
            "layer.y.label.show": 1,
            "layer.x.showLabels": 1,
            "layer.y.showLabels": 1,
            "xb.show": 1,
            "yl.show": 1,
            "xb.fsize": 36,
            "yl.fsize": 36,
            "xb.bold": 1,
            "yl.bold": 1,
            "legend.show": 0,
            "legend.x": 42,
            "legend.y": 84,
            "legend.fsize": 18,
            "legend.bold": 0,
            "title.show": 0,
            "title.fsize": 18,
            "title.bold": 0,
            "xb.font$": "Arial",
            "yl.font$": "Arial",
            "legend.font$": "Arial",
            "title.font$": "Arial",
            "__style_mimic_w_1": 15.0,
            "__style_mimic_w_2": 20.0,
            "__style_mimic_c_1": 2.0,
            "__style_mimic_c_2": 4.0,
            "__style_mimic_k_1": 1.0,
            "__style_mimic_k_2": 2.0,
            "__style_mimic_z_1": 8.0,
            "__style_mimic_z_2": 9.0,
        }

    def load_project(self, _path: Path) -> _FakeResult:
        return _FakeResult()

    def list_worksheets(self) -> _FakeResult:
        return _FakeResult(payload={"pages": [{"name": "Graph1", "type": "graph"}]})

    def run_labtalk(self, script: str) -> _FakeResult:
        self.labtalk_scripts.append(script)
        return _FakeResult()

    def get_labtalk_variable(self, name: str) -> _FakeResult:
        return _FakeResult(payload={"value": self.values.get(name)})

    def _plot_names(self, _graph_name: str) -> list[str]:
        return ["Plot1", "Plot2"]

    def set_graph_font(self, graph_name: str) -> _FakeResult:
        self.font_calls.append(graph_name)
        return _FakeResult()
