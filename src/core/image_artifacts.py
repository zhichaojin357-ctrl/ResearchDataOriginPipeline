from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import math
import os
import re
import tempfile
from pathlib import Path


class TifResolutionValidationError(RuntimeError):
    """Raised when a TIFF is not native evidence for the requested physical DPI."""


@dataclass(frozen=True)
class TifResolutionEvidence:
    """Read-only evidence tying TIFF pixels to an Origin page's physical size."""

    path: str
    requested_dpi: int
    page_width_origin_units: float
    page_height_origin_units: float
    width_px: int
    height_px: int
    expected_width_px: int
    expected_height_px: int
    pixel_tolerance_x: int
    pixel_tolerance_y: int
    tagged_dpi_x: float
    tagged_dpi_y: float
    effective_dpi_x: float
    effective_dpi_y: float
    metadata_text_tag_count: int
    sensitive_metadata_scan: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def expected_raster_pixels(
    page_width_origin_units: float,
    page_height_origin_units: float,
    *,
    dpi: int = 600,
) -> tuple[int, int]:
    """Convert Origin page units (0.001 inch) to native raster pixel dimensions."""

    width = _positive_finite_float(page_width_origin_units, "page_width_origin_units")
    height = _positive_finite_float(page_height_origin_units, "page_height_origin_units")
    requested_dpi = _positive_integer(dpi, "dpi")
    return (
        max(1, round(width * requested_dpi / 1000.0)),
        max(1, round(height * requested_dpi / 1000.0)),
    )


def validate_tif_physical_resolution(
    path: Path,
    *,
    page_width_origin_units: float,
    page_height_origin_units: float,
    dpi: int = 600,
    relative_pixel_tolerance: float = 0.005,
    minimum_pixel_tolerance: int = 2,
    tagged_dpi_tolerance: float = 1.0,
) -> TifResolutionEvidence:
    """Validate native TIFF resolution without rewriting pixels or metadata.

    Origin reports graph page dimensions in 0.001 inch.  A page dimension of
    6432 therefore requires about 3859 pixels at 600 dpi, not 6432 pixels.
    Both axes, the TIFF resolution tag, and the effective physical DPI must
    agree with the requested value.  This function is intentionally read-only.
    """

    try:
        from PIL import Image
    except Exception as exc:
        raise TifResolutionValidationError("Pillow is required to verify TIFF resolution evidence") from exc

    target = Path(path)
    requested_dpi = _positive_integer(dpi, "dpi")
    page_width = _positive_finite_float(page_width_origin_units, "page_width_origin_units")
    page_height = _positive_finite_float(page_height_origin_units, "page_height_origin_units")
    relative_tolerance = _nonnegative_finite_float(relative_pixel_tolerance, "relative_pixel_tolerance")
    minimum_tolerance = _nonnegative_integer(minimum_pixel_tolerance, "minimum_pixel_tolerance")
    tag_tolerance = _nonnegative_finite_float(tagged_dpi_tolerance, "tagged_dpi_tolerance")
    expected_width, expected_height = expected_raster_pixels(
        page_width,
        page_height,
        dpi=requested_dpi,
    )
    tolerance_x = max(minimum_tolerance, math.ceil(expected_width * relative_tolerance))
    tolerance_y = max(minimum_tolerance, math.ceil(expected_height * relative_tolerance))

    if not target.is_file() or target.stat().st_size == 0:
        raise TifResolutionValidationError(f"TIFF artifact is missing or empty: {target}")

    try:
        with Image.open(target) as image:
            if str(image.format or "").upper() != "TIFF":
                raise TifResolutionValidationError(f"artifact is not a readable TIFF: {target}")
            if int(getattr(image, "n_frames", 1)) != 1:
                raise TifResolutionValidationError(f"multi-frame TIFF resolution evidence is unsupported: {target}")
            image.load()
            width_px, height_px = (int(image.width), int(image.height))
            tagged_dpi_x, tagged_dpi_y = _read_tiff_dpi(image.info.get("dpi"), target)
            metadata_text_tag_count, sensitive_tag_ids = _scan_tiff_text_metadata(image)
    except TifResolutionValidationError:
        raise
    except Exception as exc:
        raise TifResolutionValidationError(f"failed to read TIFF resolution evidence from {target}: {exc}") from exc

    effective_dpi_x = width_px * 1000.0 / page_width
    effective_dpi_y = height_px * 1000.0 / page_height
    evidence = TifResolutionEvidence(
        path=str(target),
        requested_dpi=requested_dpi,
        page_width_origin_units=page_width,
        page_height_origin_units=page_height,
        width_px=width_px,
        height_px=height_px,
        expected_width_px=expected_width,
        expected_height_px=expected_height,
        pixel_tolerance_x=tolerance_x,
        pixel_tolerance_y=tolerance_y,
        tagged_dpi_x=tagged_dpi_x,
        tagged_dpi_y=tagged_dpi_y,
        effective_dpi_x=effective_dpi_x,
        effective_dpi_y=effective_dpi_y,
        metadata_text_tag_count=metadata_text_tag_count,
        sensitive_metadata_scan="pass",
    )

    failures: list[str] = []
    if abs(tagged_dpi_x - requested_dpi) > tag_tolerance or abs(tagged_dpi_y - requested_dpi) > tag_tolerance:
        failures.append(
            f"TIFF DPI tag is {tagged_dpi_x:.3f}x{tagged_dpi_y:.3f}, expected {requested_dpi}x{requested_dpi}"
        )
    if abs(width_px - expected_width) > tolerance_x or abs(height_px - expected_height) > tolerance_y:
        failures.append(
            "pixel dimensions are "
            f"{width_px}x{height_px}, expected {expected_width}x{expected_height} "
            f"(tolerance ±{tolerance_x}x±{tolerance_y} px)"
        )
    effective_tolerance_x = tolerance_x * 1000.0 / page_width
    effective_tolerance_y = tolerance_y * 1000.0 / page_height
    if (
        abs(effective_dpi_x - requested_dpi) > effective_tolerance_x
        or abs(effective_dpi_y - requested_dpi) > effective_tolerance_y
    ):
        failures.append(
            "effective physical DPI is "
            f"{effective_dpi_x:.3f}x{effective_dpi_y:.3f}, expected {requested_dpi}x{requested_dpi}"
        )
    if failures:
        raise TifResolutionValidationError(
            f"TIFF is not native {requested_dpi} dpi evidence for Origin page "
            f"{page_width:g}x{page_height:g} (0.001 inch): "
            + "; ".join(failures)
        )
    if sensitive_tag_ids:
        raise TifResolutionValidationError(
            "TIFF contains sensitive local-path or tool-trace metadata in tag(s) "
            + ", ".join(str(tag_id) for tag_id in sensitive_tag_ids)
            + "; the native Origin export was left unchanged and rejected"
        )
    return evidence


