from __future__ import annotations

from pathlib import Path
import json
import shutil
import subprocess

import pytest


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


def test_origin_helper_reads_bomless_utf8_csv_explicitly() -> None:
    text = _helper_text()

    assert "Get-Content -LiteralPath $DataFile -Encoding UTF8 -TotalCount 1" in text
    assert "Get-Content -LiteralPath $DataFile -Encoding UTF8)" in text


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


def _run_helper_functions(tmp_path: Path, body: str) -> dict:
    """Run real helper functions with a fake COM object; no Origin is started."""
    shell = shutil.which("powershell") or shutil.which("pwsh")
    if not shell:
        pytest.skip("PowerShell function tests run on Windows; no Origin required")
    script = tmp_path / "helper_function_test.ps1"
    helper_literal = str(HELPER_PATH).replace("'", "''")
    script.write_text(
        "$ErrorActionPreference = 'Stop'\n"
        "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)\n"
        "$tokens = $null; $parseErrors = $null\n"
        f"$ast = [System.Management.Automation.Language.Parser]::ParseFile('{helper_literal}', [ref]$tokens, [ref]$parseErrors)\n"
        "if ($parseErrors.Count) { throw ($parseErrors | Out-String) }\n"
        "$functions = $ast.FindAll({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst]}, $false)\n"
        "foreach ($definition in $functions) { . ([scriptblock]::Create($definition.Extent.Text)) }\n"
        + body,
        encoding="utf-8-sig",
    )
    completed = subprocess.run([shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                               text=True, encoding="utf-8", capture_output=True, timeout=30, cwd=tmp_path)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    prefix = "TEST_RESULT="
    return json.loads(next(line[len(prefix):] for line in completed.stdout.splitlines() if line.startswith(prefix)))


@pytest.mark.parametrize("reject_put", [False, True])
def test_helper_writes_complete_numeric_columns_and_preserves_mixed_cells(tmp_path, reject_put):
    result = _run_helper_functions(tmp_path, r'''
$app = [pscustomobject]@{ Commands = (New-Object 'System.Collections.Generic.List[string]'); Puts = (New-Object 'System.Collections.Generic.List[object]'); RejectPut = REJECT_PUT }
$app | Add-Member ScriptMethod Execute { param($command) $this.Commands.Add($command); return $true }
$app | Add-Member ScriptMethod PutWorksheet {
  param($target, $values, $row, $column)
  $this.Puts.Add(@{ Target=$target; Values=@($values); Row=$row; Column=$column })
  return (-not $this.RejectPut)
}
$rows = @([pscustomobject]@{X='0'; Y='1'; Text='first'}, [pscustomobject]@{X='1.2345678901234567'; Y=''; Text=''}, [pscustomobject]@{X='2'; Y='3'; Text='third'})
Initialize-OriginDataWorkbook $app 'Book1' 'sample.csv' @('X','Y','Text') $rows 3
Write-Output ('TEST_RESULT=' + (@{Commands=@($app.Commands.ToArray()); Puts=@($app.Puts.ToArray())} | ConvertTo-Json -Depth 6 -Compress))
'''.replace("REJECT_PUT", "$true" if reject_put else "$false"))
    assert result["Puts"] == [{"Target": "[Book1]sample", "Values": [0.0, 1.2345678901234567, 2.0], "Row": 0, "Column": 0}]
    commands = result["Commands"]
    assert "wcol(2)[1]=1;" in commands and "wcol(2)[3]=3;" in commands
    assert not any("wcol(2)[2]" in command for command in commands)
    assert 'wcol(3)[1]$="first";' in commands and 'wcol(3)[3]$="third";' in commands
    assert any(command.startswith("wcol(1)") for command in commands) is reject_put


def test_helper_single_row_keeps_double_arrays_and_chinese_headers(tmp_path):
    result = _run_helper_functions(tmp_path, r'''
$app = [pscustomobject]@{ Commands=(New-Object 'System.Collections.Generic.List[string]'); Puts=(New-Object 'System.Collections.Generic.List[object]') }
$app | Add-Member ScriptMethod Execute { param($command) $this.Commands.Add($command); return $true }
$app | Add-Member ScriptMethod PutWorksheet {
  param($target, $values, $row, $column)
  $this.Puts.Add(@{ Target=$target; Type=$values.GetType().FullName; Values=@($values); Row=$row; Column=$column })
  return $true
}
$rows = @([pscustomobject]@{'波长'='455'; '强度'='1.2345678901234567'})
Initialize-OriginDataWorkbook $app 'Book1' '光谱.csv' @('波长','强度') $rows 2
Write-Output ('TEST_RESULT=' + (@{Commands=@($app.Commands.ToArray()); Puts=@($app.Puts.ToArray())} | ConvertTo-Json -Depth 6 -Compress))
''')
    assert result["Puts"] == [
        {"Target": "[Book1]Data", "Type": "System.Double[]", "Values": [455.0], "Row": 0, "Column": 0},
        {"Target": "[Book1]Data", "Type": "System.Double[]", "Values": [1.2345678901234567], "Row": 0, "Column": 1},
    ]
    assert 'wks.col1.lname$="波长"; wks.col1.comment$="";' in result["Commands"]
    assert 'wks.col2.lname$="强度"; wks.col2.comment$="";' in result["Commands"]
    assert not any(command.startswith("wcol(") for command in result["Commands"])
