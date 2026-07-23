from __future__ import annotations

import zipfile
from datetime import date
from pathlib import Path

from src.cli import build_parser
from src.core.hplc_openlab import (
    IDENTITY_BOUNDARY,
    _build_workbook_plan,
    _date_from_filename,
    _parse_result_set_context,
    _parse_rx_result,
    _planned_workbook_paths,
    _resolve_acquisition_datetime,
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
