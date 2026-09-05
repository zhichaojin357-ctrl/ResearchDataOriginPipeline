"""Numeric table helpers shared by template product preparation."""

from __future__ import annotations

from collections.abc import Iterator


def interpolate_sorted_grid(
    points: list[tuple[float, float]],
    grid: list[float],
) -> Iterator[float | None]:
    """Apply the existing linear interpolation rule to an ascending query grid.

    Keep the first point within 1e-12, including its tie behavior, and retain
    the original arithmetic order. Each source interval is visited only once.
    Both lists come from the sorted, finite shared-X table preparation.
    """
    index = 0
    for x_value in grid:
        if not points or x_value < points[0][0] or x_value > points[-1][0]:
            yield None
            continue
        while index < len(points):
            point_x, point_y = points[index]
            if abs(point_x - x_value) <= 1e-12:
                yield point_y
                break
            if point_x > x_value and index > 0:
                prev_x, prev_y = points[index - 1]
                span = point_x - prev_x
                if span == 0:
                    yield point_y
                else:
                    fraction = (x_value - prev_x) / span
                    yield prev_y + fraction * (point_y - prev_y)
                break
            index += 1
        else:
            yield points[-1][1]
