from __future__ import annotations

import json
import os
import zipfile
from datetime import date
from pathlib import Path

import pytest

import src.core.file_utils as file_utils
from src.cli import build_parser
from src.core.hplc_openlab import (
    HplcOpenLabExportOptions,
    IDENTITY_BOUNDARY,
    _build_workbook_plan,
    _date_from_filename,
    _parse_result_set_context,
    _parse_rx_result,
    _planned_preview_directories,
    _planned_workbook_paths,
    _preflight_hplc_outputs,
    _resolve_acquisition_datetime,
    run_hplc_openlab_export,
)
from src.core.process import _manifest_auxiliary_skip_reason
from src.scanner.scanner import scan_raw_data


def test_result_set_and_vendor_peak_xml_are_joined_without_identity_assignment(tmp_path: Path):
    result_set = tmp_path / "synthetic.rslt"
    result_set.mkdir()
    (result_set / "synthetic.acaml").write_text(
        """
        <Root>
          <InjectionMetaData RawDataFileName="2026-07-18 12-00-00.dx"
              SampleSetupId="setup-1" SampleName="sample-A" VialNumber="1">
            <SampleOrderNumber val="7" />
          </InjectionMetaData>
          <Setup id="setup-1">
            <Name>sample-A</Name>
            <VialNumber>1</VialNumber>
            <InjectionVolume val="5.0" />
          </Setup>
          <Signal id="signal-1">
            <Name>VWD1 A</Name>
            <Description>VWD1 A, Wavelength=254 nm</Description>
            <Type>Chromatogram</Type>
            <TraceID>Signal179</TraceID>
            <DetectorName>VWD</DetectorName>
          </Signal>
          <Method><Name>processing.pmx</Name></Method>
          <Module>
            <Type>VWD</Type><PartNo>G7114A</PartNo><SerialNo>DEMO1</SerialNo>
          </Module>
        </Root>
        """,
        encoding="utf-8",
    )
    rx_path = result_set / "2026-07-18 12-00-00.rx"
    rx_xml = """
      <Root>
        <Result>
          <TransformationChainState>Processed</TransformationChainState>
          <SignalResult>
            <Signal_ID id="signal-1" />
            <Peak>
              <RetentionTime val="3.25" unit="min" />
              <BeginTime val="3.10" unit="min" />
              <EndTime val="3.40" unit="min" />
              <WidthBase val="0.30" unit="min" />
              <Area val="1234.5" unit="mAU*s" />
              <AreaPercent val="100.0" unit="%" />
              <Height val="88.2" unit="mAU" />
              <HeightPercent val="100.0" unit="%" />
              <Symmetry val="1.05" />
              <Type>BB</Type>
              <BaselineCode>BB</BaselineCode>
            </Peak>
          </SignalResult>
          <ProcessingStatusItem>
            <Category>Integration</Category>
            <TransformationState>Completed</TransformationState>
            <Message>Vendor result retained</Message>
          </ProcessingStatusItem>
        </Result>
      </Root>
    """
    with zipfile.ZipFile(rx_path, "w") as archive:
        archive.writestr("Base/InjectionACAML", rx_xml)

    context = _parse_result_set_context(result_set)
    result = _parse_rx_result(rx_path, context)

    assert context["injections_by_raw_file"]["2026-07-18 12-00-00.dx"]["SampleOrderNumber"] == "7"
    assert context["sample_setups"]["setup-1"]["injection_volume_ul"] == 5.0
    assert context["processing_method"] == "processing.pmx"
    assert context["instrument_modules"] == "VWD/G7114A/DEMO1"
    assert result["state"] == "Processed"
    assert len(result["peaks"]) == 1
    assert result["peaks"][0]["retention_time_min"] == 3.25
    assert result["peaks"][0]["area"] == 1234.5
    assert result["peaks"][0]["signal_name"] == "VWD1 A"
    assert result["peaks"][0]["identity_assignment"] == IDENTITY_BOUNDARY
    assert result["peaks"][0]["manual_check_required"] is True
    assert "Vendor result retained" in result["warning"]


def test_missing_rx_is_recorded_without_inventing_peaks(tmp_path: Path):
    result = _parse_rx_result(tmp_path / "missing.rx", {"signals": {}})

    assert result == {
        "peaks": [],
        "state": "missing_rx",
        "warning": "配套 .rx 结果文件缺失",
    }


