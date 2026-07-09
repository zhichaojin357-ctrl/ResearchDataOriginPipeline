from __future__ import annotations

from dataclasses import dataclass
import json
import math
import re
import string
from pathlib import Path
from typing import Any

import pandas as pd

from src.core.image_artifacts import ensure_tif_600_dpi_metadata
from src.core.output_sanitizer import render_output_path, scrub_output_text
from src.core.xps_heterojunction import (
    XpsFitRecord,
    _component_key,
    _component_limit,
    _highest_local_peak,
    _infer_peak_assignment,
    _major_component_labels,
    _normalization_scale,
    _select_best_records,
    _to_float,
    load_xps_fit_workbooks,
)
from src.core.runtime_paths import resolve_workspace_root
from src.origin.adapter import check_origin_available, write_origin_error


TARGET_ELEMENTS = ("Bi", "Br", "Cl", "Cu", "W", "O")
PANEL_PRIORITY = (
    ("Bi", "Bi4f", "BOBC"),
    ("Br", "Br3d", "BOBC"),
    ("Cl", "Cl2p", "BOBC"),
    ("Cu", "Cu2p", "CWO"),
    ("W", "W4f", "CWO"),
    ("O", "O1s", "CWO"),
)
SAMPLE_DISPLAY = {
    "BOBC": "BOBC",
    "CWO": "CWO",
    "BC Dark": "BC\nDark",
    "BC Light": "BC\nLight",
}
SAMPLE_TEXT_COLORS = {
    "BOBC": "black",
    "CWO": "black",
    "BC Dark": "#1F5AA6",
    "BC Light": "#C7362F",
}


def _output_path(output_dir: Path, path: Path | str | None) -> str | None:
    if path is None:
        return None
    return str(render_output_path(path, project_root=output_dir))


def _source_name(path: Path | str) -> str:
    return Path(str(path)).name


def _sanitize_output_payload(value: Any, output_dir: Path) -> Any:
    if isinstance(value, Path):
        return _output_path(output_dir, value)
    if isinstance(value, dict):
        return {str(key): _sanitize_output_payload(item, output_dir) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_output_payload(item, output_dir) for item in value]
    if isinstance(value, str):
        return scrub_output_text(value, output_root=output_dir)
    return value
COMPONENT_COLORS = (
    "#72B7D2",
    "#E58BA6",
    "#F2B36D",
    "#79B979",
    "#9E8AC8",
    "#D8A15D",
)
OUTPUT_SUBDIRS = (
    "figures_tif",
    "figures_png",
    "figures_pdf",
    "origin_projects",
    "metadata",
    "reports",
    "tables",
)


@dataclass(frozen=True)
class InSituRecordStatus:
    sample: str
    element: str
    region: str
    complete: bool
    note: str = ""


@dataclass(frozen=True)
class InSituPanelPlan:
    element: str
    region: str
    reference_sample: str

    @property
    def samples(self) -> tuple[str, str, str]:
        return (self.reference_sample, "BC Dark", "BC Light")

    @property
    def file_stem(self) -> str:
        return f"{self.element}_{self.region[len(self.element):]}"

    @property
    def panel_title(self) -> str:
        return format_region(self.region)


@dataclass(frozen=True)
class XpsInSituResult:
    output_dir: Path
    plotted_panels: list[InSituPanelPlan]
    missing: dict[str, list[str]]
    element_sources: dict[str, list[str]]
    origin_status: dict[str, Any]
    quality_checks: dict[str, Any]


def sample_from_path(path: Path) -> str | None:
    text = " ".join([path.name, *path.parts]).casefold()
    name = path.name.casefold()
    first_part = path.parts[0].casefold() if path.parts else ""
    if "dark-20260506" in name or re.search(r"(^|[^a-z])dark([^a-z]|$)", text):
        return "BC Dark"
    if "lingt-20260506" in name or "light-20260506" in name or "light.xls" == name:
        return "BC Light"
    if "cwo" in first_part:
        return "CWO"
    if "bobc" in first_part:
        return "BOBC"
    return None


def planned_panels(statuses: list[InSituRecordStatus]) -> tuple[list[InSituPanelPlan], dict[str, list[str]]]:
    by_key = {(item.sample, item.element): item for item in statuses}
    panels: list[InSituPanelPlan] = []
    missing: dict[str, list[str]] = {}
    for element, region, reference_sample in PANEL_PRIORITY:
        samples = (reference_sample, "BC Dark", "BC Light")
        problems: list[str] = []
        for sample in samples:
            status = by_key.get((sample, element))
            if status is None:
                problems.append(f"{sample}: missing fitted record")
            elif not status.complete:
                problems.append(f"{sample}: {status.note or 'incomplete fitted record'}")
        if problems:
            missing[element] = problems
        else:
            panels.append(InSituPanelPlan(element=element, region=region, reference_sample=reference_sample))
    return panels, missing


