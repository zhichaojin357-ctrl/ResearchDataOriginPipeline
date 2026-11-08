from pathlib import Path
from types import SimpleNamespace

import pytest

from src.core.uvvis_bundle import fit_tauc_intervals, _csv_signature, _position_bundle_axis_titles, _bundle_plot_style_contracts, _bundle_plot_styles, _write_verified_bundle_worksheet, _verify_bundle_worksheet
from src.processors.calculations import uvvis_transmittance_percent_processed_table, uvvis_processed_table
from src.core.template_product_builder import _build_template_uvvis_table, TemplateCandidate
from src.core.template_product_common import TargetPairing
from src.core.template_format_executor import TemplateFormatExecutorOptions, run_template_format_executor
from src.origin.operations import OriginOperations


def test_tauc_explicit_interval_returns_known_intercept_and_ignores_other_branch(tmp_path: Path):
    source = tmp_path / "tauc.csv"
    source.write_text("a_x,a_y,b_x,b_y\n" + "\n".join(
        f"{2.5+i/20},{3*(2.5+i/20-2.2)},{2.5+i/20},{5*(2.5+i/20-2.4)}" for i in range(9)
    ) + "\n5,900,5,800\n", encoding="utf-8")
    fits = fit_tauc_intervals(source, ["BOB", "BVO"], {"BOB": [2.5, 2.9], "BVO": [2.5, 2.9]})
    assert [f["Eg_candidate_eV"] for f in fits] == pytest.approx([2.2, 2.4])
    assert all(f["r_squared"] == pytest.approx(1) and f["point_count"] == 9 for f in fits)
    assert len(_csv_signature(source)[0][0]) == 10
    with pytest.raises(ValueError, match="five points"):
        fit_tauc_intervals(source, ["BOB", "BVO"], {"BOB": [2.5, 2.51], "BVO": [2.5, 2.9]})


