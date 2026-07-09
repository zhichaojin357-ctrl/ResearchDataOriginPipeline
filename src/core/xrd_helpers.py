from __future__ import annotations

import math
from pathlib import Path


def to_finite_float(value: object) -> float | None:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def interpolated_y(points: list[tuple[float, float]], x_value: float) -> float | None:
    if x_value < points[0][0] or x_value > points[-1][0]:
        return None
    for index, (point_x, point_y) in enumerate(points):
        if abs(point_x - x_value) <= 1e-12:
            return point_y
        if point_x > x_value and index > 0:
            prev_x, prev_y = points[index - 1]
            span = point_x - prev_x
            if span == 0:
                return point_y
            fraction = (x_value - prev_x) / span
            return prev_y + fraction * (point_y - prev_y)
    return points[-1][1]


def relative_path(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)
