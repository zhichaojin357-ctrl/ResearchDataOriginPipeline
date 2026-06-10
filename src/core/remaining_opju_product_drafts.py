from __future__ import annotations

import csv
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from src.core.opju_product_pilot import (
    ProductContext,
    TargetPairing,
    build_default_root_map,
    export_product_with_origin,
    _copy_inputs,
    _copy_reference,
    _csv_x_bounds,
    _forbidden_claims,
    _load_pairing_items,
    _manual_items,
    _product_output_path,
    _reference_policy_notes,
    _relative_to_run,
    _resolve_pairing_path,
    _root_for_label,
    _selected_relative_paths,
    _write_csv,
    _write_no_label_audit,
    _write_per_type_report,
    _write_product_metadata,
)
from src.core.output_sanitizer import scrub_output_text
from src.core.runtime_paths import create_run_output_layout, resolve_output_root
from src.core.table_reader import coerce_numeric_rows, read_table_with_metadata
from src.origin.operations import connect_origin, quote_labtalk
from src.origin.type_mimic import REMAINING_TYPE_MIMIC_SPECS
from src.processors.base import safe_name


REMAINING_TARGET_PRODUCT_KEYS = (
    "EIS",
    "Raman",
    "Mott-Schottky",
    "UV-vis DRS / Tauc",
    "PL",
    "photocurrent",
    "FTIR",
)

REMAINING_TYPE_DIRS = {
    "EIS": "EIS",
    "Raman": "Raman",
    "Mott-Schottky": "Mott_Schottky",
    "UV-vis DRS / Tauc": "UV_vis_DRS_Tauc",
    "PL": "PL",
    "photocurrent": "photocurrent",
    "FTIR": "FTIR",
    "reaction_condition_screening": "reaction_condition_screening",
    "HPLC/LC exported data": "HPLC_LC_deferred_or_generic",
}

PREVIOUS_COMPLETED_TYPES = ("BET", "XPS_in_situ", "XPS_non_in_situ", "XRD", "EPR")


@dataclass(frozen=True)
class RemainingOpjuProductDraftOptions:
    pairing_path: Path
    output_root: Path | None = None
    with_origin: bool = False
    timestamp: str | None = None
    previous_run_root: Path | None = None


@dataclass(frozen=True)
class ReferenceValidationResult:
    ok: bool
    decision: str
    reason: str
    details: dict[str, object]


ReferenceValidator = Callable[[TargetPairing], ReferenceValidationResult]
OriginExporter = Callable[[ProductContext], dict[str, object]]


def load_remaining_pairings(pairing_path: Path, root_map: dict[str, Path]) -> list[TargetPairing]:
    items = _load_pairing_items(pairing_path)
    selected: list[TargetPairing] = []
    seen: set[str] = set()
    for item in items:
        product_key = _remaining_product_key(item)
        if product_key is None or product_key in seen:
            continue
        data_root_label = str(item.get("selected_data_root_label") or "")
        opju_root_label = str(item.get("selected_opju_root_label") or "")
        data_root = _root_for_label(root_map, data_root_label)
        opju_root = _root_for_label(root_map, opju_root_label)
        raw_data_paths = [str(value) for value in item.get("selected_data_relative_paths") or []]
        opju_relative = str(item.get("selected_opju_relative_path") or "")
        if not raw_data_paths or not opju_relative:
            continue
        selected.append(
            TargetPairing(
                product_key=product_key,
                data_type=str(item.get("data_type") or ""),
                xps_subtype=str(item.get("xps_subtype") or ""),
                data_root_label=data_root_label,
                data_paths=[_resolve_pairing_path(data_root, value) for value in raw_data_paths],
                opju_root_label=opju_root_label,
                reference_opju=_resolve_pairing_path(opju_root, opju_relative),
                raw=dict(item),
            )
        )
        seen.add(product_key)
    return selected


