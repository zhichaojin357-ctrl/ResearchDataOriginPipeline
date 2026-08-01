from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import pytest

from src.core.agilent_dx import (
    DX_DECODER_NAME,
    DX_DECODER_VERSION,
    SIGNAL179_HEADER_MAGIC,
    SIGNAL179_HEADER_SIZE,
    SUPPORTED_ACMD_NAMESPACE,
    SUPPORTED_SIGNAL_ENCODING,
    decode_agilent_dx,
    read_agilent_dx_metadata,
)


def _signal_xml(
    *,
    trace_id: str = "trace-1",
    integrable: bool = True,
    encoding: str = SUPPORTED_SIGNAL_ENCODING,
    count: int = 3,
    slope: str = "2.5",
    start_ms: str = "60000",
    end_ms: str = "180000",
    channel: str = "VWD1 A",
) -> str:
    return f"""
      <Signal>
        <IsIntegrable>{str(integrable).lower()}</IsIntegrable>
        <Encoding>{encoding}</Encoding>
        <TraceId>{trace_id}</TraceId>
        <NumberOfValues>{count}</NumberOfValues>
        <Slope>{slope}</Slope>
        <TimeStart>{start_ms}</TimeStart>
        <TimeEnd>{end_ms}</TimeEnd>
        <ChannelName>{channel}</ChannelName>
        <DeviceName>VWD</DeviceName>
        <Description>VWD, Wavelength=254 nm</Description>
        <Units>mAU</Units>
      </Signal>
    """


def _acmd(*signals: str, namespace: str = SUPPORTED_ACMD_NAMESPACE) -> bytes:
    return f"""<?xml version="1.0" encoding="utf-8"?>
    <ACMD xmlns="{namespace}">
      <InjectionInfo>
        <RunDateTime>2026-07-18T15:31:54+08:00</RunDateTime>
        <AcquisitionMethod>C:\\Methods\\analysis.m</AcquisitionMethod>
        <SampleName>sample-A</SampleName>
        <Location>1:A,1</Location>
      </InjectionInfo>
      <Signals>{''.join(signals)}</Signals>
    </ACMD>""".encode("utf-8")


def _content_types(*, signal_extension: str = "s179", include_signal: bool = True) -> bytes:
    signal_default = (
        f'<Default Extension="{signal_extension}" ContentType="{SUPPORTED_SIGNAL_ENCODING}" />'
        if include_signal
        else ""
    )
    return f"""<?xml version="1.0" encoding="utf-8"?>
    <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
      {signal_default}
      <Default Extension="mwd" ContentType="Agilent.OpenLab.Rawdata/MWD" />
      <Default Extension="uvd" ContentType="Agilent.OpenLab.Rawdata/UVD" />
      <Default Extension="acmd" ContentType="application/acmd" />
    </Types>""".encode("utf-8")


def _signal179_payload(
    values: list[float] | np.ndarray,
    *,
    valid_header: bool = True,
) -> bytes:
    header = bytearray(SIGNAL179_HEADER_SIZE)
    header[: len(SIGNAL179_HEADER_MAGIC)] = (
        SIGNAL179_HEADER_MAGIC if valid_header else b"BAD!"
    )
    return bytes(header) + np.asarray(values, dtype="<f8").tobytes()


def _write_dx(
    tmp_path: Path,
    *,
    acmd: bytes | None = None,
    content_types: bytes | None = None,
    payloads: tuple[tuple[str, bytes], ...] = (),
    name: str = "synthetic.dx",
) -> Path:
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as archive:
        if acmd is not None:
            archive.writestr("injection.acmd", acmd)
        if content_types is not None:
            archive.writestr("[Content_Types].xml", content_types)
        for member, payload in payloads:
            archive.writestr(member, payload)
    return path


def _valid_dx(tmp_path: Path, **overrides: object) -> Path:
    trace_id = str(overrides.pop("trace_id", "trace-1"))
    signal = _signal_xml(trace_id=trace_id, **overrides)
    return _write_dx(
        tmp_path,
        acmd=_acmd(signal),
        content_types=_content_types(),
        payloads=((f"Signals/{trace_id}.s179", _signal179_payload([1.0, 2.0, 3.0])),),
    )


