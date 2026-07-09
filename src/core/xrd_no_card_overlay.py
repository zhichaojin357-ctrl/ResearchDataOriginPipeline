from __future__ import annotations

import csv
import json
import math
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from src.core.metadata import file_hash
from src.core.template_product_common import extract_xrd_raw_data_rows
from src.core.output_sanitizer import render_output_path, scrub_output_text
from src.core.plot_labels import XRD_X_AXIS_TITLE, XRD_Y_AXIS_TITLE
from src.core.runtime_paths import create_run_output_layout, resolve_origin_reference_pattern, resolve_output_root
from src.core.table_reader import coerce_numeric_rows, read_table
from src.core.xrd_helpers import interpolated_y as _interpolated_y
from src.core.xrd_helpers import relative_path as _relative
from src.core.xrd_helpers import to_finite_float as _to_float
from src.origin.adapter import check_origin_available, write_origin_error, write_origin_success
from src.processors.base import safe_name


@dataclass(frozen=True)
class XrdNoCardOverlayOptions:
    sources: tuple[Path, ...]
    labels: tuple[str, ...] = ()
    output_root: Path | None = None
    with_origin: bool = False
    timestamp: str | None = None
    output_stem: str = "XRD_BOBXC1_X_no_card_overlay"
    reference_opju: Path | None = None
    reference_graph: str = "Graph4"


@dataclass(frozen=True)
class XrdNoCardOverlayTable:
    headers: list[str]
    rows: list[list[float]]
    labels: list[str]
    metadata: dict[str, object]


@dataclass(frozen=True)
class XrdNoCardOverlayArtifacts:
    processed_data: Path
    metadata: Path
    report: Path
    origin_file: Path
    figure_tif: Path
    preview_png: Path
    script_output_dir: Path


def discover_xrd_text_sources(input_dir: Path) -> tuple[Path, ...]:
    if not input_dir.exists() or not input_dir.is_dir():
        raise FileNotFoundError(f"XRD no-card input directory does not exist: {input_dir}")
    allowed = {".txt", ".csv", ".dat", ".xy"}
    return tuple(sorted((path for path in input_dir.iterdir() if path.is_file() and path.suffix.casefold() in allowed), key=lambda path: path.name.casefold()))


def read_xrd_xy_points(path: Path) -> list[tuple[float, float]]:
    try:
        rows = extract_xrd_raw_data_rows(path)
        points = _numeric_xy_points(rows)
        if len(points) >= 2:
            return points
    except Exception:
        pass
    points = [(float(x), float(y)) for x, y in coerce_numeric_rows(read_table(path))]
    points = sorted({x: y for x, y in points if math.isfinite(x) and math.isfinite(y)}.items())
    if len(points) < 2:
        raise ValueError(f"XRD source has fewer than two numeric two-theta/intensity rows: {path}")
    return points


def build_xrd_no_card_overlay_table(sources: tuple[Path, ...], labels: tuple[str, ...] = ()) -> XrdNoCardOverlayTable:
    if not sources:
        raise ValueError("XRD no-card overlay requires at least one source file.")
    if labels and len(labels) != len(sources):
        raise ValueError(f"expected {len(sources)} labels for sources, got {len(labels)}")

    display_labels = [str(label).strip() for label in labels] if labels else [_default_label(path) for path in sources]
    if any(not label for label in display_labels):
        raise ValueError("XRD no-card overlay labels must not be empty.")

    series = [(label, read_xrd_xy_points(path)) for label, path in zip(display_labels, sources)]
    overlap_min = max(points[0][0] for _label, points in series)
    overlap_max = min(points[-1][0] for _label, points in series)
    if overlap_max <= overlap_min:
        raise ValueError("XRD sources do not have an overlapping two-theta range.")
    grid = sorted({x for _label, points in series for x, _y in points if overlap_min <= x <= overlap_max})
    if len(grid) < 2:
        raise ValueError("XRD no-card overlay common grid has fewer than two points.")

    offsets = [_offset_for_index(index, len(series)) for index in range(len(series))]
    normalized_series = [
        [_normalized_offset_y(points, x_value, offset) for x_value in grid]
        for (_label, points), offset in zip(series, offsets)
    ]
    rows = [[x_value, *[column[index] for column in normalized_series]] for index, x_value in enumerate(grid)]
    metadata = {
        "series_order": display_labels,
        "source_file_names": [path.name for path in sources],
        "point_counts": {label: len(points) for label, points in series},
        "common_two_theta_min": overlap_min,
        "common_two_theta_max": overlap_max,
        "common_grid_points": len(grid),
        "normalization": "Each trace is min-max normalized and vertically offset for visual XRD comparison only.",
        "offsets": offsets,
        "standard_card_added": False,
    }
    return XrdNoCardOverlayTable(
        headers=["two_theta_deg", *display_labels],
        rows=rows,
        labels=display_labels,
        metadata=metadata,
    )


