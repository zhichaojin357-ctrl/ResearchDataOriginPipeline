from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path


DATA_OFFSET_CACQU = 9500
DEFAULT_EXPORT_POINTS = 4096
JEOL_PROCESS_TYPES = {"cAcqu", "spin", "endor", "pAcqu", "cidep", "sod", "iso", "ani"}


@dataclass(frozen=True)
class JeolEprHeader:
    process_type: str
    filename: str
    aux_num: int
    data_set: int
    data_length: int
    data_kind: str
    x_offset: float
    x_range: float
    x_unit: str
    x_start: float
    x_stop: float


@dataclass(frozen=True)
class JeolEprDecodeResult:
    header: JeolEprHeader
    ch1: list[float]
    ch2: list[float] | None


def looks_like_jeol_cwesr_file(path: Path) -> bool:
    """Return true for JEOL JES-FA/JES-X3-like binary EPR files."""
    if not path.is_file() or path.suffix.lower() in {".xlsx", ".xls", ".csv", ".txt"}:
        return False
    if path.stat().st_size < DATA_OFFSET_CACQU + 4:
        return False
    try:
        with path.open("rb") as handle:
            process_type = _read_c_string(handle, 16)
    except OSError:
        return False
    return process_type in JEOL_PROCESS_TYPES


def read_jeol_cacqu(path: Path) -> JeolEprDecodeResult:
    """Read a JEOL JES-FA/JES-X3 cAcqu file into CH1/CH2 float arrays."""
    with path.open("rb") as handle:
        process_type = _read_c_string(handle, 16)
        filename = _read_c_string(handle, 64)
        handle.read(4)
        aux_num = _read_i32(handle)
        data_set = _read_i32(handle)
        data_length = _read_i32(handle)
        data_kind = _read_c_string(handle, 15)
        handle.read(1)
        x_offset = _read_f32(handle)
        x_range = _read_f32(handle)
        x_unit = _read_c_string(handle, 16)
        handle.read(8)
        _read_c_string(handle, 16)
        handle.read(4)
        _read_c_string(handle, 16)
        x_start = _read_f32(handle)
        x_stop = _read_f32(handle)

        header = JeolEprHeader(
            process_type=process_type,
            filename=filename,
            aux_num=aux_num,
            data_set=data_set,
            data_length=data_length,
            data_kind=data_kind,
            x_offset=x_offset,
            x_range=x_range,
            x_unit=x_unit,
            x_start=x_start,
            x_stop=x_stop,
        )

        if process_type != "cAcqu":
            raise ValueError(f"unsupported JEOL EPR processType {process_type!r}; only cAcqu is enabled")
        if aux_num != 0 or data_set != 1:
            raise ValueError(f"unsupported JEOL EPR aux/dataSet combination aux={aux_num}, dataSet={data_set}")
        if data_kind not in {"real", "complex"}:
            raise ValueError(f"unsupported JEOL EPR dataKind {data_kind!r}")
        if data_length <= 0:
            raise ValueError(f"invalid JEOL EPR dataLength {data_length}")

        handle.seek(DATA_OFFSET_CACQU)
        raw = handle.read(4 * data_length)
        if len(raw) != 4 * data_length:
            raise ValueError("truncated JEOL EPR CH1 data")
        ch1 = list(struct.unpack(f"<{data_length}f", raw))

        ch2 = None
        if data_kind == "complex":
            raw = handle.read(4 * data_length)
            if len(raw) != 4 * data_length:
                raise ValueError("truncated JEOL EPR CH2 data")
            ch2 = list(struct.unpack(f"<{data_length}f", raw))

    return JeolEprDecodeResult(header=header, ch1=ch1, ch2=ch2)


def decode_jeol_cacqu_rows(path: Path, *, points: int = DEFAULT_EXPORT_POINTS) -> list[dict[str, str]]:
    """Decode JEOL cAcqu CH1 to the project's two-column EPR table shape."""
    decoded = read_jeol_cacqu(path)
    x_values, y_values = to_export_series(decoded, points=points)
    return [
        {"magnetic field": f"{round(x_value, 4)}", "intensity": f"{round(y_value, 3)}"}
        for x_value, y_value in zip(x_values, y_values)
    ]


def to_export_series(decoded: JeolEprDecodeResult, *, points: int = DEFAULT_EXPORT_POINTS) -> tuple[list[float], list[float]]:
    raw_points = decoded.header.data_length
    if raw_points % points:
        raise ValueError(f"JEOL EPR dataLength {raw_points} is not divisible by export point count {points}")
    repeats = raw_points // points
    y_values = [
        sum(decoded.ch1[index * repeats + offset] for offset in range(repeats)) / repeats
        for index in range(points)
    ]
    x_step = decoded.header.x_range / (raw_points - 1)
    x_values = [decoded.header.x_offset + x_step * index for index in range(points)]
    return x_values, y_values


def _read_c_string(handle, length: int) -> str:
    raw = handle.read(length)
    return raw.split(b"\0", 1)[0].decode("latin1", "replace")


def _read_i32(handle) -> int:
    raw = handle.read(4)
    if len(raw) != 4:
        raise ValueError("truncated JEOL EPR int32 header field")
    return struct.unpack("<i", raw)[0]


def _read_f32(handle) -> float:
    raw = handle.read(4)
    if len(raw) != 4:
        raise ValueError("truncated JEOL EPR float32 header field")
    return struct.unpack("<f", raw)[0]
