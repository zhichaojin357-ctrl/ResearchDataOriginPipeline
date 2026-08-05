from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree as ET

import pytest

from src.core.hplc_openlab import HplcOpenLabExportOptions, _resolved_vendor_options
from src.core.hplc_openlab_vendor import (
    VENDOR_RESULT_ORIGIN,
    _REQUIRED_RUNTIME_FILES,
    _write_single_injection_acaml,
    apply_vendor_reprocess_provenance,
    compare_vendor_peak_datasets,
    reprocess_openlab_with_vendor_method,
)


def _acaml() -> str:
    return """
    <ACAML>
      <Doc><DocInfo><CustomField><Xml><ArrayOfInjectionMetaData>
        <InjectionMetaData RawDataFileName="one.dx" InjectionId="guid-1"
            SampleSetupId="setup-1" DaMethodName="" />
        <InjectionMetaData RawDataFileName="two.dx" InjectionId="guid-2"
            SampleSetupId="setup-2" DaMethodName="" />
      </ArrayOfInjectionMetaData></Xml></CustomField></DocInfo>
      <Content>
        <Resources />
        <Method><Name>old-method</Name></Method>
        <SampleContexts>
          <Setup id="context-setup">
            <SampleSetup_ID id="setup-1" /><SampleSetup_ID id="setup-2" />
          </Setup>
          <MeasData id="context-meas">
            <SampleMeasData_ID id="sample-meas-1" />
            <SampleMeasData_ID id="sample-meas-2" />
          </MeasData>
        </SampleContexts>
        <Samples>
          <Setup id="setup-1" /><Setup id="setup-2" />
          <MeasData id="sample-meas-1"><InjectionMeasData_ID id="guid-1" /></MeasData>
          <MeasData id="sample-meas-2"><InjectionMeasData_ID id="guid-2" /></MeasData>
        </Samples>
        <Injections>
          <MeasData id="guid-1" /><MeasData id="guid-2" />
        </Injections>
        <Actions />
      </Content></Doc>
    </ACAML>
    """


