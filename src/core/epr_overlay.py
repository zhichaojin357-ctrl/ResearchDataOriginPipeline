from __future__ import annotations

import csv
import json
import os
import shutil
import tempfile
import uuid
import warnings
from dataclasses import dataclass
from pathlib import Path
from statistics import median

from src.core.epr_jeol import read_verified_jeol_export_series
from src.core.file_utils import (
    apply_safe_owned_directory_removal,
    ensure_safe_output_file_target,
    lexical_absolute_path,
    plan_safe_owned_directory_removal,
)
from src.core.output_sanitizer import render_output_path
from src.core.project import (
    ensure_output_path_separate_from_inputs,
    ensure_write_path_allowed,
)
from src.core.runtime_paths import resolve_output_root, resolve_workspace_root
from src.origin.adapter import (
    OriginPlotOutputPaths,
    OriginResult,
    check_origin_available,
    export_plot,
    plan_origin_plot_output_paths,
)
from src.origin.operations import origin_process_ids


DEFAULT_EPR_GROUPS = {
    "OH": (
        ("BC", "BC-OH-light2.xlsx"),
        ("CWO", "CWO-OH-light2.xlsx"),
        ("BOBC", "BOBC-OH-light1.xlsx"),
    ),
    "O3": (
        ("BC", "BC-O3-light5.xlsx"),
        ("CWO", "CWO-O3-light1.xlsx"),
        ("BOBC", "BOBC-O3-light2.xlsx"),
    ),
}


@dataclass(frozen=True)
class EprOverlayOptions:
    reference_dir: Path | None = None
    output_root: Path | None = None
    group: str = "all"
    with_origin: bool = False
    force: bool = False
    normalize: bool = False
    smooth_window: int = 0
    background: str | None = None
    report_json: Path | None = None
    report_md: Path | None = None


@dataclass(frozen=True)
class EprOverlayOutputPlan:
    output_base: Path
    data_dir: Path
    plot_csv: Path
    detail_csv: Path
    metadata_path: Path
    origin_paths: OriginPlotOutputPaths | None

    @property
    def targets(self) -> tuple[Path, ...]:
        paths = [self.plot_csv, self.detail_csv, self.metadata_path]
        if self.origin_paths is not None:
            paths.extend(
                (
                    self.origin_paths.plot_csv,
                    self.origin_paths.origin_file,
                    self.origin_paths.figure_tif,
                    self.origin_paths.preview_png,
                    self.origin_paths.job_script,
                )
            )
        return tuple(paths)


class _EprOverlayRollbackError(RuntimeError):
    """Raised when a failed EPR package commit cannot be rolled back fully."""


def run_epr_overlay(project_root: Path, options: EprOverlayOptions) -> int:
    reference_dir = options.reference_dir or _default_reference_dir(project_root)
    if not reference_dir.is_dir():
        raise FileNotFoundError(f"EPR verified Excel reference directory not found: {reference_dir}")

    selected_groups = _selected_groups(options.group)
    _validate_smoothing_window(options.smooth_window)
    output_root = lexical_absolute_path(
        resolve_output_root(project_root, options.output_root)
    )
    output_json = _resolve_output_file(
        project_root,
        options.report_json or output_root / "reports" / "epr_overlay_report.json",
        output_root,
    )
    output_md = _resolve_output_file(
        project_root,
        options.report_md or output_root / "reports" / "epr_overlay_report.md",
        output_root,
    )
    report_targets = (
        output_json,
        output_md,
    )
    plans = {
        group_name: _plan_epr_overlay_outputs(
            project_root,
            group_name,
            with_origin=options.with_origin,
            output_root=output_root,
        )
        for group_name in selected_groups
    }
    input_paths = _validated_epr_input_paths(
        reference_dir,
        selected_groups,
        background=options.background,
    )
    for group_name in selected_groups:
        _prevalidate_epr_group_semantics(
            reference_dir,
            group_name,
            normalize=options.normalize,
            smooth_window=options.smooth_window,
            background=options.background,
        )
    if options.with_origin:
        origin_ok, origin_message = check_origin_available()
        if not origin_ok:
            raise RuntimeError(
                "Origin is unavailable before EPR output preflight: "
                + origin_message
            )
        pre_existing_pids = origin_process_ids()
        if pre_existing_pids:
            raise RuntimeError(
                "Origin is already running before EPR output preflight; "
                "refusing to replace any existing product "
                f"(PIDs: {', '.join(str(pid) for pid in sorted(pre_existing_pids))})."
            )
    _ensure_epr_outputs_separate_from_inputs(
        project_root,
        output_root,
        reference_dir,
        input_paths,
    )
    _prepare_epr_targets(
        (*[path for plan in plans.values() for path in plan.targets], *report_targets),
        output_root=output_root,
        force=options.force,
        context="EPR overlay command",
    )

    rows = []
    for group_name in selected_groups:
        result = build_epr_condition_overlay(
            project_root,
            reference_dir,
            group_name,
            with_origin=options.with_origin,
            force=options.force,
            normalize=options.normalize,
            smooth_window=options.smooth_window,
            background=options.background,
            _output_plan=plans[group_name],
            _preflight_complete=True,
        )
        rows.append(result)

    payload = {
        "command": "epr-overlay",
        "reference_dir": render_output_path(reference_dir, project_root=project_root),
        "normalization": "max_abs_per_trace" if options.normalize else "none; amplitudes preserved",
        "baseline_correction": "edge-region median baseline subtraction",
        "smoothing": f"moving_average_window_{options.smooth_window}" if options.smooth_window else "none by default",
        "background_subtraction": options.background or "none unless explicit dark/background mapping is supplied",
        "offset_rule": "median peak-to-peak range * 0.85 rounded to a readable step; BC top, CWO middle, BOBC bottom",
        "forbidden_claims": ["no automatic radical assignment", "no automatic mechanism claim"],
        "items": rows,
    }
    _write_reports_atomically(
        project_root,
        output_json,
        output_md,
        payload,
        output_root,
        force=options.force,
    )
    return 0 if all(item["status"] in {"table_only", "success"} for item in rows) else 2


