from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

import numpy as np


DX_DECODER_NAME = "project-native-agilent-openlab-dx"
DX_DECODER_VERSION = "1.0.0"
SUPPORTED_ACMD_NAMESPACE = "urn:schemas-agilent-com:acmd20"
SUPPORTED_SIGNAL_ENCODING = "Agilent.OpenLab.Rawdata/Signal179"
SIGNAL179_HEADER_SIZE = 6144
SIGNAL179_HEADER_MAGIC = b"\x03179"


@dataclass(frozen=True)
class AgilentDxSignal:
    """One directly decoded, integrable detector signal from an OpenLab .dx package."""

    name: str
    detector: str
    xlabels: np.ndarray
    data: np.ndarray
    metadata: dict[str, Any]
    trace_id: str
    source_member: str
    encoding: str


@dataclass(frozen=True)
class AgilentDxData:
    """Compatibility-shaped native decode result used by the OpenLab pipeline."""

    datafiles: tuple[AgilentDxSignal, ...]
    metadata: dict[str, Any]


def read_agilent_dx_metadata(
    path: str | Path,
    *,
    verify_members: bool = True,
) -> dict[str, Any]:
    """Read only the OPC manifest and ACMD metadata; never require OpenLab or .rx/.pmx."""
    dx_path = Path(path)
    root, content_types, member_names = _read_package_manifest(
        dx_path,
        verify_members=verify_members,
    )
    _validate_acmd_namespace(root, dx_path)
    metadata = _injection_metadata(root)
    datafiles = [
        name
        for name in member_names
        if _is_raw_data_member(name, content_types)
    ]
    return {"datafiles": datafiles, "metadata": metadata}


def decode_agilent_dx(path: str | Path) -> AgilentDxData:
    """Decode ACMD20/Signal179 chromatograms directly from one .dx OPC package.

    The implementation is intentionally strict. Unsupported encodings, malformed headers,
    truncated payloads, empty integrable channels, and non-finite values fail explicitly.
    Instrument telemetry remains outside this HPLC chromatogram adapter's scope.
    """
    dx_path = Path(path)
    try:
        with ZipFile(dx_path) as archive:
            corrupt_member = archive.testzip()
            if corrupt_member:
                raise ValueError(f"corrupt ZIP member: {corrupt_member}")
            root = ET.fromstring(archive.read("injection.acmd"))
            content_types = _parse_content_types(archive.read("[Content_Types].xml"))
            _validate_acmd_namespace(root, dx_path)
            payload_members: dict[tuple[str, str], list[str]] = {}
            for name in archive.namelist():
                key = (
                    name.rsplit(".", 1)[-1].casefold(),
                    Path(name).stem.casefold(),
                )
                payload_members.setdefault(key, []).append(name)
            signals = tuple(
                _decode_integrable_signal(
                    archive=archive,
                    signal=signal,
                    content_types=content_types,
                    payload_members=payload_members,
                    dx_path=dx_path,
                )
                for signal in _signal_elements(root)
                if _child_text(signal, "IsIntegrable").casefold() == "true"
            )
    except BadZipFile as exc:
        raise ValueError(f"Agilent .dx is not a valid OPC/ZIP package: {dx_path}") from exc
    except KeyError as exc:
        raise ValueError(f"Agilent .dx is missing required package member {exc}: {dx_path}") from exc
    except ET.ParseError as exc:
        raise ValueError(f"Agilent .dx contains malformed XML: {dx_path}") from exc
    if not signals:
        raise ValueError(f"Agilent .dx contains no non-empty integrable detector signal: {dx_path}")
    return AgilentDxData(datafiles=signals, metadata=_injection_metadata(root))


