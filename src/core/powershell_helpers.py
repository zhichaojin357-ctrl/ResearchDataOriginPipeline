from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path


def ps_quote(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def ps_array(values: Iterable[str | Path]) -> str:
    return "@(" + ", ".join(ps_quote(value) for value in values) + ")"


def ps_int_array(values: Iterable[int]) -> str:
    return "@(" + ", ".join(str(int(value)) for value in values) + ")"
