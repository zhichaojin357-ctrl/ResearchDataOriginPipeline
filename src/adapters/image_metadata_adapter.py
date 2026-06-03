from __future__ import annotations

from pathlib import Path
from typing import Any

from src.adapters.common import import_optional, is_module_available, metadata_provenance, version_for

PACKAGE = "Pillow/tifffile/scikit-image"


def is_available() -> bool:
    return is_module_available("PIL") or is_module_available("tifffile")


def version_info() -> dict[str, object]:
    return {
        "package": PACKAGE,
        "available": is_available(),
        "pillow": version_for("Pillow", "PIL"),
        "tifffile": version_for("tifffile", "tifffile"),
        "scikit_image": version_for("scikit-image", "skimage"),
    }


def capabilities() -> dict[str, object]:
    return {
        "data_types": ["SEM_image_data", "TEM_image_data"],
        "methods": ["image metadata probe", "thumbnail only when output_dir is provided"],
        "outputs": ["width", "height", "mode", "dpi", "series_count_optional"],
        "forbidden_claims": ["no morphology statistics", "no lattice/plane assignment"],
    }


def process_or_analyze(path: Path, *, output_dir: Path | None = None) -> dict[str, Any]:
    pil, pil_error = import_optional("PIL.Image")
    tifffile, tif_error = import_optional("tifffile")
    metadata: dict[str, Any] = {"path": str(path), "exists": path.exists(), "bytes": path.stat().st_size if path.exists() else 0}
    warnings: list[str] = []
    if pil is not None and path.exists():
        with pil.open(path) as image:
            metadata.update({"width": image.width, "height": image.height, "mode": image.mode, "format": image.format, "dpi": image.info.get("dpi")})
            if output_dir is not None:
                output_dir.mkdir(parents=True, exist_ok=True)
                thumb = output_dir / f"{path.stem}_thumbnail.png"
                preview = image.copy()
                preview.thumbnail((512, 512))
                preview.save(thumb)
                metadata["thumbnail"] = str(thumb)
    elif pil_error:
        warnings.append(f"Pillow unavailable: {pil_error}")
    if tifffile is not None and path.suffix.casefold() in {".tif", ".tiff"} and path.exists():
        try:
            with tifffile.TiffFile(path) as tif:
                metadata["tiff_pages"] = len(tif.pages)
                if tif.series:
                    metadata["tiff_series"] = len(tif.series)
        except Exception as exc:
            warnings.append(f"tifffile probe failed: {exc}")
    elif path.suffix.casefold() in {".tif", ".tiff"} and tif_error:
        warnings.append(f"tifffile unavailable: {tif_error}")
    return {
        "ok": bool(metadata.get("width") or metadata.get("tiff_pages")),
        "metadata": metadata,
        "warnings": warnings,
        "fallback_reason": "; ".join(warnings) or None,
        "metadata_provenance": metadata_provenance(
            adapter="image_metadata_adapter",
            package=PACKAGE,
            module="PIL/tifffile/skimage",
            version=str(version_info()),
            method="metadata_probe_only",
            fallback_reason="; ".join(warnings) or None,
        ),
    }


def smoke_test() -> dict[str, object]:
    return {"ok": is_available(), "version_info": version_info()}
