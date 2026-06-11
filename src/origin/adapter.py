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

from src.core.project import _parse_simple_yaml, output_dir
from src.core.output_sanitizer import render_output_path, scrub_output_text
from src.core.runtime_paths import resolve_origin_helper, resolve_origin_reference_pattern
from src.origin.operations import connect_origin
from src.origin.plot_policy import Graph4FixedStyle, PlotPolicy, all_plot_policies, get_plot_policy, validate_graph4_style_config


ORIGIN_DISABLE_ENV_VARS = (
    "RESEARCHDATAORIGINPIPELINE_DISABLE_ORIGIN",
    "GROUPMEETINGAUTOPPT_DISABLE_ORIGIN",
)


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
    plot_policy: PlotPolicy
    fixed_style: Graph4FixedStyle
    page_name: str
    column_count: int
    labels: tuple[str, ...]
    xy_column_pairs: tuple[tuple[int, int], ...]
    curve_colors: tuple[int, ...]
    color_assignments: tuple[dict[str, object], ...]
    x_title: str
    y_title: str


@dataclass(frozen=True)
class BetCombinedSource:
    dataset_id: str
    processed_csv: Path
    source_file: Path


@dataclass(frozen=True)
class BetCombinedGroup:
    page_name: str
    plot_csv: Path
    labels: tuple[str, ...]
    curve_colors: tuple[int, ...]
    column_count: int


@dataclass(frozen=True)
class BetCombinedOriginJob:
    dataset_id: str
    origin_file: Path
    preview_dir: Path
    helper_script: Path
    reference_graph: str
    automation_entrypoint: str
    avoid_entrypoint: str
    groups: tuple[BetCombinedGroup, ...]


