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
    assert "New-NeutralOriginStage" in text
    assert "Assert-UnderOrEqual $OutputDir $projectOutputRoot" in text
    assert "OutputDir must stay under the configured output root" in text
    assert "Set-HplcTextObjectBounds" in text
    assert "Assert-HplcTextObjectBounds" in text
    assert "Get-ProjectOutputRoot" in text
    assert "$stageTemplateDir" in text
    assert "Join-Path $projectRoot 'output\\hplc_calibration_origin'" not in text
    assert "Join-Path $OutputDir 'origin_templates'" not in text
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
    assert "metadata\\HPLC_calibration_curves" in text
    assert "metadata.json" in text
    assert "METADATA=" in text
    assert "manual_check_required" in text
    assert "expGraph type:=png" in text
    assert "expGraph type:=tif" in text
    assert "600" in text
    assert "To-RunRelativePath $templateOriginalPreviewMap" in text
    assert "To-RunRelativePath $templatePreviewMap" in text
    assert "To-RunRelativePath $generatedPreviewMap" in text
    assert "TIF DPI normalization failed" in text
    assert "TIF DPI normalization skipped" not in text


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
    assert "layer.y.label.divideBy=' + $YDivideBy" in text
    assert "layer.x.ticks=2" in text
    assert "layer.x.ticklength=8" in text
    assert "layer.y.ticks=2" in text
    assert r"Peak area \(40)10\+(3) mAU*s\(41)" in text
    assert r"Peak area \(40)10\+(2) mAU*s\(41)" in text
    assert "YDivideBy=1000" in text
    assert "YDivideBy=100" in text
    assert "LegendLeft=2300; LegendTop=760; LegendWidth=2429; LegendHeight=826" in text
    assert "LegendLeft=2300; LegendTop=760; LegendWidth=2308; LegendHeight=826" in text
    assert "LegendLeft=2300; LegendTop=760; LegendWidth=2457; LegendHeight=760" in text
    assert "XTitleLeft=1927; XTitleTop=4487; XTitleWidth=2835; XTitleHeight=338" in text
    assert "YTitleLeft=226; YTitleTop=736; YTitleWidth=384; YTitleHeight=3204" in text
    assert "YTitleLeft=413; YTitleTop=736; YTitleWidth=384; YTitleHeight=3204" in text
    assert "layer.y.showLabels=1" in text


def test_hplc_template_comparison_is_full_pixel_exact_and_archives_original_reference() -> None:
    text = _script_text()

    assert "[double]$ComparisonMeanTolerance = 0.0" in text
    assert "[double]$ComparisonMaxTolerance = 0.0" in text
    assert "Strict template comparison requires zero mean and max pixel tolerances." in text
    assert "HplcImageComparer" in text
    assert "ChangedPixels" in text
    assert "ExactPixelMatch" in text
    assert "exact_pixel_match" in text
    assert "[Math]::Min(101" not in text
    assert "Assert-HplcGraphExists $app $s.TemplateGraph" in text
    original_export_index = text.index("$templateOriginalPreviewMap[$s.Page] = Export-GraphPng")
    axis_normalization_index = text.index(
        "Apply-HplcYAxisStyle $app $s.TemplateGraph $s.YDivideBy $s.YTitle"
    )
    expected_export_index = text.index("$templatePreviewMap[$s.Page] = Export-GraphPng")
    template_save_index = text.index("template_saveas pg:=")
    assert original_export_index < axis_normalization_index < expected_export_index < template_save_index