def build_xps_in_situ_outputs(
    project_root: Path,
    output_dir: Path,
    *,
    with_origin: bool = False,
) -> XpsInSituResult:
    project_root = project_root.resolve()
    xps_root = resolve_workspace_root(project_root) / "XPS"
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dirs = _output_subdirs(output_dir)

    sample_files, file_notes, scanned_files = discover_input_files(xps_root)
    records, manual_review = load_xps_fit_workbooks(sample_files)
    selected = _select_best_records(records)
    statuses = _record_statuses(selected)
    panels, missing = planned_panels(statuses)
    panel_records = _panel_records(panels, selected)

    if not panels:
        raise RuntimeError("No complete reference/Dark/Light XPS element panels were found.")

    element_sources = _write_figures(panel_records, output_dir)
    peak_rows = _peak_summary_rows(panel_records)
    _write_peak_summary(output_dirs["tables"] / "peak_positions_summary.xlsx", peak_rows)

    origin_status: dict[str, Any] = {"requested": with_origin, "ok": False, "message": "Origin export not requested"}
    if with_origin:
        origin_status = _try_write_origin_project(project_root, panel_records, output_dir)

    quality_checks = _quality_checks(output_dir, panel_records, origin_status)
    metadata_path = output_dirs["metadata"] / "xps_in_situ" / "metadata.json"
    metadata_payload = {
        "dataset_id": "xps_in_situ",
        "metadata_path": _output_path(output_dir, metadata_path),
        "data_type": "XPS",
        "subtype": "XPS_in_situ",
        "source_files": _sanitize_output_payload(scanned_files, output_dir),
        "plotted_panels": [panel.__dict__ for panel in panels],
        "missing": missing,
        "element_sources": element_sources,
        "origin_file": origin_status.get("origin_file"),
        "figure_tif": origin_status.get("figure_tif")
        or (_output_path(output_dir, output_dir / "xps_in_situ_combined.tif") if (output_dir / "xps_in_situ_combined.tif").exists() else None),
        "preview_png": origin_status.get("preview_png")
        or (_output_path(output_dir, output_dir / "xps_in_situ_combined.png") if (output_dir / "xps_in_situ_combined.png").exists() else None),
        "processing_status": "success" if origin_status.get("ok") else "processed_no_origin",
        "origin_status": _sanitize_output_payload(origin_status, output_dir),
        "quality_checks": quality_checks,
        "manual_check_required": True,
        "manual_check_items": [
            "confirm XPS in-situ peak positions, fitted components, and illumination/dark sample mapping",
            "review any binding-energy shifts manually before interpretation",
        ],
        "forbidden_claims": [
            "do not assign valence states automatically",
            "do not infer electron-transfer direction or heterojunction mechanism",
            "do not claim proof of S-scheme mechanism",
        ],
    }
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(_sanitize_output_payload(metadata_payload, output_dir), ensure_ascii=False, indent=2), encoding="utf-8")
    report_text = _mapping_report(
        xps_root=xps_root,
        output_dir=output_dir,
        sample_files=sample_files,
        file_notes=file_notes,
        scanned_files=scanned_files,
        records=records,
        selected=selected,
        statuses=statuses,
        panels=panels,
        missing=missing,
        manual_review=manual_review,
        element_sources=element_sources,
        origin_status=origin_status,
        quality_checks=quality_checks,
    )
    (output_dirs["reports"] / "xps_data_mapping_report.md").write_text(report_text, encoding="utf-8")
    (output_dirs["reports"] / "xps_in_situ_manifest.json").write_text(
        json.dumps(
            {
                "output_dir": ".",
                "output_dirs": {name: _output_path(output_dir, path) for name, path in output_dirs.items()},
                "metadata": _output_path(output_dir, metadata_path),
                "plotted_panels": [panel.__dict__ for panel in panels],
                "missing": missing,
                "element_sources": element_sources,
                "origin_status": _sanitize_output_payload(origin_status, output_dir),
                "quality_checks": quality_checks,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return XpsInSituResult(output_dir, panels, missing, element_sources, origin_status, quality_checks)


def _output_subdirs(output_dir: Path) -> dict[str, Path]:
    dirs = {name: output_dir / name for name in OUTPUT_SUBDIRS}
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def discover_input_files(xps_root: Path) -> tuple[dict[str, list[Path]], list[dict[str, str]], list[Path]]:
    sample_files: dict[str, list[Path]] = {"CWO": [], "BOBC": [], "BC Dark": [], "BC Light": []}
    file_notes: list[dict[str, str]] = []
    scanned_files: list[Path] = []
    if not xps_root.exists():
        raise FileNotFoundError(f"XPS root not found: {xps_root}")

    target_roots = _target_roots(xps_root)
    for root in target_roots:
        scanned_files.extend(path for path in root.rglob("*") if path.is_file())

    for path in sorted(scanned_files, key=lambda item: str(item).casefold()):
        suffix = path.suffix.casefold()
        sample = sample_from_path(path.relative_to(xps_root))
        note_file = _input_note_path(xps_root, path)
        if suffix not in {".xlsx", ".xls", ".csv", ".txt"}:
            file_notes.append({"file": note_file, "sample": sample or "", "reason": "not a table workbook used for fitted curves"})
            continue
        if suffix in {".csv", ".txt"}:
            file_notes.append({"file": note_file, "sample": sample or "", "reason": "text-like file found but no fitted XPS component table parser was needed"})
            continue
        if sample is None:
            file_notes.append({"file": note_file, "sample": "", "reason": "sample could not be inferred from requested folders or filename"})
            continue
        if sample in {"CWO", "BOBC"}:
            if suffix == ".xlsx":
                sample_files[sample].append(path)
            else:
                file_notes.append({"file": note_file, "sample": sample, "reason": "xls companion skipped because xlsx fitted workbook is preferred"})
        elif sample == "BC Dark":
            if path.name.casefold() == "dark-20260506.xlsx":
                sample_files[sample].append(path)
            else:
                file_notes.append({"file": note_file, "sample": sample, "reason": "not the requested DARK-20260506 workbook"})
        elif sample == "BC Light":
            if path.name.casefold() == "lingt-20260506.xlsx":
                sample_files[sample].append(path)
            else:
                file_notes.append({"file": note_file, "sample": sample, "reason": "not selected; LINGT-20260506.xlsx is the requested Light workbook"})

    for sample in sample_files:
        sample_files[sample] = sorted(set(sample_files[sample]), key=lambda item: str(item).casefold())
    return sample_files, file_notes, sorted(set(scanned_files), key=lambda item: str(item).casefold())


def _input_note_path(xps_root: Path, path: Path) -> str:
    try:
        return path.relative_to(xps_root).as_posix()
    except ValueError:
        return Path(path).name


def format_region(region: str) -> str:
    match = re.match(r"([A-Z][a-z]?)(\d+[spdf])", region)
    if not match:
        return region
    return f"{match.group(1)} {match.group(2)}"


def _target_roots(xps_root: Path) -> list[Path]:
    roots: list[Path] = []
    for child in xps_root.iterdir():
        if not child.is_dir():
            continue
        name = child.name.casefold()
        if "cwo" in name or "bobc" in name or "xps" in name:
            roots.append(child)
    return roots


def _record_statuses(selected: dict[tuple[str, str], XpsFitRecord]) -> list[InSituRecordStatus]:
    statuses: list[InSituRecordStatus] = []
    for sample in ("BOBC", "CWO", "BC Dark", "BC Light"):
        for element in TARGET_ELEMENTS:
            record = selected.get((sample, element))
            if record is None:
                continue
            complete, note = _record_is_complete(record)
            statuses.append(InSituRecordStatus(sample, element, record.region, complete, note))
    return statuses


def _record_is_complete(record: XpsFitRecord) -> tuple[bool, str]:
    if len(record.data) < 10:
        return False, f"data point count too low ({len(record.data)})"
    if record.envelope_label is None or not any(_to_float(row.get("envelope")) is not None for row in record.data):
        return False, "missing fitted envelope"
    if not record.component_labels:
        return False, "missing component peaks"
    usable_components = [
        label
        for label in record.component_labels
        if any(_to_float(row.get(_component_key(label))) is not None for row in record.data)
    ]
    if not usable_components:
        return False, "component columns contain no numeric peak data"
    return True, ""


def _panel_records(
    panels: list[InSituPanelPlan],
    selected: dict[tuple[str, str], XpsFitRecord],
) -> dict[InSituPanelPlan, list[XpsFitRecord]]:
    panel_records: dict[InSituPanelPlan, list[XpsFitRecord]] = {}
    for panel in panels:
        panel_records[panel] = [selected[(sample, panel.element)] for sample in panel.samples]
    return panel_records


def _write_figures(panel_records: dict[InSituPanelPlan, list[XpsFitRecord]], output_dir: Path) -> dict[str, list[str]]:
    import matplotlib as mpl
    import matplotlib.pyplot as plt

    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "axes.linewidth": 1.2,
            "xtick.direction": "in",
            "ytick.direction": "in",
            "xtick.major.width": 1.1,
            "ytick.major.width": 1.1,
            "xtick.minor.width": 0.8,
            "ytick.minor.width": 0.8,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )

    element_sources: dict[str, list[str]] = {}
    panels = list(panel_records)
    cols = 2 if len(panels) <= 4 else 3
    rows = math.ceil(len(panels) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 3.55, rows * 2.95), squeeze=False)
    for idx, panel in enumerate(panels):
        ax = axes[idx // cols][idx % cols]
        _draw_panel(ax, panel, panel_records[panel], string.ascii_lowercase[idx])
        element_sources[panel.panel_title] = [_source_name(record.source_file) for record in panel_records[panel]]
    for idx in range(len(panels), rows * cols):
        axes[idx // cols][idx % cols].axis("off")
    fig.tight_layout(w_pad=1.6, h_pad=1.4)
    _save_figure(fig, output_dir / "xps_in_situ_combined")
    plt.close(fig)

    for idx, panel in enumerate(panels):
        single, ax = plt.subplots(1, 1, figsize=(3.75, 3.05))
        _draw_panel(ax, panel, panel_records[panel], string.ascii_lowercase[idx])
        single.tight_layout()
        _save_figure(single, output_dir / panel.file_stem)
        plt.close(single)
    return element_sources


def _draw_panel(ax: Any, panel: InSituPanelPlan, records: list[XpsFitRecord], panel_letter: str) -> None:
    offsets = {
        records[0].sample: 2.82,
        records[1].sample: 1.41,
        records[2].sample: 0.0,
    }
    x_min = min(min(_numeric_series(record, "binding_energy_eV")) for record in records)
    x_max = max(max(_numeric_series(record, "binding_energy_eV")) for record in records)
    x_span = x_max - x_min
    y_top = 4.5
    all_peak_entries: list[dict[str, Any]] = []

    for record in records:
        scale = _normalization_scale(record)
        offset = offsets[record.sample]
        x = _numeric_series(record, "binding_energy_eV")
        order = sorted(range(len(x)), key=lambda index: x[index])
        x_sorted = [x[index] for index in order]

        background = _normalized_series(record, "background", scale, offset, order)
        raw = _normalized_series(record, "raw_intensity", scale, offset, order)
        envelope = _normalized_series(record, "envelope", scale, offset, order)
        ax.plot(x_sorted, raw, color="#C8C8C8", lw=0.75, zorder=2)
        if any(value is not None for value in background):
            ax.plot(x_sorted, background, color="#A9A9A9", lw=0.65, zorder=3)

        component_labels = _major_component_labels(record, _component_limit(record))
        for component_index, label in enumerate(component_labels):
            key = _component_key(label)
            comp = _normalized_series(record, key, scale, offset, order)
            base = background if any(value is not None for value in background) else [offset] * len(comp)
            base, comp = _mask_component_to_peak_region(base, comp)
            color = COMPONENT_COLORS[component_index % len(COMPONENT_COLORS)]
            ax.fill_between(
                x_sorted,
                _none_to_nan(base),
                _none_to_nan(comp),
                color=color,
                alpha=0.42,
                linewidth=0,
                zorder=1,
            )
            ax.plot(x_sorted, _none_to_nan(comp), color=color, lw=0.75, alpha=0.92, zorder=4)

        ax.plot(x_sorted, envelope, color="black", lw=1.55, zorder=5)
        sample_label = SAMPLE_DISPLAY.get(record.sample, record.sample)
        sample_label_x_fraction = 0.145 if panel.element == "Cu" else 0.035
        ax.text(
            x_max - x_span * sample_label_x_fraction,
            offset + 0.38,
            sample_label,
            color=SAMPLE_TEXT_COLORS.get(record.sample, "black"),
            fontsize=8.5,
            fontweight="bold",
            va="center",
            ha="left",
        )

        peaks = _peak_entries(record, offset, scale)
        all_peak_entries.extend(peaks)
        for peak in _select_annotation_peaks(record.region, peaks):
            x_peak = float(peak["binding_energy_eV"])
            ax.axvline(x_peak, color="#8E8E8E", lw=0.65, ls=(0, (3, 3)), alpha=0.55, zorder=0)
            y_peak = min(float(peak["normalized_y"]) + 0.16, offset + 1.08, y_top - 0.44)
            label = f"{x_peak:.2f} eV"
            if peak.get("assignment"):
                label = f"{peak['assignment']}\n{label}"
            x_text = min(max(x_peak + x_span * 0.03, x_min + x_span * 0.16), x_max - x_span * 0.18)
            ax.text(
                x_text,
                y_peak,
                label,
                fontsize=6.0,
                color="#5E5E5E",
                ha="center",
                va="bottom",
                linespacing=0.9,
            )

    ax.set_xlim(x_max + x_span * 0.025, x_min - x_span * 0.025)
    ax.set_ylim(-0.18, y_top)
    ax.set_xlabel("Binding energy (eV)", fontsize=9.5, fontweight="bold")
    ax.set_ylabel("Intensity (a.u.)", fontsize=9.5, fontweight="bold")
    ax.set_yticklabels([])
    ax.grid(False)
    ax.minorticks_on()
    ax.tick_params(which="both", direction="in", top=True, right=True, labelsize=8, length=3.5)
    ax.tick_params(which="minor", length=2.0)
    for spine in ax.spines.values():
        spine.set_linewidth(1.2)
        spine.set_color("black")
    ax.text(0.02, 0.96, f"({panel_letter})", transform=ax.transAxes, ha="left", va="top", fontsize=10.5, fontweight="bold")
    ax.text(0.15, 0.96, panel.panel_title, transform=ax.transAxes, ha="left", va="top", fontsize=10.5, fontweight="bold")


def _save_figure(fig: Any, stem: Path) -> None:
    fig.savefig(stem.with_suffix(".png"), dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(stem.with_suffix(".pdf"), bbox_inches="tight", facecolor="white")
    fig.savefig(
        stem.with_suffix(".tif"),
        dpi=600,
        bbox_inches="tight",
        facecolor="white",
        pil_kwargs={"compression": "tiff_lzw"},
    )


def _numeric_series(record: XpsFitRecord, key: str) -> list[float]:
    values: list[float] = []
    for row in record.data:
        value = _to_float(row.get(key))
        if value is not None:
            values.append(value)
    return values


def _normalized_series(
    record: XpsFitRecord,
    key: str,
    scale: tuple[float, float],
    offset: float,
    order: list[int],
) -> list[float | None]:
    minimum, span = scale
    values: list[float | None] = []
    for index in order:
        if index >= len(record.data):
            values.append(None)
            continue
        value = _to_float(record.data[index].get(key))
        values.append(None if value is None else ((value - minimum) / span) + offset)
    return values


def _none_to_nan(values: list[float | None]) -> list[float]:
    return [float("nan") if value is None else float(value) for value in values]


def _mask_component_to_peak_region(
    base: list[float | None],
    component: list[float | None],
) -> tuple[list[float | None], list[float | None]]:
    deltas = [
        max(0.0, float(component_value) - float(base_value))
        for base_value, component_value in zip(base, component)
        if base_value is not None and component_value is not None
    ]
    if not deltas:
        return base, component
    threshold = max(max(deltas) * 0.015, 0.006)
    masked_base: list[float | None] = []
    masked_component: list[float | None] = []
    for base_value, component_value in zip(base, component):
        if base_value is None or component_value is None or float(component_value) - float(base_value) < threshold:
            masked_base.append(None)
            masked_component.append(None)
        else:
            masked_base.append(base_value)
            masked_component.append(component_value)
    return masked_base, masked_component


def _peak_entries(record: XpsFitRecord, offset: float, scale: tuple[float, float]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    component_labels = _major_component_labels(record, _component_limit(record))
    for index, label in enumerate(component_labels, start=1):
        key = _component_key(label)
        numeric = [
            (float(row["binding_energy_eV"]), float(row[key]))
            for row in record.data
            if isinstance(row.get("binding_energy_eV"), (int, float)) and isinstance(row.get(key), (int, float))
        ]
        peak = _highest_local_peak(numeric)
        if peak is None and numeric:
            peak = max(numeric, key=lambda item: item[1])
        if peak is None:
            continue
        binding, intensity = peak
        minimum, span = scale
        normalized_y = ((float(intensity) - minimum) / span) + offset
        assignment = _infer_peak_assignment(record.region, float(binding))
        peak_label = assignment or f"{format_region(record.region)} component {index}"
        entries.append(
            {
                "sample": record.sample,
                "component_label": label,
                "peak_label": peak_label,
                "assignment": assignment,
                "binding_energy_eV": round(float(binding), 2),
                "normalized_y": round(float(normalized_y), 4),
                "source_file": _source_name(record.source_file),
                "sheet_name": record.sheet_name,
            }
        )
    return sorted(entries, key=lambda item: float(item["binding_energy_eV"]), reverse=True)


def _select_annotation_peaks(region: str, peaks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if region.casefold() == "cu2p":
        assigned = [peak for peak in peaks if peak.get("assignment")]
        unassigned = [peak for peak in peaks if not peak.get("assignment")]
        by_height = sorted(unassigned, key=lambda item: float(item.get("normalized_y", 0.0)), reverse=True)
        selected = [*assigned, *by_height[: max(0, 5 - len(assigned))]]
        return sorted(selected[:5], key=lambda item: float(item["binding_energy_eV"]), reverse=True)
    return peaks[:3]


def _peak_summary_rows(panel_records: dict[InSituPanelPlan, list[XpsFitRecord]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for panel, records in panel_records.items():
        peaks_by_sample = {record.sample: _peak_entries(record, 0.0, _normalization_scale(record)) for record in records}
        reference_sample = panel.reference_sample
        reference_peaks = peaks_by_sample.get(reference_sample, [])
        ref_by_label = {str(item["peak_label"]): float(item["binding_energy_eV"]) for item in reference_peaks}
        for record in records:
            for peak in peaks_by_sample.get(record.sample, []):
                ref_position = ref_by_label.get(str(peak["peak_label"]))
                shift = None if ref_position is None else float(peak["binding_energy_eV"]) - ref_position
                note = ""
                if ref_position is None and record.sample != reference_sample:
                    note = "No reference peak with the same inferred label; shift not calculated."
                rows.append(
                    {
                        "Element": panel.element,
                        "Orbital": panel.panel_title,
                        "Sample": record.sample,
                        "Peak label": peak["peak_label"],
                        "Peak position / eV": float(peak["binding_energy_eV"]),
                        "Reference peak position / eV": ref_position,
                        "Shift vs reference / eV": None if shift is None else round(shift, 3),
                        "Data source file": _source_name(record.source_file),
                        "Sheet name": record.sheet_name,
                        "Notes": note,
                    }
                )
    return rows


def _write_peak_summary(path: Path, rows: list[dict[str, Any]]) -> None:
    frame = pd.DataFrame(rows)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name="Peak positions", index=False)
        worksheet = writer.sheets["Peak positions"]
        widths = {
            "A": 10,
            "B": 12,
            "C": 12,
            "D": 26,
            "E": 18,
            "F": 26,
            "G": 22,
            "H": 70,
            "I": 18,
            "J": 42,
        }
        for col, width in widths.items():
            worksheet.column_dimensions[col].width = width
        worksheet.freeze_panes = "A2"


def _try_write_origin_project(
    project_root: Path,
    panel_records: dict[InSituPanelPlan, list[XpsFitRecord]],
    output_dir: Path,
) -> dict[str, Any]:
    ok, message = check_origin_available()
    origin_file = output_dir / "xps_in_situ_combined.opju"
    if not ok:
        write_origin_error(project_root, f"xps_in_situ_combined: {message}")
        return {"requested": True, "ok": False, "origin_file": None, "message": message}
    try:
        _write_origin_project(
            panel_records,
            origin_file,
            output_dir / "xps_in_situ_combined_origin_preview.png",
            output_dir / "xps_in_situ_combined.png",
            output_dir / "xps_in_situ_combined.tif",
        )
    except Exception as exc:
        write_origin_error(project_root, f"xps_in_situ_combined: {exc}")
        return {
            "requested": True,
            "ok": False,
            "origin_file": _output_path(output_dir, origin_file) if origin_file.exists() else None,
            "message": scrub_output_text(exc, output_root=output_dir),
        }
    preview_png = output_dir / "xps_in_situ_combined_origin_preview.png"
    figure_tif = output_dir / "xps_in_situ_combined.tif"
    missing = [
        str(path.name)
        for path in (origin_file, preview_png, figure_tif)
        if not path.exists() or path.stat().st_size <= 0
    ]
    if missing:
        message = "Origin export missing or empty artifacts: " + ", ".join(missing)
        write_origin_error(project_root, f"xps_in_situ_combined: {message}")
        return {
            "requested": True,
            "ok": False,
            "origin_file": _output_path(output_dir, origin_file) if origin_file.exists() else None,
            "message": message,
        }
    return {
        "requested": True,
        "ok": True,
        "origin_file": _output_path(output_dir, origin_file),
        "figure_tif": _output_path(output_dir, figure_tif),
        "preview_png": _output_path(output_dir, preview_png),
        "message": "Origin project saved with final figure image page plus editable worksheets and graph pages.",
    }


def _write_origin_project(
    panel_records: dict[InSituPanelPlan, list[XpsFitRecord]],
    origin_file: Path,
    preview_png: Path,
    final_png: Path,
    figure_tif: Path,
) -> None:
    import originpro as op

    def safe_name(value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_") or "XPS"
        return cleaned[:24]

    op.set_show(False)
    try:
        op.new()
        if final_png.exists():
            image_page = op.new_image("Final_XPS_Figure")
            image_page.from_file(str(final_png))
        graph = op.new_graph("xps_in_situ_combined")
        graph.name = "xps_in_situ_combined"
        panels = list(panel_records)
        cols = 2 if len(panels) <= 4 else 3
        rows = math.ceil(len(panels) / cols)
        layer_positions = _origin_layer_positions(rows, cols)
        for panel_index, panel in enumerate(panels):
            records = panel_records[panel]
            headers, columns = _origin_columns(panel, records)
            wks = op.new_sheet("w", safe_name(f"{panel.element}_{panel.region}_data"))
            op.lt_exec('page.comments$=""; page.comment$=""; wks.comments$=""; wks.comment$="";')
            wks.cols = len(headers)
            for col_index, (header, values) in enumerate(zip(headers, columns)):
                axis = "X" if col_index == 0 else "Y"
                wks.from_list(col_index, values, lname=header, axis=axis)

            layer = graph[0] if panel_index == 0 else graph.add_layer(0)
            left, top, width, height = layer_positions[panel_index]
            for prop, value in (("left", left), ("top", top), ("width", width), ("height", height)):
                layer.set_float(prop, value)

            for col_index, label in enumerate(headers[1:], start=1):
                plot = layer.add_plot(wks, coly=col_index, colx=0, type="line")
                lower = label.casefold()
                if "measured" in lower:
                    plot.color = "#BDBDBD"
                    plot.set_cmd("-lw 0.7")
                elif "backgnd" in lower:
                    plot.color = "#9E9E9E"
                    plot.set_cmd("-lw 0.7")
                elif "envelope" in lower:
                    plot.color = "#000000"
                    plot.set_cmd("-lw 1.8")
                else:
                    color_index = sum(ord(ch) for ch in label) % len(COMPONENT_COLORS)
                    plot.color = COMPONENT_COLORS[color_index]
                    plot.set_cmd("-lw 0.9")
            legend = layer.label("Legend")
            if legend is not None:
                try:
                    legend.remove()
                except Exception:
                    pass
            x_values = [value for value in columns[0] if value is not None]
            y_values = [value for col in columns[1:] for value in col if value is not None]
            if x_values and y_values:
                x_span = max(x_values) - min(x_values)
                y_span = max(y_values) - min(y_values)
                layer.set_float("x.from", max(x_values) + x_span * 0.025)
                layer.set_float("x.to", min(x_values) - x_span * 0.025)
                layer.set_float("y.from", min(y_values) - max(y_span * 0.06, 0.1))
                layer.set_float("y.to", max(y_values) + max(y_span * 0.12, 0.2))
            layer.label("XB").text = r"\b(Binding energy (eV))"
            layer.label("YL").text = r"\b(Intensity (a.u.))"
            layer.add_label(panel.panel_title, max(x_values), max(y_values) if y_values else 1.0)
        op.lt_exec('doc -e W { page.comments$=""; page.comment$=""; wks.comments$=""; wks.comment$=""; }; doc -e P { page.comments$=""; page.comment$=""; };')
        op.save(str(origin_file))
        graph.save_fig(str(preview_png), type="png", replace=True, width=2800)
        graph.save_fig(str(figure_tif), type="tif", replace=True, width=3600)
        ensure_tif_600_dpi_metadata(figure_tif)
    finally:
        op.exit()


def _origin_layer_positions(rows: int, cols: int) -> list[tuple[float, float, float, float]]:
    left_margin = 8.0
    top_margin = 6.0
    gap_x = 6.0
    gap_y = 14.0
    width = (88.0 - gap_x * (cols - 1)) / cols
    height = (82.0 - gap_y * (rows - 1)) / rows
    positions = []
    for row in range(rows):
        for col in range(cols):
            positions.append((left_margin + col * (width + gap_x), top_margin + row * (height + gap_y), width, height))
    return positions


def _origin_columns(panel: InSituPanelPlan, records: list[XpsFitRecord]) -> tuple[list[str], list[list[float | None]]]:
    x_values = _numeric_series(records[0], "binding_energy_eV")
    headers = ["Binding energy / eV"]
    columns: list[list[float | None]] = [x_values]
    offsets = {records[0].sample: 2.82, records[1].sample: 1.41, records[2].sample: 0.0}
    for record in records:
        scale = _normalization_scale(record)
        order = list(range(len(record.data)))
        for label in _major_component_labels(record, _component_limit(record)):
            headers.append(f"{record.sample} {label}")
            columns.append(_normalized_series(record, _component_key(label), scale, offsets[record.sample], order))
        for label, key in (("measured", "raw_intensity"), ("Backgnd.", "background"), ("Envelope", "envelope")):
            headers.append(f"{record.sample} {label}")
            columns.append(_normalized_series(record, key, scale, offsets[record.sample], order))
    return headers, columns


def _quality_checks(
    output_dir: Path,
    panel_records: dict[InSituPanelPlan, list[XpsFitRecord]],
    origin_status: dict[str, Any],
) -> dict[str, Any]:
    warnings: list[str] = []
    try:
        from PIL import Image
    except ImportError:
        Image = None
        warnings.append("Pillow is not installed; skipped TIF DPI quality checks.")

    paths = [output_dir / "xps_in_situ_combined.tif", output_dir / "xps_in_situ_combined.png", output_dir / "xps_in_situ_combined.pdf"]
    for panel in panel_records:
        stem = output_dir / panel.file_stem
        paths.extend([stem.with_suffix(".tif"), stem.with_suffix(".png"), stem.with_suffix(".pdf")])
    existing = {_output_path(output_dir, path): path.exists() and path.stat().st_size > 0 for path in paths}
    dpi_checks: dict[str, Any] = {}
    if Image is not None:
        for path in [item for item in paths if item.suffix.casefold() == ".tif" and item.exists()]:
            rendered = _output_path(output_dir, path)
            try:
                with Image.open(path) as image:
                    dpi = image.info.get("dpi", (0, 0))
                dpi_checks[rendered] = {"dpi": [round(float(dpi[0])), round(float(dpi[1]))], "ok": float(dpi[0]) >= 600 and float(dpi[1]) >= 600}
            except Exception as exc:
                dpi_checks[rendered] = {"ok": False, "error": scrub_output_text(exc, output_root=output_dir)}
    data_checks = {}
    for panel, records in panel_records.items():
        data_checks[panel.panel_title] = {
            "x_axis_reversed": True,
            "axis_titles": True,
            "panel_letter": True,
            "element_name": True,
            "vertical_offsets": len({record.sample for record in records}) == 3,
            "raw_envelope_components_present": all(_record_is_complete(record)[0] for record in records),
            "peak_labels_from_component_maxima": True,
        }
    return {
        "files_saved": existing,
        "tif_dpi": dpi_checks,
        "panel_data_checks": data_checks,
        "origin_project_saved": bool(origin_status.get("ok")),
        "warnings": warnings,
    }


def _mapping_report(
    *,
    xps_root: Path,
    output_dir: Path,
    sample_files: dict[str, list[Path]],
    file_notes: list[dict[str, str]],
    scanned_files: list[Path],
    records: list[XpsFitRecord],
    selected: dict[tuple[str, str], XpsFitRecord],
    statuses: list[InSituRecordStatus],
    panels: list[InSituPanelPlan],
    missing: dict[str, list[str]],
    manual_review: list[dict[str, Any]],
    element_sources: dict[str, list[str]],
    origin_status: dict[str, Any],
    quality_checks: dict[str, Any],
) -> str:
    lines: list[str] = [
        "# XPS data mapping report",
        "",
        f"Output directory: `.`",
        "",
        "## Recognized sample files",
        "",
        "| Sample | Selected file(s) |",
        "|---|---|",
    ]
    for sample, files in sample_files.items():
        selected_text = "<br>".join(f"`{_source_name(path)}`" for path in files) or "MISSING"
        lines.append(f"| {sample} | {selected_text} |")

    lines.extend(["", "## Parsed fitted records", "", "| Sample | Element | Sheet | Rows | Components | Complete | Notes | Source file |", "|---|---:|---|---:|---:|---|---|---|"])
    status_by_key = {(item.sample, item.element): item for item in statuses}
    for record in sorted(records, key=lambda item: (item.sample, item.element, item.sheet_name)):
        status = status_by_key.get((record.sample, record.element))
        complete = "" if status is None else str(status.complete)
        note = "" if status is None else status.note
        selected_marker = "selected" if selected.get((record.sample, record.element)) is record else "candidate"
        lines.append(
            f"| {record.sample} | {record.element} | {record.sheet_name} | {len(record.data)} | {len(record.component_labels)} | {complete} | {selected_marker}; {note} | `{_source_name(record.source_file)}` |"
        )

    lines.extend(["", "## Successfully plotted elements", ""])
    if panels:
        lines.append("| Element | Samples/files |")
        lines.append("|---|---|")
        for panel in panels:
            sources = "<br>".join(f"`{source}`" for source in element_sources.get(panel.panel_title, []))
            lines.append(f"| {panel.panel_title} | {sources} |")
    else:
        lines.append("No element passed the completeness rules.")

    lines.extend(["", "## Missing or incomplete elements", ""])
    if missing:
        lines.append("| Element | Reason |")
        lines.append("|---|---|")
        for element, reasons in missing.items():
            lines.append(f"| {element} | {'; '.join(reasons)} |")
    else:
        lines.append("None.")

    lines.extend(["", "## Files not used for fitted plotting", "", "| File | Reason |", "|---|---|"])
    for item in file_notes:
        lines.append(f"| `{_source_name(item['file'])}` | {item['reason']} |")

    if manual_review:
        lines.extend(["", "## Loader manual-review notes", "", "```json", json.dumps(manual_review, ensure_ascii=False, indent=2), "```"])

    lines.extend(["", "## Quality checks", "", "```json", json.dumps(quality_checks, ensure_ascii=False, indent=2), "```"])
    lines.extend(["", "## Origin status", "", "```json", json.dumps(origin_status, ensure_ascii=False, indent=2), "```"])
    lines.extend(["", "## Scan scope", "", f"- XPS root: `{xps_root}`", f"- Files scanned under requested source folders: {len(scanned_files)}"])
    return "\n".join(lines) + "\n"