LINE_PLOT_TYPE = "200"
LINE_SYMBOL_PLOT_TYPE = "202"
COLUMN_PLOT_TYPE = "203"
MAX_ORIGIN_PAGE_NAME = 24
BET_PRIMARY_MATERIAL_ORDER = ("CWO", "BICU", "BOBC")
BET_MATERIAL_DISPLAY_NAMES = {
    "CWO": "CuWO4",
    "BICU": "BiCu-10",
    "BC": "BiCu-10",
    "BOBC": "BiOBrCl",
}
GENERIC_SERIES_LABELS = {
    "y",
    "signal",
    "intensity",
    "normalized_intensity",
    "current",
    "photocurrent_ua",
    "one_over_c_squared",
    "raw_intensity",
}
NON_PLOT_COLUMN_TOKENS = (
    "candidate",
    "flag",
    "optional",
    "cycle",
    "state",
    "residual",
    "metadata",
    "comment",
    "note",
    "photon_energy",
    "reflectance_fraction",
    "kubelka",
)
NON_PLOT_COLUMN_TOKENS_FOR_PREFERRED_SERIES = tuple(
    token for token in NON_PLOT_COLUMN_TOKENS if token != "optional"
)
XRD_NON_RAW_COLUMN_TOKENS = (
    "reference",
    "referencecard",
    "standard",
    "standardcard",
    "jcpds",
    "pdf",
    "hkl",
    "phase",
    "plane",
    "crystal",
    "dspacing",
    "normalized",
    "candidate",
    "flag",
    "optional",
    "card",
    "标卡",
    "标准卡",
    "晶面",
    "物相",
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
BRANCH_COLOR_BY_LABEL = {
    "adsorption": {"key": "ADSORPTION_BRANCH", "role": "branch", "name": "black", "rgb": (0, 0, 0), "origin_ocolor": 16777216},
    "desorption": {"key": "DESORPTION_BRANCH", "role": "branch", "name": "vermillion", "rgb": (213, 94, 0), "origin_ocolor": 16801493},
}
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

BET_MATERIAL_PATTERNS = (
    ("BOBC", re.compile(r"BOBC", re.IGNORECASE)),
    ("CWO", re.compile(r"CWO", re.IGNORECASE)),
    ("BICU", re.compile(r"BiCu|BiCu-?10", re.IGNORECASE)),
    ("BC", re.compile(r"(?<![A-Z])BC(?=[A-Z0-9_\-\s]|$)", re.IGNORECASE)),
)


PLOT_TYPE_CODES = {data_type: policy.origin_plot_code for data_type, policy in all_plot_policies().items()}


def check_origin_available() -> tuple[bool, str]:
    for env_var in ORIGIN_DISABLE_ENV_VARS:
        if os.environ.get(env_var) == "1":
            return False, f"Origin disabled by {env_var}=1"
    try:
        import originpro  # noqa: F401
    except Exception as exc:
        return False, f"originpro unavailable: {exc}"
    try:
        import win32com.client  # noqa: F401
    except Exception as exc:
        return False, f"win32com unavailable: {exc}"
    return True, "originpro and win32com are importable"


def write_origin_error(project_root: Path, message: str, *, output_root: Path | None = None) -> None:
    reports = output_dir(project_root, "reports", output_root=output_root)
    path = reports / "origin_errors.md"
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Origin Errors\n\n"
    line = f"- {scrub_output_text(message, project_root=project_root, output_root=output_root)}"
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


def write_origin_success(project_root: Path, *, output_root: Path | None = None) -> None:
    reports = output_dir(project_root, "reports", output_root=output_root)
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


def _ps_xy_pairs(pairs: tuple[tuple[int, int], ...]) -> str:
    return "'" + ";".join(f"{int(x)}:{int(y)}" for x, y in pairs) + "'"


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


def _bet_material_key(text: str) -> str | None:
    for key, pattern in BET_MATERIAL_PATTERNS:
        if pattern.search(text):
            return key
    return None


def _bet_material_display_name(text: str) -> str:
    key = _bet_material_key(text)
    if key is None:
        cleaned = re.sub(r"[_\s]+", " ", Path(text).stem if any(sep in text for sep in ("/", "\\")) else text)
        return cleaned.strip() or "Unknown sample"
    return BET_MATERIAL_DISPLAY_NAMES[key]


def _bet_material_color(material_key: str | None) -> int:
    if material_key == "BICU":
        return int(COLOR_BY_KEY["BC"]["origin_ocolor"])
    if material_key and material_key in COLOR_BY_KEY:
        return int(COLOR_BY_KEY[material_key]["origin_ocolor"])
    return int(FALLBACK_COLOR_SEQUENCE[0])


def _source_label(source_file: Path | None, dataset_id: str) -> str:
    value = source_file.stem if source_file else dataset_id
    value = re.sub(r"\((?:OCP|ocp)\)", "", value)
    value = re.sub(r"[_\s]+", " ", value).strip(" -_")
    return value or dataset_id


def _split_bet_combined_sources(sources: tuple[BetCombinedSource, ...]) -> tuple[tuple[BetCombinedSource, ...], tuple[BetCombinedSource, ...]]:
    keyed = [(source, _bet_material_key(" ".join((source.dataset_id, str(source.source_file))))) for source in sources]
    selected_indexes: set[int] = set()
    primary: list[BetCombinedSource] = []
    for wanted_key in BET_PRIMARY_MATERIAL_ORDER:
        for index, (source, key) in enumerate(keyed):
            if index in selected_indexes or key != wanted_key:
                continue
            primary.append(source)
            selected_indexes.add(index)
            break
    remaining = [source for index, (source, _key) in enumerate(keyed) if index not in selected_indexes]
    return tuple(primary), tuple(remaining)


def _read_bet_plot_rows(path: Path) -> dict[float, tuple[float | None, float | None]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: dict[float, tuple[float | None, float | None]] = {}
        for row in reader:
            x = _float_or_none(row.get("relative_pressure_p_p0"))
            if x is None:
                continue
            adsorption = _float_or_none(row.get("adsorbed_volume"))
            desorption = _float_or_none(row.get("desorption_volume_optional") or row.get("desorption_volume"))
            rows[x] = (adsorption, desorption)
        return rows


def _float_or_none(value: object) -> float | None:
    try:
        text = str(value).strip()
        if not text:
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def _format_float(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.12g}"


def _write_bet_combined_group_csv(plot_csv: Path, sources: tuple[BetCombinedSource, ...]) -> tuple[tuple[str, ...], tuple[int, ...]]:
    labels: list[str] = []
    curve_colors: list[int] = []
    source_rows: list[dict[float, tuple[float | None, float | None]]] = []
    for source in sources:
        material_text = " ".join((source.dataset_id, str(source.source_file)))
        material_key = _bet_material_key(material_text)
        material_label = _bet_material_display_name(material_text)
        labels.extend((f"{material_label} adsorption", f"{material_label} desorption"))
        curve_colors.extend((_bet_material_color(material_key), _bet_material_color(material_key)))
        source_rows.append(_read_bet_plot_rows(source.processed_csv))
    x_values = sorted({x for rows in source_rows for x in rows})
    plot_csv.parent.mkdir(parents=True, exist_ok=True)
    with plot_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["relative_pressure_p_p0", *labels])
        for x in x_values:
            row = [_format_float(x)]
            for rows in source_rows:
                adsorption, desorption = rows.get(x, (None, None))
                row.extend((_format_float(adsorption), _format_float(desorption)))
            writer.writerow(row)
    return tuple(labels), tuple(curve_colors)


def build_bet_combined_origin_job(
    project_root: Path,
    dataset_id: str,
    sources: list[BetCombinedSource] | tuple[BetCombinedSource, ...],
    *,
    output_root: Path | None = None,
) -> BetCombinedOriginJob:
    source_tuple = tuple(sources)
    if not source_tuple:
        raise ValueError("BET combined Origin job requires at least one source.")
    primary, remaining = _split_bet_combined_sources(source_tuple)
    groups_raw = [
        ("BET_primary_materials", primary),
        ("BET_additional_materials", remaining),
    ]
    if output_root is not None:
        job_dir = output_dir(project_root, "logs", "origin_jobs", output_root=output_root)
    else:
        job_dir = output_dir(project_root, "origin_jobs")
    origin_dir = output_dir(project_root, "origin_files", output_root=output_root)
    preview_dir = output_dir(project_root, "figures_preview", output_root=output_root)
    groups: list[BetCombinedGroup] = []
    for page_name, group_sources in groups_raw:
        if not group_sources:
            continue
        plot_csv = job_dir / f"{dataset_id}_{page_name}_plot_input.csv"
        labels, curve_colors = _write_bet_combined_group_csv(plot_csv, group_sources)
        groups.append(
            BetCombinedGroup(
                page_name=page_name,
                plot_csv=plot_csv,
                labels=labels,
                curve_colors=curve_colors,
                column_count=len(labels) + 1,
            )
        )
    return BetCombinedOriginJob(
        dataset_id=dataset_id,
        origin_file=origin_dir / f"{safe_origin_file_name(dataset_id)}.opju",
        preview_dir=preview_dir,
        helper_script=resolve_origin_helper(project_root),
        reference_graph=_read_plot_style_value(project_root, "default_graph_page", "Graph4"),
        automation_entrypoint=_read_plot_style_value(project_root, "automation_entrypoint", "Origin.Application"),
        avoid_entrypoint=_read_plot_style_value(project_root, "avoid_entrypoint", "Origin.ApplicationSI"),
        groups=tuple(groups),
    )


def safe_origin_file_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("_") or "origin_output"


def build_bet_combined_origin_invocation_script(job: BetCombinedOriginJob) -> str:
    policy = get_plot_policy("BET")
    group_blocks = []
    for group in job.groups:
        group_blocks.append(
            "@{\n"
            f"  DataFile = {_ps_quote(group.plot_csv)}\n"
            f"  PageName = {_ps_quote(group.page_name)}\n"
            f"  ColumnCount = {group.column_count}\n"
            f"  Labels = {_ps_array(group.labels)}\n"
            f"  Palette = {_ps_int_array(group.curve_colors)}\n"
            f"  PlotType = {_ps_quote(policy.origin_plot_code)}\n"
            f"  PlotPrimitive = {_ps_quote(policy.plot_primitive)}\n"
            f"  MarkerMode = {_ps_quote(policy.marker_policy)}\n"
            f"  FitOverlayMode = {_ps_quote(policy.fit_overlay_condition)}\n"
            f"  ShowYAxis = ${str(policy.y_axis_visible).lower()}\n"
            f"  ShowYTicks = ${str(policy.y_ticks_visible).lower()}\n"
            f"  ShowYTickValues = ${str(policy.y_tick_values_visible).lower()}\n"
            f"  ShowXTickValues = ${str(policy.x_tick_values_visible).lower()}\n"
            "  XTitle = 'Relative Pressure (P/P0)'\n"
            "  YTitle = 'Quantity Adsorbed (cm3/g STP)'\n"
            "}"
        )
    lines = [
        "$ErrorActionPreference = 'Stop'",
        "$groups = @(" + ", ".join(group_blocks) + ")",
        f"& {_ps_quote(job.helper_script)} -ReferenceGraph {_ps_quote(job.reference_graph)} "
        f"-OutputOpju {_ps_quote(job.origin_file)} -ExportDir {_ps_quote(job.preview_dir)} "
        "-Groups $groups -Headless -CloseOrigin",
    ]
    script = "\n".join(lines) + "\n"
    if job.avoid_entrypoint in script:
        raise ValueError(f"BET combined Origin job script unexpectedly uses forbidden entrypoint {job.avoid_entrypoint}")
    return script


def _select_plot_columns(header: list[str], data_type: str) -> tuple[int, list[int]]:
    normalized = [item.strip().lower() for item in header]
    if len(header) < 2:
        return 0, [1]
    if _is_eis_fit_header(normalized):
        return 0, [1, 2, 3]
    if data_type == "XRD":
        return _select_xrd_plot_columns(header)
    if data_type == "BET":
        return _select_bet_plot_columns(header)
    if data_type == "EIS" and "real_impedance" in normalized and "neg_imag_impedance" in normalized:
        return normalized.index("real_impedance"), [normalized.index("neg_imag_impedance")]
    exact_preferred_by_type = {
        "photocurrent": ("current_density_uA_cm2_optional", "photocurrent_uA", "current_density", "current"),
        "photocurrent_response": ("current_density_uA_cm2_optional", "photocurrent_uA", "current_density", "current"),
        "EPR": ("intensity",),
        "Raman": ("intensity",),
        "PL": ("intensity",),
        "FTIR": ("intensity", "absorbance", "transmittance"),
        "XRD": ("intensity",),
        "XPS": ("raw_intensity", "intensity"),
        "Mott-Schottky": ("one_over_c_squared",),
        "BET": ("adsorbed_volume", "desorption_volume_optional"),
        "HPLC/LC exported data": ("signal",),
    }
    exact_y_indices = []
    for name in exact_preferred_by_type.get(data_type, ()):
        if name in normalized and normalized.index(name) != 0:
            exact_y_indices.append(normalized.index(name))
    if exact_y_indices:
        return 0, exact_y_indices
    preferred_by_type = {
        "photocurrent": ("current_density_uA", "photocurrent_uA", "current_density", "current"),
        "photocurrent_response": ("current_density_uA", "photocurrent_uA", "current_density", "current"),
        "EPR": ("intensity",),
        "Raman": ("intensity",),
        "PL": ("intensity",),
        "FTIR": ("intensity", "absorbance", "transmittance"),
        "XRD": ("intensity",),
        "XPS": ("raw_intensity", "intensity"),
        "Mott-Schottky": ("one_over_c_squared",),
        "BET": ("adsorbed_volume", "desorption_volume"),
        "HPLC/LC exported data": ("signal",),
        "XPS fitted": ("raw_intensity", "intensity", "background", "envelope", "component"),
        "EIS Bode": ("magnitude", "phase"),
        "BET pore distribution": ("pore_volume", "dv", "dV"),
        "calibration_curve": ("peak_area", "area"),
    }
    y_indices: list[int] = []
    for token in preferred_by_type.get(data_type, ()):
        for index, name in enumerate(normalized[1:], start=1):
            if (
                token in name
                and index not in y_indices
                and not any(aux in name for aux in NON_PLOT_COLUMN_TOKENS_FOR_PREFERRED_SERIES)
            ):
                y_indices.append(index)
    if not y_indices:
        for index, name in enumerate(normalized[1:], start=1):
            if any(aux in name for aux in NON_PLOT_COLUMN_TOKENS):
                continue
            y_indices.append(index)
    if not y_indices:
        y_indices = [1]
    return 0, y_indices


def _select_xrd_plot_columns(header: list[str]) -> tuple[int, list[int]]:
    normalized = [_normalized_column_name(item) for item in header]
    x_index = 0
    x_tokens = ("twothetadeg", "twotheta", "2theta", "angle", "角度")
    for index, name in enumerate(normalized):
        if any(token in name for token in x_tokens):
            x_index = index
            break

    exact_raw_y = ("intensity", "counts", "rawintensity", "rawcounts", "y", "signal")
    y_indices = [
        index
        for index, name in enumerate(normalized)
        if index != x_index and name in exact_raw_y and not _is_xrd_non_raw_column(name)
    ]
    if y_indices:
        return x_index, y_indices

    for index, name in enumerate(normalized):
        if index == x_index or _is_xrd_non_raw_column(name):
            continue
        if "intensity" in name or "counts" in name:
            y_indices.append(index)
    if y_indices:
        return x_index, y_indices

    fallback_y_indices = [
        index
        for index, name in enumerate(normalized)
        if index != x_index and not _is_xrd_non_raw_column(name)
    ]
    if fallback_y_indices:
        return x_index, fallback_y_indices

    raise ValueError(
        "XRD plot requires a raw pattern intensity/counts column; reference-card, hkl, phase, plane, "
        "normalized, and peak-candidate columns are not plotted automatically."
    )


def _select_bet_plot_columns(header: list[str]) -> tuple[int, list[int]]:
    normalized = [_normalized_column_name(item) for item in header]
    x_tokens = (
        "relativepressurepp0",
        "relativepressureppo",
        "relativepressurep/po",
        "relativepressurep/p0",
        "relativepressure",
        "pp0",
        "ppo",
    )
    x_index = next((index for index, name in enumerate(normalized) if any(token in name for token in x_tokens)), None)

    branch_tokens = (
        "adsorbedvolume",
        "quantityadsorbed",
        "adsorptionvolume",
        "desorptionvolume",
        "quantitydesorption",
        "quantitydesorbed",
    )
    if x_index is not None:
        y_indices = [
            index
            for index, name in enumerate(normalized)
            if index != x_index and any(token in name for token in branch_tokens) and not _is_bet_non_curve_column(name)
        ]
        if len(y_indices) >= 1:
            return x_index, y_indices

    pore_x_tokens = ("poresize", "porediameter", "porewidth")
    pore_y_tokens = ("porevolume", "dv", "dvpore", "dvlog", "differentialporevolume")
    pore_x_index = next((index for index, name in enumerate(normalized) if any(token in name for token in pore_x_tokens)), None)
    if pore_x_index is not None:
        y_indices = [
            index
            for index, name in enumerate(normalized)
            if index != pore_x_index and any(token in name for token in pore_y_tokens) and not _is_bet_non_curve_column(name)
        ]
        if y_indices:
            return pore_x_index, y_indices

    raise ValueError(
        "BET Origin plot requires relative-pressure isotherm or pore-size distribution curve columns; "
        "summary metrics such as surface area, pore volume, and pore diameter are metadata only."
    )


def _normalized_column_name(value: str) -> str:
    return re.sub(r"[\s_\-()/%#.]+", "", value.strip().casefold())


def _is_bet_non_curve_column(normalized_name: str) -> bool:
    non_curve_tokens = (
        "betsurfacearea",
        "surfacearea",
        "averageporediameter",
        "porediametercandidate",
        "porevolumecandidate",
        "candidate",
        "summary",
        "metric",
        "unit",
    )
    return any(token in normalized_name for token in non_curve_tokens)


def _is_xrd_non_raw_column(normalized_name: str) -> bool:
    return any(token in normalized_name for token in XRD_NON_RAW_COLUMN_TOKENS)


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


def _xy_column_pairs(header: list[str], data_type: str) -> tuple[tuple[int, int], ...]:
    normalized = [item.strip().lower() for item in header]
    if data_type == "EIS" and _is_eis_fit_header(normalized):
        return ((1, 2), (3, 4))
    return ()


def _is_eis_fit_header(normalized_header: list[str]) -> bool:
    return normalized_header[:4] == [
        "cleaned_z_real_ohm",
        "cleaned_minus_z_imag_ohm",
        "fit_z_real_ohm",
        "draft_fit_minus_z_imag_ohm",
    ]


def _series_labels(raw_labels: tuple[str, ...], dataset_id: str, source_file: Path | None) -> tuple[str, ...]:
    source = _source_label(source_file, dataset_id)
    raw_labels = tuple(_pretty_series_label(label) for label in raw_labels)
    normalized = [label.strip().lower() for label in raw_labels]
    if len(raw_labels) == 1 and normalized[0] in GENERIC_SERIES_LABELS:
        return (source,)
    if normalized and all(label in GENERIC_SERIES_LABELS for label in normalized):
        return tuple(f"{source} {label}" for label in raw_labels)
    return raw_labels


def _pretty_series_label(label: str) -> str:
    normalized = label.strip().lower()
    if normalized in {"adsorbed_volume", "quantity_adsorbed"}:
        return "Quantity Adsorbed"
    if normalized in {"desorption_volume_optional", "desorption_volume", "quantity_desorption"}:
        return "Quantity Desorption"
    return label


def _branch_color_for_label(label: str) -> dict[str, object] | None:
    normalized = label.strip().casefold()
    if "desorption" in normalized:
        return BRANCH_COLOR_BY_LABEL["desorption"]
    if "adsorption" in normalized or "adsorbed" in normalized:
        return BRANCH_COLOR_BY_LABEL["adsorption"]
    return None


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
        branch_color = _branch_color_for_label(label)
        if data_type == "BET" and branch_color is not None:
            rgb = tuple(int(value) for value in branch_color["rgb"])  # type: ignore[index]
            assignments.append(
                {
                    "dataset_id": dataset_id,
                    "data_type": data_type,
                    "curve_index": index + 1,
                    "curve_label": label,
                    "material_key": branch_color["key"],
                    "material_role": branch_color["role"],
                    "inference_confidence": 1.0,
                    "color_name": branch_color["name"],
                    "rgb": list(rgb),
                    "hex": "#{:02X}{:02X}{:02X}".format(*rgb),
                    "origin_ocolor": int(branch_color["origin_ocolor"]),
                    "source_file": render_output_path(source_file) if source_file else None,
                    "processed_csv": render_output_path(processed_csv),
                    "evidence": "BET adsorption/desorption branch color; branch is not treated as material identity",
                    "requires_user_review": False,
                }
            )
            continue
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
                "source_file": render_output_path(source_file) if source_file else None,
                "processed_csv": render_output_path(processed_csv),
                "evidence": "matched label/dataset/source path token" if material_key in COLOR_BY_KEY else "fallback sample key; material not confidently inferred",
                "requires_user_review": material_key not in COLOR_BY_KEY,
            }
        )
    return tuple(assignments)