def test_tauc_rejects_non_rising_edge(tmp_path: Path):
    source = tmp_path / "tauc.csv"
    source.write_text("x,y\n1,6\n2,5\n3,4\n4,3\n5,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="positive linear edge"):
        fit_tauc_intervals(source, ["BOB"], {"BOB": [1,5]})


def test_uvvis_explicit_names_preserve_source_values(tmp_path: Path):
    source = tmp_path / "bv7.5%.csv"
    source.write_text("wavelength,absorbance\n800,0.02\n500,-0.1\n", encoding="utf-8")
    pairing = TargetPairing("UV-vis DRS", "UV-vis DRS", "", "test", [source], "test", tmp_path / "uv.opju", {"legend_entries": ["BV-7.5%"]})
    result = _build_template_uvvis_table(pairing, TemplateCandidate("UV-vis DRS", pairing.reference_opju, "test"), origin_style_mode="auto")
    assert result["labels"]["legend_entries"] == ["BV-7.5%"]
    assert result["rows"] == [[800, 0.02], [500, -0.1]]
    pairing.raw["legend_entries"] = []
    with pytest.raises(ValueError, match="one nonempty sample"):
        _build_template_uvvis_table(pairing, TemplateCandidate("UV-vis DRS", pairing.reference_opju, "test"), origin_style_mode="auto")


def test_uvvis_bundle_requires_explicit_origin(tmp_path: Path):
    with pytest.raises(ValueError, match="requires --with-origin"):
        run_template_format_executor(tmp_path, TemplateFormatExecutorOptions(tmp_path / "pairing.json", uvvis_bundle=True))


def test_append_project_uses_document_append_without_opening_or_saving_source(tmp_path: Path):
    path = tmp_path / "graph.opju"
    path.write_bytes(b"project")
    commands = []
    ops = OriginOperations(SimpleNamespace(Execute=lambda command: commands.append(command) or True))
    assert ops.append_project(path).ok
    assert len(commands) == 1 and commands[0].startswith('doc -a "')
    assert not ops.append_project(tmp_path / "missing.opju").ok


def test_native_axis_titles_are_positioned_inside_fixed_page_without_com_attach_setter(monkeypatch):
    from src.core import template_format_executor

    class AxisTitle:
        def __init__(self, width, height):
            self.Width, self.Height = width, height

        @property
        def Attach(self):
            return 1

        @Attach.setter
        def Attach(self, value):
            raise AttributeError("Not exposed by the native axis-title COM wrapper")

    objects = {"XB": AxisTitle(2000, 400), "YL": AxisTitle(400, 1800)}
    monkeypatch.setattr(template_format_executor, "_find_origin_graph_object", lambda layer, name: objects[name])
    commands = []
    ops = SimpleNamespace(app=SimpleNamespace(FindGraphLayer=lambda name: object()),
                          run_labtalk=lambda command: commands.append(command) or SimpleNamespace(ok=True))
    _position_bundle_axis_titles(ops, "Tauc", {"layout_values": {"page.width": 6432, "page.height": 4923,
        "layer.left": 17.88, "layer.top": 11.6, "layer.width": 68.17, "layer.height": 71.83}})
    for obj in objects.values():
        assert 0 <= obj.Left < obj.Left + obj.Width <= 6432
        assert 0 <= obj.Top < obj.Top + obj.Height <= 4923
    assert "xb.attach=1; yl.attach=1;" in commands[0]


def test_explicit_percent_transmission_retains_raw_values_and_signed_absorbance():
    numeric = [(800.0,100.0),(700.0,10.0),(600.0,1000.0)]
    rows = [{"wavelength_nm":str(x),"transmittance_percent":str(y)} for x,y in numeric]
    headers, values = uvvis_transmittance_percent_processed_table(numeric, rows)
    assert headers[1:4] == ["transmittance_percent","transmittance_fraction","absorbance"]
    assert [v[1] for v in values] == [100,10,1000]
    assert [v[3] for v in values] == pytest.approx([0,1,-1])
    assert [v[5] for v in values] == pytest.approx([0,(1239.7/700)**2,(1239.7/600)**2])
    with pytest.raises(ValueError, match="explicit, reviewed conversion"):
        uvvis_processed_table(numeric, rows)


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf")])
def test_transmission_log_rejects_nonpositive_or_nonfinite(value):
    with pytest.raises(ValueError, match="positive finite"):
        uvvis_transmittance_percent_processed_table([(500,value)], [{"wavelength":"500","%T":str(value)}])


def test_transmission_requires_percent_units():
    with pytest.raises(ValueError, match="percent-transmittance headers"):
        uvvis_transmittance_percent_processed_table([(500,0.5)], [{"wavelength":"500","transmittance":"0.5"}])


def test_transmission_template_conversion_is_opt_in_and_cache_does_not_bypass_it(tmp_path):
    source = tmp_path / "bob.csv"
    source.write_text("wavelength,transmittance_percent\n800,90\n400,250\n",encoding="utf-8")
    pairing=TargetPairing("UV-vis DRS","UV-vis DRS","","test",[source],"test",tmp_path/"template.opju",
                          {"legend_entries":["BOB"],"transmittance_conversion":"percent_to_absorbance_log10"})
    template=TemplateCandidate("UV-vis DRS",pairing.reference_opju,"test")
    cache={}
    spectrum=_build_template_uvvis_table(pairing,template,origin_style_mode="auto",processed_cache=cache)
    assert spectrum["rows"] == [[800,90],[400,250]]
    assert spectrum["labels"]["y_label"] == "Transmittance (%)"
    assert spectrum["alignment"]["transmission_audit"][0]["negative_absorbance_points"] == 1
    pairing.raw.pop("transmittance_conversion")
    with pytest.raises(ValueError,match="explicit, reviewed conversion"):
        _build_template_uvvis_table(pairing,template,origin_style_mode="auto",processed_cache=cache)


def test_user_palette_requires_a_color_for_each_sample():
    overrides={"BOB":{"rgb":[230,184,0]},"BVO":{"rgb":[230,106,166]},"BV-7.5%":{"rgb":[230,106,166],"line_style":1}}
    specs=_bundle_plot_style_contracts(["BOB","BVO","BV-7.5%"],overrides)
    assert specs[1]["color_code"] == specs[2]["color_code"]
    assert [v["line_style"] for v in specs] == [0,0,1]
    with pytest.raises(ValueError,match="each current sample"):
        _bundle_plot_style_contracts(["Missing"],overrides)
    with pytest.raises(ValueError,match="Invalid bundle RGB"):
        _bundle_plot_style_contracts(["BOB"],{"BOB":{"rgb":[256,1,2]}})


def test_palette_readback_rejects_a_changed_color():
    specs=_bundle_plot_style_contracts(["BOB"],{"BOB":{"rgb":[230,184,0]}})
    ops=SimpleNamespace(_plot_names=lambda graph:["Book_B"],
                        run_labtalk=lambda script:SimpleNamespace(ok=True),
                        get_labtalk_variable=lambda name:SimpleNamespace(ok=True,payload={"value":0}))
    with pytest.raises(RuntimeError,match="Palette readback mismatch"):
        _bundle_plot_styles(ops,"DRS",specs,apply=False)


def test_retained_bundle_worksheet_uses_native_sheet_and_preserves_signed_values():
    stored = {}

    def write(book, sheet, columns, headers):
        stored[book, sheet] = columns
        return SimpleNamespace(ok=True)

    ops = SimpleNamespace(
        create_worksheet=lambda book: SimpleNamespace(ok=True),
        set_worksheet_data=write,
        get_worksheet_data=lambda book, sheet: SimpleNamespace(ok=True, payload={"columns": stored[book, sheet]}),
    )
    columns = [[500, 600], [-0.3, 0.2]]
    _write_verified_bundle_worksheet(ops, "Transmission1", columns, ["Wavelength", "Absorbance"])
    assert stored["Transmission1", "Sheet1"] == columns


@pytest.mark.parametrize("saved", [[], [[500, 600], [0.3, 0.2]], [[500], [-0.3]]])
def test_retained_worksheet_rejects_silent_write_failure_or_changed_values(saved):
    ops = SimpleNamespace(get_worksheet_data=lambda book, sheet: SimpleNamespace(ok=True, payload={"columns": saved}))
    with pytest.raises(RuntimeError, match="Retained worksheet values do not match"):
        _verify_bundle_worksheet(ops, "Transmission1", [[500, 600], [-0.3, 0.2]])
