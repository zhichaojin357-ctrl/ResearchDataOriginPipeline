from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "data_types" / "hplc_lc" / "plot_hplc_calibration_origin.ps1"


def _script_text() -> str:
    assert SCRIPT_PATH.is_file(), f"missing HPLC calibration Origin script: {SCRIPT_PATH}"
    return SCRIPT_PATH.read_text(encoding="utf-8-sig")


def _copy_hplc_script_project(tmp_path: Path) -> tuple[Path, Path, Path]:
    project_root = tmp_path / "project"
    copied_script = (
        project_root
        / "scripts"
        / "data_types"
        / "hplc_lc"
        / SCRIPT_PATH.name
    )
    copied_script.parent.mkdir(parents=True)
    shutil.copy2(SCRIPT_PATH, copied_script)
    return copied_script, project_root, project_root.parent / "\u8f93\u51fa"


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
    assert "Get-NeutralOriginStagePath" in text
    assert "Assert-UnderOrEqual $finalOutputDir $projectOutputRoot" in text
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
    assert "Stamp must be one safe filename component" in text
    assert "'^[A-Za-z0-9][A-Za-z0-9_.-]*$'" in text
    assert "[switch]$Force" in text


def test_hplc_calibration_script_preflights_source_output_and_origin_before_writes() -> None:
    text = _script_text()

    output_reparse_guard = text.index(
        "Assert-NoReparsePointInPath $finalOutputDir 'OutputDir'"
    )
    stamp_guard = text.index("Stamp must be one safe filename component")
    template_reparse_guard = text.index(
        "Assert-NoReparsePointInPath $templateOpjuPath 'TemplateOpju'"
    )
    template_guard = text.index(
        "if (Test-UnderOrEqual $templateOpjuPath $finalOutputDir)"
    )
    output_guard = text.index("OutputDir is not empty; rerun with -Force")
    transaction_selection = text.index(
        "$transactionOutputDir = Join-Path $projectOutputRoot"
    )
    origin_guard = text.index("if ($originPidsBefore.Count -gt 0)")
    data_guard = text.index("Assert-HplcCalibrationInputs $points $series")
    isolated_template_copy = text.index(
        "Copy-Item -LiteralPath $templateOpjuPath -Destination $workingTemplate"
    )
    isolated_template_load = text.index("$app.Load($workingTemplate)")
    template_structure_guard = text.index(
        "Assert-HplcTemplateStructure $app $series",
        isolated_template_load,
    )
    stage_selection = text.index("$stageRoot = Get-NeutralOriginStagePath")
    planned_target_guard = text.index(
        "foreach ($target in $plannedOutputFiles)",
        stage_selection,
    )
    output_write = text.index(
        "New-Item -ItemType Directory -Path $dataDir",
        template_structure_guard,
    )

    assert (
        output_reparse_guard
        < stamp_guard
        < template_reparse_guard
        < template_guard
        < output_guard
        < transaction_selection
        < stage_selection
        < planned_target_guard
        < origin_guard
        < data_guard
        < isolated_template_copy
        < isolated_template_load
        < template_structure_guard
        < output_write
    )
    assert "TemplateOpju must be outside OutputDir" in text
    assert "Origin is already running; close every Origin session" in text
    assert "function Assert-HplcTemplateStructure" in text
    assert "page.nlayers" in text
    assert "Required HPLC template graph has invalid structure" in text


def test_hplc_force_builds_and_validates_staging_before_package_swap() -> None:
    text = _script_text()

    main_start = text.index(
        "$projectRoot = [System.IO.Path]::GetFullPath"
    )
    output_write = text.index(
        "New-Item -ItemType Directory -Path $dataDir",
        main_start,
    )
    comparison_failure = text.index(
        'throw ("Template comparison failed: "',
        output_write,
    )
    metadata_write = text.index(
        "Set-Content -LiteralPath $metadataPath",
        comparison_failure,
    )
    staged_validation = text.index(
        "Assert-HplcStagedPackageComplete `",
        metadata_write,
    )
    commit = text.index(
        "Commit-HplcOutputPackage `",
        staged_validation,
    )

    assert (
        output_write
        < comparison_failure
        < metadata_write
        < staged_validation
        < commit
    )
    main_text = text[main_start:]
    assert "if ($Force) {\n    foreach ($target in $plannedOutputFiles)" not in main_text
    assert "$OutputDir = $transactionOutputDir" in main_text
    assert "'.hplc_package_stage_'" in main_text
    assert "'.hplc_package_backup_'" in main_text
    assert "transactional_package_commit = $true" in main_text