def run_remaining_opju_product_drafts(
    project_root: Path,
    options: RemainingOpjuProductDraftOptions,
    *,
    root_map: dict[str, Path] | None = None,
    origin_exporter: OriginExporter | None = None,
    reference_validator: ReferenceValidator | None = None,
) -> dict[str, object]:
    project_root = project_root.resolve()
    roots = root_map or build_default_root_map(project_root)
    pairings = load_remaining_pairings(options.pairing_path, roots)
    output_root = resolve_output_root(project_root, explicit=options.output_root)
    previous_run = options.previous_run_root or _latest_previous_completed_run(output_root)
    layout = create_run_output_layout(
        project_root,
        scope="remaining_opju_product_drafts",
        command="remaining-opju-product-drafts",
        mode="with_origin" if options.with_origin else "no_origin",
        input_paths=[
            options.pairing_path,
            *[path for item in pairings for path in item.data_paths],
            *[item.reference_opju for item in pairings],
        ],
        timestamp=options.timestamp,
        no_origin=not options.with_origin,
        dry_run=False,
        output_base=output_root / "runs",
    )
    for directory in REMAINING_TYPE_DIRS.values():
        _ensure_type_dirs(layout.root / directory)
    _write_previous_completed_links(layout.root, previous_run)

    exporter = origin_exporter or export_product_with_origin
    validator = reference_validator or validate_mott_schottky_exemplar
    products: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    skipped: list[dict[str, object]] = []

    for pairing in pairings:
        if pairing.product_key == "Mott-Schottky":
            validation = validator(pairing)
            if not validation.ok:
                skipped.append(
                    {
                        "data_type": pairing.product_key,
                        "decision": validation.decision,
                        "reason": validation.reason,
                        "details": validation.details,
                    }
                )
                continue
        try:
            product = _prepare_remaining_product(layout.root, pairing)
            export_status: dict[str, object] = {"ok": False, "message": "Origin export skipped"}
            if options.with_origin:
                export_status = exporter(product)
            metadata = _write_product_metadata(layout.root, product, export_status)
            report = _write_per_type_report(layout.root, product, export_status)
            products.append(_product_summary(layout.root, product, export_status, metadata, report))
        except Exception as exc:
            failures.append({"product_key": pairing.product_key, "message": scrub_output_text(exc, output_root=layout.root)})

    hplc_deferred = _hplc_lc_deferred_items(options.pairing_path, roots)
    if hplc_deferred:
        skipped.append(
            {
                "data_type": "HPLC/LC exported data",
                "decision": "deferred_hplc_lc_pdf_only_no_opju",
                "reason": "Only PDF samples were present in the reviewed pairing; no OPJU exemplar was available.",
                "details": {"items": hplc_deferred},
            }
        )
    reaction_skip = _reaction_condition_skip(roots)
    skipped.append(reaction_skip)

    _write_hplc_lc_report(layout.root, hplc_deferred)
    label_audit = _write_no_label_audit(layout.root)
    _write_remaining_reports(layout.root, products, failures, skipped, bool(options.with_origin), label_audit, previous_run)
    label_audit = _write_no_label_audit(layout.root)
    _write_remaining_reports(layout.root, products, failures, skipped, bool(options.with_origin), label_audit, previous_run)
    return {
        "run_root": str(layout.root),
        "summary": {
            "product_count": len(products),
            "failure_count": len(failures),
            "skipped_count": len(skipped),
            "with_origin": bool(options.with_origin),
            "previous_run_root": str(previous_run) if previous_run else "",
        },
        "products": products,
        "failures": failures,
        "skipped": skipped,
    }


def validate_mott_schottky_exemplar(pairing: TargetPairing) -> ReferenceValidationResult:
    operations = connect_origin(entrypoint="Origin.Application", isolated=True, visible=False)
    try:
        load_result = operations.load_project(pairing.reference_opju)
        if not load_result.ok:
            return ReferenceValidationResult(
                False,
                "failed_mott_exemplar_load",
                load_result.message,
                {"reference_opju": str(pairing.reference_opju)},
            )
        pages = operations.list_worksheets().payload.get("pages", [])
        graph_pages = [str(item["name"]) for item in pages if item.get("type") == "graph"]
        axis_reads = []
        for graph_name in graph_pages[:5]:
            operations.run_labtalk(f'win -a "{quote_labtalk(graph_name)}";')
            x_text = str(operations.get_labtalk_variable("xb.text$").payload.get("value") or "")
            y_text = str(operations.get_labtalk_variable("yl.text$").payload.get("value") or "")
            axis_reads.append({"graph": graph_name, "x": x_text, "y": y_text})
        if _axis_reads_look_like_mott(axis_reads):
            return ReferenceValidationResult(True, "mott_exemplar_validated", "Mott-style axis text found.", {"axis_reads": axis_reads})
        return ReferenceValidationResult(
            False,
            "invalid_mott_exemplar_mismatched_type",
            "Origin readback did not show Mott-Schottky axis text; selected exemplar appears to be XRD or another graph type.",
            {"axis_reads": axis_reads},
        )
    finally:
        operations.close()


