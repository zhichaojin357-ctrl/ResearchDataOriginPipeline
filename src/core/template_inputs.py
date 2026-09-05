"""Reuse immutable preparation inputs during one template product export.

The owning exporter opens and closes the scope.  Data transforms explicitly
invalidate the processed table before any later read; nothing survives a job.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from src.origin.template_binding import (
    TemplateBindingContract,
    default_template_binding_contract_path,
    load_template_binding_contracts as _load_contracts,
)


@dataclass
class TemplateInputCache:
    tables: dict[Path, tuple[list[str], list[list[object]]]] = field(default_factory=dict)
    contracts: dict[Path, dict[str, TemplateBindingContract]] = field(default_factory=dict)
    bindings: dict[tuple[int, str], dict[str, object]] = field(default_factory=dict)


_input_cache: ContextVar[TemplateInputCache | None] = ContextVar("template_inputs", default=None)


@contextmanager
def template_input_scope() -> Iterator[TemplateInputCache]:
    cache = TemplateInputCache()
    token = _input_cache.set(cache)
    try:
        yield cache
    finally:
        _input_cache.reset(token)


def current_template_inputs() -> TemplateInputCache | None:
    return _input_cache.get()


def invalidate_processed_table(path: Path) -> None:
    cache = _input_cache.get()
    if cache is not None:
        cache.tables.pop(Path(path), None)
        cache.bindings.clear()


def load_template_binding_contracts(
    path: str | Path | None = None,
) -> dict[str, TemplateBindingContract]:
    source = Path(path) if path is not None else default_template_binding_contract_path()
    cache = _input_cache.get()
    if cache is None:
        return _load_contracts(source)
    if source not in cache.contracts:
        cache.contracts[source] = _load_contracts(source)
    return cache.contracts[source]
