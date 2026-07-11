from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = PROJECT_ROOT / "scripts" / "origin" / "origin_plot_from_template.ps1"


def _helper_text() -> str:
    assert HELPER_PATH.is_file(), f"missing Origin helper script: {HELPER_PATH}"
    return HELPER_PATH.read_text(encoding="utf-8-sig")


def test_origin_helper_uses_data_file_name_without_comments() -> None:
    text = _helper_text()

    assert "impASC" not in text
    assert "[System.IO.Path]::GetFileName($dataFile)" in text
    assert "Convert-ToSafeOriginName ([System.IO.Path]::GetFileNameWithoutExtension($dataFile))" in text
    assert "wks.longname$=" in text
    assert "wks.comments$=\"\"" in text
    assert "wks.comment$=\"\"" in text
    assert 'doc -e W { page.comments$=""; page.comment$=""; wks.comments$=""; wks.comment$=""; };' in text
    assert 'wks.name$="Data"' not in text
    assert 'page.comments$=""' in text
    assert 'page.comment$=""' in text
    assert "page.longname$=page.name$" not in text


def test_origin_helper_stdout_uses_leaf_names_for_generated_artifacts() -> None:
    text = _helper_text()

    assert 'Write-Output ("SAVED=" + (Split-Path -Leaf $OutputOpju))' in text
    assert 'Write-Output ("EXPORT_DIR=" + (Split-Path -Leaf $ExportDir))' in text
    assert 'Write-Output ("REFERENCE=" + (Split-Path -Leaf $ReferenceOpju))' in text
    assert "CodexOrigin" not in text


def test_origin_helper_defaults_to_project_local_reference_opju() -> None:
    text = _helper_text()

    assert "D:\\OriginFlies\\Manual Save" not in text
    assert "CWO+BOBC+*.opju" not in text
    assert "templates\\origin_styles\\reference_opju\\XRD.opju" in text


def test_origin_helper_enforces_unframed_or_hidden_legends() -> None:
    text = _helper_text()

    assert "Get-GroupValue $Group 'ShowLegend' $true" in text
    assert "legend.show=0;" in text
    assert "$legend.Destroy()" in text
    assert "Visible legend text is missing" in text
    assert "$legend.SetNumProp('background', 0)" in text
    assert "$legend.SetNumProp('lineWidth', 0)" in text
    assert (
        "legend.show=1; legend.background=0; legend.border=0; legend.frame=0; legend.fill=0; "
        "legend.fillColor=0; legend.borderColor=0; legend.lineWidth=0;"
    ) in text
