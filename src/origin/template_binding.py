from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
READY_STATUS = "mapping_readback_complete"


@dataclass(frozen=True)
class TemplatePlotBinding:
    layer_index: int
    plot_index: int
    x_dataset: str
    y_dataset: str
    row_from: int
    row_to: int
    source_series_index: int
    semantic_role: str

    def to_dict(self) -> dict[str, object]:
        return {
            "layer_index": self.layer_index,
            "plot_index": self.plot_index,
            "x_dataset": self.x_dataset,
            "y_dataset": self.y_dataset,
            "row_from": self.row_from,
            "row_to": self.row_to,
            "source_series_index": self.source_series_index,
            "semantic_role": self.semantic_role,
        }


@dataclass(frozen=True)
class TemplateBindingContract:
    product_key: str
    status: str
    graph_page: str
    reference_opju_sha256: str
    source_series_count: int = 0
    source_schema: dict[str, object] = field(default_factory=dict)
    plots: tuple[TemplatePlotBinding, ...] = ()
    reason: str = ""

    @property
    def ready(self) -> bool:
        return self.status == READY_STATUS

    def to_dict(self) -> dict[str, object]:
        return {
            "product_key": self.product_key,
            "status": self.status,
            "ready": self.ready,
            "graph_page": self.graph_page,
            "reference_opju_sha256": self.reference_opju_sha256,
            "source_series_count": self.source_series_count,
            "source_schema": dict(self.source_schema),
            "plots": [plot.to_dict() for plot in self.plots],
            "reason": self.reason,
        }


@dataclass(frozen=True)
class TemplateBindingResolution:
    ok: bool
    status: str
    message: str
    contract: TemplateBindingContract | None = None
    plot_mappings: tuple[dict[str, object], ...] = ()
    failures: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "status": self.status,
            "message": self.message,
            "contract": self.contract.to_dict() if self.contract is not None else {},
            "plot_mappings": [
                {key: value for key, value in mapping.items()}
                for mapping in self.plot_mappings
            ],
            "failures": list(self.failures),
        }


def default_template_binding_contract_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "templates"
        / "origin_styles"
        / "binding_contracts"
        / "BET.json"
    )