def _read_package_manifest(
    dx_path: Path,
    *,
    verify_members: bool = True,
) -> tuple[ET.Element, dict[str, str], tuple[str, ...]]:
    try:
        with ZipFile(dx_path) as archive:
            if verify_members:
                corrupt_member = archive.testzip()
                if corrupt_member:
                    raise ValueError(f"corrupt ZIP member: {corrupt_member}")
            root = ET.fromstring(archive.read("injection.acmd"))
            content_types = _parse_content_types(archive.read("[Content_Types].xml"))
            names = tuple(archive.namelist())
    except BadZipFile as exc:
        raise ValueError(f"Agilent .dx is not a valid OPC/ZIP package: {dx_path}") from exc
    except KeyError as exc:
        raise ValueError(f"Agilent .dx is missing required package member {exc}: {dx_path}") from exc
    except ET.ParseError as exc:
        raise ValueError(f"Agilent .dx contains malformed XML: {dx_path}") from exc
    return root, content_types, names


def _decode_integrable_signal(
    *,
    archive: ZipFile,
    signal: ET.Element,
    content_types: dict[str, str],
    payload_members: dict[tuple[str, str], list[str]],
    dx_path: Path,
) -> AgilentDxSignal:
    encoding = _child_text(signal, "Encoding")
    if encoding != SUPPORTED_SIGNAL_ENCODING:
        raise ValueError(
            f"unsupported integrable Agilent signal encoding {encoding!r}: {dx_path}"
        )
    extension = next(
        (suffix for suffix, content_type in content_types.items() if content_type == encoding),
        None,
    )
    if not extension:
        raise ValueError(f".dx content types do not map encoding {encoding!r}: {dx_path}")
    trace_id = _child_text(signal, "TraceId")
    candidates = payload_members.get((extension.casefold(), trace_id.casefold()), [])
    if len(candidates) != 1:
        raise ValueError(
            f"integrable signal {trace_id!r} maps to {len(candidates)} payload members: {dx_path}"
        )
    member = candidates[0]
    number_of_values = _required_int(signal, "NumberOfValues", dx_path)
    if number_of_values <= 0:
        raise ValueError(f"integrable signal {trace_id!r} has no values: {dx_path}")
    payload = archive.read(member)
    expected_size = SIGNAL179_HEADER_SIZE + number_of_values * np.dtype("<f8").itemsize
    if len(payload) != expected_size:
        raise ValueError(
            f"Signal179 payload size mismatch for {member}: expected {expected_size}, "
            f"found {len(payload)} in {dx_path}"
        )
    if payload[: len(SIGNAL179_HEADER_MAGIC)] != SIGNAL179_HEADER_MAGIC:
        raise ValueError(f"Signal179 header signature mismatch for {member}: {dx_path}")
    raw_values = np.frombuffer(
        payload,
        dtype="<f8",
        count=number_of_values,
        offset=SIGNAL179_HEADER_SIZE,
    )
    slope = _required_float(signal, "Slope", dx_path)
    values = raw_values * slope
    time_start_ms = _required_float(signal, "TimeStart", dx_path)
    time_end_ms = _required_float(signal, "TimeEnd", dx_path)
    if time_end_ms < time_start_ms:
        raise ValueError(f"integrable signal time range is reversed for {member}: {dx_path}")
    if number_of_values > 1 and time_end_ms == time_start_ms:
        raise ValueError(
            f"integrable signal time axis is not strictly increasing for {member}: {dx_path}"
        )
    if number_of_values == 1:
        times_min = np.asarray([time_start_ms / 60000.0], dtype=np.float64)
    else:
        time_step_ms = (time_end_ms - time_start_ms) / (number_of_values - 1)
        # Signal179 declares inclusive start/end times.  Constructing the regular
        # grid in the declared millisecond unit and then converting it preserves
        # the exact IEEE-754 values recovered from all supported audit packages.
        times_ms = np.arange(
            time_start_ms,
            time_end_ms + time_step_ms / 2.0,
            time_step_ms,
            dtype=np.float64,
        )
        if len(times_ms) != number_of_values:
            raise ValueError(
                f"Signal179 time grid size mismatch for {member}: expected "
                f"{number_of_values}, constructed {len(times_ms)} in {dx_path}"
            )
        times_min = times_ms / 60000.0
    if not np.isfinite(times_min).all() or not np.isfinite(values).all():
        raise ValueError(f"integrable signal contains non-finite values for {member}: {dx_path}")
    if len(times_min) > 1 and not np.all(np.diff(times_min) > 0):
        raise ValueError(f"integrable signal time axis is not strictly increasing for {member}: {dx_path}")
    channel_name = _child_text(signal, "ChannelName") or trace_id
    device_name = _child_text(signal, "DeviceName")
    return AgilentDxSignal(
        name=f"{channel_name}.{extension}",
        detector=_detector_category(device_name),
        xlabels=times_min,
        data=values.reshape(-1, 1),
        metadata={
            "device": device_name,
            "description": _child_text(signal, "Description"),
            "unit": _child_text(signal, "Units"),
        },
        trace_id=trace_id,
        source_member=member,
        encoding=encoding,
    )