_WINDOWS_ABSOLUTE_PATH_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9])(?:[a-z]:[\\/]|\\\\[^\\/\s]+[\\/])"
)
_POSIX_LOCAL_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9])/(?:home|users|mnt|media|private|tmp|var/tmp)/",
    re.IGNORECASE,
)
_ASSISTANT_TRACE_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9])(?:codex|chatgpt|openai|assistant|agent)(?![A-Za-z0-9])"
)


def _scan_tiff_text_metadata(image: object) -> tuple[int, list[int]]:
    tags = getattr(image, "tag_v2", None)
    if tags is None:
        return 0, []
    text_tag_count = 0
    sensitive: list[int] = []
    for tag_id, value in tags.items():
        text_values = list(_metadata_text_values(value))
        if not text_values:
            continue
        text_tag_count += 1
        if any(_metadata_text_contains_local_path(text) for text in text_values):
            sensitive.append(int(tag_id))
    return text_tag_count, sensitive


def _metadata_text_values(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, bytes):
        decoded = [value.decode("utf-8", errors="ignore")]
        if b"\x00" in value:
            decoded.append(value.decode("utf-16le", errors="ignore"))
        return tuple(decoded)
    if isinstance(value, (tuple, list)):
        output: list[str] = []
        for item in value:
            output.extend(_metadata_text_values(item))
        return tuple(output)
    return ()


def _metadata_text_contains_local_path(value: str) -> bool:
    text = str(value or "")
    lowered = text.casefold()
    return bool(
        _WINDOWS_ABSOLUTE_PATH_RE.search(text)
        or _POSIX_LOCAL_PATH_RE.search(text)
        or "file://" in lowered
        or _ASSISTANT_TRACE_RE.search(text)
    )


