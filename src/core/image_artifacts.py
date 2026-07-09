from __future__ import annotations

from pathlib import Path


def ensure_tif_600_dpi_metadata(path: Path) -> None:
    try:
        from PIL import Image
    except Exception:
        return
    with Image.open(path) as image:
        output = image.copy()
    output.save(path, format="TIFF", dpi=(600, 600), compression="tiff_lzw")
