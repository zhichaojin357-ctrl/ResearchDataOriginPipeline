from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "data_types" / "hplc_lc" / "plot_hplc_calibration_origin.ps1"


def _script_text() -> str:
    assert SCRIPT_PATH.is_file(), f"missing HPLC calibration Origin script: {SCRIPT_PATH}"
    return SCRIPT_PATH.read_text(encoding="utf-8-sig")


def test_hplc_calibration_script_requires_explicit_hplc_opju_template() -> None:
    text = _script_text()

    assert "[Parameter(Mandatory=$true)]" in text
    assert "D:\\OriginFlies\\Manual Save" not in text
    assert "CWO+BOBC" not in text
    assert "Origin.ApplicationSI" not in text
    assert "New-Object -ComObject Origin.Application" in text
    assert "[string]$TemplateOpju" in text
    assert "[string]$OutputDir" in text
    assert "impASC" not in text
    assert "CodexOrigin" not in text
    assert "category:=\"HPLC_Calibration\"" in text
    assert "Set-OriginWorksheetColumn" in text
    assert "Sanitize-ProjectPages" in text
    assert "$dataFileName = $Substance + '_calibration_data.tsv'" in text
    assert "wks.longname$=" in text
    assert "wks.comments$=\"\"" in text
    assert "wks.comment$=\"\"" in text
    assert 'doc -e W { page.comments$=""; page.comment$=""; wks.comments$=""; wks.comment$=""; };' in text
    assert 'wks.name$="Data"' not in text
    assert "page.longname$=page.name$" not in text
    assert "Stamp must not include assistant or tool labels." in text


def test_hplc_calibration_script_exports_expected_artifact_set() -> None:
    text = _script_text()

    assert "HPLC_calibration_curves_" in text
    assert "final_calibration_data.tsv" in text
    assert "origin_run_log.txt" in text
    assert "figures_preview" in text
    assert "figures_tif" in text
    assert "expGraph type:=png" in text
    assert "expGraph type:=tif" in text
    assert "600" in text
    assert "To-RunRelativePath $templatePreviewMap" in text
    assert "To-RunRelativePath $generatedPreviewMap" in text


def test_hplc_calibration_script_preserves_three_template_pages_and_locked_style() -> None:
    text = _script_text()

    for page in ("Cal_Sulfoxide", "Cal_Sulfone", "Cal_Sulfide"):
        assert page in text
    for graph_page in ("TemplateGraph='Cal_Sulfoxide'", "TemplateGraph='Cal_Sulfone'", "TemplateGraph='Cal_Sulfide'"):
        assert graph_page in text
    assert "page.width=6432" in text
    assert "page.height=4923" in text
    assert "layer.left=17.89" in text
    assert "layer.width=68.19" in text
    assert "axis_title_size=36" in text
    assert "layer.x.label.pt=28" in text
    assert "layer.y.label.pt=22" in text
    assert "layer.y.label.divideBy=1000" in text
    assert "layer.y.ticks=2" in text
    assert r"Peak area \(40)10\+(3) mAU*s\(41)" in text
    assert "layer.y.showLabels=1" in text
