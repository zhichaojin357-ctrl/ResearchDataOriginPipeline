from __future__ import annotations

from dataclasses import dataclass
import csv
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path

from src.core.project import _parse_simple_yaml


@dataclass(frozen=True)
class OriginResult:
    ok: bool
    origin_file: Path | None
    figure_tif: Path | None
    preview_png: Path | None
    message: str


@dataclass(frozen=True)
class OriginPlotJob:
    dataset_id: str
    data_type: str
    processed_csv: Path
    plot_csv: Path
    source_file: Path | None
    origin_file: Path
    figure_tif: Path
    preview_png: Path
    job_script: Path
    helper_script: Path
    reference_opju: Path | None
    reference_search_pattern: str
    reference_graph: str
    automation_entrypoint: str
    avoid_entrypoint: str
    font_family: str
    line_width: float
    axis_line_width: float
    plot_type_code: str
    page_name: str
    column_count: int
    labels: tuple[str, ...]
    curve_colors: tuple[int, ...]
    color_assignments: tuple[dict[str, object], ...]
    x_title: str
    y_title: str


LINE_PLOT_TYPE = "200"
COLUMN_PLOT_TYPE = "203"
MAX_ORIGIN_PAGE_NAME = 24
GENERIC_SERIES_LABELS = {
    "y",
    "signal",
    "intensity",
    "normalized_intensity",
    "current",
    "one_over_c_squared",
    "raw_intensity",
}
NON_PLOT_COLUMN_TOKENS = (
    "candidate",
    "flag",
    "optional",
    "cycle",
    "state",
    "photon_energy",
    "reflectance_fraction",
    "kubelka",
)


CURVE_COLOR_PALETTE = (
    {"key": "CWO", "role": "material", "name": "blue", "rgb": (0, 114, 178), "origin_ocolor": 28471808},
    {"key": "BOBC", "role": "material", "name": "orange", "rgb": (230, 159, 0), "origin_ocolor": 16818150},
    {"key": "CWO+BOBC", "role": "material_composite", "name": "bluish_green", "rgb": (0, 158, 115), "origin_ocolor": 24354304},
    {"key": "BOC", "role": "material", "name": "sky_blue", "rgb": (86, 180, 233), "origin_ocolor": 32093270},
    {"key": "MCS", "role": "material", "name": "vermillion", "rgb": (213, 94, 0), "origin_ocolor": 16801493},
    {"key": "BM", "role": "material_or_sample_code", "name": "reddish_purple", "rgb": (204, 121, 167), "origin_ocolor": 27752908},
    {"key": "BPO", "role": "material_or_sample_code", "name": "black", "rgb": (0, 0, 0), "origin_ocolor": 16777216},
    {"key": "BPOM", "role": "material_or_sample_code", "name": "dark_teal", "rgb": (17, 119, 51), "origin_ocolor": 20150033},
    {"key": "BOBCMS", "role": "material_or_sample_code", "name": "wine", "rgb": (136, 34, 85), "origin_ocolor": 22356616},
    {"key": "BC", "role": "material_or_sample_code", "name": "teal", "rgb": (68, 170, 153), "origin_ocolor": 26847812},
    {"key": "MS", "role": "material_or_sample_code", "name": "dark_blue", "rgb": (51, 34, 136), "origin_ocolor": 25698867},
    {"key": "MOSE2", "role": "material_or_sample_code", "name": "purple", "rgb": (170, 68, 153), "origin_ocolor": 26821802},
    {"key": "MOTE2", "role": "material_or_sample_code", "name": "sand", "rgb": (221, 204, 119), "origin_ocolor": 24628445},
    {"key": "MB", "role": "sample_series", "name": "olive", "rgb": (153, 153, 51), "origin_ocolor": 20158873},
    {"key": "MT", "role": "sample_series", "name": "brown", "rgb": (102, 17, 0), "origin_ocolor": 16781670},
)
COLOR_BY_KEY = {str(item["key"]): item for item in CURVE_COLOR_PALETTE}
FALLBACK_COLOR_SEQUENCE = tuple(int(item["origin_ocolor"]) for item in CURVE_COLOR_PALETTE)
MATERIAL_PATTERNS = (
    ("CWO+BOBC", re.compile(r"CWO\s*[\+_\-\s]\s*BOBC")),
    ("BOBCMS", re.compile(r"BOBCMS")),
    ("BPOM", re.compile(r"BPOM")),
    ("MOSE2", re.compile(r"MOSE2|MOSE")),
    ("MOTE2", re.compile(r"MOTE2")),
    ("BOBC", re.compile(r"BOBC")),
    ("CWO", re.compile(r"CWO")),
    ("BOC", re.compile(r"BOC")),
    ("MCS", re.compile(r"MCS")),
    ("BPO", re.compile(r"BPO")),
    ("BM", re.compile(r"(?<![A-Z])BM(?=[A-Z0-9_\-\s]|$)")),
    ("BC", re.compile(r"(?<![A-Z])BC(?=[A-Z0-9_\-\s]|$)")),
    ("MS", re.compile(r"(?<![A-Z])MS(?=[A-Z0-9_\-\s]|$)")),
    ("MB", re.compile(r"(?<![A-Z])MB(?=[A-Z0-9_\-\s]|$)")),
    ("MT", re.compile(r"(?<![A-Z])MT(?=[A-Z0-9_\-\s]|$)")),
)