def run_xrd_no_card_overlay(project_root: Path, options: XrdNoCardOverlayOptions) -> dict[str, object]:
    project_root = project_root.resolve()
    _validate_sources(options.sources)
    output_root = resolve_output_root(project_root, explicit=options.output_root)
    reference_opju = _resolve_reference_opju(project_root, options.reference_opju)
    input_paths = list(options.sources)
    if reference_opju is not None:
        input_paths.append(reference_opju)
    layout = create_run_output_layout(
        project_root,
        scope=safe_name(options.output_stem),
        command="xrd-no-card-overlay",
        mode="with_origin" if options.with_origin else "no_origin",
        input_paths=input_paths,
        timestamp=options.timestamp,
        no_origin=not options.with_origin,
        dry_run=not options.with_origin,
        output_base=output_root / "runs",
    )
    artifacts = XrdNoCardOverlayArtifacts(
        processed_data=layout.processed_data / f"{safe_name(options.output_stem)}.csv",
        metadata=layout.metadata / safe_name(options.output_stem) / "metadata.json",
        report=layout.reports / "xrd_no_card_overlay_report.md",
        origin_file=layout.origin_files / f"{safe_name(options.output_stem)}.opju",
        figure_tif=layout.figures_tif / f"{safe_name(options.output_stem)}.tif",
        preview_png=layout.figures_preview / f"{safe_name(options.output_stem)}.png",
        script_output_dir=layout.logs / "xrd_no_card_script_output",
    )
    table = build_xrd_no_card_overlay_table(options.sources, options.labels)
    _write_csv(artifacts.processed_data, table.headers, table.rows)

    export_status: dict[str, object] = {"ok": False, "message": "Origin export skipped by --dry-run/--no-origin."}
    if options.with_origin:
        export_status = _export_with_existing_script(project_root, options, table, artifacts, reference_opju)
    metadata = _write_metadata(layout.root, options, table, artifacts, export_status, reference_opju)
    report = _write_report(layout.root, options, table, artifacts, export_status, reference_opju)
    return {
        "run_root": _relative(project_root, layout.root),
        "processed_data": _relative(project_root, artifacts.processed_data),
        "metadata": _relative(project_root, metadata),
        "report": _relative(project_root, report),
        "origin_file": _relative(project_root, artifacts.origin_file),
        "figure_tif": _relative(project_root, artifacts.figure_tif),
        "preview_png": _relative(project_root, artifacts.preview_png),
        "will_launch_origin": bool(options.with_origin),
        "origin_status": export_status,
    }


def _export_with_existing_script(
    project_root: Path,
    options: XrdNoCardOverlayOptions,
    table: XrdNoCardOverlayTable,
    artifacts: XrdNoCardOverlayArtifacts,
    reference_opju: Path | None,
) -> dict[str, object]:
    ok, message = check_origin_available()
    if not ok:
        write_origin_error(project_root, f"xrd-no-card-overlay: {message}", output_root=artifacts.origin_file.parents[1])
        return {"ok": False, "message": f"Origin unavailable: {message}"}
    pre_existing_origin_pids = set(_origin_process_ids())

    script = project_root / "scripts" / "data_types" / "xrd" / "plot_xrd_no_card_overlay_origin.py"
    if not script.is_file():
        message = f"XRD no-card Origin script is missing: {script}"
        write_origin_error(project_root, f"xrd-no-card-overlay: {message}", output_root=artifacts.origin_file.parents[1])
        return {"ok": False, "message": scrub_output_text(message, project_root=project_root, output_root=artifacts.origin_file.parents[1])}

    _remove_stale_outputs(artifacts)
    if artifacts.script_output_dir.exists():
        shutil.rmtree(artifacts.script_output_dir)
    artifacts.script_output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(script),
        "--input-csv",
        str(artifacts.processed_data),
        "--output-dir",
        str(artifacts.script_output_dir),
        "--output-root",
        str(artifacts.script_output_dir.parents[1]),
        "--reference-graph",
        options.reference_graph,
        "--output-stem",
        safe_name(options.output_stem),
        "--page-name",
        safe_name(options.output_stem)[:24] or "XRD_no_card_overlay",
        "--labels",
        *table.labels,
    ]
    if reference_opju is not None:
        command[command.index("--reference-graph") : command.index("--reference-graph")] = ["--reference-opju", str(reference_opju)]
    completed = subprocess.run(command, cwd=project_root, text=True, capture_output=True, timeout=900)
    if completed.returncode and _origin_process_ids(pre_existing_origin_pids):
        _terminate_task_origin_processes(pre_existing_origin_pids)
        time.sleep(3)
        completed = subprocess.run(command, cwd=project_root, text=True, capture_output=True, timeout=900)
    if completed.returncode:
        message = (completed.stderr or completed.stdout or "XRD no-card Origin script failed").strip()
        _terminate_task_origin_processes(pre_existing_origin_pids)
        write_origin_error(project_root, f"xrd-no-card-overlay: {message}", output_root=artifacts.origin_file.parents[1])
        return {"ok": False, "message": scrub_output_text(message, project_root=project_root, output_root=artifacts.origin_file.parents[1])}

    produced = {
        "origin_file": artifacts.script_output_dir / f"{safe_name(options.output_stem)}.opju",
        "figure_tif": artifacts.script_output_dir / f"{safe_name(options.output_stem)}.tif",
        "preview_png": artifacts.script_output_dir / f"{safe_name(options.output_stem)}.png",
    }
    missing = [name for name, path in produced.items() if not path.exists() or path.stat().st_size == 0]
    if missing:
        message = "XRD no-card Origin script missing required artifacts: " + ", ".join(missing)
        write_origin_error(project_root, f"xrd-no-card-overlay: {message}", output_root=artifacts.origin_file.parents[1])
        return {"ok": False, "message": message}
    _copy_artifact(produced["origin_file"], artifacts.origin_file)
    _copy_artifact(produced["figure_tif"], artifacts.figure_tif)
    _copy_artifact(produced["preview_png"], artifacts.preview_png)
    _terminate_task_origin_processes(pre_existing_origin_pids)
    shutil.rmtree(artifacts.script_output_dir, ignore_errors=True)
    write_origin_success(project_root, output_root=artifacts.origin_file.parents[1])
    return {
        "ok": True,
        "message": "Origin export succeeded using the project XRD no-card overlay script.",
        "origin_script": render_output_path(script, project_root=project_root, output_root=artifacts.origin_file.parents[1]),
        "reference_opju": _display_path(artifacts.origin_file.parents[1], reference_opju) if reference_opju else None,
        "pre_existing_origin_pids": sorted(pre_existing_origin_pids),
        "stdout": scrub_output_text(completed.stdout, project_root=project_root, output_root=artifacts.origin_file.parents[1]).strip(),
    }