def test_hplc_calibration_origin_cleanup_targets_only_captured_owned_pids() -> None:
    text = _script_text()

    assert "function Get-OriginProcessIdsStartedByScript([int[]]$BeforePids)" in text
    assert "function Close-OriginProcessesStartedByScript([int[]]$OwnedPids)" in text
    assert "if ($stabilized.Count -eq 1) { return $stabilized }" in text
    assert "exactly one provable task-owned" in text
    close_start = text.index(
        "function Close-OriginProcessesStartedByScript([int[]]$OwnedPids)"
    )
    close_end = text.index("function Get-OriginPageRasterSpec", close_start)
    close_block = text[close_start:close_end]
    assert "Get-Process -Id @($owned.Keys)" in close_block
    assert "ProcessName -like 'Origin*'" in close_block
    assert "Get-Process -Name Origin*" not in close_block
    assert "Close-OriginProcessesStartedByScript $ownedOriginPids" in text
    assert "$originRunSucceeded = $false" in text
    assert "$CloseOrigin -or (-not $originRunSucceeded)" in text


def test_hplc_package_commit_uses_backup_postmove_validation_and_rollback() -> None:
    text = _script_text()

    commit_start = text.index("function Commit-HplcOutputPackage(")
    commit_end = text.index("function Has-AssistantTrace", commit_start)
    commit_block = text[commit_start:commit_end]
    backup_move = commit_block.index(
        "Move-Item -LiteralPath $FinalDir -Destination $BackupDir"
    )
    staged_move = commit_block.index(
        "Move-Item -LiteralPath $StagedDir -Destination $FinalDir"
    )
    postmove_validation = commit_block.index(
        "Assert-HplcStagedPackageComplete `",
        staged_move,
    )
    new_rollback = commit_block.index(
        "Move-Item -LiteralPath $FinalDir -Destination $StagedDir",
        postmove_validation,
    )
    old_restore = commit_block.index(
        "Move-Item -LiteralPath $BackupDir -Destination $FinalDir",
        new_rollback,
    )
    backup_cleanup = commit_block.index(
        "Remove-Item -LiteralPath $BackupDir -Recurse -Force",
        old_restore,
    )

    assert (
        backup_move
        < staged_move
        < postmove_validation
        < new_rollback
        < old_restore
        < backup_cleanup
    )
    assert "Assert-NoReparsePointInTree $FinalDir" in commit_block
    assert "Assert-NoReparsePointInTree $BackupDir" in commit_block
    assert "prior package was restored" in commit_block
    assert "rollback was incomplete" in commit_block


def test_hplc_staged_package_verifies_all_three_product_and_comparison_rows() -> None:
    text = _script_text()

    verify_start = text.index("function Assert-HplcStagedPackageComplete(")
    verify_end = text.index("function Commit-HplcOutputPackage(", verify_start)
    verify_block = text[verify_start:verify_end]

    assert "Assert-NoReparsePointInTree $PackageRoot" in verify_block
    assert "artifact is missing or empty" in verify_block
    assert "ConvertFrom-Json" in verify_block
    assert "@($metadataObject.figure_tif).Count -ne 3" in verify_block
    assert "@($metadataObject.preview_png).Count -ne 3" in verify_block
    assert "$comparisonRows.Count -ne 3" in verify_block
    assert "([string]$row.ExactPixelMatch) -ne 'True'" in verify_block
    assert "([string]$row.Status) -ne 'exact_pixel_match'" in verify_block


def test_hplc_calibration_rejects_project_tree_as_configured_output_root(
    tmp_path: Path,
) -> None:
    copied_script, project_root, _output_root = _copy_hplc_script_project(tmp_path)
    config = project_root / "config" / "local.yaml"
    config.parent.mkdir()
    config.write_text(
        "paths:\n  output_root: input/raw_data\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(copied_script),
            "-TemplateOpju",
            str(tmp_path / "unused.opju"),
            "-Stamp",
            "20260731_security",
            "-Force",
        ],
        cwd=project_root,
        text=True,
        capture_output=True,
        timeout=30,
    )

    combined = completed.stdout + completed.stderr
    assert completed.returncode != 0
    assert "must be independent from the project, raw-data" in combined
    assert not (project_root / "input").exists()


def test_hplc_calibration_empty_configured_output_root_fails_closed(
    tmp_path: Path,
) -> None:
    copied_script, project_root, output_root = _copy_hplc_script_project(tmp_path)
    config = project_root / "config" / "local.yaml"
    config.parent.mkdir()
    config.write_text(
        "paths:\n  output_root:\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(copied_script),
            "-TemplateOpju",
            str(tmp_path / "unused.opju"),
            "-Stamp",
            "20260731_security",
            "-Force",
        ],
        cwd=project_root,
        text=True,
        capture_output=True,
        timeout=30,
    )

    combined = completed.stdout + completed.stderr
    assert completed.returncode != 0
    assert "must have a non-empty scalar path value" in combined
    assert not output_root.exists()