def build_epr_condition_overlay(
    project_root: Path,
    reference_dir: Path,
    group_name: str,
    *,
    with_origin: bool = False,
    force: bool = False,
    normalize: bool = False,
    smooth_window: int = 0,
    background: str | None = None,
    output_data_dir: Path | None = None,
    output_root: Path | None = None,
    _output_plan: EprOverlayOutputPlan | None = None,
    _preflight_complete: bool = False,
) -> dict:
    entries = DEFAULT_EPR_GROUPS[group_name]
    background_map = _background_map(background, group_name)
    traces = []
    for label, file_name in entries:
        path = reference_dir / file_name
        if not path.is_file():
            raise FileNotFoundError(f"EPR overlay input missing for {group_name}: {path}")
        export = read_verified_jeol_export_series(path)
        x_values, y_values = export.x_values, export.y_values
        if len(x_values) < 2:
            raise ValueError(f"EPR overlay input needs at least two points, got {len(x_values)} rows in {path}")
        raw_values = list(y_values)
        background_subtracted = None
        if label in background_map:
            background_path = reference_dir / background_map[label]
            if not background_path.is_file():
                raise FileNotFoundError(f"EPR background file missing for {label}: {background_path}")
            background_export = read_verified_jeol_export_series(background_path)
            background_x, background_y = background_export.x_values, background_export.y_values
            if export.x_unit and background_export.x_unit and export.x_unit != background_export.x_unit:
                raise ValueError(
                    f"EPR field-unit mismatch for {label}: {export.x_unit} versus {background_export.x_unit}"
                )
            _validate_common_x([x_values, background_x])
            y_values = [value - bg for value, bg in zip(y_values, background_y)]
            background_subtracted = list(y_values)
        centered, baseline = _baseline_correct(y_values)
        if smooth_window:
            centered = _moving_average(centered, smooth_window)
        if normalize:
            centered = _max_abs_normalize(centered)
        traces.append(
            {
                "label": label,
                "file_label": Path(file_name).stem,
                "path": path,
                "x": x_values,
                "centered": centered,
                "raw": raw_values,
                "baseline": baseline,
                "background_subtracted": background_subtracted,
                "background_file": background_map.get(label),
                "field_unit": export.x_unit,
                "field_axis_source": export.axis_source,
                "raw_source": export.raw_source,
            }
        )

    _validate_common_x([trace["x"] for trace in traces])
    field_units = {str(trace["field_unit"]) for trace in traces if str(trace["field_unit"]).strip()}
    if len(field_units) > 1:
        raise ValueError(f"EPR overlay inputs use inconsistent field units: {sorted(field_units)}")
    field_unit = next(iter(field_units), "")
    step = _offset_step([trace["centered"] for trace in traces])
    offsets = {trace["label"]: (len(traces) - index - 1) * step for index, trace in enumerate(traces)}

    slug = f"epr_{group_name.lower()}_overlay"
    plan = _output_plan or _plan_epr_overlay_outputs(
        project_root,
        group_name,
        with_origin=with_origin,
        output_data_dir=output_data_dir,
        output_root=output_root,
    )
    data_dir = plan.data_dir
    output_base = plan.output_base
    plot_csv = plan.plot_csv
    detail_csv = plan.detail_csv
    metadata_path = plan.metadata_path
    input_paths = [
        Path(str(trace["path"]))
        for trace in traces
    ]
    input_paths.extend(
        reference_dir / str(trace["background_file"])
        for trace in traces
        if trace["background_file"]
    )
    input_paths.extend(
        Path(str(trace["raw_source"]))
        for trace in traces
        if trace["raw_source"] is not None
    )
    _ensure_epr_outputs_separate_from_inputs(
        project_root,
        output_base,
        reference_dir,
        input_paths,
    )
    ensure_write_path_allowed(
        project_root,
        output_base,
        output_root=output_base,
    )
    ensure_safe_output_file_target(output_base, output_root=output_base)
    if with_origin:
        _assert_epr_origin_ready_before_output_mutation()
    if not _preflight_complete:
        _prepare_epr_targets(
            plan.targets,
            output_root=output_base,
            force=force,
            context=f"EPR {group_name} overlay",
        )
    origin_result = _materialize_epr_overlay_group(
        project_root=project_root,
        reference_dir=reference_dir,
        group_name=group_name,
        traces=traces,
        field_unit=field_unit,
        offsets=offsets,
        offset_step=step,
        plan=plan,
        with_origin=with_origin,
        force=force,
    )
    status = "success" if origin_result is not None else "table_only"
    render = lambda value: render_output_path(
        value,
        project_root=project_root,
        output_root=output_base,
    )

    return {
        "group": group_name,
        "status": status,
        "input_files": [Path(str(trace["path"])).name for trace in traces],
        "labels": [trace["label"] for trace in traces],
        "file_labels": [trace["file_label"] for trace in traces],
        "point_count": len(traces[0]["x"]),
        "x_min": min(traces[0]["x"]),
        "x_max": max(traces[0]["x"]),
        "field_unit": field_unit,
        "field_axis_sources": {trace["label"]: trace["field_axis_source"] for trace in traces},
        "offset_step": step,
        "offsets": offsets,
        "baseline_correction": "edge-region median baseline subtraction",
        "baseline_values": {trace["label"]: trace["baseline"] for trace in traces},
        "smoothing": f"moving_average_window_{smooth_window}" if smooth_window else "none",
        "normalization": "max_abs_per_trace" if normalize else "none",
        "background_subtraction": background or "none",
        "background_files": {trace["label"]: trace["background_file"] for trace in traces if trace["background_file"]},
        "processed_csv": render(plot_csv),
        "detail_csv": render(detail_csv),
        "metadata": render(metadata_path),
        "origin_file": render(origin_result.origin_file) if origin_result and origin_result.origin_file else None,
        "figure_tif": render(origin_result.figure_tif) if origin_result and origin_result.figure_tif else None,
        "preview_png": render(origin_result.preview_png) if origin_result and origin_result.preview_png else None,
        "origin_message": origin_result.message if origin_result else "Origin export not requested",
    }