def load_template_binding_contracts(
    path: str | Path | None = None,
) -> dict[str, TemplateBindingContract]:
    contract_path = Path(path) if path is not None else default_template_binding_contract_path()
    try:
        payload = json.loads(contract_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Template binding contract file is missing: {contract_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Template binding contract file is not valid JSON: {contract_path}") from exc
    if not isinstance(payload, dict) or int(payload.get("schema_version", 0) or 0) != 1:
        raise ValueError("Template binding contracts require schema_version=1")
    raw_contracts = payload.get("contracts")
    if not isinstance(raw_contracts, list):
        raise ValueError("Template binding contract file must contain a contracts list")
    contracts: dict[str, TemplateBindingContract] = {}
    for raw in raw_contracts:
        if not isinstance(raw, dict):
            raise ValueError("Every template binding contract must be an object")
        contract = _parse_contract(raw)
        key = _product_key(contract.product_key)
        if key in contracts:
            raise ValueError(f"Duplicate template binding contract: {contract.product_key}")
        contracts[key] = contract
    return contracts


def resolve_template_binding_contract(
    product_key: str,
    graph_page: str,
    plot_mappings: list[dict[str, object]] | tuple[dict[str, object], ...],
    *,
    path: str | Path | None = None,
) -> TemplateBindingResolution:
    contracts = load_template_binding_contracts(path)
    contract = contracts.get(_product_key(product_key))
    if contract is None:
        return TemplateBindingResolution(
            False,
            "missing_contract",
            f"No explicit template binding contract exists for {product_key}.",
        )
    if not contract.ready:
        message = contract.reason or f"Template binding contract is {contract.status}."
        return TemplateBindingResolution(
            False,
            contract.status,
            message,
            contract=contract,
            failures=(message,),
        )
    if str(graph_page).casefold() != contract.graph_page.casefold():
        message = (
            f"Template graph page {graph_page!r} does not match the reviewed contract "
            f"{contract.graph_page!r}."
        )
        return TemplateBindingResolution(
            False,
            "graph_page_mismatch",
            message,
            contract=contract,
            failures=(message,),
        )

    actual_by_plot: dict[tuple[int, int], dict[str, object]] = {}
    failures: list[str] = []
    for raw in plot_mappings:
        if not isinstance(raw, dict):
            failures.append("Origin returned a non-object plot mapping.")
            continue
        try:
            key = (int(raw.get("layer_index")), int(raw.get("plot_index")))
        except (TypeError, ValueError):
            failures.append("Origin returned a plot mapping without numeric layer/plot indices.")
            continue
        if key in actual_by_plot:
            failures.append(f"Origin returned duplicate mapping for layer {key[0]} plot {key[1]}.")
            continue
        actual_by_plot[key] = dict(raw)

    expected_keys = {(plot.layer_index, plot.plot_index) for plot in contract.plots}
    actual_keys = set(actual_by_plot)
    missing = sorted(expected_keys - actual_keys)
    unexpected = sorted(actual_keys - expected_keys)
    if missing:
        failures.append(f"Missing contracted plots: {missing}.")
    if unexpected:
        failures.append(f"Unexpected plots outside the contract: {unexpected}.")

    resolved: list[dict[str, object]] = []
    for plot in contract.plots:
        key = (plot.layer_index, plot.plot_index)
        actual = actual_by_plot.get(key)
        if actual is None:
            continue
        actual_x = str(actual.get("x_dataset") or "").strip()
        actual_y = str(actual.get("y_dataset") or "").strip()
        try:
            actual_from = int(actual.get("row_from"))
            actual_to = int(actual.get("row_to"))
        except (TypeError, ValueError):
            actual_from, actual_to = 0, -1
        if actual_x.casefold() != plot.x_dataset.casefold():
            failures.append(
                f"Layer {plot.layer_index} plot {plot.plot_index} X dataset is {actual_x!r}, "
                f"expected {plot.x_dataset!r}."
            )
        if actual_y.casefold() != plot.y_dataset.casefold():
            failures.append(
                f"Layer {plot.layer_index} plot {plot.plot_index} Y dataset is {actual_y!r}, "
                f"expected {plot.y_dataset!r}."
            )
        if (actual_from, actual_to) != (plot.row_from, plot.row_to):
            failures.append(
                f"Layer {plot.layer_index} plot {plot.plot_index} row range is "
                f"{actual_from}:{actual_to}, expected {plot.row_from}:{plot.row_to}."
            )
        resolved.append(
            {
                **actual,
                "source_series_index": plot.source_series_index,
                "semantic_role": plot.semantic_role,
                "contract_x_dataset": plot.x_dataset,
                "contract_y_dataset": plot.y_dataset,
                "contract_row_from": plot.row_from,
                "contract_row_to": plot.row_to,
            }
        )

    if failures:
        return TemplateBindingResolution(
            False,
            "mapping_mismatch",
            "; ".join(failures),
            contract=contract,
            plot_mappings=tuple(resolved),
            failures=tuple(failures),
        )
    return TemplateBindingResolution(
        True,
        "ready",
        "Origin plot mappings match the explicit reviewed binding contract.",
        contract=contract,
        plot_mappings=tuple(resolved),
    )


def validate_template_source_bindings(
    contract: TemplateBindingContract,
    headers: list[str] | tuple[str, ...],
    source_pairs: list[tuple[int, int]] | tuple[tuple[int, int], ...],
) -> dict[str, object]:
    """Validate processed source columns before a contracted OPJU replacement.

    This gate is intentionally separate from target-plot validation.  A graph
    can match the reviewed X/Y datasets while the processed columns are still
    semantically misordered.
    """

    schema = dict(contract.source_schema)
    if str(schema.get("status") or "") != "ready":
        reason = str(schema.get("reason") or "source binding contract is not ready")
        return {
            "ok": False,
            "status": str(schema.get("status") or "missing"),
            "message": reason,
            "source_bindings": [],
        }
    if str(schema.get("layout") or "") != "paired_xy_columns":
        return {
            "ok": False,
            "status": "unsupported_source_layout",
            "message": f"Unsupported source layout: {schema.get('layout')!r}",
            "source_bindings": [],
        }
    if len(source_pairs) != contract.source_series_count:
        return {
            "ok": False,
            "status": "source_series_count_mismatch",
            "message": (
                f"Processed source has {len(source_pairs)} X/Y pairs; contract requires "
                f"{contract.source_series_count}."
            ),
            "source_bindings": [],
        }

    x_suffix = str(schema.get("x_header_suffix") or "")
    y_suffix = str(schema.get("y_header_suffix") or "")
    transform = str(schema.get("transform") or "")
    if not x_suffix or not y_suffix or not transform:
        return {
            "ok": False,
            "status": "incomplete_source_schema",
            "message": "Source schema requires X/Y header suffixes and transform provenance.",
            "source_bindings": [],
        }

    failures: list[str] = []
    identities: list[str] = []
    bindings: list[dict[str, object]] = []
    for series_index, raw_pair in enumerate(source_pairs, start=1):
        try:
            x_index, y_index = int(raw_pair[0]), int(raw_pair[1])
        except (TypeError, ValueError, IndexError):
            failures.append(f"Source series {series_index} has an invalid X/Y pair.")
            continue
        if min(x_index, y_index) < 0 or max(x_index, y_index) >= len(headers):
            failures.append(f"Source series {series_index} references unavailable columns.")
            continue
        x_header = str(headers[x_index]).strip()
        y_header = str(headers[y_index]).strip()
        if not x_header.endswith(x_suffix):
            failures.append(
                f"Source series {series_index} X header {x_header!r} does not end with {x_suffix!r}."
            )
        if not y_header.endswith(y_suffix):
            failures.append(
                f"Source series {series_index} Y header {y_header!r} does not end with {y_suffix!r}."
            )
        x_identity = x_header[: -len(x_suffix)] if x_suffix and x_header.endswith(x_suffix) else ""
        y_identity = y_header[: -len(y_suffix)] if y_suffix and y_header.endswith(y_suffix) else ""
        if not x_identity or x_identity != y_identity:
            failures.append(
                f"Source series {series_index} X/Y headers do not share one nonempty identity prefix."
            )
        identities.append(x_identity)
        bindings.append(
            {
                "source_series_index": series_index,
                "source_x_column_index": x_index,
                "source_y_column_index": y_index,
                "source_x_header": x_header,
                "source_y_header": y_header,
                "source_identity": x_identity,
                "transform": transform,
            }
        )
    nonempty_identities = [identity.casefold() for identity in identities if identity]
    if len(nonempty_identities) != len(set(nonempty_identities)):
        failures.append("Processed source series identities are not unique.")
    return {
        "ok": not failures,
        "status": "ready" if not failures else "source_identity_mismatch",
        "message": (
            "Processed source X/Y headers match the explicit source schema."
            if not failures
            else "; ".join(failures)
        ),
        "layout": "paired_xy_columns",
        "transform": transform,
        "source_bindings": bindings,
        "failures": failures,
    }


def _parse_contract(raw: dict[str, Any]) -> TemplateBindingContract:
    product_key = str(raw.get("product_key") or "").strip()
    status = str(raw.get("status") or "").strip()
    graph_page = str(raw.get("graph_page") or "").strip()
    reference_hash = str(raw.get("reference_opju_sha256") or "").strip().casefold()
    reason = str(raw.get("reason") or "").strip()
    if not product_key or not status or not graph_page:
        raise ValueError("Template binding contract requires product_key, status, and graph_page")
    if _SHA256_RE.fullmatch(reference_hash) is None:
        raise ValueError(f"Template binding contract {product_key} has an invalid reference OPJU hash")
    raw_source_schema = raw.get("source_schema")
    if raw_source_schema is not None and not isinstance(raw_source_schema, dict):
        raise ValueError(f"Template binding contract {product_key} source_schema must be an object")
    source_schema = dict(raw_source_schema or {})

    raw_plots = raw.get("plots")
    plots: list[TemplatePlotBinding] = []
    if raw_plots is not None:
        if not isinstance(raw_plots, list):
            raise ValueError(f"Template binding contract {product_key} plots must be a list")
        for raw_plot in raw_plots:
            if not isinstance(raw_plot, dict):
                raise ValueError(f"Template binding contract {product_key} contains a non-object plot")
            plot = TemplatePlotBinding(
                layer_index=_positive_int(raw_plot.get("layer_index"), "layer_index", product_key),
                plot_index=_positive_int(raw_plot.get("plot_index"), "plot_index", product_key),
                x_dataset=str(raw_plot.get("x_dataset") or "").strip(),
                y_dataset=str(raw_plot.get("y_dataset") or "").strip(),
                row_from=_positive_int(raw_plot.get("row_from"), "row_from", product_key),
                row_to=_positive_int(raw_plot.get("row_to"), "row_to", product_key),
                source_series_index=_positive_int(
                    raw_plot.get("source_series_index"),
                    "source_series_index",
                    product_key,
                ),
                semantic_role=str(raw_plot.get("semantic_role") or "").strip(),
            )
            if not plot.x_dataset or not plot.y_dataset or not plot.semantic_role:
                raise ValueError(
                    f"Template binding contract {product_key} plot requires X/Y datasets and semantic_role"
                )
            if plot.row_to < plot.row_from:
                raise ValueError(f"Template binding contract {product_key} has an inverted row range")
            plots.append(plot)

    source_series_count = int(raw.get("source_series_count", 0) or 0)
    if status == READY_STATUS:
        if not plots or source_series_count <= 0:
            raise ValueError(
                f"Ready template binding contract {product_key} requires plots and source_series_count"
            )
        source_indices = {plot.source_series_index for plot in plots}
        if source_indices != set(range(1, source_series_count + 1)):
            raise ValueError(
                f"Template binding contract {product_key} source series must cover 1..{source_series_count}"
            )
    elif not reason:
        raise ValueError(f"Blocked template binding contract {product_key} requires a reason")
    return TemplateBindingContract(
        product_key=product_key,
        status=status,
        graph_page=graph_page,
        reference_opju_sha256=reference_hash,
        source_series_count=source_series_count,
        source_schema=source_schema,
        plots=tuple(plots),
        reason=reason,
    )


def _positive_int(value: object, field_name: str, product_key: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Template binding contract {product_key} has a nonnumeric {field_name}"
        ) from exc
    if number <= 0:
        raise ValueError(f"Template binding contract {product_key} requires positive {field_name}")
    return number


def _product_key(value: str) -> str:
    return str(value).strip().casefold().replace("-", "_").replace(" ", "_").replace("/", "_")
