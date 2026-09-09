"""Preview composition and diagnostic comparison, separate from acceptance."""

from __future__ import annotations

import math
from pathlib import Path


def _load_preview_pair(reference: Path, generated: Path):
    from PIL import Image

    with Image.open(reference) as left, Image.open(generated) as right:
        return left.convert("RGB"), right.convert("RGB")


def _preview_difference_metrics(left, right) -> dict[str, object]:
    from PIL import ImageChops, ImageStat

    reference_size = f"{left.width}x{left.height}"
    generated_size = f"{right.width}x{right.height}"
    target_width = 1200
    left = _resize_template_preview_to_width(left, target_width)
    right = _resize_template_preview_to_width(right, target_width)
    height = min(left.height, right.height)
    left = left.crop((0, 0, target_width, height))
    right = right.crop((0, 0, target_width, height))
    stat = ImageStat.Stat(ImageChops.difference(left, right))
    rms = math.sqrt(sum(value * value for value in stat.rms) / max(len(stat.rms), 1))
    return {
        "reference_size": reference_size,
        "generated_size": generated_size,
        "preview_rms": rms,
    }


def _template_preview_difference_metrics(reference: Path, generated: Path) -> dict[str, object]:
    left, right = _load_preview_pair(reference, generated)
    with left, right:
        return _preview_difference_metrics(left, right)


def _resize_template_preview_to_width(image, target_width: int):
    if image.width == target_width:
        return image
    ratio = target_width / float(image.width)
    height = max(1, int(round(image.height * ratio)))
    return image.resize((target_width, height))


def _make_preview_side_by_side(left, right, output: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    target_height = max(left.height, right.height)
    left = _resize_template_preview_to_height(left, target_height)
    right = _resize_template_preview_to_height(right, target_height)
    label_height = 46
    gap = 24
    width = left.width + gap + right.width
    height = target_height + label_height
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except Exception:
        font = ImageFont.load_default()
    draw.text((12, 10), "Reference format preview", fill="black", font=font)
    draw.text((left.width + gap + 12, 10), "Regenerated product", fill="black", font=font)
    canvas.paste(left, (0, label_height))
    canvas.paste(right, (left.width + gap, label_height))
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)


def _make_template_preview_side_by_side(reference: Path, generated: Path, output: Path) -> None:
    left, right = _load_preview_pair(reference, generated)
    with left, right:
        _make_preview_side_by_side(left, right, output)


def _resize_template_preview_to_height(image, target_height: int):
    if image.height == target_height:
        return image
    ratio = target_height / float(image.height)
    width = max(1, int(round(image.width * ratio)))
    return image.resize((width, target_height))


def make_template_preview_comparison(reference: Path, generated: Path, output: Path) -> dict[str, object]:
    """Decode each PNG once for both the review image and diagnostic RMS."""
    left, right = _load_preview_pair(reference, generated)
    with left, right:
        _make_preview_side_by_side(left, right, output)
        return _preview_difference_metrics(left, right)