def _write_material_color_report(
    project_root: Path,
    assignments: tuple[dict[str, object], ...],
    *,
    output_root: Path | None = None,
) -> None:
    reports = output_dir(project_root, "reports", output_root=output_root)
    docs = project_root / "docs" / "agent_reports"
    if output_root is None:
        docs.mkdir(parents=True, exist_ok=True)
    json_path = reports / "phase1_6_material_color_map.json"
    existing: dict[str, object] = {}
    if json_path.exists():
        try:
            existing = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    assignment_map = {
        f"{item['dataset_id']}::{item['curve_index']}": _sanitize_report_payload(item)
        for item in existing.get("assignments", [])
        if isinstance(item, dict) and "dataset_id" in item and "curve_index" in item
    }
    for item in assignments:
        assignment_map[f"{item['dataset_id']}::{item['curve_index']}"] = _sanitize_report_payload(item)
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
    if output_root is None:
        (docs / "phase1_6_material_color_map.md").write_text(text, encoding="utf-8")


def _sanitize_report_payload(value: object) -> object:
    if isinstance(value, Path):
        return render_output_path(value)
    if isinstance(value, dict):
        return {str(key): _sanitize_report_payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_report_payload(item) for item in value]
    if isinstance(value, str):
        if re.search(r"^[A-Za-z]:[\\/]|^[\\/]{2}", value):
            return render_output_path(value)
        return scrub_output_text(value)
    return value