def _write_metadata(
    run_root: Path,
    options: XrdNoCardOverlayOptions,
    table: XrdNoCardOverlayTable,
    artifacts: XrdNoCardOverlayArtifacts,
    export_status: dict[str, object],
    reference_opju: Path | None,
) -> Path:
    payload = {
        "dataset_id": safe_name(options.output_stem),
        "run_root": ".",
        "data_type": "XRD",
        "processor_name": "xrd_no_card_overlay_processor",
        "processing_status": "success" if export_status.get("ok") else ("fail" if options.with_origin else "processed_no_origin"),
        "source_files": [_display_path(run_root, path) for path in options.sources],
        "source_hashes": {label: file_hash(path) for label, path in zip(table.labels, options.sources)},
        "processed_data": _relative(run_root, artifacts.processed_data),
        "origin_file": _relative(run_root, artifacts.origin_file) if artifacts.origin_file.exists() else None,
        "figure_tif": _relative(run_root, artifacts.figure_tif) if artifacts.figure_tif.exists() else None,
        "preview_png": _relative(run_root, artifacts.preview_png) if artifacts.preview_png.exists() else None,
        "origin_reference_opju": _display_path(run_root, reference_opju) if reference_opju else None,
        "origin_status": _sanitize_output_value(run_root, export_status),
        "plot_type": "single-page normalized offset XRD overlay without standard-card lines",
        "standard_card_added": False,
        "manual_check_required": True,
        "manual_check_items": [
            "confirm sample labels, order, normalization, offsets, and XRD peak positions",
            "no standard-card sticks were added per user request",
            "inspect PNG preview for Graph4 style, single graph page, and no template residue",
        ],
        "forbidden_claims": [
            "do not assign phase automatically",
            "do not label crystal planes automatically",
            "do not claim impurity-free automatically",
            "do not infer heterojunction type or electron transfer direction from this plot",
        ],
        "parameters": table.metadata,
    }
    artifacts.metadata.parent.mkdir(parents=True, exist_ok=True)
    artifacts.metadata.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return artifacts.metadata