def test_hplc_calibration_rejects_output_root_that_contains_template_source(
    tmp_path: Path,
) -> None:
    copied_script, project_root, _output_root = _copy_hplc_script_project(tmp_path)
    protected_source = tmp_path / "protected_source"
    template = protected_source / "templates" / "reference.opju"
    template.parent.mkdir(parents=True)
    template.write_bytes(b"reference-template")
    output_dir = protected_source / "run"
    config = project_root / "config" / "local.yaml"
    config.parent.mkdir()
    config.write_text(
        f"paths:\n  output_root: {protected_source.as_posix()}\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(copied_script),
            "-TemplateOpju",
            str(template),
            "-OutputDir",
            str(output_dir),
            "-Stamp",
            "20260731_security",
            "-Force",
        ],
        cwd=project_root,
        text=True,
        capture_output=True,
        timeout=30,
    )

    combined = completed.stdout + completed.stderr
    assert completed.returncode != 0
    assert "must be independent from the TemplateOpju source directory" in combined
    assert template.read_bytes() == b"reference-template"
    assert not output_dir.exists()


def test_hplc_calibration_script_rejects_reparse_and_same_file_aliases() -> None:
    text = _script_text()

    assert "public static bool IsReparsePoint(string path)" in text
    assert "GetFileAttributes" in text
    assert "FileAttributeReparsePoint" in text
    assert "function Assert-NoReparsePointInPath" in text
    assert "function Assert-NoReparsePointInTree" in text
    assert "function Assert-SafeOutputFileTarget" in text
    assert "function Assert-SafeOutputDirectoryTarget" in text
    assert "public static string GetFileIdentity(string path)" in text
    assert "GetFileInformationByHandle" in text
    assert "function Assert-NotSameFile" in text
    assert "Planned output is the same file as TemplateOpju" in text
    assert "foreach ($target in $plannedOutputFiles)" in text
    assert "foreach ($target in $plannedStageFiles)" in text
    assert (
        "Assert-SafeOutputFileTarget $target $OutputDir $templateOpjuPath "
        "'HPLC planned output'"
    ) in text
    assert (
        "Assert-SafeOutputFileTarget $target $stageRoot $templateOpjuPath "
        "'Origin stage file'"
    ) in text
    assert "Assert-NoReparsePointInTree $full 'Origin stage cleanup'" in text


def test_hplc_calibration_script_preflights_every_written_artifact_family() -> None:
    text = _script_text()

    plan_index = text.index("$plannedOutputFiles = @(")
    preflight_index = text.index(
        "foreach ($target in $plannedOutputFiles)",
        plan_index,
    )
    planned_block = text[plan_index:preflight_index]
    for expected in (
        "$outputOpju",
        "$comparisonReport",
        "$metadataPath",
        "$script:LogPath",
        "final_calibration_data.tsv",
        "_plot_data.tsv",
        "$previewDir",
        "$tifDir",
        "$templateOriginalPreviewDir",
        "$templateOriginalTifDir",
        "$templatePreviewDir",
        "$templateTifDir",
    ):
        assert expected in planned_block
    assert "$plannedStageFiles = @($workingTemplate)" in text
    assert ".otpu" in text[text.index("$plannedStageFiles = @($workingTemplate)"):preflight_index]


@pytest.mark.skipif(os.name != "nt", reason="Windows file identity is required")
def test_hplc_calibration_force_rejects_hardlink_alias_to_template(
    tmp_path: Path,
) -> None:
    copied_script, project_root, output_root = _copy_hplc_script_project(tmp_path)
    template = tmp_path / "template_source" / "template.opju"
    template.parent.mkdir()
    template.write_bytes(b"template-must-remain-byte-identical")
    output_dir = output_root / "hardlink-run"
    planned_opju = (
        output_dir
        / "origin_files"
        / "HPLC_calibration_curves_20260731_security.opju"
    )
    planned_opju.parent.mkdir(parents=True)
    os.link(template, planned_opju)
    template_before = template.read_bytes()

    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(copied_script),
            "-TemplateOpju",
            str(template),
            "-OutputDir",
            str(output_dir),
            "-Stamp",
            "20260731_security",
            "-Force",
        ],
        cwd=project_root,
        text=True,
        capture_output=True,
        timeout=30,
    )

    combined = completed.stdout + completed.stderr
    assert completed.returncode != 0
    assert "same file as TemplateOpju" in combined
    assert template.read_bytes() == template_before
    assert planned_opju.read_bytes() == template_before
    assert not (output_dir / "processed_data").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows junction behavior is required")