PLOT_TYPE_CODES = {
    "XRD": LINE_PLOT_TYPE,
    "UV-vis DRS": LINE_PLOT_TYPE,
    "EIS": LINE_PLOT_TYPE,
    "photocurrent": LINE_PLOT_TYPE,
    "photocurrent_response": LINE_PLOT_TYPE,
    "XPS": LINE_PLOT_TYPE,
    "PL": LINE_PLOT_TYPE,
    "FTIR": LINE_PLOT_TYPE,
    "Raman": LINE_PLOT_TYPE,
    "HPLC/LC exported data": LINE_PLOT_TYPE,
    "BET": LINE_PLOT_TYPE,
    "EPR": LINE_PLOT_TYPE,
    "Mott-Schottky": LINE_PLOT_TYPE,
    "reaction_condition_screening": COLUMN_PLOT_TYPE,
}


def check_origin_available() -> tuple[bool, str]:
    if os.environ.get("GROUPMEETINGAUTOPPT_DISABLE_ORIGIN") == "1":
        return False, "Origin disabled by GROUPMEETINGAUTOPPT_DISABLE_ORIGIN=1"
    try:
        import originpro  # noqa: F401
    except Exception as exc:
        return False, f"originpro unavailable: {exc}"
    try:
        import win32com.client  # noqa: F401
    except Exception as exc:
        return False, f"win32com unavailable: {exc}"
    return True, "originpro and win32com are importable"


def write_origin_error(project_root: Path, message: str) -> None:
    reports = project_root / "output" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    path = reports / "origin_errors.md"
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Origin Errors\n\n"
    line = f"- {message}"
    error_lines = []
    seen = set()
    for existing_line in existing.splitlines():
        if not existing_line.startswith("- "):
            continue
        if existing_line in seen:
            continue
        seen.add(existing_line)
        error_lines.append(existing_line)
    if line not in seen:
        error_lines.append(line)
    body = "\n\n".join(error_lines)
    path.write_text("# Origin Errors\n\n" + body + ("\n" if body else ""), encoding="utf-8")


def write_origin_success(project_root: Path) -> None:
    reports = project_root / "output" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "origin_errors.md").write_text("# Origin Errors\n\nNo current Origin errors.\n", encoding="utf-8")


def _read_plot_style_value(project_root: Path, key: str, default: str) -> str:
    path = project_root / "config" / "plot_style.yaml"
    if not path.exists():
        return default
    config = _parse_simple_yaml(path.read_text(encoding="utf-8"))
    if key in config:
        return str(config[key])
    origin_template = config.get("origin_template", {})
    if isinstance(origin_template, dict) and key in origin_template:
        return str(origin_template[key])
    export = config.get("export", {})
    if isinstance(export, dict) and key in export:
        return str(export[key])
    return default