def _prepare_remaining_product(run_root: Path, pairing: TargetPairing) -> ProductContext:
    spec = REMAINING_TYPE_MIMIC_SPECS[pairing.product_key]
    type_root = run_root / REMAINING_TYPE_DIRS[pairing.product_key]
    _ensure_type_dirs(type_root)
    processed_data = type_root / "processed_data" / f"{spec.output_slug}.csv"
    input_copies = _copy_inputs(pairing.data_paths, type_root / "input_copies")
    reference_copy = _copy_reference(pairing.reference_opju, type_root / "reference_opju")
    headers, rows, labels = _build_remaining_processed_plot_table(pairing)
    _write_csv(processed_data, headers, rows)
    return ProductContext(
        product_key=pairing.product_key,
        slug=spec.output_slug,
        pairing=pairing,
        type_root=type_root,
        processed_data=processed_data,
        input_copies=input_copies,
        reference_opju_copy=reference_copy,
        reference_preview_png=type_root / "reference_exports" / f"{spec.output_slug}_reference_preview.png",
        origin_file=type_root / "origin_files" / f"{spec.output_slug}.opju",
        figure_tif=type_root / "figures_tif" / f"{spec.output_slug}.tif",
        preview_png=type_root / "figures_preview" / f"{spec.output_slug}_preview.png",
        x_label=labels["x_label"],
        y_label=labels["y_label"],
        graph_title=labels["title"],
        plot_type=labels.get("plot_type", "line"),
        x_descending=labels.get("x_descending", "false") == "true",
        y_ticks=labels.get("y_ticks", "true") == "true",
        y_tick_values=labels.get("y_tick_values", "true") == "true",
        legend_entries=[header.replace("_", " ") for header in headers[1:]],
        notes=labels.get("notes", "").splitlines() if labels.get("notes") else [],
    )


def _build_remaining_processed_plot_table(pairing: TargetPairing) -> tuple[list[str], list[list[float | str | None]], dict[str, str]]:
    if pairing.product_key == "EIS":
        result = read_table_with_metadata(pairing.data_paths[0])
        rows = _numeric_column_rows(result.rows, "z_real", ("z'", "z real", "zreal"), "minus_z_imag", ("-z''", "-z", "imag"))
        return ["z_real_ohm", "minus_z_imag_ohm"], rows, {
            "x_label": "Z' (ohm)",
            "y_label": "-Z'' (ohm)",
            "title": "EIS draft",
            "plot_type": "line+symbol",
            "notes": "Nyquist draft only; equivalent-circuit interpretation requires manual review.",
        }
    if pairing.product_key == "Raman":
        rows = _coerced_xy_rows(pairing.data_paths[0])
        return ["raman_shift_cm-1", "intensity"], rows, {
            "x_label": "Raman shift (cm-1)",
            "y_label": "Intensity (a.u.)",
            "title": "Raman draft",
            "plot_type": "line",
        }
    if pairing.product_key == "Mott-Schottky":
        rows = _coerced_xy_rows(pairing.data_paths[0])
        return ["potential_v", "signal"], rows, {
            "x_label": "Potential (V)",
            "y_label": "Signal (manual review)",
            "title": "Mott-Schottky draft",
            "plot_type": "line+symbol",
            "notes": "Carrier type and band positions are not inferred.",
        }
    if pairing.product_key == "UV-vis DRS / Tauc":
        rows = _data_points_rows(pairing.data_paths[0])
        return ["wavelength_nm", "signal"], rows, {
            "x_label": "Wavelength (nm)",
            "y_label": "Signal (a.u.)",
            "title": "UV-vis DRS draft",
            "plot_type": "line",
            "notes": "DRS/Tauc transform and bandgap interpretation require manual review.",
        }
    if pairing.product_key == "PL":
        rows = _coerced_xy_rows(pairing.data_paths[0])
        return ["wavelength_nm", "counts"], rows, {
            "x_label": "Wavelength (nm)",
            "y_label": "Counts",
            "title": "PL draft",
            "plot_type": "line",
        }
    if pairing.product_key == "photocurrent":
        rows = _coerced_xy_rows(pairing.data_paths[0])
        return ["time_s", "current_a"], rows, {
            "x_label": "Time (s)",
            "y_label": "Current (A)",
            "title": "Photocurrent draft",
            "plot_type": "line",
            "notes": "Light on/off segmentation requires manual review if labels are needed.",
        }
    if pairing.product_key == "FTIR":
        return _ftir_overlay_table(pairing.data_paths)
    raise ValueError(f"Unsupported remaining product key: {pairing.product_key}")


