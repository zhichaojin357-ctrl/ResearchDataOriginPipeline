from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import quoteattr
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from src.core.agilent_pmx import (
    pmx_integration_policy,
    read_agilent_pmx,
    read_uniform_pmx_integration_policy,
)


def test_reads_enabled_twelve_tone_settings_and_events(tmp_path: Path):
    pmx = tmp_path / "method.pmx"
    _write_pmx(pmx)

    method = read_agilent_pmx(pmx)
    policy = pmx_integration_policy(method)

    assert method["integration"]["engine_type"] == "TwelveToneIntegratorTransformation64"
    assert policy["slope_sensitivity"] == 1.0
    assert policy["initial_peak_width_min"] == 0.02
    assert policy["area_reject_mau_s"] == 1.0
    assert policy["height_reject_mau"] == 1.7
    assert policy["shoulders_mode"] == "OFF"
    assert policy["area_percent_reject"] == 0.0
    assert policy["baseline_correction"] == "Advanced"
    assert policy["peak_to_valley_ratio"] == 500.0
    assert policy["timed_events"] == []
    assert method["reader"]["vendor_code_executed"] is False


def test_uniform_corpus_parser_reads_every_method_copy(tmp_path: Path):
    _write_pmx(tmp_path / "one" / "method.pmx")
    _write_pmx(tmp_path / "two" / "method.pmx")

    policy, audit = read_uniform_pmx_integration_policy(tmp_path)

    assert policy["method_source"]["kind"] == "pmx_corpus"
    assert audit["pmx_file_count"] == 2
    assert audit["unique_package_count"] == 1
    assert audit["unique_integration_policy_count"] == 1
    assert audit["all_pmx_files_parsed"] is True


def test_missing_required_initial_event_is_rejected(tmp_path: Path):
    pmx = tmp_path / "method.pmx"
    _write_pmx(pmx, include_height=False)

    with pytest.raises(ValueError, match="HeightReject"):
        pmx_integration_policy(read_agilent_pmx(pmx))


def test_duplicate_enabled_initial_event_is_rejected(tmp_path: Path):
    pmx = tmp_path / "method.pmx"
    _write_pmx(pmx, duplicate_slope=True)

    with pytest.raises(ValueError, match="duplicate enabled initial event"):
        pmx_integration_policy(read_agilent_pmx(pmx))


def _write_pmx(
    path: Path,
    *,
    include_height: bool = True,
    duplicate_slope: bool = False,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    events = [
        ("SlopeSensitivity", "1"),
        ("PeakWidth", "0.02"),
        ("AreaReject", "1"),
        ("ShouldersMode", "OFF"),
        ("AreaPercentReject", "0"),
    ]
    if include_height:
        events.insert(3, ("HeightReject", "1.7"))
    if duplicate_slope:
        events.append(("SlopeSensitivity", "1"))
    event_xml = "".join(_event_xml(name, value, index) for index, (name, value) in enumerate(events, 1))
    nested = f"""<TransformationPSets>
      <ParameterSet usagekey="12ToneIntegratorSettings" displayName="12-tone" class="test">
        <Parameters>
          <Parameter id="TangentSkimMode"><Value>Standard</Value></Parameter>
          <Parameter id="BaselineCorrection"><Value>Advanced</Value></Parameter>
          <Parameter id="FrontSkimHeightRatio"><Value>0</Value></Parameter>
          <Parameter id="TailSkimHeightRatio"><Value>0</Value></Parameter>
          <Parameter id="SkimValleyRatio"><Value>20</Value></Parameter>
          <Parameter id="PeakToValleyRatio"><Value>500</Value></Parameter>
          <Parameter id="InitialEventsTable"><Value>{event_xml}</Value></Parameter>
          <Parameter id="TimedEventsTable"><Value /></Parameter>
          <Parameter id="GroupParameter"><Value /></Parameter>
        </Parameters>
      </ParameterSet>
    </TransformationPSets>"""
    outer = f"""<TransformationChain Name="DefaultChain" Version="6">
      <TwelveToneIntegratorTransformation64
        TransformationId="test-integrator"
        TransformationCategory="Integration"
        ProcessingLevel="Injection"
        DisplayName="12-tone Integrator"
        IsEnabled="True">
        <TwelveToneIntegratorSetpointContainer SerializedPsetRepresentation={quoteattr(nested)} />
      </TwelveToneIntegratorTransformation64>
    </TransformationChain>"""
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("TransformationChains/DefaultChain", outer.encode("utf-16"))


def _event_xml(name: str, value: str, event_id: int) -> str:
    return f"""<ParameterSet usagekey="" class="event"><Parameters>
      <Parameter id="IntegrationEvent"><Value>
        <IntegrationEvent>{name}</IntegrationEvent>
        <IsTimedEvent>False</IsTimedEvent><IsUsed>True</IsUsed>
        <IntegrationEventValue><Parameter><Value>{value}</Value></Parameter></IntegrationEventValue>
      </Value></Parameter>
      <Parameter id="Time"><Value>0</Value></Parameter>
      <Parameter id="Id"><Value>{event_id}</Value></Parameter>
    </Parameters></ParameterSet>"""
