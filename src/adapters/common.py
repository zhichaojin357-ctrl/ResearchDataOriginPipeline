from __future__ import annotations

import importlib
import importlib.metadata as metadata
import importlib.util
from collections.abc import Iterable
from functools import lru_cache
from typing import Any


FORBIDDEN_CLAIM_TOKENS = (
    "valence assignment",
    "radical assignment",
    "phase assignment",
    "crystal-plane assignment",
    "product identification",
    "heterojunction mechanism",
    "carrier separation conclusion",
    "recombination conclusion",
    "cb/vb assignment",
)


@lru_cache(maxsize=None)
def is_module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


@lru_cache(maxsize=None)
def import_optional(module_name: str) -> tuple[Any | None, str | None]:
    try:
        return importlib.import_module(module_name), None
    except Exception as exc:
        return None, str(exc)


@lru_cache(maxsize=None)
def version_for(package_name: str, module_name: str | None = None) -> str | None:
    for name in (package_name, package_name.lower(), module_name or ""):
        if not name:
            continue
        try:
            return metadata.version(name)
        except metadata.PackageNotFoundError:
            continue
    return None


def metadata_provenance(
    *,
    adapter: str,
    package: str,
    module: str,
    version: str | None,
    method: str,
    parameters: dict[str, Any] | None = None,
    fallback_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "adapter": adapter,
        "package": package,
        "module": module,
        "version": version,
        "method": method,
        "parameters": parameters or {},
        "fallback_reason": fallback_reason,
        "claim_policy": "candidate metrics only; scientific interpretation requires manual review",
        "forbidden_claims_enforced": list(FORBIDDEN_CLAIM_TOKENS),
    }


def contains_forbidden_claims(values: Iterable[object]) -> bool:
    text = " ".join(str(value).casefold() for value in values)
    return any(token in text for token in FORBIDDEN_CLAIM_TOKENS)