def test_metadata_reads_manifest_and_filters_non_chromatogram_members(tmp_path: Path):
    path = _valid_dx(tmp_path)
    with zipfile.ZipFile(path, "a") as archive:
        archive.writestr("Signals/telemetry.mwd", b"telemetry")
        archive.writestr("Signals/legacy.uvd", b"excluded")
        archive.writestr("notes.txt", b"not raw data")

    result = read_agilent_dx_metadata(path)

    assert result == {
        "datafiles": ["Signals/trace-1.s179", "Signals/telemetry.mwd"],
        "metadata": {
            "vendor": "Agilent",
            "date": "2026-07-18T15:31:54+08:00",
            "method": "analysis.m",
            "sample": "sample-A",
            "vialpos": "1:A,1",
        },
    }


def test_decodes_signal179_with_slope_minutes_and_compatibility_shape(tmp_path: Path):
    path = _valid_dx(tmp_path)

    result = decode_agilent_dx(path)

    assert result.metadata["vendor"] == "Agilent"
    assert len(result.datafiles) == 1
    signal = result.datafiles[0]
    assert signal.name == "VWD1 A.s179"
    assert signal.detector == "UV"
    assert signal.trace_id == "trace-1"
    assert signal.source_member == "Signals/trace-1.s179"
    assert signal.encoding == SUPPORTED_SIGNAL_ENCODING
    assert signal.metadata == {
        "device": "VWD",
        "description": "VWD, Wavelength=254 nm",
        "unit": "mAU",
    }
    assert signal.xlabels.dtype == np.float64
    assert signal.data.dtype == np.float64
    assert signal.xlabels.shape == (3,)
    assert signal.data.shape == (3, 1)
    np.testing.assert_allclose(signal.xlabels, [1.0, 2.0, 3.0])
    np.testing.assert_allclose(signal.data[:, 0], [2.5, 5.0, 7.5])
    assert DX_DECODER_NAME == "project-native-agilent-openlab-dx"
    assert DX_DECODER_VERSION == "1.0.0"


def test_nonintegrable_telemetry_is_not_decoded_or_validated(tmp_path: Path):
    path = _write_dx(
        tmp_path,
        acmd=_acmd(
            _signal_xml(),
            _signal_xml(
                trace_id="telemetry",
                integrable=False,
                encoding="Agilent.OpenLab.Rawdata/Telemetry999",
                count=0,
                slope="not-a-number",
                start_ms="not-a-time",
                end_ms="also-not-a-time",
            ),
        ),
        content_types=_content_types(),
        payloads=(
            ("Signals/trace-1.s179", _signal179_payload([1.0, 2.0, 3.0])),
            ("Signals/telemetry.bad", b"ignored"),
        ),
    )

    result = decode_agilent_dx(path)

    assert [signal.trace_id for signal in result.datafiles] == ["trace-1"]