def test_hplc_calibration_rejects_junction_output_before_writes(
    tmp_path: Path,
) -> None:
    copied_script, project_root, output_root = _copy_hplc_script_project(tmp_path)
    output_root.mkdir()
    external_target = tmp_path / "external-target"
    external_target.mkdir()
    sentinel = external_target / "sentinel.bin"
    sentinel.write_bytes(b"external-must-remain-untouched")
    output_dir = output_root / "junction-run"
    junction = subprocess.run(
        [
            "cmd.exe",
            "/d",
            "/c",
            "mklink",
            "/J",
            str(output_dir),
            str(external_target),
        ],
        text=True,
        capture_output=True,
        timeout=10,
    )
    if junction.returncode != 0:
        pytest.skip("creating a Windows junction is unavailable")

    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(copied_script),
            "-TemplateOpju",
            str(tmp_path / "unused.opju"),
            "-OutputDir",
            str(output_dir),
            "-Stamp",
            "20260731_security",
            "-Force",
        ],
        cwd=project_root,
        text=True,
        capture_output=True,
        timeout=30,
    )

    combined = completed.stdout + completed.stderr
    assert completed.returncode != 0
    assert "symbolic link, junction, or reparse point" in combined
    assert sentinel.read_bytes() == b"external-must-remain-untouched"
    assert list(external_target.iterdir()) == [sentinel]


def test_hplc_calibration_rejects_stamp_path_escape_before_writes(
    tmp_path: Path,
) -> None:
    copied_script, project_root, output_root = _copy_hplc_script_project(tmp_path)
    output_dir = output_root / "stamp-run"

    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(copied_script),
            "-TemplateOpju",
            str(tmp_path / "unused.opju"),
            "-OutputDir",
            str(output_dir),
            "-Stamp",
            r"..\escape",
            "-Force",
        ],
        cwd=project_root,
        text=True,
        capture_output=True,
        timeout=30,
    )

    combined = completed.stdout + completed.stderr
    assert completed.returncode != 0
    assert "Stamp must be one safe filename component" in combined
    assert not output_dir.exists()


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
    assert "tr1.Unit:=2" in text
    assert "tr1.Width:=" in text
    assert "sysopts:=0" in text
    assert "tr.Margin:=2" in text
    assert "tr2.TIF.dotsperinch:=" in text
    assert "Assert-TifPhysicalResolution" in text
    assert "effective physical DPI" in text
    assert "TIF_DPI_EVIDENCE=" in text
    assert "To-RunRelativePath $templateOriginalPreviewMap" in text
    assert "To-RunRelativePath $templatePreviewMap" in text
    assert "To-RunRelativePath $generatedPreviewMap" in text
    assert "function Normalize-TifDpi" not in text
    assert ".SetResolution(" not in text
    assert "$graphics.DrawImage($source" not in text
    assert ".tmp.tif" not in text
    assert "sensitive local-path or tool-trace metadata" in text
    assert "tif_resolution_evidence" in text
    assert "calibration_fit" in text
    assert "sha256_before" in text
    assert "sha256_after" in text
    assert "function Reset-ProjectIdentityForArtifactExport" in text
    assert "doc -rn; doc -s;" in text
    assert "$App.LTStr('%X')" in text
    assert "$App.LTStr('%G')" in text


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
    assert "LegendLeft=1585; LegendTop=880; LegendWidth=2429; LegendHeight=826" in text
    assert "LegendLeft=1740; LegendTop=808; LegendWidth=2308; LegendHeight=826" in text
    assert "LegendLeft=1578; LegendTop=850; LegendWidth=2457; LegendHeight=760" in text
    assert "XTitleLeft=1927; XTitleTop=4487; XTitleWidth=2835; XTitleHeight=338" in text
    assert "YTitleLeft=362; YTitleTop=736; YTitleWidth=384; YTitleHeight=3204" in text
    assert "YTitleLeft=413; YTitleTop=736; YTitleWidth=384; YTitleHeight=3204" in text
    assert "layer.y.showLabels=1" in text


def test_hplc_final_exports_are_read_back_from_the_reopened_opju() -> None:
    text = _script_text()

    save_index = text.index("$app.Save($outputOpju)")
    reopen_new_index = text.index("$app.NewProject()", save_index)
    reopen_load_index = text.index("$app.Load($outputOpju)", reopen_new_index)
    identity_reset_index = text.index(
        "Reset-ProjectIdentityForArtifactExport $app",
        reopen_load_index,
    )
    page_check_index = text.index("Assert-HplcGraphExists $app $s.Page", reopen_load_index)
    preview_export_index = text.index(
        "$generatedPreviewMap[$s.Page] = Export-GraphPng",
        page_check_index,
    )
    tif_export_index = text.index(
        "$generatedTifMap[$s.Page] = Export-GraphTif",
        preview_export_index,
    )

    assert (
        save_index
        < reopen_new_index
        < reopen_load_index
        < identity_reset_index
        < page_check_index
        < preview_export_index
        < tif_export_index
    )
    assert "$App.LTStr('page.name$')" in text
    assert "ReopenedFinalOpju=" in text


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