def _local(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def test_single_injection_acaml_keeps_only_the_requested_relationship_closure(
    tmp_path: Path,
) -> None:
    source = tmp_path / "sequence.acaml"
    target = tmp_path / "single.acaml"
    source.write_text(_acaml(), encoding="utf-8")

    details = _write_single_injection_acaml(
        source=source,
        target=target,
        raw_file="two.dx",
        injection_guid="guid-2",
        method_name="GC_LC_DefaultMethod",
    )

    root = ET.parse(target).getroot()
    metadata = [item for item in root.iter() if _local(item) == "InjectionMetaData"]
    setups = [
        item
        for item in root.iter()
        if _local(item) == "Samples"
        for item in list(item)
        if _local(item) == "Setup"
    ]
    injection_rows = [
        item
        for item in root.iter()
        if _local(item) == "Injections"
        for item in list(item)
        if _local(item) == "MeasData"
    ]

    assert [(item.get("RawDataFileName"), item.get("DaMethodName")) for item in metadata] == [
        ("two.dx", "GC_LC_DefaultMethod")
    ]
    assert [item.get("id") for item in setups] == ["setup-2"]
    assert [item.get("id") for item in injection_rows] == ["guid-2"]
    assert details["sample_setup_id"] == "setup-2"
    assert details["sample_meas_data_id"] == "sample-meas-2"


def test_vendor_options_use_bundled_assets_or_explicit_all_or_none_overrides(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = dict(
        input_root=tmp_path / "raw",
        since=__import__("datetime").date(2026, 7, 18),
        output_root=tmp_path / "out",
        node_exe=tmp_path / "node.exe",
        builder_workdir=tmp_path / "out" / ".artifact",
    )
    runtime_bin = tmp_path / "bundled" / "Bin"
    bridge = runtime_bin / "OpenLabVendorBridge.exe"
    method = tmp_path / "bundled" / "Methods" / "default.pmx"
    monkeypatch.setattr(
        "src.core.hplc_openlab.resolve_bundled_openlab_vendor_assets",
        lambda: SimpleNamespace(
            runtime_bin=runtime_bin,
            bridge_exe=bridge,
            processing_method=method,
        ),
    )

    assert _resolved_vendor_options(
        HplcOpenLabExportOptions(**base, vendor_reprocess=True)
    ) == (runtime_bin, bridge, method)
    explicit = (
        tmp_path / "runtime",
        tmp_path / "runtime" / "bridge.exe",
        tmp_path / "method.pmx",
    )
    assert _resolved_vendor_options(
        HplcOpenLabExportOptions(
            **base,
            vendor_reprocess=True,
            vendor_runtime_bin=explicit[0],
            vendor_bridge_exe=explicit[1],
            vendor_processing_method=explicit[2],
        )
    ) == tuple(path.resolve() for path in explicit)
    with pytest.raises(ValueError, match="overrides must provide"):
        _resolved_vendor_options(
            HplcOpenLabExportOptions(
                **base,
                vendor_reprocess=True,
                vendor_runtime_bin=tmp_path / "runtime",
            )
        )
    with pytest.raises(ValueError, match="require --vendor-reprocess"):
        _resolved_vendor_options(
            HplcOpenLabExportOptions(**base, vendor_runtime_bin=tmp_path / "runtime")
        )
    with pytest.raises(ValueError, match="greater than zero"):
        _resolved_vendor_options(
            HplcOpenLabExportOptions(
                **base,
                vendor_reprocess=True,
                vendor_timeout_seconds=0,
            )
        )


def test_vendor_peak_comparison_uses_normalized_signal_ordinals() -> None:
    injection = {
        "injection_id": "I001",
        "source_relative": "batch/sample.rslt/I001.dx",
    }
    common = {
        "injection_id": "I001",
        "signal_name": "VWD1A",
        "begin_time_min": 1.0,
        "end_time_min": 1.2,
        "width_base_min": 0.2,
        "area_percent": 100.0,
        "height": 4.0,
        "height_percent": 100.0,
        "symmetry": 1.0,
        "baseline_start": 0.0,
        "baseline_end": 0.0,
        "baseline_model": "Linear",
        "baseline_code": "BB",
        "peak_type": "BB",
        "area_unit": "mAU*s",
        "height_unit": "mAU",
        "purity_passed": None,
        "ms_purity_passed": None,
    }
    reference = {
        "injections": [injection],
        "peaks": [
            {**common, "peak_ordinal": 1, "retention_time_min": 1.1, "area": 12.0},
            {**common, "peak_ordinal": 2, "retention_time_min": 2.1, "area": 25.0},
        ],
    }
    candidate = json.loads(json.dumps(reference))

    comparison = compare_vendor_peak_datasets(reference, candidate)

    assert comparison["peak_identity_exact"] is True
    assert comparison["all_compared_fields_bit_exact"] is True
    assert all(value == 0.0 for value in comparison["maximum_absolute_difference"].values())

    candidate["peaks"][1]["area"] = 25.5
    changed = compare_vendor_peak_datasets(reference, candidate)
    assert changed["peak_identity_exact"] is True
    assert changed["all_compared_fields_bit_exact"] is False
    assert changed["maximum_absolute_difference"]["area"] == 0.5


def test_vendor_adapter_invokes_bridge_only_on_a_copy_and_joins_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "raw"
    result_set = source_root / "batch" / "sample.rslt"
    result_set.mkdir(parents=True)
    (result_set / "sample.acaml").write_text(_acaml(), encoding="utf-8")
    (result_set / "one.dx").write_bytes(b"raw-one")
    (result_set / "one.rx").write_bytes(b"old-rx")
    method = tmp_path / "GC_LC_DefaultMethod.pmx"
    method.write_bytes(b"complete-pmx")
    runtime_bin = tmp_path / "runtime" / "Bin"
    runtime_bin.mkdir(parents=True)
    for name in _REQUIRED_RUNTIME_FILES:
        (runtime_bin / name).write_bytes(name.encode("ascii"))
    bridge = runtime_bin / "OpenLabVendorBridge.exe"
    bridge.write_bytes(b"bridge")
    dataset = {
        "injections": [
            {
                "source_relative": "batch/sample.rslt/one.dx",
                "raw_file": "one.dx",
                "injection_guid": "guid-1",
                "sequence_order": 1,
                "result_name": "sample",
            }
        ]
    }
    source_before = {path.relative_to(source_root): path.read_bytes() for path in source_root.rglob("*") if path.is_file()}

    def fake_bridge(**kwargs):
        assert kwargs["work_area"] != result_set
        jobs = (kwargs["work_area"] / kwargs["jobs_name"]).read_text(encoding="utf-8").splitlines()
        assert len(jobs) == 1
        raw_file = jobs[0].split("\t")[2]
        (kwargs["work_area"] / Path(raw_file).with_suffix(".rx")).write_bytes(b"new-vendor-rx")
        kwargs["report_path"].write_text(
            json.dumps(
                {
                    "jobs": [
                        {
                            "raw_file": raw_file,
                            "success": True,
                            "warnings": ["normalization warning"],
                            "load_errors": [],
                            "failures": [],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess([], 0, "bridge-ok", "")

    monkeypatch.setattr("src.core.hplc_openlab_vendor._run_bridge", fake_bridge)
    result = reprocess_openlab_with_vendor_method(
        source_root=source_root,
        staged_input_root=tmp_path / "staged",
        dataset=dataset,
        runtime_bin=runtime_bin,
        bridge_exe=bridge,
        processing_method=method,
        timeout_seconds=30,
    )

    source_after = {path.relative_to(source_root): path.read_bytes() for path in source_root.rglob("*") if path.is_file()}
    assert source_after == source_before
    assert (result.effective_input_root / "batch" / "sample.rslt" / "one.rx").read_bytes() == b"new-vendor-rx"
    provenance = result.injection_provenance["batch/sample.rslt/one.dx"]
    assert provenance["vendor_result_origin"] == VENDOR_RESULT_ORIGIN
    assert provenance["vendor_reprocess_status"] == "success"
    assert result.manifest["vendor_code_executed"] is True
    assert result.manifest["completed_injection_count"] == 1

    extracted = {
        "source_root_name": "staged",
        "library_provenance": {},
        "scientific_boundary": {},
        "injections": [{"source_relative": "batch/sample.rslt/one.dx"}],
    }
    apply_vendor_reprocess_provenance(extracted, result, source_root_name="raw")
    assert extracted["source_root_name"] == "raw"
    assert extracted["injections"][0]["vendor_result_origin"] == VENDOR_RESULT_ORIGIN