def _materialize_epr_overlay_group(
    *,
    project_root: Path,
    reference_dir: Path,
    group_name: str,
    traces: list[dict],
    field_unit: str,
    offsets: dict[str, float],
    offset_step: float,
    plan: EprOverlayOutputPlan,
    with_origin: bool,
    force: bool,
) -> OriginResult | None:
    output_base = plan.output_base
    output_base.mkdir(parents=True, exist_ok=True)
    ensure_safe_output_file_target(output_base, output_root=output_base)
    stage_root: Path | None = None
    preserve_stage_for_recovery = False
    try:
        stage_root = lexical_absolute_path(
            Path(
                tempfile.mkdtemp(
                    prefix=f".epr-{group_name.lower()}-staging-",
                    dir=output_base,
                )
            )
        )
        ensure_safe_output_file_target(stage_root, output_root=output_base)
        staged_data_dir = stage_root / plan.data_dir.relative_to(output_base)
        staged_plan = _plan_epr_overlay_outputs(
            project_root,
            group_name,
            with_origin=with_origin,
            output_data_dir=staged_data_dir,
        )
        _write_epr_overlay_csvs(staged_plan, traces, offsets)

        published_origin: OriginResult | None = None
        color_report_mappings: list[tuple[Path, Path]] = []
        if with_origin:
            _seed_epr_material_color_reports(
                output_base=output_base,
                stage_root=stage_root,
            )
            staged_origin = export_plot(
                project_root,
                f"EPR_{group_name}_overlay",
                staged_plan.plot_csv,
                (
                    f"Magnetic Field ({field_unit})"
                    if field_unit
                    else "Magnetic Field"
                ),
                "Intensity (a.u.)",
                data_type="EPR overlay",
                source_file=reference_dir,
                output_root=stage_root,
                force=False,
            )
            if not staged_origin.ok:
                raise RuntimeError(
                    "Origin EPR overlay export failed before package commit: "
                    f"{staged_origin.message}"
                )
            if plan.origin_paths is None or staged_plan.origin_paths is None:
                raise RuntimeError("EPR Origin output plan is missing")
            published_origin = OriginResult(
                True,
                plan.origin_paths.origin_file,
                plan.origin_paths.figure_tif,
                plan.origin_paths.preview_png,
                staged_origin.message,
                getattr(staged_origin, "tif_resolution_evidence", None),
            )
            for name in (
                "locked_result_material_color_map.json",
                "locked_result_material_color_map.md",
            ):
                staged_report = stage_root / "reports" / name
                if staged_report.is_file():
                    color_report_mappings.append(
                        (staged_report, output_base / "reports" / name)
                    )

        metadata_payload = _epr_overlay_metadata_payload(
            project_root=project_root,
            reference_dir=reference_dir,
            group_name=group_name,
            traces=traces,
            field_unit=field_unit,
            offsets=offsets,
            offset_step=offset_step,
            plan=plan,
            origin_result=published_origin,
        )
        staged_plan.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        staged_plan.metadata_path.write_text(
            json.dumps(metadata_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        mappings: list[tuple[Path, Path]] = [
            (staged_plan.plot_csv, plan.plot_csv),
            (staged_plan.detail_csv, plan.detail_csv),
            (staged_plan.metadata_path, plan.metadata_path),
        ]
        deletion_targets: tuple[Path, ...] = ()
        if with_origin:
            assert staged_plan.origin_paths is not None
            assert plan.origin_paths is not None
            mappings.extend(
                (
                    (
                        staged_plan.origin_paths.plot_csv,
                        plan.origin_paths.plot_csv,
                    ),
                    (
                        staged_plan.origin_paths.origin_file,
                        plan.origin_paths.origin_file,
                    ),
                    (
                        staged_plan.origin_paths.figure_tif,
                        plan.origin_paths.figure_tif,
                    ),
                    (
                        staged_plan.origin_paths.preview_png,
                        plan.origin_paths.preview_png,
                    ),
                )
            )
            deletion_targets = (plan.origin_paths.job_script,)
        mappings.extend(color_report_mappings)
        _validate_staged_epr_overlay_files(
            tuple(staged for staged, _final in mappings),
            stage_root=stage_root,
        )
        _commit_staged_epr_overlay_files(
            tuple(mappings),
            deletion_targets=deletion_targets,
            replace_existing_targets=tuple(
                final for _staged, final in color_report_mappings
            ),
            output_root=output_base,
            stage_root=stage_root,
            force=force,
        )
        return published_origin
    except _EprOverlayRollbackError:
        preserve_stage_for_recovery = True
        raise
    finally:
        if stage_root is not None and not preserve_stage_for_recovery:
            _remove_safe_epr_overlay_tree_best_effort(
                stage_root,
                output_root=output_base,
            )


def _write_epr_overlay_csvs(
    plan: EprOverlayOutputPlan,
    traces: list[dict],
    offsets: dict[str, float],
) -> None:
    plan.plot_csv.parent.mkdir(parents=True, exist_ok=True)
    header = ["magnetic_field", *[trace["label"] for trace in traces]]
    detail_header = ["magnetic_field"]
    for trace in traces:
        label = trace["label"]
        detail_header.extend(
            [
                f"{label}_raw",
                f"{label}_baseline",
                f"{label}_baseline_corrected",
                f"{label}_offset",
            ]
        )
        if trace["background_subtracted"] is not None:
            detail_header.append(f"{label}_background_subtracted_optional")

    with plan.plot_csv.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for row_index, field in enumerate(traces[0]["x"]):
            writer.writerow(
                [
                    field,
                    *[
                        trace["centered"][row_index] + offsets[trace["label"]]
                        for trace in traces
                    ],
                ]
            )

    with plan.detail_csv.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(detail_header)
        for row_index, field in enumerate(traces[0]["x"]):
            row = [field]
            for trace in traces:
                row.extend(
                    [
                        trace["raw"][row_index],
                        trace["baseline"],
                        trace["centered"][row_index],
                        trace["centered"][row_index]
                        + offsets[trace["label"]],
                    ]
                )
                if trace["background_subtracted"] is not None:
                    row.append(trace["background_subtracted"][row_index])
            writer.writerow(row)


def _epr_overlay_metadata_payload(
    *,
    project_root: Path,
    reference_dir: Path,
    group_name: str,
    traces: list[dict],
    field_unit: str,
    offsets: dict[str, float],
    offset_step: float,
    plan: EprOverlayOutputPlan,
    origin_result: OriginResult | None,
) -> dict:
    render = lambda value: render_output_path(
        value,
        project_root=project_root,
        output_root=plan.output_base,
    )
    status = "success" if origin_result is not None else "table_only"
    tif_resolution_evidence: dict[str, object] | None = None
    if origin_result is not None:
        evidence = getattr(origin_result, "tif_resolution_evidence", None)
        if evidence is not None:
            tif_resolution_evidence = dict(evidence.as_dict())
            if origin_result.figure_tif is not None:
                tif_resolution_evidence["path"] = render(
                    origin_result.figure_tif
                )
    return {
        "dataset_id": f"epr_{group_name.lower()}_overlay",
        "metadata_path": render(plan.metadata_path),
        "data_type": "EPR",
        "subtype": "EPR overlay",
        "group": group_name,
        "source_files": [Path(str(trace["path"])).name for trace in traces],
        "processed_data": render(plan.plot_csv),
        "detail_csv": render(plan.detail_csv),
        "origin_file": (
            render(origin_result.origin_file)
            if origin_result and origin_result.origin_file
            else None
        ),
        "figure_tif": (
            render(origin_result.figure_tif)
            if origin_result and origin_result.figure_tif
            else None
        ),
        "preview_png": (
            render(origin_result.preview_png)
            if origin_result and origin_result.preview_png
            else None
        ),
        "tif_resolution_evidence": tif_resolution_evidence,
        "processing_status": status,
        "field_unit": field_unit or None,
        "field_axis_sources": {
            trace["label"]: trace["field_axis_source"] for trace in traces
        },
        "verified_raw_sources": {
            trace["label"]: Path(str(trace["raw_source"])).name
            for trace in traces
            if trace["raw_source"] is not None
        },
        "manual_check_required": True,
        "manual_check_items": [
            "confirm EPR field calibration, baseline handling, and trace offsets",
            "radical identity assignment requires manual scientific review",
        ],
        "forbidden_claims": [
            "no automatic radical assignment",
            "no automatic mechanism claim",
        ],
        "key_results": {
            "point_count": len(traces[0]["x"]),
            "x_min": min(traces[0]["x"]),
            "x_max": max(traces[0]["x"]),
            "offset_step": offset_step,
            "offsets": offsets,
            "baseline_values": {
                trace["label"]: trace["baseline"] for trace in traces
            },
        },
    }


def _assert_epr_origin_ready_before_output_mutation() -> None:
    origin_ok, origin_message = check_origin_available()
    if not origin_ok:
        raise RuntimeError(
            "Origin is unavailable before EPR output preflight: "
            + origin_message
        )
    pre_existing_pids = origin_process_ids()
    if pre_existing_pids:
        raise RuntimeError(
            "Origin is already running before EPR output preflight; "
            "refusing to replace any existing product "
            f"(PIDs: {', '.join(str(pid) for pid in sorted(pre_existing_pids))})."
        )


def _seed_epr_material_color_reports(
    *,
    output_base: Path,
    stage_root: Path,
) -> None:
    for name in (
        "locked_result_material_color_map.json",
        "locked_result_material_color_map.md",
    ):
        final_path = ensure_safe_output_file_target(
            output_base / "reports" / name,
            output_root=output_base,
        )
        if not os.path.lexists(os.fspath(final_path)):
            continue
        if not final_path.is_file():
            raise IsADirectoryError(
                f"EPR material-color report target is not a file: {final_path}"
            )
        staged_path = ensure_safe_output_file_target(
            stage_root / "reports" / name,
            output_root=stage_root,
        )
        staged_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(final_path, staged_path)


def _validate_staged_epr_overlay_files(
    paths: tuple[Path, ...],
    *,
    stage_root: Path,
) -> None:
    for path in paths:
        safe_path = ensure_safe_output_file_target(path, output_root=stage_root)
        if not safe_path.is_file() or safe_path.stat().st_size <= 0:
            raise RuntimeError(
                f"Staged EPR overlay package file is missing or empty: {safe_path}"
            )
        if safe_path.name == "metadata.json":
            payload = json.loads(safe_path.read_text(encoding="utf-8"))
            if payload.get("processing_status") not in {"table_only", "success"}:
                raise RuntimeError(
                    f"Staged EPR overlay metadata status is invalid: {safe_path}"
                )


def _commit_staged_epr_overlay_files(
    mappings: tuple[tuple[Path, Path], ...],
    *,
    deletion_targets: tuple[Path, ...],
    replace_existing_targets: tuple[Path, ...],
    output_root: Path,
    stage_root: Path,
    force: bool,
) -> None:
    replace_keys = {
        lexical_absolute_path(path) for path in replace_existing_targets
    }
    final_targets = tuple(
        ensure_safe_output_file_target(path, output_root=output_root)
        for _staged, path in mappings
    )
    safe_deletions = tuple(
        ensure_safe_output_file_target(path, output_root=output_root)
        for path in deletion_targets
    )
    all_targets = (*final_targets, *safe_deletions)
    if len(set(all_targets)) != len(all_targets):
        raise ValueError("EPR overlay commit targets must be distinct")
    existing = [
        path for path in all_targets if os.path.lexists(os.fspath(path))
    ]
    directories = [path for path in existing if path.is_dir()]
    if directories:
        raise IsADirectoryError(
            "EPR overlay file target became a directory before commit: "
            + ", ".join(str(path) for path in directories)
        )
    disallowed_existing = [
        path
        for path in existing
        if not force and lexical_absolute_path(path) not in replace_keys
    ]
    if disallowed_existing:
        raise FileExistsError(
            "EPR overlay targets appeared before commit; rerun with force=True: "
            + ", ".join(str(path) for path in disallowed_existing)
        )
    for staged, _final in mappings:
        safe_staged = ensure_safe_output_file_target(
            staged,
            output_root=stage_root,
        )
        if not safe_staged.is_file() or safe_staged.stat().st_size <= 0:
            raise RuntimeError(
                f"Staged EPR overlay file changed before commit: {safe_staged}"
            )

    backup_root = ensure_safe_output_file_target(
        stage_root / "rollback",
        output_root=stage_root,
    )
    backups: list[tuple[Path, Path]] = []
    installed: list[Path] = []
    try:
        for final_path in all_targets:
            if not os.path.lexists(os.fspath(final_path)):
                continue
            backup = ensure_safe_output_file_target(
                backup_root / final_path.relative_to(output_root),
                output_root=stage_root,
            )
            backup.parent.mkdir(parents=True, exist_ok=True)
            _atomic_replace_epr_overlay(final_path, backup)
            backups.append((backup, final_path))
        for (staged, _original_final), final_path in zip(
            mappings,
            final_targets,
            strict=True,
        ):
            if os.path.lexists(os.fspath(final_path)):
                raise RuntimeError(
                    f"EPR overlay target changed during commit: {final_path}"
                )
            final_path.parent.mkdir(parents=True, exist_ok=True)
            _atomic_replace_epr_overlay(staged, final_path)
            installed.append(final_path)
    except Exception as exc:
        rollback_errors: list[str] = []
        for final_path in reversed(installed):
            try:
                safe_path = ensure_safe_output_file_target(
                    final_path,
                    output_root=output_root,
                )
                if not safe_path.is_file():
                    raise RuntimeError("installed target is not a regular file")
                safe_path.unlink()
            except Exception as rollback_exc:
                rollback_errors.append(f"remove {final_path}: {rollback_exc}")
        for backup, final_path in reversed(backups):
            try:
                if os.path.lexists(os.fspath(final_path)):
                    raise RuntimeError(
                        "unexpected target appeared before rollback restoration"
                    )
                final_path.parent.mkdir(parents=True, exist_ok=True)
                _atomic_replace_epr_overlay(backup, final_path)
            except Exception as rollback_exc:
                rollback_errors.append(f"restore {final_path}: {rollback_exc}")
        if rollback_errors:
            raise _EprOverlayRollbackError(
                "EPR overlay commit failed and rollback was incomplete; "
                f"recovery files remain under {stage_root}: "
                + "; ".join(rollback_errors)
            ) from exc
        raise RuntimeError(
            f"EPR overlay commit failed; previous outputs were restored: {exc}"
        ) from exc


def _atomic_replace_epr_overlay(source: Path, target: Path) -> None:
    os.replace(source, target)


def _remove_safe_epr_overlay_tree(path: Path, *, output_root: Path) -> None:
    if not os.path.lexists(os.fspath(path)):
        return
    plan = plan_safe_owned_directory_removal(path, output_root=output_root)
    apply_safe_owned_directory_removal(plan, output_root=output_root)


def _remove_safe_epr_overlay_tree_best_effort(
    path: Path,
    *,
    output_root: Path,
) -> None:
    try:
        _remove_safe_epr_overlay_tree(path, output_root=output_root)
    except Exception as exc:
        warnings.warn(
            "EPR overlay outputs were committed, but the task-owned staging "
            f"directory could not be removed safely: {path}: {exc}",
            RuntimeWarning,
            stacklevel=2,
        )


def _output_base_for_data_dir(project_root: Path, data_dir: Path) -> Path:
    data_dir = lexical_absolute_path(data_dir)
    if data_dir.parent.name == "processed_data":
        return data_dir.parent.parent
    if data_dir.name == "processed_data":
        return data_dir.parent
    return data_dir


def _epr_overlay_metadata_path(project_root: Path, data_dir: Path, slug: str) -> Path:
    if data_dir.name == "processed_data":
        return data_dir.parent / "metadata" / slug / "metadata.json"
    if data_dir.parent.name == "processed_data":
        return data_dir.parent.parent / "metadata" / data_dir.name / slug / "metadata.json"
    return _output_base_for_data_dir(project_root, data_dir) / "metadata" / "EPR" / slug / "metadata.json"


def _plan_epr_overlay_outputs(
    project_root: Path,
    group_name: str,
    *,
    with_origin: bool,
    output_data_dir: Path | None = None,
    output_root: Path | None = None,
) -> EprOverlayOutputPlan:
    if output_data_dir is None:
        output_base = lexical_absolute_path(
            resolve_output_root(project_root, output_root)
        )
        data_dir = output_base / "processed_data" / "EPR"
    else:
        data_dir = lexical_absolute_path(output_data_dir)
        output_base = _output_base_for_data_dir(project_root, data_dir)
    slug = f"epr_{group_name.lower()}_overlay"
    origin_paths = (
        plan_origin_plot_output_paths(
            project_root,
            f"EPR_{group_name}_overlay",
            output_root=output_base,
        )
        if with_origin
        else None
    )
    return EprOverlayOutputPlan(
        output_base=output_base,
        data_dir=data_dir,
        plot_csv=data_dir / f"{slug}_processed.csv",
        detail_csv=data_dir / f"{slug}_detail.csv",
        metadata_path=_epr_overlay_metadata_path(project_root, data_dir, slug),
        origin_paths=origin_paths,
    )


def _validated_epr_input_paths(
    reference_dir: Path,
    groups: list[str],
    *,
    background: str | None,
) -> tuple[Path, ...]:
    paths: list[Path] = []
    for group_name in groups:
        paths.extend(reference_dir / file_name for _label, file_name in DEFAULT_EPR_GROUPS[group_name])
        paths.extend(
            reference_dir / file_name
            for file_name in _background_map(background, group_name).values()
        )
    verified_paths = list(dict.fromkeys(paths))
    raw_sources: list[Path] = []
    for path in verified_paths:
        if not path.is_file():
            raise FileNotFoundError(f"EPR overlay input missing: {path}")
        series = read_verified_jeol_export_series(path)
        if series.raw_source is not None:
            raw_sources.append(series.raw_source)
    return tuple(dict.fromkeys((*verified_paths, *raw_sources)))


def _ensure_epr_outputs_separate_from_inputs(
    project_root: Path,
    output_base: Path,
    reference_dir: Path,
    input_paths: list[Path] | tuple[Path, ...],
) -> None:
    ensure_output_path_separate_from_inputs(
        project_root,
        output_base,
        (reference_dir, *input_paths),
    )


def _prepare_epr_targets(
    paths: list[Path] | tuple[Path, ...],
    *,
    output_root: Path,
    force: bool,
    context: str,
) -> tuple[Path, ...]:
    lexical_paths = tuple(lexical_absolute_path(path) for path in paths)
    if len(set(lexical_paths)) != len(lexical_paths):
        raise ValueError(f"Planned {context} targets must be distinct.")
    safe_paths = tuple(
        ensure_safe_output_file_target(path, output_root=output_root)
        for path in lexical_paths
    )
    existing = [
        path for path in safe_paths if os.path.lexists(os.fspath(path))
    ]
    directories = [path for path in existing if path.is_dir()]
    if directories:
        raise IsADirectoryError(
            f"Planned {context} file target collides with a directory: "
            + ", ".join(str(path) for path in directories[:8])
        )
    if existing and not force:
        raise FileExistsError(
            f"One or more planned {context} files already exist; "
            "rerun with force=True to overwrite: "
            + ", ".join(str(path) for path in existing[:8])
        )
    return safe_paths


def _default_reference_dir(project_root: Path) -> Path:
    return resolve_workspace_root(project_root) / "EPR" / "导出后的数据"


def _selected_groups(group: str) -> list[str]:
    if group == "all":
        return list(DEFAULT_EPR_GROUPS)
    normalized = group.upper()
    if normalized not in DEFAULT_EPR_GROUPS:
        raise ValueError(f"unknown EPR overlay group: {group}; expected one of all, OH, O3")
    return [normalized]


def _baseline_correct(values: list[float]) -> tuple[list[float], float]:
    baseline = _edge_region_baseline(values)
    return [value - baseline for value in values], baseline


def _edge_region_baseline(values: list[float]) -> float:
    if len(values) < 40:
        return median(values)
    edge_count = max(20, int(len(values) * 0.05))
    return median(values[:edge_count] + values[-edge_count:])


def _max_abs_normalize(values: list[float]) -> list[float]:
    scale = max((abs(value) for value in values), default=0.0)
    if scale == 0:
        return values
    return [value / scale for value in values]


def _moving_average(values: list[float], window: int) -> list[float]:
    _validate_smoothing_window(window)
    if window <= 1:
        return list(values)
    half = window // 2
    output = []
    for index in range(len(values)):
        start = max(0, index - half)
        end = min(len(values), index + half + 1)
        output.append(sum(values[start:end]) / (end - start))
    return output


def _validate_smoothing_window(window: int) -> None:
    if window < 0:
        raise ValueError("EPR smoothing window may not be negative")
    if window > 1 and window % 2 == 0:
        raise ValueError("EPR smoothing window must be odd to preserve peak centers")
    if window > 31:
        raise ValueError("EPR smoothing window is too large for conservative plotting; use <=31")


def _prevalidate_epr_group_semantics(
    reference_dir: Path,
    group_name: str,
    *,
    normalize: bool,
    smooth_window: int,
    background: str | None,
) -> None:
    background_map = _background_map(background, group_name)
    grids: list[list[float]] = []
    units: set[str] = set()
    for label, file_name in DEFAULT_EPR_GROUPS[group_name]:
        export = read_verified_jeol_export_series(reference_dir / file_name)
        if len(export.x_values) < 2:
            raise ValueError(
                f"EPR overlay input needs at least two points: {file_name}"
            )
        values = list(export.y_values)
        if export.x_unit:
            units.add(export.x_unit)
        grids.append(list(export.x_values))
        background_name = background_map.get(label)
        if background_name:
            background_export = read_verified_jeol_export_series(
                reference_dir / background_name
            )
            if (
                export.x_unit
                and background_export.x_unit
                and export.x_unit != background_export.x_unit
            ):
                raise ValueError(
                    f"EPR field-unit mismatch for {label}: "
                    f"{export.x_unit} versus {background_export.x_unit}"
                )
            _validate_common_x(
                [list(export.x_values), list(background_export.x_values)]
            )
            values = [
                value - background_value
                for value, background_value in zip(
                    values,
                    background_export.y_values,
                )
            ]
        centered, _baseline = _baseline_correct(values)
        if smooth_window:
            centered = _moving_average(centered, smooth_window)
        if normalize:
            _max_abs_normalize(centered)
    _validate_common_x(grids)
    if len(units) > 1:
        raise ValueError(
            f"EPR overlay inputs use inconsistent field units: {sorted(units)}"
        )


def _background_map(background: str | None, group_name: str) -> dict[str, str]:
    if background in {None, "", "none"}:
        return {}
    if background == "matched_dark" and group_name == "OH":
        return {
            "BC": "BC-OH-dark.xlsx",
            "CWO": "CWO-OH-dark.xlsx",
        }
    if background == "matched_dark" and group_name == "O3":
        return {
            "BC": "BC-O3-dark.xlsx",
            "CWO": "CWO-O3-dark.xlsx",
        }
    raise ValueError(f"unsupported EPR background option for {group_name}: {background}")


def _offset_step(traces: list[list[float]]) -> float:
    ranges = [max(trace) - min(trace) for trace in traces if trace]
    if not ranges:
        return 100.0
    raw_step = median(ranges) * 0.85
    if raw_step <= 100:
        return round(raw_step / 10.0 + 0.499) * 10.0
    return round(raw_step / 50.0 + 0.499) * 50.0


def _validate_common_x(series: list[list[float]]) -> None:
    first = series[0]
    for values in series[1:]:
        if len(values) != len(first):
            raise ValueError("EPR overlay traces have different row counts")
        max_delta = max(abs(a - b) for a, b in zip(first, values))
        if max_delta > 0.0001:
            raise ValueError(f"EPR overlay traces have different magnetic field grids; max delta={max_delta}")


def _report_markdown(payload: dict) -> str:
    lines = [
        "# EPR Overlay Report",
        "",
        f"- Reference dir: `{payload['reference_dir']}`",
        f"- Baseline correction: `{payload['baseline_correction']}`",
        f"- Normalization: `{payload['normalization']}`",
        f"- Smoothing: `{payload['smoothing']}`",
        f"- Background subtraction: `{payload['background_subtraction']}`",
        f"- Offset rule: {payload['offset_rule']}",
        "- Forbidden: no radical assignment, no mechanism claim.",
        "",
        "| group | status | labels | offset step | processed CSV | preview PNG |",
        "|---|---|---|---:|---|---|",
    ]
    for item in payload["items"]:
        lines.append(
            f"| {item['group']} | {item['status']} | {', '.join(item['labels'])} | {item['offset_step']} | "
            f"`{item['processed_csv']}` | `{item.get('preview_png') or ''}` |"
        )
    return "\n".join(lines) + "\n"


def _write_reports_atomically(
    project_root: Path,
    json_path: Path,
    markdown_path: Path,
    payload: dict,
    output_root: Path,
    *,
    force: bool,
) -> None:
    del project_root
    token = uuid.uuid4().hex
    staged: list[tuple[Path, Path]] = []
    backups: list[tuple[Path, Path]] = []
    installed: list[Path] = []
    contents = (
        (json_path, json.dumps(payload, ensure_ascii=False, indent=2)),
        (markdown_path, _report_markdown(payload)),
    )
    try:
        for target, content in contents:
            temporary = target.with_name(
                f".{target.name}.{token}.epr-overlay.tmp"
            )
            ensure_safe_output_file_target(target, output_root=output_root)
            ensure_safe_output_file_target(temporary, output_root=output_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            target = ensure_safe_output_file_target(
                target,
                output_root=output_root,
            )
            if os.path.lexists(os.fspath(target)):
                if target.is_dir():
                    raise IsADirectoryError(
                        f"EPR report target is a directory: {target}"
                    )
                if not force:
                    raise FileExistsError(
                        "One or more EPR report files already exist; "
                        f"rerun with force=True to overwrite: {target}"
                    )
            staged.append((temporary, target))
            with temporary.open("x", encoding="utf-8", newline="") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())

        for _temporary, target in staged:
            ensure_safe_output_file_target(target, output_root=output_root)
            if os.path.lexists(os.fspath(target)):
                backup = target.with_name(
                    f".{target.name}.{token}.epr-overlay.rollback"
                )
                ensure_safe_output_file_target(
                    backup,
                    output_root=output_root,
                )
                os.replace(target, backup)
                backups.append((backup, target))
        for temporary, target in staged:
            os.replace(temporary, target)
            installed.append(target)
    except Exception:
        rollback_errors: list[str] = []
        for target in reversed(installed):
            try:
                safe_target = ensure_safe_output_file_target(
                    target,
                    output_root=output_root,
                )
                if os.path.lexists(os.fspath(safe_target)):
                    safe_target.unlink()
            except Exception as exc:
                rollback_errors.append(f"remove {target}: {exc}")
        for backup, target in reversed(backups):
            try:
                if os.path.lexists(os.fspath(target)):
                    raise RuntimeError(
                        "report target appeared before rollback restoration"
                    )
                os.replace(backup, target)
            except Exception as exc:
                rollback_errors.append(f"restore {target}: {exc}")
        if rollback_errors:
            raise RuntimeError(
                "EPR report commit failed and rollback was incomplete: "
                + "; ".join(rollback_errors)
            )
        raise
    else:
        for backup, _target in backups:
            if os.path.lexists(os.fspath(backup)):
                try:
                    backup.unlink()
                except OSError as exc:
                    warnings.warn(
                        "EPR reports were committed, but a task-owned rollback "
                        f"file could not be removed: {backup}: {exc}",
                        RuntimeWarning,
                        stacklevel=2,
                    )
    finally:
        for temporary, _target in staged:
            if os.path.lexists(os.fspath(temporary)):
                try:
                    temporary.unlink()
                except OSError as exc:
                    warnings.warn(
                        "A task-owned EPR report temporary file could not be "
                        f"removed: {temporary}: {exc}",
                        RuntimeWarning,
                        stacklevel=2,
                    )


def _resolve_output_file(project_root: Path, path: Path, output_root: Path) -> Path:
    target = path if path.is_absolute() else output_root / path
    ensure_write_path_allowed(project_root, target, output_root=output_root)
    return ensure_safe_output_file_target(target, output_root=output_root)