@pytest.mark.parametrize(
    ("acmd", "content_types", "payloads", "expected"),
    [
        (
            _acmd(_signal_xml(encoding="Agilent.OpenLab.Rawdata/Signal42")),
            _content_types(),
            (("Signals/trace-1.s179", _signal179_payload([1, 2, 3])),),
            "unsupported integrable Agilent signal encoding",
        ),
        (
            _acmd(_signal_xml()),
            _content_types(include_signal=False),
            (("Signals/trace-1.s179", _signal179_payload([1, 2, 3])),),
            "content types do not map encoding",
        ),
        (
            _acmd(_signal_xml()),
            _content_types(),
            (),
            "maps to 0 payload members",
        ),
        (
            _acmd(_signal_xml()),
            _content_types(),
            (
                ("one/trace-1.s179", _signal179_payload([1, 2, 3])),
                ("two/trace-1.s179", _signal179_payload([1, 2, 3])),
            ),
            "maps to 2 payload members",
        ),
        (
            _acmd(_signal_xml(count=0)),
            _content_types(),
            (("Signals/trace-1.s179", _signal179_payload([])),),
            "has no values",
        ),
        (
            _acmd(_signal_xml()),
            _content_types(),
            (("Signals/trace-1.s179", _signal179_payload([1, 2])),),
            "payload size mismatch",
        ),
        (
            _acmd(_signal_xml()),
            _content_types(),
            (("Signals/trace-1.s179", _signal179_payload([1, 2, 3], valid_header=False)),),
            "header signature mismatch",
        ),
        (
            _acmd(_signal_xml(start_ms="120000", end_ms="60000")),
            _content_types(),
            (("Signals/trace-1.s179", _signal179_payload([1, 2, 3])),),
            "time range is reversed",
        ),
        (
            _acmd(_signal_xml(start_ms="60000", end_ms="60000")),
            _content_types(),
            (("Signals/trace-1.s179", _signal179_payload([1, 2, 3])),),
            "time axis is not strictly increasing",
        ),
        (
            _acmd(_signal_xml(slope="nan")),
            _content_types(),
            (("Signals/trace-1.s179", _signal179_payload([1, 2, 3])),),
            "contains non-finite values",
        ),
        (
            _acmd(_signal_xml()),
            _content_types(),
            (("Signals/trace-1.s179", _signal179_payload([1, np.nan, 3])),),
            "contains non-finite values",
        ),
    ],
    ids=[
        "unsupported_encoding",
        "unmapped_encoding",
        "zero_payloads",
        "multiple_payloads",
        "empty_signal",
        "size_mismatch",
        "header_mismatch",
        "reversed_time",
        "nonincreasing_time",
        "nonfinite_slope",
        "nonfinite_payload",
    ],
)
def test_decode_rejects_invalid_integrable_signal(
    tmp_path: Path,
    acmd: bytes,
    content_types: bytes,
    payloads: tuple[tuple[str, bytes], ...],
    expected: str,
):
    path = _write_dx(tmp_path, acmd=acmd, content_types=content_types, payloads=payloads)

    with pytest.raises(ValueError, match=expected):
        decode_agilent_dx(path)


@pytest.mark.parametrize(
    ("members", "expected"),
    [
        (
            {"[Content_Types].xml": _content_types()},
            "missing required package member",
        ),
        (
            {"injection.acmd": _acmd(_signal_xml())},
            "missing required package member",
        ),
        (
            {
                "injection.acmd": b"<ACMD>",
                "[Content_Types].xml": _content_types(),
            },
            "contains malformed XML",
        ),
        (
            {
                "injection.acmd": _acmd(_signal_xml(), namespace="urn:unsupported"),
                "[Content_Types].xml": _content_types(),
            },
            "unsupported Agilent ACMD schema",
        ),
    ],
    ids=["missing_acmd", "missing_content_types", "malformed_xml", "unsupported_namespace"],
)
def test_manifest_failures_are_explicit(
    tmp_path: Path, members: dict[str, bytes], expected: str
):
    path = tmp_path / "invalid.dx"
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)

    with pytest.raises(ValueError, match=expected):
        decode_agilent_dx(path)
    with pytest.raises(ValueError, match=expected):
        read_agilent_dx_metadata(path)


def test_corrupt_zip_is_rejected_by_metadata_and_decoder(tmp_path: Path):
    path = tmp_path / "corrupt.dx"
    path.write_bytes(b"this is not a ZIP archive")

    for reader in (read_agilent_dx_metadata, decode_agilent_dx):
        with pytest.raises(ValueError, match="not a valid OPC/ZIP package"):
            reader(path)


def test_no_integrable_signal_is_rejected(tmp_path: Path):
    path = _write_dx(
        tmp_path,
        acmd=_acmd(_signal_xml(integrable=False)),
        content_types=_content_types(),
        payloads=(("Signals/trace-1.s179", _signal179_payload([1, 2, 3])),),
    )

    with pytest.raises(ValueError, match="no non-empty integrable detector signal"):
        decode_agilent_dx(path)