def _numeric_column_rows(
    rows: list[dict[str, str]],
    x_header: str,
    x_needles: tuple[str, ...],
    y_header: str,
    y_needles: tuple[str, ...],
) -> list[list[float | str | None]]:
    if not rows:
        raise ValueError("No rows were read from the selected data table.")
    columns = list(rows[0].keys())
    x_col = _pick_column(columns, x_needles)
    y_col = _pick_column(columns, y_needles)
    if x_col is None or y_col is None or x_col == y_col:
        numeric = coerce_numeric_rows(rows)
        if len(numeric) < 2:
            raise ValueError(f"Could not find numeric columns for {x_header}/{y_header}.")
        return [[x, y] for x, y in numeric]
    output = []
    for row in rows:
        x_value = _to_float(row.get(x_col, ""))
        y_value = _to_float(row.get(y_col, ""))
        if x_value is not None and y_value is not None:
            output.append([x_value, y_value])
    if len(output) < 2:
        raise ValueError(f"Fewer than 2 numeric rows for {x_col}/{y_col}.")
    return output


def _coerced_xy_rows(path: Path) -> list[list[float | str | None]]:
    result = read_table_with_metadata(path)
    numeric = coerce_numeric_rows(result.rows)
    if len(numeric) < 2:
        raise ValueError(f"Fewer than 2 numeric rows could be read from {path}")
    return [[x, y] for x, y in numeric]


def _data_points_rows(path: Path) -> list[list[float | str | None]]:
    text = _read_text(path)
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip().casefold() == "data points":
            start = index + 1
            break
    if start is None:
        return _coerced_xy_rows(path)
    output = []
    for line in lines[start + 1 :]:
        parts = [part for part in re.split(r"[,\t; ]+", line.strip()) if part]
        if len(parts) < 2:
            continue
        x_value = _to_float(parts[0])
        y_value = _to_float(parts[1])
        if x_value is not None and y_value is not None:
            output.append([x_value, y_value])
    if len(output) < 2:
        raise ValueError(f"Fewer than 2 data-point rows could be read from {path}")
    return output


def _ftir_overlay_table(paths: list[Path]) -> tuple[list[str], list[list[float | str | None]], dict[str, str]]:
    series = []
    for path in paths:
        rows = _coerced_xy_rows(path)
        series.append((safe_name(path.stem), rows))
    if not series:
        raise ValueError("No FTIR source files were selected.")
    point_count = min(len(rows) for _name, rows in series)
    headers = ["wavenumber_cm-1", *[f"{name}_transmittance" for name, _rows in series]]
    output = []
    for index in range(point_count):
        row = [series[0][1][index][0]]
        for _name, rows in series:
            row.append(rows[index][1])
        output.append(row)
    return headers, output, {
        "x_label": "Wavenumber (cm-1)",
        "y_label": "Transmittance (a.u.)",
        "title": "FTIR draft",
        "plot_type": "line",
        "x_descending": "true",
        "notes": "Wavenumber direction and peak labels require manual review.",
    }