def _resolve_reference_opju(pattern: str) -> Path | None:
    path = Path(pattern)
    if "*" not in pattern and "?" not in pattern:
        return path if path.exists() else None
    parent = path.parent
    if not parent.exists():
        return None
    candidates = sorted(parent.glob(path.name), key=lambda item: item.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _csv_header(path: Path) -> list[str]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        return next(reader, [])


def _ps_quote(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _ps_array(values: tuple[str, ...]) -> str:
    return "@(" + ", ".join(_ps_quote(value) for value in values) + ")"


def _ps_int_array(values: tuple[int, ...]) -> str:
    return "@(" + ", ".join(str(int(value)) for value in values) + ")"


def _safe_origin_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    digest = hashlib.sha1(value.encode("utf-8", errors="replace")).hexdigest()[:8]
    base_limit = MAX_ORIGIN_PAGE_NAME - len(digest) - 1
    base = (cleaned or "dataset")[:base_limit].strip("_") or "dataset"
    return f"{base}_{digest}"[:MAX_ORIGIN_PAGE_NAME]


def _normalize_material_text(value: str) -> str:
    return re.sub(r"[^A-Z0-9+]+", "_", value.upper())


def _infer_material_key(*texts: str) -> tuple[str | None, str, float]:
    haystack = " ".join(_normalize_material_text(text) for text in texts if text)
    for key, pattern in MATERIAL_PATTERNS:
        if pattern.search(haystack):
            role = str(COLOR_BY_KEY.get(key, {}).get("role", "material_or_sample_code"))
            confidence = 0.95 if role in {"material", "material_composite"} else 0.8
            return key, role, confidence
    return None, "unassigned", 0.0


def _fallback_sample_key(dataset_id: str, source_file: Path | None) -> str:
    stem = source_file.stem if source_file else dataset_id
    cleaned = re.sub(r"[^A-Za-z0-9_.+-]+", "_", stem).strip("_")
    return f"SAMPLE:{cleaned or dataset_id}"


def _fallback_color_for_key(key: str) -> dict[str, object]:
    digest = hashlib.sha1(key.encode("utf-8", errors="replace")).hexdigest()
    index = int(digest[:8], 16) % len(FALLBACK_COLOR_SEQUENCE)
    base = CURVE_COLOR_PALETTE[index]
    return {
        "key": key,
        "role": "sample_or_unknown",
        "name": f"fallback_{base['name']}",
        "rgb": base["rgb"],
        "origin_ocolor": base["origin_ocolor"],
    }


def _source_label(source_file: Path | None, dataset_id: str) -> str:
    value = source_file.stem if source_file else dataset_id
    value = re.sub(r"\((?:OCP|ocp)\)", "", value)
    value = re.sub(r"[_\s]+", " ", value).strip(" -_")
    return value or dataset_id


def _select_plot_columns(header: list[str], data_type: str) -> tuple[int, list[int]]:
    normalized = [item.strip().lower() for item in header]
    if len(header) < 2:
        return 0, [1]
    if data_type == "EIS" and "real_impedance" in normalized and "neg_imag_impedance" in normalized:
        return normalized.index("real_impedance"), [normalized.index("neg_imag_impedance")]
    preferred_by_type = {
        "photocurrent": ("current_density", "current"),
        "photocurrent_response": ("current_density", "current"),
        "EPR": ("intensity",),
        "Raman": ("intensity",),
        "PL": ("intensity",),
        "FTIR": ("intensity", "absorbance", "transmittance"),
        "XRD": ("intensity",),
        "XPS": ("raw_intensity", "intensity"),
        "Mott-Schottky": ("one_over_c_squared",),
        "BET": ("adsorbed_volume", "desorption_volume"),
        "HPLC/LC exported data": ("signal",),
    }
    y_indices: list[int] = []
    for token in preferred_by_type.get(data_type, ()):
        for index, name in enumerate(normalized[1:], start=1):
            if token in name and index not in y_indices and not any(aux in name for aux in NON_PLOT_COLUMN_TOKENS):
                y_indices.append(index)
    if not y_indices:
        for index, name in enumerate(normalized[1:], start=1):
            if any(aux in name for aux in NON_PLOT_COLUMN_TOKENS):
                continue
            y_indices.append(index)
    if not y_indices:
        y_indices = [1]
    return 0, y_indices


def _write_plot_csv(source_csv: Path, plot_csv: Path, data_type: str) -> list[str]:
    with source_csv.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    header = rows[0] if rows else []
    x_index, y_indices = _select_plot_columns(header, data_type)
    selected_indices = [x_index, *y_indices]
    selected_header = [header[index] if index < len(header) else f"col{index + 1}" for index in selected_indices] if header else ["x", "y"]
    plot_csv.parent.mkdir(parents=True, exist_ok=True)
    with plot_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(selected_header)
        for row in rows[1:]:
            writer.writerow([row[index] if index < len(row) else "" for index in selected_indices])
    return selected_header


def _series_labels(raw_labels: tuple[str, ...], dataset_id: str, source_file: Path | None) -> tuple[str, ...]:
    source = _source_label(source_file, dataset_id)
    normalized = [label.strip().lower() for label in raw_labels]
    if len(raw_labels) == 1 and normalized[0] in GENERIC_SERIES_LABELS:
        return (source,)
    if normalized and all(label in GENERIC_SERIES_LABELS for label in normalized):
        return tuple(f"{source} {label}" for label in raw_labels)
    return raw_labels


def _color_assignments(
    dataset_id: str,
    data_type: str,
    labels: tuple[str, ...],
    source_file: Path | None,
    processed_csv: Path,
) -> tuple[dict[str, object], ...]:
    assignments: list[dict[str, object]] = []
    source_text = str(source_file) if source_file else ""
    for index, label in enumerate(labels):
        material_key, role, confidence = _infer_material_key(label, dataset_id)
        if not material_key and source_text:
            material_key, role, confidence = _infer_material_key(source_text)
        if material_key:
            color = COLOR_BY_KEY[material_key]
        else:
            material_key = _fallback_sample_key(dataset_id, source_file)
            color = _fallback_color_for_key(material_key)
            role = "sample_or_unknown"
            confidence = 0.4
        rgb = tuple(int(value) for value in color["rgb"])  # type: ignore[index]
        assignments.append(
            {
                "dataset_id": dataset_id,
                "data_type": data_type,
                "curve_index": index + 1,
                "curve_label": label,
                "material_key": material_key,
                "material_role": role,
                "inference_confidence": confidence,
                "color_name": color["name"],
                "rgb": list(rgb),
                "hex": "#{:02X}{:02X}{:02X}".format(*rgb),
                "origin_ocolor": int(color["origin_ocolor"]),
                "source_file": str(source_file) if source_file else None,
                "processed_csv": str(processed_csv),
                "evidence": "matched label/dataset/source path token" if material_key in COLOR_BY_KEY else "fallback sample key; material not confidently inferred",
                "requires_user_review": material_key not in COLOR_BY_KEY,
            }
        )
    return tuple(assignments)


def _write_material_color_report(project_root: Path, assignments: tuple[dict[str, object], ...]) -> None:
    reports = project_root / "output" / "reports"
    docs = project_root / "docs" / "agent_reports"
    reports.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    json_path = reports / "phase1_6_material_color_map.json"
    existing: dict[str, object] = {}
    if json_path.exists():
        try:
            existing = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    assignment_map = {
        f"{item['dataset_id']}::{item['curve_index']}": item
        for item in existing.get("assignments", [])
        if isinstance(item, dict) and "dataset_id" in item and "curve_index" in item
    }
    for item in assignments:
        assignment_map[f"{item['dataset_id']}::{item['curve_index']}"] = item
    material_colors = [
        {
            "material_key": item["key"],
            "material_role": item["role"],
            "color_name": item["name"],
            "rgb": list(item["rgb"]),
            "hex": "#{:02X}{:02X}{:02X}".format(*item["rgb"]),
            "origin_ocolor": item["origin_ocolor"],
        }
        for item in CURVE_COLOR_PALETTE
    ]
    data = {
        "policy": "Same inferred material/sample key uses the same Origin curve color across Phase 1.6 exports; uncertain sample-code assignments are marked for user review.",
        "material_colors": material_colors,
        "assignments": sorted(
            assignment_map.values(),
            key=lambda item: (str(item["material_key"]), str(item["dataset_id"]), int(item["curve_index"])),
        ),
    }
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Phase 1.6 Material Color Map",
        "",
        data["policy"],
        "",
        "## Material / Sample-Key Colors",
        "",
        "| key | role | color | RGB | Origin OColor |",
        "|---|---|---|---|---:|",
    ]
    for item in material_colors:
        lines.append(
            f"| `{item['material_key']}` | {item['material_role']} | {item['color_name']} `{item['hex']}` | {item['rgb']} | {item['origin_ocolor']} |"
        )
    lines.extend(
        [
            "",
            "## Curve Assignments",
            "",
            "| dataset_id | curve | label | key | color | confidence | review |",
            "|---|---:|---|---|---|---:|---|",
        ]
    )
    for item in data["assignments"]:
        lines.append(
            f"| `{item['dataset_id']}` | {item['curve_index']} | `{item['curve_label']}` | `{item['material_key']}` | {item['color_name']} `{item['hex']}` | {item['inference_confidence']} | {item['requires_user_review']} |"
        )
    text = "\n".join(lines) + "\n"
    (reports / "phase1_6_material_color_map.md").write_text(text, encoding="utf-8")
    (docs / "phase1_6_material_color_map.md").write_text(text, encoding="utf-8")


def build_origin_plot_job(
    project_root: Path,
    dataset_id: str,
    processed_csv: Path,
    x_title: str,
    y_title: str,
    data_type: str = "generic",
    source_file: Path | None = None,
) -> OriginPlotJob:
    job_dir = project_root / "output" / "origin_jobs"
    job_dir.mkdir(parents=True, exist_ok=True)
    plot_csv = job_dir / f"{dataset_id}_plot_input.csv"
    header = _write_plot_csv(processed_csv, plot_csv, data_type)
    column_count = max(2, len(header))
    raw_labels = tuple(label.strip() for label in header[1:] if label.strip()) or ("Signal",)
    labels = _series_labels(raw_labels, dataset_id, source_file)
    if len(labels) != column_count - 1:
        labels = tuple(f"Series {index}" for index in range(1, column_count))
    color_assignments = _color_assignments(dataset_id, data_type, labels, source_file, processed_csv)
    curve_colors = tuple(int(item["origin_ocolor"]) for item in color_assignments)

    origin_dir = project_root / "output" / "origin_files"
    tif_dir = project_root / "output" / "figures_tif"
    preview_dir = project_root / "output" / "figures_preview"
    for directory in (origin_dir, tif_dir, preview_dir, job_dir):
        directory.mkdir(parents=True, exist_ok=True)

    reference_search_pattern = _read_plot_style_value(
        project_root,
        "reference_search_pattern",
        r"D:\OriginFlies\Manual Save\CWO+BOBC+*.opju",
    )
    refresh_reference_style = _read_plot_style_value(project_root, "refresh_reference_style", "false").casefold() == "true"
    line_width = float(_read_plot_style_value(project_root, "line_width", "3"))
    axis_line_width = float(_read_plot_style_value(project_root, "axis_line_width", "3"))
    if line_width != 3 or axis_line_width != 3:
        raise ValueError("Origin Graph4 contract requires line_width and axis_line_width to be 3.")

    page_name = _safe_origin_name(dataset_id)
    return OriginPlotJob(
        dataset_id=dataset_id,
        data_type=data_type,
        processed_csv=processed_csv,
        plot_csv=plot_csv,
        source_file=source_file,
        origin_file=origin_dir / f"{dataset_id}.opju",
        figure_tif=tif_dir / f"{page_name}.tif",
        preview_png=preview_dir / f"{page_name}.png",
        job_script=job_dir / f"{dataset_id}.ps1",
        helper_script=Path(r"D:\CodexData\.codex\skills\origin-plotting\scripts\origin_plot_from_template.ps1"),
        reference_opju=_resolve_reference_opju(reference_search_pattern) if refresh_reference_style else None,
        reference_search_pattern=reference_search_pattern,
        reference_graph=_read_plot_style_value(project_root, "default_graph_page", "Graph4"),
        automation_entrypoint=_read_plot_style_value(project_root, "automation_entrypoint", "Origin.Application"),
        avoid_entrypoint=_read_plot_style_value(project_root, "avoid_entrypoint", "Origin.ApplicationSI"),
        font_family=_read_plot_style_value(project_root, "font_family", "Arial"),
        line_width=line_width,
        axis_line_width=axis_line_width,
        plot_type_code=PLOT_TYPE_CODES.get(data_type, LINE_PLOT_TYPE),
        page_name=page_name,
        column_count=column_count,
        labels=labels,
        curve_colors=curve_colors,
        color_assignments=color_assignments,
        x_title=x_title,
        y_title=y_title,
    )


def build_origin_invocation_script(job: OriginPlotJob) -> str:
    group = (
        "@{\n"
        f"  DataFile = {_ps_quote(job.plot_csv)}\n"
        f"  PageName = {_ps_quote(job.page_name)}\n"
        f"  ColumnCount = {job.column_count}\n"
        f"  Labels = {_ps_array(job.labels)}\n"
        f"  Palette = {_ps_int_array(job.curve_colors)}\n"
        f"  PlotType = {_ps_quote(job.plot_type_code)}\n"
        f"  XTitle = {_ps_quote(job.x_title)}\n"
        f"  YTitle = {_ps_quote(job.y_title)}\n"
        "}"
    )
    preview_dir = job.preview_png.parent
    reference_args = f"-ReferenceOpju {_ps_quote(job.reference_opju)} " if job.reference_opju else ""
    lines = [
        "$ErrorActionPreference = 'Stop'",
        f"$groups = @({group})",
    ]
    lines.extend(
        [
        f"& {_ps_quote(job.helper_script)} {reference_args}-ReferenceGraph {_ps_quote(job.reference_graph)} "
        f"-OutputOpju {_ps_quote(job.origin_file)} -ExportDir {_ps_quote(preview_dir)} "
        "-Groups $groups -Headless -CloseOrigin",
        "$originCloseDeadline = (Get-Date).AddSeconds(30)",
        "do {",
        "  $runningOrigin = Get-Process -Name Origin* -ErrorAction SilentlyContinue",
        "  if (-not $runningOrigin) { break }",
        "  Start-Sleep -Milliseconds 500",
        "} while ((Get-Date) -lt $originCloseDeadline)",
        "if ($runningOrigin) { throw 'Origin remained running after OPJU/PNG export. Close it before retrying.' }",
        f"if (-not (Test-Path -LiteralPath {_ps_quote(job.preview_png)})) {{ throw 'PNG preview was not exported.' }}",
        f"if ((Get-Item -LiteralPath {_ps_quote(job.preview_png)}).Length -le 0) {{ throw 'PNG preview was empty.' }}",
        ]
    )
    script = "\n".join(lines) + "\n"
    if job.avoid_entrypoint in script:
        raise ValueError(f"Origin job script unexpectedly uses forbidden entrypoint {job.avoid_entrypoint}")
    return script


def _run_origin_job(job: OriginPlotJob) -> subprocess.CompletedProcess[str]:
    if not job.helper_script.exists():
        raise FileNotFoundError(f"Origin helper script not found: {job.helper_script}")
    job.job_script.write_text(build_origin_invocation_script(job), encoding="utf-8-sig")
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(job.job_script)],
        text=True,
        capture_output=True,
        timeout=600,
    )