def test_openlab_cli_accepts_inclusive_iso_date_contract(tmp_path: Path):
    args = build_parser().parse_args(
        [
            "hplc-openlab-export",
            "--input",
            str(tmp_path / "raw"),
            "--since",
            "2026-07-18",
            "--output-root",
            str(tmp_path / "output"),
            "--node-exe",
            str(tmp_path / "node.exe"),
            "--builder-workdir",
            str(tmp_path / "output" / ".artifact_work"),
        ]
    )

    assert args.command == "hplc-openlab-export"
    assert args.since == date(2026, 7, 18)


def test_result_set_injection_time_is_converted_to_dx_local_offset():
    acquisition, source = _resolve_acquisition_datetime(
        raw_metadata={"date": "2026-07-18T15:31:54+08:00"},
        raw_file_info={"InjectionAcqDateTime": "2026-07-18T07:53:13.290Z"},
    )

    assert acquisition.isoformat(timespec="seconds") == "2026-07-18T15:53:13+08:00"
    assert source == "result_set_acaml.InjectionMetaData.InjectionAcqDateTime"


def test_scanner_classifies_openlab_files_when_lc_folder_is_the_scan_root(tmp_path: Path):
    raw_root = tmp_path / "旧液相全"
    result_set = raw_root / "batch" / "sample.rslt"
    result_set.mkdir(parents=True)
    for name in ("sample.dx", "sample.rx", "sample.acaml"):
        (result_set / name).write_bytes(b"fixture")

    project_root = Path(__file__).resolve().parents[1]
    manifest = scan_raw_data(project_root, raw_root, output_root=tmp_path / "out")
    classification = next(
        item for item in manifest["classifications"] if item["id"] == "lc_openlab_raw"
    )

    assert classification["physical_presence"] == "present"
    assert classification["selected_processor"] == "hplc_openlab_raw_exporter"
    assert len(classification["files"]) == 3


def test_generic_process_records_raw_openlab_components_as_dedicated_command_items():
    classification = {
        "supported_in_pipeline": True,
        "special_handling": "dedicated_hplc_openlab_export_command",
        "inferred_data_type": "HPLC/LC OpenLab raw data",
    }

    assert (
        _manifest_auxiliary_skip_reason(classification, Path("sample.dx"))
        == "dedicated_command_required"
    )


def test_generic_process_does_not_send_unimplemented_native_spectra_to_table_reader():
    for data_type, suffix in (
        ("EPR", ".dta"),
        ("EPR", ".spc"),
        ("FTIR", ".spc"),
        ("Raman", ".spc"),
    ):
        classification = {
            "supported_in_pipeline": True,
            "special_handling": "process_when_present_manual_check",
            "inferred_data_type": data_type,
        }

        assert (
            _manifest_auxiliary_skip_reason(classification, Path(f"sample{suffix}"))
            == "native_reader_not_implemented"
        )


def test_filename_date_helper_is_only_a_hint_and_parses_openlab_names():
    assert _date_from_filename("2026-07-18 12-00-00.dx") == date(2026, 7, 18)
    assert _date_from_filename("sample.dx") is None


def test_workbook_plan_splits_by_top_level_batch_and_keeps_raw_points_out_of_excel(
    tmp_path: Path,
):
    dataset = {
        "injections": [
            {"injection_id": "I001", "batch_folder": "20260718:批次/A"},
            {"injection_id": "I002", "batch_folder": "20260718:批次/A"},
            {"injection_id": "I003", "batch_folder": "20260722过夜"},
        ],
        "result_sets": [
            {"result_set_id": "R01", "batch_folder": "20260718:批次/A"},
            {"result_set_id": "R02", "batch_folder": "20260722过夜"},
        ],
    }
    output_root = tmp_path / "output"
    summary = output_root / "安捷伦液相汇总.xlsx"

    plan = _build_workbook_plan(dataset, summary)
    paths = _planned_workbook_paths(output_root, summary, plan)

    assert plan["summary_workbook"] == "安捷伦液相汇总.xlsx"
    assert plan["excel_includes_raw_signals"] is False
    assert len(plan["batch_workbooks"]) == 2
    assert plan["batch_workbooks"][0]["result_set_ids"] == ["R01"]
    assert plan["batch_workbooks"][0]["injection_ids"] == ["I001", "I002"]
    assert ":" not in plan["batch_workbooks"][0]["filename"]
    assert "/" not in plan["batch_workbooks"][0]["filename"]
    assert paths[0] == summary.resolve()
    assert all(path.suffix == ".xlsx" for path in paths)
    assert all(path == output_root.resolve() or output_root.resolve() in path.parents for path in paths)