def _product_summary(
    run_root: Path,
    product: ProductContext,
    export_status: dict[str, object],
    metadata: Path,
    report: Path,
) -> dict[str, object]:
    return {
        "product_key": product.product_key,
        "data_root_label": product.pairing.data_root_label,
        "selected_data_relative_paths": _selected_relative_paths(product.pairing, "selected_data_relative_paths"),
        "opju_root_label": product.pairing.opju_root_label,
        "selected_opju_relative_path": _selected_relative_paths(product.pairing, "selected_opju_relative_path"),
        "processed_data": _product_output_path(run_root, product.processed_data),
        "origin_file": _product_output_path(run_root, product.origin_file),
        "figure_tif": _product_output_path(run_root, product.figure_tif),
        "preview_png": _product_output_path(run_root, product.preview_png),
        "reference_opju_copy": _product_output_path(run_root, product.reference_opju_copy),
        "reference_preview_png": _product_output_path(run_root, product.reference_preview_png),
        "metadata": _product_output_path(run_root, metadata),
        "report": _product_output_path(run_root, report),
        "status": "success" if bool(export_status.get("ok")) else "origin_failed",
        "origin_message": str(export_status.get("message") or ""),
    }


def _write_remaining_reports(
    run_root: Path,
    products: list[dict[str, object]],
    failures: list[dict[str, str]],
    skipped: list[dict[str, object]],
    with_origin: bool,
    label_audit: dict[str, object],
    previous_run_root: Path | None,
) -> None:
    reports = run_root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    payload = {
        "with_origin": with_origin,
        "products": products,
        "failures": failures,
        "skipped": skipped,
        "product_count": len(products),
        "failure_count": len(failures),
        "visible_label_audit": label_audit,
        "previous_completed_run_id": previous_run_root.name if previous_run_root else "",
    }
    (reports / "remaining_opju_product_drafts_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_final_summary(run_root, products, failures, skipped, with_origin, label_audit, previous_run_root)
    _write_manual_review_checklist(run_root, products, failures, skipped, previous_run_root)
    _write_per_type_status(run_root, products, failures, skipped)
    _write_deferred_or_failed_types(run_root, failures, skipped)


def _write_final_summary(
    run_root: Path,
    products: list[dict[str, object]],
    failures: list[dict[str, str]],
    skipped: list[dict[str, object]],
    with_origin: bool,
    label_audit: dict[str, object],
    previous_run_root: Path | None,
) -> None:
    lines = [
        "# Final summary",
        "",
        f"- Products prepared: {len(products)}",
        f"- Failures: {len(failures)}",
        f"- Origin requested: {with_origin}",
        f"- Visible-label audit result: {'pass' if int(label_audit.get('hit_count', 0)) == 0 else 'fail'}",
        f"- Visible-label audit hit count: {label_audit.get('hit_count', 0)}",
        "- F-drive files modified: no",
        "- Original OPJU/OPJ files modified: no",
        "- Output products committed: no",
        f"- Previous completed run id: {previous_run_root.name if previous_run_root else 'not found'}",
        "",
        "## Products",
    ]
    for product in products:
        key = str(product["product_key"])
        source_rel = [str(item) for item in product.get("selected_data_relative_paths", []) if str(item)]
        opju_rel = [str(item) for item in product.get("selected_opju_relative_path", []) if str(item)]
        lines.extend(
            [
                f"### {key}",
                f"- Status: {product['status']}",
                f"- Failure reason: {product['origin_message'] or 'none'}",
                f"- Selected data root label: {product.get('data_root_label', 'see metadata')}",
                f"- Selected data: {', '.join(source_rel) if source_rel else 'see metadata'}",
                f"- Selected OPJU root label: {product.get('opju_root_label', 'see metadata')}",
                f"- Selected OPJU: {', '.join(opju_rel) if opju_rel else 'see metadata'}",
                f"- Generated OPJU: {_relative_to_run(run_root, Path(str(product['origin_file'])))}",
                f"- Generated TIF: {_relative_to_run(run_root, Path(str(product['figure_tif'])))}",
                f"- Generated PNG preview: {_relative_to_run(run_root, Path(str(product['preview_png'])))}",
                f"- Manual review report: {_relative_to_run(run_root, Path(str(product['report'])))}",
                f"- Manual review needs: {'; '.join(_manual_items(key))}",
                f"- Forbidden scientific claims avoided: {'; '.join(_forbidden_claims(key))}",
                f"- Visible-label audit result: {'pass' if int(label_audit.get('hit_count', 0)) == 0 else 'fail'}",
                "",
            ]
        )
    lines.extend(["## Deferred or failed", ""])
    for failure in failures:
        lines.append(f"- {failure['product_key']}: {failure['message']}")
    for item in skipped:
        lines.append(f"- {item['data_type']}: {item['decision']} - {item.get('reason', '')}")
    if not failures and not skipped:
        lines.append("- none")
    (run_root / "reports" / "final_summary.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_manual_review_checklist(
    run_root: Path,
    products: list[dict[str, object]],
    failures: list[dict[str, str]],
    skipped: list[dict[str, object]],
    previous_run_root: Path | None,
) -> None:
    lines = [
        "# Manual review checklist",
        "",
        f"- Previous completed run id: {previous_run_root.name if previous_run_root else 'not found'}",
        "",
    ]
    for product in products:
        key = str(product["product_key"])
        lines.extend([f"## {key}", ""])
        for item in _manual_items(key):
            lines.append(f"- {item}")
        for item in _reference_policy_notes(key):
            lines.append(f"- {item}")
        lines.append("")
    if skipped:
        lines.extend(["## Deferred or skipped", ""])
        for item in skipped:
            lines.append(f"- {item['data_type']}: {item['decision']} - {item.get('reason', '')}")
        lines.append("")
    if failures:
        lines.extend(["## Failed preparations", ""])
        for failure in failures:
            lines.append(f"- {failure['product_key']}: {failure['message']}")
        lines.append("")
    text = "\n".join(lines).rstrip() + "\n"
    (run_root / "reports" / "manual_review_checklist.md").write_text(text, encoding="utf-8")
    (run_root / "reports" / "manual_calibration_checklist.md").write_text(text, encoding="utf-8")


def _write_per_type_status(
    run_root: Path,
    products: list[dict[str, object]],
    failures: list[dict[str, str]],
    skipped: list[dict[str, object]],
) -> None:
    with (run_root / "reports" / "per_type_status.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["product_key", "status", "origin_file", "figure_tif", "preview_png", "reason"])
        for product in products:
            writer.writerow(
                [
                    product["product_key"],
                    product["status"],
                    _relative_to_run(run_root, Path(str(product["origin_file"]))),
                    _relative_to_run(run_root, Path(str(product["figure_tif"]))),
                    _relative_to_run(run_root, Path(str(product["preview_png"]))),
                    product.get("origin_message", ""),
                ]
            )
        for failure in failures:
            writer.writerow([failure["product_key"], "failed", "", "", "", failure["message"]])
        for item in skipped:
            writer.writerow([item["data_type"], item["decision"], "", "", "", item.get("reason", "")])


def _write_deferred_or_failed_types(
    run_root: Path,
    failures: list[dict[str, str]],
    skipped: list[dict[str, object]],
) -> None:
    lines = ["# Deferred or failed types", ""]
    if not failures and not skipped:
        lines.append("- none")
    for failure in failures:
        lines.append(f"- {failure['product_key']}: {failure['message']}")
    for item in skipped:
        lines.append(f"- {item['data_type']}: {item['decision']} - {item.get('reason', '')}")
    (run_root / "reports" / "deferred_or_failed_types.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_hplc_lc_report(run_root: Path, items: list[dict[str, object]]) -> None:
    lines = [
        "# Deferred HPLC/LC",
        "",
        "- Decision: deferred_hplc_lc_pdf_only_no_opju",
        "- Origin figure generated: no",
        "- OCR performed: no",
        "- Conversion/selectivity/yield calculated: no",
        "- Product identity assigned: no",
        "",
        "## Reviewed samples",
    ]
    if not items:
        lines.append("- none")
    for item in items:
        lines.append(f"- {item['relative_path']} ({item['suffix']}, {item['size_bytes']} bytes)")
    (run_root / "reports" / "deferred_hplc_lc.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_previous_completed_links(run_root: Path, previous_run: Path | None) -> None:
    links_dir = run_root / "previous_completed_links"
    links_dir.mkdir(parents=True, exist_ok=True)
    lines = ["# Previous completed products", ""]
    if previous_run is None:
        lines.append("- Previous run: not found")
    else:
        lines.append(f"- Previous run id: {previous_run.name}")
        lines.append("")
        for product_type in PREVIOUS_COMPLETED_TYPES:
            lines.append(f"- {product_type}: see previous completed run")
    (links_dir / "previous_completed_products.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _hplc_lc_deferred_items(pairing_path: Path, root_map: dict[str, Path]) -> list[dict[str, object]]:
    items = []
    for item in _load_pairing_items(pairing_path):
        if str(item.get("data_type") or "") != "HPLC/LC exported data":
            continue
        root_label = str(item.get("selected_data_root_label") or "")
        root = root_map.get(root_label)
        for rel in item.get("selected_data_relative_paths") or []:
            path = _resolve_pairing_path(root, str(rel)) if root else Path(str(rel))
            items.append(
                {
                    "root_label": root_label,
                    "relative_path": str(rel),
                    "suffix": path.suffix.casefold(),
                    "size_bytes": path.stat().st_size if path.exists() else 0,
                    "exists": path.exists(),
                }
            )
    return items


def _reaction_condition_skip(root_map: dict[str, Path]) -> dict[str, object]:
    f_root = root_map.get("f_drive_detection")
    reaction_root = (f_root / "\u5149\u53cd\u5e94\u7684\u6761\u4ef6\u7b5b\u9009") if f_root else None
    data_candidates: list[str] = []
    opju_candidates: list[str] = []
    if reaction_root is not None and reaction_root.exists():
        for path in reaction_root.rglob("*"):
            if not path.is_file():
                continue
            suffix = path.suffix.casefold()
            if suffix == ".opju":
                opju_candidates.append(str(path.relative_to(f_root)))
            elif suffix in {".csv", ".txt", ".xlsx", ".xls"}:
                data_candidates.append(str(path.relative_to(f_root)))
    return {
        "data_type": "reaction_condition_screening",
        "decision": "skipped_no_clear_data_pair",
        "reason": "OPJU candidates exist, but no clear exported data table was found in the reviewed reaction-condition folder.",
        "details": {
            "opju_candidate_count": len(opju_candidates),
            "data_candidate_count": len(data_candidates),
            "opju_candidates_sample": opju_candidates[:10],
            "data_candidates_sample": data_candidates[:10],
        },
    }


def _latest_previous_completed_run(output_root: Path) -> Path | None:
    runs = output_root / "runs"
    if not runs.exists():
        return None
    candidates = []
    for item in runs.iterdir():
        if not item.is_dir():
            continue
        if all((item / product_type).is_dir() for product_type in PREVIOUS_COMPLETED_TYPES):
            candidates.append(item)
    return sorted(candidates, key=lambda path: (path.stat().st_mtime, path.name), reverse=True)[0] if candidates else None


def _remaining_product_key(item: dict[str, Any]) -> str | None:
    data_type = str(item.get("data_type") or "")
    return data_type if data_type in REMAINING_TARGET_PRODUCT_KEYS else None


def _ensure_type_dirs(type_root: Path) -> None:
    for name in (
        "input_copies",
        "reference_opju",
        "reference_exports",
        "processed_data",
        "metadata",
        "origin_files",
        "figures_tif",
        "figures_preview",
        "reports",
    ):
        (type_root / name).mkdir(parents=True, exist_ok=True)


def _axis_reads_look_like_mott(axis_reads: list[dict[str, str]]) -> bool:
    combined = " ".join(f"{item.get('x', '')} {item.get('y', '')}" for item in axis_reads).casefold()
    good_tokens = ("mott", "schottky", "potential", "capacit", "c^-", "c-2", "1/c")
    bad_tokens = ("2θ", "2theta", "intensity")
    return any(token in combined for token in good_tokens) and not (
        any(token in combined for token in bad_tokens) and not any(token in combined for token in ("potential", "capacit"))
    )


def _pick_column(columns: list[str], needles: tuple[str, ...]) -> str | None:
    normalized = [(column, _normalize(column)) for column in columns]
    for needle in needles:
        norm_needle = _normalize(needle)
        for original, column in normalized:
            if norm_needle and norm_needle in column:
                return original
    return None


def _normalize(value: object) -> str:
    text = str(value).casefold()
    text = text.replace("\u03a9".casefold(), "ohm").replace("\u60df", "ohm")
    text = re.sub(r"[\[\]\(\),;:/\\_\s]+", " ", text)
    return text.strip()


def _to_float(value: object) -> float | None:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk", "cp936"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8-sig", errors="replace")