def _injection_metadata(root: ET.Element) -> dict[str, Any]:
    injection_info = next(
        (element for element in root.iter() if _local_name(element.tag) == "InjectionInfo"),
        None,
    )
    if injection_info is None:
        raise ValueError("Agilent injection.acmd does not contain InjectionInfo")
    method = _child_text(injection_info, "AcquisitionMethod")
    return {
        "vendor": "Agilent",
        "date": _child_text(injection_info, "RunDateTime"),
        "method": PureWindowsPath(method).name if method else "",
        "sample": _child_text(injection_info, "SampleName"),
        "vialpos": _child_text(injection_info, "Location"),
    }


def _parse_content_types(xml_bytes: bytes) -> dict[str, str]:
    root = ET.fromstring(xml_bytes)
    return {
        str(element.get("Extension") or ""): str(element.get("ContentType") or "")
        for element in root
        if _local_name(element.tag) == "Default" and element.get("Extension")
    }


def _is_raw_data_member(name: str, content_types: dict[str, str]) -> bool:
    if "." not in name:
        return False
    extension = name.rsplit(".", 1)[-1]
    content_type = content_types.get(extension, "")
    return content_type.startswith("Agilent.OpenLab.Rawdata/") and extension.casefold() not in {
        "uvd",
        "acmd",
    }


def _signal_elements(root: ET.Element) -> list[ET.Element]:
    signals = next(
        (element for element in root.iter() if _local_name(element.tag) == "Signals"),
        None,
    )
    if signals is None:
        return []
    return [element for element in signals if _local_name(element.tag) == "Signal"]


def _validate_acmd_namespace(root: ET.Element, dx_path: Path) -> None:
    namespace = root.tag[1:].split("}", 1)[0] if root.tag.startswith("{") else ""
    if _local_name(root.tag) != "ACMD" or namespace != SUPPORTED_ACMD_NAMESPACE:
        raise ValueError(
            f"unsupported Agilent ACMD schema {root.tag!r}; expected ACMD20: {dx_path}"
        )


def _required_float(element: ET.Element, name: str, dx_path: Path) -> float:
    value = _child_text(element, name)
    if not value:
        raise ValueError(f"integrable signal is missing {name}: {dx_path}")
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"integrable signal has invalid {name}={value!r}: {dx_path}") from exc


def _required_int(element: ET.Element, name: str, dx_path: Path) -> int:
    value = _child_text(element, name)
    if not value:
        raise ValueError(f"integrable signal is missing {name}: {dx_path}")
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"integrable signal has invalid {name}={value!r}: {dx_path}") from exc


def _child_text(element: ET.Element, name: str) -> str:
    child = next((item for item in element if _local_name(item.tag) == name), None)
    return (child.text or "").strip() if child is not None else ""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _detector_category(device_name: str) -> str:
    """Return a stable detector family while retaining the device in metadata."""
    normalized = device_name.strip().upper()
    if normalized in {"VWD", "DAD", "MWD"}:
        return "UV"
    return device_name