def _write_report(
    run_root: Path,
    options: XrdNoCardOverlayOptions,
    table: XrdNoCardOverlayTable,
    artifacts: XrdNoCardOverlayArtifacts,
    export_status: dict[str, object],
    reference_opju: Path | None,
) -> Path:
    lines = [
        "# XRD No-Card Overlay Report",
        "",
        f"- Status: {'success' if export_status.get('ok') else ('origin_failed' if options.with_origin else 'processed_no_origin')}",
        f"- Processed CSV: `{_relative(run_root, artifacts.processed_data)}`",
        f"- Origin OPJU: `{_relative(run_root, artifacts.origin_file) if artifacts.origin_file.exists() else 'not exported'}`",
        f"- TIF: `{_relative(run_root, artifacts.figure_tif) if artifacts.figure_tif.exists() else 'not exported'}`",
        f"- PNG preview: `{_relative(run_root, artifacts.preview_png) if artifacts.preview_png.exists() else 'not exported'}`",
        f"- Reference OPJU: `{_display_path(run_root, reference_opju) if reference_opju else 'cached Graph4 constants only'}`",
        "- Standard card: not added",
        "",
        "## Series",
        "",
        "| order | label | source | role |",
        "|---:|---|---|---|",
    ]
    for index, (label, source) in enumerate(zip(table.labels, options.sources), start=1):
        lines.append(f"| {index} | `{label}` | `{source.name}` | normalized offset XRD trace |")
    lines.extend(
        [
            "",
            "No phase assignment, crystal-plane assignment, mechanism conclusion, or impurity conclusion is made by this output.",
        ]
    )
    artifacts.report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return artifacts.report


def _validate_sources(sources: tuple[Path, ...]) -> None:
    if not sources:
        raise ValueError("XRD no-card overlay requires at least one source file.")
    for source in sources:
        if not source.exists() or not source.is_file():
            raise FileNotFoundError(f"XRD no-card source does not exist or is not a file: {source}")


def _resolve_reference_opju(project_root: Path, reference_opju: Path | None) -> Path | None:
    if reference_opju is not None:
        path = reference_opju if reference_opju.is_absolute() else project_root / reference_opju
        if not path.exists():
            raise FileNotFoundError(f"Explicit XRD no-card reference OPJU does not exist: {reference_opju}")
        return path
    pattern = resolve_origin_reference_pattern(project_root)
    path = Path(pattern)
    if "*" not in pattern and "?" not in pattern:
        return path if path.exists() else None
    parent = path.parent
    if not parent.exists():
        return None
    candidates = sorted(parent.glob(path.name), key=lambda item: item.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _numeric_xy_points(rows: list[list[float]]) -> list[tuple[float, float]]:
    points: dict[float, float] = {}
    for row in rows:
        if len(row) < 2:
            continue
        x_value = _to_float(row[0])
        y_value = _to_float(row[1])
        if x_value is not None and y_value is not None:
            points[float(x_value)] = float(y_value)
    return sorted(points.items(), key=lambda item: item[0])


def _normalized_offset_y(points: list[tuple[float, float]], x_value: float, offset: float) -> float:
    raw = _interpolated_y(points, x_value)
    y_values = [y for _x, y in points]
    low = min(y_values)
    high = max(y_values)
    if raw is None or high == low:
        return offset
    return offset + (raw - low) / (high - low)


def _offset_for_index(index: int, count: int) -> float:
    return xrd_no_card_offset_for_index(index, count)


def xrd_no_card_offset_for_index(index: int, count: int) -> float:
    return round((count - index - 1) * 1.15, 6)


def _default_label(path: Path) -> str:
    return path.stem.strip() or "sample"


def _write_csv(path: Path, headers: list[str], rows: list[list[float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def _remove_stale_outputs(artifacts: XrdNoCardOverlayArtifacts) -> None:
    for path in (artifacts.origin_file, artifacts.figure_tif, artifacts.preview_png):
        if path.exists():
            path.unlink()


def _origin_process_ids(exclude: set[int] | None = None) -> list[int]:
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-Process -Name Origin* -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id",
            ],
            text=True,
            capture_output=True,
            timeout=10,
        )
    except Exception:
        return []
    excluded = exclude or set()
    pids: list[int] = []
    for line in completed.stdout.splitlines():
        try:
            pid = int(line.strip())
        except ValueError:
            continue
        if pid not in excluded:
            pids.append(pid)
    return pids


def _terminate_task_origin_processes(pre_existing_pids: set[int] | None = None) -> None:
    task_pids = _origin_process_ids(pre_existing_pids or set())
    if not task_pids:
        return
    pid_list = ",".join(str(pid) for pid in task_pids)
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            f"$ids = @({pid_list}); $p = Get-Process -Id $ids -ErrorAction SilentlyContinue; if ($p) {{ $p | Stop-Process -Force }}",
        ],
        text=True,
        capture_output=True,
        timeout=30,
    )


def _copy_artifact(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    shutil.copy2(source, target)


def _display_path(root: Path, path: Path | None) -> str:
    if path is None:
        return ""
    rendered = render_output_path(path, output_root=root)
    return rendered or Path(path).name


def _sanitize_output_value(root: Path, value: object) -> object:
    if isinstance(value, dict):
        return {key: _sanitize_output_value(root, item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_output_value(root, item) for item in value]
    if isinstance(value, str):
        return scrub_output_text(value, output_root=root)
    return value