def test_openlab_export_preflights_all_outputs_before_writing_and_force_overwrites(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = Path(__file__).resolve().parents[1]
    input_root = tmp_path / "raw"
    input_root.mkdir()
    output_root = tmp_path / "output"
    builder_workdir = output_root / ".artifact_work"
    (builder_workdir / "node_modules" / "@oai" / "artifact-tool").mkdir(
        parents=True
    )
    node_exe = tmp_path / "node.exe"
    node_exe.write_bytes(b"node")
    since = date(2026, 7, 18)
    slug = "hplc_openlab_20260718_plus"
    existing_metadata = output_root / "metadata" / slug / "metadata.json"
    existing_metadata.parent.mkdir(parents=True)
    existing_metadata.write_bytes(b"preserve")
    dataset = _minimal_openlab_run_dataset(since)
    monkeypatch.setattr(
        "src.core.hplc_openlab.extract_hplc_openlab_dataset",
        lambda *_args, **_kwargs: json.loads(json.dumps(dataset)),
    )
    options = HplcOpenLabExportOptions(
        input_root=input_root,
        since=since,
        output_root=output_root,
        node_exe=node_exe,
        builder_workdir=builder_workdir,
        force=False,
    )

    with pytest.raises(FileExistsError, match="--force"):
        run_hplc_openlab_export(project_root, options)

    assert existing_metadata.read_bytes() == b"preserve"
    assert not (
        output_root / "processed_data" / f"{slug}_dataset.json"
    ).exists()
    assert not (output_root / "agilent_hplc_openlab_20260718_plus.xlsx").exists()
    assert not (builder_workdir / "build_openlab_workbook.mjs").exists()

    def fake_builder(**kwargs) -> None:
        _write_complete_fake_openlab_package(kwargs)

    monkeypatch.setattr(
        "src.core.hplc_openlab._run_workbook_builder",
        fake_builder,
    )
    result = run_hplc_openlab_export(
        project_root,
        HplcOpenLabExportOptions(**{**options.__dict__, "force": True}),
    )

    metadata = json.loads(result["metadata"].read_text(encoding="utf-8"))
    assert metadata["processing_status"] == "processed_to_split_excel_no_plot"
    assert all(zipfile.is_zipfile(path) for path in result["workbooks"])


def test_openlab_export_rejects_output_inside_raw_input_before_writing(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[1]
    input_root = tmp_path / "raw"
    input_root.mkdir()
    output_root = input_root / "output"

    with pytest.raises(ValueError, match="overlaps protected input"):
        run_hplc_openlab_export(
            project_root,
            HplcOpenLabExportOptions(
                input_root=input_root,
                since=date(2026, 7, 18),
                output_root=output_root,
                node_exe=tmp_path / "node.exe",
                builder_workdir=output_root / ".artifact_work",
            ),
        )

    assert not output_root.exists()


def test_openlab_force_preflight_validates_without_deleting_declared_outputs(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "output"
    builder_copy = output_root / ".artifact_work" / "build_openlab_workbook.mjs"
    builder_copy.parent.mkdir(parents=True)
    builder_copy.write_bytes(b"builder")
    preview_dir = output_root / "workbook_previews" / "00_总索引"
    preview_dir.mkdir(parents=True)
    preview = preview_dir / "01_使用说明.png"
    preview.write_bytes(b"preview")
    unrelated = output_root / "workbook_previews" / "other-run" / "keep.png"
    unrelated.parent.mkdir(parents=True)
    unrelated.write_bytes(b"keep")

    with pytest.raises(FileExistsError, match="--force"):
        _preflight_hplc_outputs(
            output_root,
            file_targets=(builder_copy,),
            owned_directory_targets=(preview_dir,),
            force=False,
        )

    assert builder_copy.read_bytes() == b"builder"
    assert preview.read_bytes() == b"preview"
    _preflight_hplc_outputs(
        output_root,
        file_targets=(builder_copy,),
        owned_directory_targets=(preview_dir,),
        force=True,
    )

    assert builder_copy.read_bytes() == b"builder"
    assert preview.read_bytes() == b"preview"
    assert unrelated.read_bytes() == b"keep"


def test_openlab_force_rejects_reparse_target_without_deleting_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_root = tmp_path / "output"
    target = output_root / "metadata" / "metadata.json"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"preserve")
    target_key = file_utils.lexical_absolute_path(target)
    original_check = file_utils._path_is_link_or_reparse
    monkeypatch.setattr(
        file_utils,
        "_path_is_link_or_reparse",
        lambda path: file_utils.lexical_absolute_path(path) == target_key
        or original_check(path),
    )

    with pytest.raises(ValueError, match="symlink, junction, or reparse"):
        _preflight_hplc_outputs(
            output_root,
            file_targets=(target,),
            owned_directory_targets=(),
            force=True,
        )

    assert target.read_bytes() == b"preserve"


def test_openlab_force_validates_entire_preview_tree_before_any_deletion(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_root = tmp_path / "output"
    file_target = output_root / "metadata" / "metadata.json"
    file_target.parent.mkdir(parents=True)
    file_target.write_bytes(b"preserve-file")
    preview_dir = output_root / "workbook_previews" / "owned"
    preview_dir.mkdir(parents=True)
    preview = preview_dir / "preview.png"
    preview.write_bytes(b"preserve-preview")
    preview_key = file_utils.lexical_absolute_path(preview)
    original_check = file_utils._path_is_link_or_reparse
    monkeypatch.setattr(
        file_utils,
        "_path_is_link_or_reparse",
        lambda path: file_utils.lexical_absolute_path(path) == preview_key
        or original_check(path),
    )

    with pytest.raises(ValueError, match="symlink, junction, or reparse"):
        _preflight_hplc_outputs(
            output_root,
            file_targets=(file_target,),
            owned_directory_targets=(preview_dir,),
            force=True,
        )

    assert file_target.read_bytes() == b"preserve-file"
    assert preview.read_bytes() == b"preserve-preview"


def test_openlab_force_rejects_hardlinked_package_file_without_deleting_it(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "output"
    target = output_root / "reports" / "summary.md"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"preserve-hardlink")
    alias = tmp_path / "summary-alias.md"
    try:
        os.link(target, alias)
    except OSError as exc:
        pytest.skip(f"Hard links are unavailable on this filesystem: {exc}")

    with pytest.raises(ValueError, match="multiple hard links"):
        _preflight_hplc_outputs(
            output_root,
            file_targets=(target,),
            owned_directory_targets=(),
            force=True,
        )

    assert target.read_bytes() == b"preserve-hardlink"
    assert alias.read_bytes() == b"preserve-hardlink"


def test_openlab_force_builder_failure_preserves_old_package_byte_for_byte(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = _openlab_transaction_case(tmp_path)
    _seed_old_openlab_package(case)
    before = _snapshot_files(case["output_root"])
    monkeypatch.setattr(
        "src.core.hplc_openlab.extract_hplc_openlab_dataset",
        lambda *_args, **_kwargs: json.loads(json.dumps(case["dataset"])),
    )

    def failing_builder(**kwargs) -> None:
        kwargs["workbook_path"].parent.mkdir(parents=True, exist_ok=True)
        kwargs["workbook_path"].write_bytes(b"partial-new-workbook")
        raise RuntimeError("injected builder failure")

    monkeypatch.setattr(
        "src.core.hplc_openlab._run_workbook_builder",
        failing_builder,
    )

    with pytest.raises(RuntimeError, match="injected builder failure"):
        run_hplc_openlab_export(
            case["project_root"],
            case["options"],
        )

    assert _snapshot_files(case["output_root"]) == before
    _assert_no_openlab_transaction_directories(case)


def test_openlab_force_invalid_staged_verification_preserves_old_package(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = _openlab_transaction_case(tmp_path)
    _seed_old_openlab_package(case)
    before = _snapshot_files(case["output_root"])
    monkeypatch.setattr(
        "src.core.hplc_openlab.extract_hplc_openlab_dataset",
        lambda *_args, **_kwargs: json.loads(json.dumps(case["dataset"])),
    )

    def invalid_builder(**kwargs) -> None:
        _write_complete_fake_openlab_package(kwargs)
        kwargs["verification_path"].write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        "src.core.hplc_openlab._run_workbook_builder",
        invalid_builder,
    )

    with pytest.raises(RuntimeError, match="verification"):
        run_hplc_openlab_export(
            case["project_root"],
            case["options"],
        )

    assert _snapshot_files(case["output_root"]) == before
    _assert_no_openlab_transaction_directories(case)


def test_openlab_force_commit_failure_rolls_back_whole_old_package(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = _openlab_transaction_case(tmp_path)
    _seed_old_openlab_package(case)
    before = _snapshot_files(case["output_root"])
    monkeypatch.setattr(
        "src.core.hplc_openlab.extract_hplc_openlab_dataset",
        lambda *_args, **_kwargs: json.loads(json.dumps(case["dataset"])),
    )
    monkeypatch.setattr(
        "src.core.hplc_openlab._run_workbook_builder",
        lambda **kwargs: _write_complete_fake_openlab_package(kwargs),
    )
    real_replace = os.replace
    failure_injected = False

    def flaky_replace(source: Path, target: Path) -> None:
        nonlocal failure_injected
        source_path = Path(source)
        target_path = Path(target)
        if (
            not failure_injected
            and "payload" in source_path.parts
            and target_path == case["dataset_path"]
        ):
            failure_injected = True
            raise OSError("injected commit failure")
        real_replace(source_path, target_path)

    monkeypatch.setattr(
        "src.core.hplc_openlab._atomic_replace",
        flaky_replace,
    )

    with pytest.raises(RuntimeError, match="previous package was restored"):
        run_hplc_openlab_export(
            case["project_root"],
            case["options"],
        )

    assert failure_injected is True
    assert _snapshot_files(case["output_root"]) == before
    _assert_no_openlab_transaction_directories(case)


def test_workbook_builder_contract_is_plain_bordered_and_omits_raw_signal_sheets():
    project_root = Path(__file__).resolve().parents[1]
    builder = (
        project_root
        / "scripts"
        / "data_types"
        / "hplc_lc"
        / "build_openlab_workbook.mjs"
    ).read_text(encoding="utf-8")

    assert 'borders: { preset: "all", style: "thin", color: COLORS.border }' in builder
    assert "TableStyleMedium" not in builder
    assert "dataset.raw_sheets" not in builder
    assert 'workbook.worksheets.add("样品信息")' in builder
    assert "`${resultSet.result_set_id}_峰面积`" in builder
    assert '"采集方法",' not in builder
    assert '"处理方法",' not in builder
    assert '"方法",' in builder
    assert '"峰序号",' in builder
    assert '"出峰时间(min)",' in builder
    assert "const peakRows = resultSetInjections.map" in builder
    assert '.join("\\n")' in builder


def _minimal_openlab_run_dataset(since: date) -> dict:
    return {
        "data_type": "HPLC/LC OpenLab raw data",
        "processor_name": "hplc_openlab_raw_exporter",
        "source_root_name": "raw",
        "cutoff_date": since.isoformat(),
        "injections": [
            {
                "injection_id": "I001",
                "batch_folder": "batch-one",
            }
        ],
        "result_sets": [
            {
                "result_set_id": "R01",
                "batch_folder": "batch-one",
            }
        ],
        "scientific_boundary": {"forbidden_outputs": []},
        "library_provenance": {},
        "summary": {
            "cutoff_date": since.isoformat(),
            "selected_injection_count": 1,
            "result_set_count": 1,
            "batch_count": 1,
            "peak_count": 0,
            "signal_point_count": 2,
        },
    }


def _write_minimal_xlsx(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?><Types/>',
        )
        archive.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8"?><workbook/>',
        )


def _write_complete_fake_openlab_package(kwargs: dict) -> None:
    payload = json.loads(kwargs["dataset_path"].read_text(encoding="utf-8"))
    staged_output_root = kwargs["workbook_path"].parent
    workbook_paths = _planned_workbook_paths(
        staged_output_root,
        kwargs["workbook_path"],
        payload["workbook_plan"],
    )
    preview_directories = _planned_preview_directories(
        kwargs["previews_dir"],
        payload["workbook_plan"],
    )
    verification_workbooks = []
    for index, (workbook, preview_directory) in enumerate(
        zip(workbook_paths, preview_directories, strict=True),
        start=1,
    ):
        _write_minimal_xlsx(workbook)
        preview_directory.mkdir(parents=True, exist_ok=True)
        preview = preview_directory / f"01_preview_{index}.png"
        preview.write_bytes(b"\x89PNG\r\n\x1a\nfake-preview")
        verification_workbooks.append(
            {
                "path": str(workbook.resolve()),
                "sheet_count": 1,
                "preview_files": [str(preview.resolve())],
            }
        )

    kwargs["verification_path"].parent.mkdir(parents=True, exist_ok=True)
    kwargs["verification_path"].write_text(
        json.dumps(
            {
                "workbooks": verification_workbooks,
                "workbook_count": len(verification_workbooks),
                "sheet_count": len(verification_workbooks),
                "preview_count": len(verification_workbooks),
            }
        ),
        encoding="utf-8",
    )
    kwargs["log_path"].parent.mkdir(parents=True, exist_ok=True)
    kwargs["log_path"].write_text(
        f"exit_code=0\nworkbook={kwargs['workbook_path'].resolve()}",
        encoding="utf-8",
    )


def _openlab_transaction_case(tmp_path: Path) -> dict:
    project_root = Path(__file__).resolve().parents[1]
    input_root = tmp_path / "raw"
    input_root.mkdir()
    output_root = tmp_path / "output"
    builder_workdir = output_root / ".artifact_work"
    (builder_workdir / "node_modules" / "@oai" / "artifact-tool").mkdir(
        parents=True
    )
    node_exe = tmp_path / "node.exe"
    node_exe.write_bytes(b"node")
    since = date(2026, 7, 18)
    slug = "hplc_openlab_20260718_plus"
    dataset = _minimal_openlab_run_dataset(since)
    workbook_path = output_root / "agilent_hplc_openlab_20260718_plus.xlsx"
    workbook_plan = _build_workbook_plan(dataset, workbook_path)
    workbook_paths = _planned_workbook_paths(
        output_root,
        workbook_path,
        workbook_plan,
    )
    preview_targets = _planned_preview_directories(
        output_root / "workbook_previews",
        workbook_plan,
    )
    dataset_path = output_root / "processed_data" / f"{slug}_dataset.json"
    file_targets = (
        *workbook_paths,
        dataset_path,
        output_root / "reports" / f"{slug}_workbook_verification.json",
        output_root / "logs" / f"{slug}_workbook_builder.log",
        output_root / "metadata" / slug / "metadata.json",
        output_root / "reports" / f"{slug}_processing_summary.md",
    )
    return {
        "project_root": project_root,
        "input_root": input_root,
        "output_root": output_root,
        "builder_workdir": builder_workdir,
        "slug": slug,
        "dataset": dataset,
        "dataset_path": dataset_path,
        "file_targets": file_targets,
        "preview_targets": preview_targets,
        "options": HplcOpenLabExportOptions(
            input_root=input_root,
            since=since,
            output_root=output_root,
            node_exe=node_exe,
            builder_workdir=builder_workdir,
            force=True,
        ),
    }


def _seed_old_openlab_package(case: dict) -> None:
    output_root = case["output_root"]
    for index, path in enumerate(case["file_targets"], start=1):
        path.parent.mkdir(parents=True, exist_ok=True)
        relative = path.relative_to(output_root).as_posix()
        path.write_bytes(f"old-file-{index}:{relative}".encode("utf-8"))
    for index, directory in enumerate(case["preview_targets"], start=1):
        directory.mkdir(parents=True, exist_ok=True)
        preview = directory / "old-preview.png"
        preview.write_bytes(f"old-preview-{index}".encode("utf-8"))


def _snapshot_files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"), key=lambda item: str(item).casefold())
        if path.is_file()
    }


def _assert_no_openlab_transaction_directories(case: dict) -> None:
    slug = case["slug"]
    assert not list(case["output_root"].glob(f".{slug}.staging-*"))
    assert not list(case["builder_workdir"].glob(f".{slug}.builder-*"))