def build_origin_plot_job(
    project_root: Path,
    dataset_id: str,
    processed_csv: Path,
    x_title: str,
    y_title: str,
    data_type: str = "generic",
    source_file: Path | None = None,
    *,
    output_root: Path | None = None,
) -> OriginPlotJob:
    if output_root is not None:
        job_dir = output_dir(project_root, "logs", "origin_jobs", output_root=output_root)
    else:
        job_dir = output_dir(project_root, "origin_jobs")
    plot_csv = job_dir / f"{dataset_id}_plot_input.csv"
    header = _write_plot_csv(processed_csv, plot_csv, data_type)
    column_count = max(2, len(header))
    xy_column_pairs = _xy_column_pairs(header, data_type)
    if xy_column_pairs and data_type == "EIS":
        labels = ("Measured", "Draft Randles-CPE fit")
    else:
        raw_labels = tuple(label.strip() for label in header[1:] if label.strip()) or ("Signal",)
        labels = _series_labels(raw_labels, dataset_id, source_file)
    expected_label_count = len(xy_column_pairs) if xy_column_pairs else column_count - 1
    if len(labels) != expected_label_count:
        labels = tuple(f"Series {index}" for index in range(1, expected_label_count + 1))
    color_assignments = _color_assignments(dataset_id, data_type, labels, source_file, processed_csv)
    curve_colors = tuple(int(item["origin_ocolor"]) for item in color_assignments)

    origin_dir = output_dir(project_root, "origin_files", output_root=output_root)
    tif_dir = output_dir(project_root, "figures_tif", output_root=output_root)
    preview_dir = output_dir(project_root, "figures_preview", output_root=output_root)

    reference_search_pattern = resolve_origin_reference_pattern(project_root)
    refresh_reference_style = _read_plot_style_value(project_root, "refresh_reference_style", "false").casefold() == "true"
    fixed_style = validate_graph4_style_config(project_root / "config" / "plot_style.yaml")
    line_width = float(_read_plot_style_value(project_root, "line_width", str(fixed_style.line_width)))
    axis_line_width = float(_read_plot_style_value(project_root, "axis_line_width", str(fixed_style.axis_line_width)))
    if line_width != fixed_style.line_width or axis_line_width != fixed_style.axis_line_width:
        raise ValueError("Origin Graph4 contract requires line_width and axis_line_width to be 3.")
    plot_policy = get_plot_policy(data_type)

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
        helper_script=resolve_origin_helper(project_root),
        reference_opju=_resolve_reference_opju(reference_search_pattern) if refresh_reference_style else None,
        reference_search_pattern=reference_search_pattern,
        reference_graph=_read_plot_style_value(project_root, "default_graph_page", "Graph4"),
        automation_entrypoint=_read_plot_style_value(project_root, "automation_entrypoint", "Origin.Application"),
        avoid_entrypoint=_read_plot_style_value(project_root, "avoid_entrypoint", "Origin.ApplicationSI"),
        font_family=_read_plot_style_value(project_root, "font_family", "Arial"),
        line_width=line_width,
        axis_line_width=axis_line_width,
        plot_type_code=plot_policy.origin_plot_code,
        plot_policy=plot_policy,
        fixed_style=fixed_style,
        page_name=page_name,
        column_count=column_count,
        labels=labels,
        xy_column_pairs=xy_column_pairs,
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
        f"  XYPairs = {_ps_xy_pairs(job.xy_column_pairs)}\n"
        f"  Palette = {_ps_int_array(job.curve_colors)}\n"
        f"  PlotType = {_ps_quote(job.plot_type_code)}\n"
        f"  PlotPrimitive = {_ps_quote(job.plot_policy.plot_primitive)}\n"
        f"  MarkerMode = {_ps_quote(job.plot_policy.marker_policy)}\n"
        f"  FitOverlayMode = {_ps_quote(job.plot_policy.fit_overlay_condition)}\n"
        f"  ShowYAxis = ${str(job.plot_policy.y_axis_visible).lower()}\n"
        f"  ShowYTicks = ${str(job.plot_policy.y_ticks_visible).lower()}\n"
        f"  ShowYTickValues = ${str(job.plot_policy.y_tick_values_visible).lower()}\n"
        f"  ShowXTickValues = ${str(job.plot_policy.x_tick_values_visible).lower()}\n"
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