def _remove_stale_artifacts(job: OriginPlotJob) -> None:
    for artifact in (job.origin_file, job.figure_tif, job.preview_png):
        if artifact.exists():
            artifact.unlink()


def _wait_for_no_origin_process(timeout_seconds: float = 90.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        running = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Process -Name Origin* -ErrorAction SilentlyContinue"],
            text=True,
            capture_output=True,
            timeout=10,
        )
        if not running.stdout.strip():
            return True
        time.sleep(0.5)
    return False


def _export_tif_with_originpro(job: OriginPlotJob) -> None:
    if job.figure_tif.exists() and job.figure_tif.stat().st_size > 0:
        return
    if not _wait_for_no_origin_process():
        raise RuntimeError("Origin is still running before originpro TIF fallback; aborting to avoid attaching to an unsafe session.")

    import originpro as op

    try:
        op.set_show(False)
        if not op.open(str(job.origin_file), readonly=False, asksave=False):
            raise RuntimeError(f"Failed to load generated OPJU for TIF export: {job.origin_file}")
        graph = op.find_graph(job.page_name)
        if graph is None:
            raise RuntimeError(f"Generated OPJU did not contain graph page {job.page_name}")
        job.figure_tif.parent.mkdir(parents=True, exist_ok=True)
        tif_path = str(job.figure_tif)
        result = graph.save_fig(tif_path, type="tif", replace=True)
        if not result or not job.figure_tif.exists() or job.figure_tif.stat().st_size == 0:
            raise RuntimeError("originpro GPage.save_fig did not create the TIF output.")
    finally:
        try:
            op.exit()
        except Exception:
            pass
        _wait_for_no_origin_process()


