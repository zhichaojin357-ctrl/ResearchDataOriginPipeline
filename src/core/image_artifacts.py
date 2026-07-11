from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path


def ensure_tif_600_dpi_metadata(path: Path) -> None:
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