def _wait_for_no_origin_process(timeout_seconds: float = 5.0) -> bool:
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
        result = graph.save_fig(tif_path, type="tif", replace=True, width=int(job.fixed_style.page_width))
        if not result or not job.figure_tif.exists() or job.figure_tif.stat().st_size == 0:
            raise RuntimeError("originpro GPage.save_fig did not create the TIF output.")
        _ensure_tif_600_dpi(job.figure_tif, job.fixed_style)
    finally:
        try:
            op.exit()
        except Exception:
            pass
        _wait_for_no_origin_process()


def _ensure_tif_600_dpi(path: Path, fixed_style: Graph4FixedStyle = Graph4FixedStyle()) -> None:
    """Normalize Origin TIF evidence to the Graph4 600 dpi bitmap contract when Pillow can read it."""
    try:
        from PIL import Image
    except Exception:
        return
    try:
        with Image.open(path) as image:
            output = image.copy()
    except Exception:
        return
    target_width = int(fixed_style.page_width)
    if output.width < target_width:
        target_height = max(1, round(output.height * (target_width / output.width)))
        output = output.resize((target_width, target_height))
    output.save(path, format="TIFF", dpi=(600, 600), compression="tiff_lzw")


def export_plot(
    project_root: Path,
    dataset_id: str,
    processed_csv: Path,
    x_title: str,
    y_title: str,
    data_type: str = "generic",
    source_file: Path | None = None,
    *,
    output_root: Path | None = None,
) -> OriginResult:
    job = build_origin_plot_job(
        project_root,
        dataset_id,
        processed_csv,
        x_title,
        y_title,
        data_type,
        source_file=source_file,
        output_root=output_root,
    )
    ok, message = check_origin_available()
    if not ok:
        write_origin_error(project_root, f"{dataset_id}: {message}", output_root=output_root)
        return OriginResult(False, None, None, None, f"Origin unavailable: {message}")
    try:
        _remove_stale_artifacts(job)
        if not _wait_for_no_origin_process():
            message = "Origin is still running before starting export; aborting to avoid attaching to an unsafe session."
            write_origin_error(project_root, f"{dataset_id}: {message}", output_root=output_root)
            return OriginResult(False, None, None, None, message)
        completed = _run_origin_job(job)
        if completed.returncode:
            details = (completed.stderr or completed.stdout or "Origin helper failed").strip()
            write_origin_error(project_root, f"{dataset_id}: {details}", output_root=output_root)
            return OriginResult(False, None, None, None, f"Origin export failed: {details}")
        if not job.figure_tif.exists():
            _export_tif_with_originpro(job)
        _ensure_tif_600_dpi(job.figure_tif, job.fixed_style)
        if not job.origin_file.exists() or not job.figure_tif.exists() or not job.preview_png.exists():
            message = "Origin helper did not produce required .opju, .tif, and PNG preview outputs."
            write_origin_error(project_root, f"{dataset_id}: {message}", output_root=output_root)
            return OriginResult(False, None, None, None, message)
        if job.origin_file.stat().st_size == 0:
            message = "OPJU output was empty; Origin export evidence is missing."
            write_origin_error(project_root, f"{dataset_id}: {message}", output_root=output_root)
            return OriginResult(False, None, None, None, message)
        if job.figure_tif.stat().st_size == 0:
            message = "TIF export was empty; print-quality figure evidence is missing."
            write_origin_error(project_root, f"{dataset_id}: {message}", output_root=output_root)
            return OriginResult(False, None, None, None, message)
        if job.preview_png.stat().st_size == 0:
            message = "PNG preview was empty; visual verification evidence is missing."
            write_origin_error(project_root, f"{dataset_id}: {message}", output_root=output_root)
            return OriginResult(False, None, None, None, message)
        _write_material_color_report(project_root, job.color_assignments, output_root=output_root)
        return OriginResult(True, job.origin_file, job.figure_tif, job.preview_png, "Origin export succeeded with Graph4 template workflow")
    except Exception as exc:
        write_origin_error(project_root, f"{dataset_id}: {exc}", output_root=output_root)
        return OriginResult(False, None, None, None, f"Origin export failed: {exc}")
    finally:
        try:
            if job.job_script.exists():
                job.job_script.unlink()
        except OSError:
            pass