def export_plot(
    project_root: Path,
    dataset_id: str,
    processed_csv: Path,
    x_title: str,
    y_title: str,
    data_type: str = "generic",
    source_file: Path | None = None,
) -> OriginResult:
    job = build_origin_plot_job(project_root, dataset_id, processed_csv, x_title, y_title, data_type, source_file=source_file)
    ok, message = check_origin_available()
    if not ok:
        write_origin_error(project_root, f"{dataset_id}: {message}")
        return OriginResult(False, None, None, None, f"Origin unavailable: {message}")
    try:
        _remove_stale_artifacts(job)
        if not _wait_for_no_origin_process():
            message = "Origin is still running before starting export; aborting to avoid attaching to an unsafe session."
            write_origin_error(project_root, f"{dataset_id}: {message}")
            return OriginResult(False, None, None, None, message)
        completed = _run_origin_job(job)
        if completed.returncode:
            details = (completed.stderr or completed.stdout or "Origin helper failed").strip()
            write_origin_error(project_root, f"{dataset_id}: {details}")
            return OriginResult(False, None, None, None, f"Origin export failed: {details}")
        if not job.figure_tif.exists():
            _export_tif_with_originpro(job)
        if not job.origin_file.exists() or not job.figure_tif.exists() or not job.preview_png.exists():
            message = "Origin helper did not produce required .opju, .tif, and PNG preview outputs."
            write_origin_error(project_root, f"{dataset_id}: {message}")
            return OriginResult(False, None, None, None, message)
        if job.origin_file.stat().st_size == 0:
            message = "OPJU output was empty; Origin export evidence is missing."
            write_origin_error(project_root, f"{dataset_id}: {message}")
            return OriginResult(False, None, None, None, message)
        if job.figure_tif.stat().st_size == 0:
            message = "TIF export was empty; print-quality figure evidence is missing."
            write_origin_error(project_root, f"{dataset_id}: {message}")
            return OriginResult(False, None, None, None, message)
        if job.preview_png.stat().st_size == 0:
            message = "PNG preview was empty; visual verification evidence is missing."
            write_origin_error(project_root, f"{dataset_id}: {message}")
            return OriginResult(False, None, None, None, message)
        _write_material_color_report(project_root, job.color_assignments)
        return OriginResult(True, job.origin_file, job.figure_tif, job.preview_png, "Origin export succeeded with Graph4 template workflow")
    except Exception as exc:
        write_origin_error(project_root, f"{dataset_id}: {exc}")
        return OriginResult(False, None, None, None, f"Origin export failed: {exc}")


def origin_smoke_test(project_root: Path) -> OriginResult:
    ok, message = check_origin_available()
    if not ok:
        write_origin_error(project_root, message)
        return OriginResult(False, None, None, None, message)
    data_dir = project_root / "output" / "processed_data" / "_origin_test"
    data_dir.mkdir(parents=True, exist_ok=True)
    csv_path = data_dir / "origin_smoke_test.csv"
    csv_path.write_text("x,y\n0,0\n1,1\n", encoding="utf-8")
    result = export_plot(project_root, "origin_smoke_test", csv_path, "x", "y")
    if result.ok:
        write_origin_success(project_root)
    return result