def _read_tiff_dpi(value: object, path: Path) -> tuple[float, float]:
    if not isinstance(value, (tuple, list)) or len(value) < 2:
        raise TifResolutionValidationError(f"TIFF DPI tag is missing or invalid for {path}: {value!r}")
    try:
        dpi_x = float(value[0])
        dpi_y = float(value[1])
    except (TypeError, ValueError, OverflowError) as exc:
        raise TifResolutionValidationError(f"TIFF DPI tag is missing or invalid for {path}: {value!r}") from exc
    if not math.isfinite(dpi_x) or not math.isfinite(dpi_y) or dpi_x <= 0 or dpi_y <= 0:
        raise TifResolutionValidationError(f"TIFF DPI tag is missing or invalid for {path}: {value!r}")
    return dpi_x, dpi_y


def _positive_finite_float(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise TifResolutionValidationError(f"{name} must be a positive finite number, got {value!r}")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TifResolutionValidationError(f"{name} must be a positive finite number, got {value!r}") from exc
    if not math.isfinite(number) or number <= 0:
        raise TifResolutionValidationError(f"{name} must be a positive finite number, got {value!r}")
    return number


def _nonnegative_finite_float(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise TifResolutionValidationError(f"{name} must be a non-negative finite number, got {value!r}")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TifResolutionValidationError(f"{name} must be a non-negative finite number, got {value!r}") from exc
    if not math.isfinite(number) or number < 0:
        raise TifResolutionValidationError(f"{name} must be a non-negative finite number, got {value!r}")
    return number


def _positive_integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise TifResolutionValidationError(f"{name} must be a positive integer, got {value!r}")
    return int(value)


def _nonnegative_integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise TifResolutionValidationError(f"{name} must be a non-negative integer, got {value!r}")
    return int(value)


def ensure_tif_600_dpi_metadata(path: Path) -> None:
    """Repair only the TIFF DPI tag while preserving pixels.

    This compatibility helper does not prove native 600 dpi resolution.
    Production Origin paths must additionally call
    :func:`validate_tif_physical_resolution` with page dimensions read from
    the final reopened OPJU.
    """

    try:
        from PIL import Image
    except Exception as exc:
        raise RuntimeError("Pillow is required to verify and normalize TIFF DPI metadata") from exc

    target = Path(path)
    if not target.is_file() or target.stat().st_size == 0:
        raise RuntimeError(f"TIFF artifact is missing or empty: {target}")

    temporary: Path | None = None
    output = None
    try:
        with Image.open(target) as image:
            if str(image.format or "").upper() != "TIFF":
                raise RuntimeError(f"artifact is not a readable TIFF: {target}")
            if int(getattr(image, "n_frames", 1)) != 1:
                raise RuntimeError(f"multi-frame TIFF normalization is unsupported: {target}")
            image.load()
            source_mode = image.mode
            source_size = image.size
            source_pixel_digest = hashlib.sha256(image.tobytes()).digest()
            output = image.copy()

        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.stem}_dpi_",
            suffix=".tif",
            dir=target.parent,
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        output.save(temporary, format="TIFF", dpi=(600, 600), compression="tiff_lzw")

        with Image.open(temporary) as verified:
            if str(verified.format or "").upper() != "TIFF":
                raise RuntimeError("normalized artifact is not TIFF")
            verified.load()
            dpi = verified.info.get("dpi")
            dpi_is_600 = (
                isinstance(dpi, tuple)
                and len(dpi) >= 2
                and tuple(round(float(value)) for value in dpi[:2]) == (600, 600)
            )
            if not dpi_is_600:
                raise RuntimeError(f"normalized TIFF DPI readback is not 600x600: {dpi!r}")
            verified_digest = hashlib.sha256(verified.tobytes()).digest()
            if verified.mode != source_mode or verified.size != source_size or verified_digest != source_pixel_digest:
                raise RuntimeError("normalized TIFF pixel data differs from the source artifact")

        os.replace(temporary, target)
        temporary = None
    except Exception as exc:
        raise RuntimeError(f"TIFF normalization failed for {target}: {exc}") from exc
    finally:
        if output is not None:
            output.close()
        if temporary is not None:
            temporary.unlink(missing_ok=True)