def origin_smoke_test(project_root: Path) -> OriginResult:
    ok, message = check_origin_available()
    if not ok:
        write_origin_error(project_root, message)
        return OriginResult(False, None, None, None, message)
    data_dir = output_dir(project_root, "processed_data", "_origin_test")
    data_dir.mkdir(parents=True, exist_ok=True)
    csv_path = data_dir / "origin_smoke_test.csv"
    csv_path.write_text("x,y\n0,0\n1,1\n", encoding="utf-8")
    origin_file = output_dir(project_root, "origin_files") / "origin_smoke_test.opju"
    figure_tif = output_dir(project_root, "figures_tif") / "origin_smoke_test.tif"
    preview_png = output_dir(project_root, "figures_preview") / "origin_smoke_test.png"
    operations = None
    try:
        operations = connect_origin(entrypoint="Origin.Application", isolated=True, visible=False)
        created = operations.new_project()
        if not created.ok:
            raise RuntimeError(created.message)
        imported = operations.import_csv_to_worksheet(csv_path, book_name="origin_smoke_test")
        if not imported.ok:
            raise RuntimeError(imported.message)
        book_name = str(imported.payload["book_name"])
        graph = operations.create_graph("origin_smoke_test", book_name, "Sheet1", 1, 2, plot_type="line")
        if not graph.ok:
            raise RuntimeError(graph.message)
        graph_name = str(graph.payload["graph_name"])
        operations.set_axis_labels(graph_name, "x", "y", "")
        origin_file.parent.mkdir(parents=True, exist_ok=True)
        saved = operations.save_project(origin_file)
        if not saved.ok:
            raise RuntimeError(saved.message)
        png = operations.export_graph(graph_name, preview_png, "png")
        tif = operations.export_graph(graph_name, figure_tif, "tif")
        if not png.ok or not tif.ok:
            raise RuntimeError(f"{png.message}; {tif.message}")
        missing = [path for path in (origin_file, figure_tif, preview_png) if not path.exists() or path.stat().st_size == 0]
        if missing:
            raise RuntimeError("missing smoke test artifacts: " + "; ".join(str(path) for path in missing))
        write_origin_success(project_root)
        return OriginResult(True, origin_file, figure_tif, preview_png, "Origin isolated operations smoke test succeeded")
    except Exception as exc:
        message = f"Origin isolated operations smoke test failed: {exc}"
        write_origin_error(project_root, message)
        return OriginResult(False, None, None, None, message)
    finally:
        if operations is not None:
            operations.close()
