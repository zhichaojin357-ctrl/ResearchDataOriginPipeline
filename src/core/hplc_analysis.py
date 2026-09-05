from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import defaultdict
from copy import deepcopy
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

import numpy as np


ANALYSIS_CONFIG_RELATIVE_PATH = Path("config") / "hplc_openlab_analysis.yaml"
TARGET_ORDER = ("sulfoxide", "sulfone", "thioanisole")

MAIN_RESULT_COLUMNS = (
    "序号",
    "实验日期",
    "样品名",
    "实验批次",
    "反应时间（h）",
    "光源",
    "茴香亚砜 RT（min）",
    "茴香亚砜峰面积",
    "茴香亚砜原液浓度（mM）",
    "茴香砜 RT（min）",
    "茴香砜峰面积",
    "茴香砜原液浓度（mM）",
    "茴香硫醚 RT（min）",
    "茴香硫醚峰面积",
    "茴香硫醚原液浓度（mM）",
    "C₀（mM）",
    "转化率（%）",
    "茴香亚砜选择性（%）",
    "茴香亚砜产率（%）",
    "物料回收率（%）",
    "数据质量",
    "处理方式",
    "使用数据组",
    "舍弃数据组",
    "处理说明",
    "重打组ID",
    "实际采集时间",
    "采集方法",
    "序列名称",
    "OpenLab结果名称",
    "日期文件夹",
    "原始文件名",
    "原始文件路径",
)

PEAK_DETAIL_COLUMNS = (
    "序号",
    "实验日期",
    "样品名",
    "茴香亚砜峰序号",
    "茴香亚砜出峰时间(min)",
    "茴香亚砜峰面积",
    "茴香砜峰序号",
    "茴香砜出峰时间(min)",
    "茴香砜峰面积",
    "茴香硫醚峰序号",
    "茴香硫醚出峰时间(min)",
    "茴香硫醚峰面积",
    "数据质量",
    "是否参与最终计算",
    "处理方式",
    "实际采集时间",
    "采集方法",
    "序列名称",
    "OpenLab结果名称",
    "原始文件名",
)

_TIME_PATTERN = re.compile(
    r"(?<![A-Z0-9.])(?P<hours>\d+(?:\.\d+)?)\s*(?:H|小时)"
    r"(?:\s*(?P<minutes>\d+(?:\.\d+)?)\s*(?:MIN|分钟))?",
    re.IGNORECASE,
)
_TIME_RANGE_PATTERN = re.compile(
    r"(?<![A-Z0-9.])\d+(?:\.\d+)?(?:\s*-\s*\d+(?:\.\d+)?)+\s*(?:H|小时)",
    re.IGNORECASE,
)
_DATE_TOKEN = re.compile(r"(?<!\d)\d{8}(?!\d)|(?<!\d)\d{4}(?!\d)")
_RERUN_SUFFIX = re.compile(
    r"(?:\s*[-_]\s*2|\s*[（(]\s*2\s*[)）]|\s+(?:REPEAT|RERUN|RE)|\s*重打)\s*$",
    re.IGNORECASE,
)
_BATCH_PATTERN = re.compile(r"第\s*(?P<value>[一二三四五六七八九十\d]+)\s*批", re.IGNORECASE)
_SHORT_BATCH_PATTERN = re.compile(
    r"(?:^|[^第A-Z0-9])(?P<value>[一二三四五六七八九十])\s*批(?:$|[^A-Z0-9])",
    re.IGNORECASE,
)
_BATCH_ENGLISH_PATTERN = re.compile(r"(?:^|[^A-Z0-9])BATCH\s*(?P<value>\d+)(?:$|[^A-Z0-9])", re.IGNORECASE)
_CHINESE_BATCH_NUMBERS = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def load_hplc_analysis_config(project_root: Path) -> dict[str, Any]:
    """Load and minimally validate the centralized OpenLab analysis policy."""
    path = project_root / ANALYSIS_CONFIG_RELATIVE_PATH
    if not path.is_file():
        raise FileNotFoundError(f"HPLC analysis configuration is missing: {path}")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise TypeError("HPLC analysis configuration must be a JSON/YAML mapping")
    for key in (
        "analysis_version",
        "peak_selection",
        "date_rules",
        "targets",
        "repeat_rules",
        "quality_thresholds",
    ):
        if key not in loaded:
            raise ValueError(f"HPLC analysis configuration is missing required key: {key}")
    if tuple(loaded["targets"].keys()) != TARGET_ORDER:
        raise ValueError(f"HPLC target order must be exactly {TARGET_ORDER}")
    peak_selection = loaded["peak_selection"]
    if peak_selection.get("primary_source") != "vendor_rx_only":
        raise ValueError("HPLC primary peak source must be vendor_rx_only")
    if peak_selection.get("missing_result_action") != "require_vendor_reprocess":
        raise ValueError("Missing HPLC vendor results must require vendor reprocessing")
    return loaded


def parse_folder_date(folder_name: str, config: dict[str, Any]) -> date:
    """Parse the leading YYYYMMDD experiment date; never use filesystem times."""
    pattern = re.compile(str(config["date_rules"]["folder_date_pattern"]))
    match = pattern.search(str(folder_name))
    if not match:
        raise ValueError(f"日期文件夹未以 YYYYMMDD 开头: {folder_name}")
    return datetime.strptime(match.group("date"), "%Y%m%d").date()


def classify_light_source(
    experiment_date: date,
    config: dict[str, Any],
    *,
    folder_name: str = "",
) -> str:
    rules = config["date_rules"]
    screening = date.fromisoformat(rules["light_screening_date"])
    ordinary_306_start = date.fromisoformat(rules["ordinary_306_start"])
    ordinary_306_end = date.fromisoformat(rules["ordinary_306_end"])
    ordinary_301_start = date.fromisoformat(rules["ordinary_301_start"])
    if experiment_date < screening:
        return str(rules["before_screening_label"])
    if experiment_date == screening:
        normalized_folder = normalize_hplc_name(folder_name, strip_rerun_suffix=False)
        if any(term in normalized_folder for term in ("光源选择", "光源筛选")):
            return str(rules["screening_label"])
        return "光源日期边界待确认"
    if ordinary_306_start <= experiment_date <= ordinary_306_end:
        return str(rules["ordinary_306_label"])
    if experiment_date >= ordinary_301_start:
        return str(rules["ordinary_301_label"])
    return "光源日期边界待确认"


def normalize_hplc_name(value: str, *, strip_rerun_suffix: bool = True) -> str:
    """Normalize typography while preserving experimental numbers and conditions."""
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    normalized = normalized.replace("_", "-").strip().upper()
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"\s*-\s*", "-", normalized)
    normalized = re.sub(r"\.(?:RSLT|SQX)$", "", normalized, flags=re.IGNORECASE)
    if strip_rerun_suffix:
        previous = None
        while normalized != previous:
            previous = normalized
            normalized = _RERUN_SUFFIX.sub("", normalized).strip(" -_")
    return normalized


def has_rerun_marker(value: str, config: dict[str, Any]) -> bool:
    raw = unicodedata.normalize("NFKC", str(value or "")).strip()
    no_extension = re.sub(r"\.(?:rslt|sqx)$", "", raw, flags=re.IGNORECASE)
    if _RERUN_SUFFIX.search(no_extension):
        return True
    folded = no_extension.casefold()
    return any(str(term).casefold() in folded for term in config["name_rules"]["rerun_words"])


def has_explicit_rerun_word(value: str, config: dict[str, Any]) -> bool:
    folded = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return any(str(term).casefold() in folded for term in config["name_rules"]["rerun_words"])


def is_wash_sample(sample_name: str, config: dict[str, Any]) -> bool:
    compact = re.sub(r"[\s_\-]+", "", unicodedata.normalize("NFKC", str(sample_name))).casefold()
    for term in config["name_rules"]["wash_terms"]:
        term_compact = re.sub(r"[\s_\-]+", "", unicodedata.normalize("NFKC", str(term))).casefold()
        if term_compact and term_compact in compact:
            return True
    return False


def is_pre_reaction_sample(sample_name: str, config: dict[str, Any]) -> bool:
    normalized = normalize_hplc_name(sample_name, strip_rerun_suffix=False)
    compact = re.sub(r"[\s_\-]+", "", normalized)
    for term in config["name_rules"]["pre_reaction_terms"]:
        term_compact = re.sub(
            r"[\s_\-]+",
            "",
            normalize_hplc_name(str(term), strip_rerun_suffix=False),
        )
        if term_compact and term_compact in compact:
            return True
    return bool(re.fullmatch(r"(?:\d{4,8})?SM(?:\d{4,8})?", compact))


def extract_reaction_time_h(sample_name: str, *, pre_reaction: bool = False) -> float | None:
    if pre_reaction:
        return 0.0
    normalized = unicodedata.normalize("NFKC", str(sample_name)).upper()
    match = _TIME_PATTERN.search(normalized)
    if not match:
        return None
    hours = float(match.group("hours"))
    minutes = float(match.group("minutes") or 0.0)
    return hours + minutes / 60.0


def detect_batch_marker(*values: str) -> tuple[str, bool, list[str]]:
    """Return an explicit batch marker and surface conflicts across all contexts."""
    matches: list[int] = []
    for value in values:
        normalized = normalize_hplc_name(value, strip_rerun_suffix=False)
        for match in _BATCH_PATTERN.finditer(normalized):
            token = match.group("value")
            matches.append(int(token) if token.isdigit() else _CHINESE_BATCH_NUMBERS.get(token, 0))
        for match in _SHORT_BATCH_PATTERN.finditer(normalized):
            matches.append(_CHINESE_BATCH_NUMBERS.get(match.group("value"), 0))
        for match in _BATCH_ENGLISH_PATTERN.finditer(normalized):
            matches.append(int(match.group("value")))
        if "新批次" in normalized:
            matches.append(2)
    matches = [item for item in matches if item > 0]
    unique = sorted(set(matches))
    if not unique:
        return "默认批次", False, []
    rendered = [f"第{number}批" for number in unique]
    if len(unique) > 1:
        return "批次待确认", True, rendered
    return rendered[0], False, rendered


def _condition_key(sample_name: str) -> str:
    normalized = normalize_hplc_name(sample_name, strip_rerun_suffix=False)
    normalized = _TIME_PATTERN.sub(" ", normalized)
    normalized = _BATCH_PATTERN.sub(" ", normalized)
    normalized = _SHORT_BATCH_PATTERN.sub(" ", normalized)
    normalized = _BATCH_ENGLISH_PATTERN.sub(" ", normalized)
    normalized = _DATE_TOKEN.sub(" ", normalized)
    normalized = re.sub(
        r"(?:\bSM\b|茴香硫醚反应前|硫醚反应前|反应前|BEFORE\s+REACTION|原液)",
        " ",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(r"\s+", " ", normalized).strip(" -_")
    return normalized or "默认反应体系"


def _repeat_condition_key(sample_name: str) -> str:
    """Comparison-only condition key without deleting a sample-number suffix."""
    return _condition_key(normalize_hplc_name(sample_name, strip_rerun_suffix=False))


def _folder_condition_key(folder_name: str) -> str:
    normalized = normalize_hplc_name(folder_name, strip_rerun_suffix=False)
    normalized = _DATE_TOKEN.sub(" ", normalized)
    normalized = _BATCH_PATTERN.sub(" ", normalized)
    normalized = _SHORT_BATCH_PATTERN.sub(" ", normalized)
    normalized = _BATCH_ENGLISH_PATTERN.sub(" ", normalized)
    normalized = re.sub(r"(?:REPEAT|RERUN|重打|第二天|次日)", " ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s+", " ", normalized).strip(" -_")
    return normalized or "未描述条件"


def _sequence_condition_key(sequence_name: str, result_name: str) -> str:
    """Keep experiment descriptors while removing dates, run times and rerun labels."""
    normalized = normalize_hplc_name(result_name or sequence_name)
    normalized = _DATE_TOKEN.sub(" ", normalized)
    normalized = _TIME_RANGE_PATTERN.sub(" ", normalized)
    normalized = _TIME_PATTERN.sub(" ", normalized)
    normalized = _BATCH_PATTERN.sub(" ", normalized)
    normalized = _SHORT_BATCH_PATTERN.sub(" ", normalized)
    normalized = _BATCH_ENGLISH_PATTERN.sub(" ", normalized)
    normalized = re.sub(
        r"(?:第二天|次日|异常重打|第一次异常|REPEAT|RERUN|重打|\bSM\b)",
        " ",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(r"\s+", " ", normalized).strip(" -_")
    return normalized or "未描述序列条件"


def _batch_condition_key(folder_name: str, sequence_name: str, result_name: str) -> str:
    """Use the dated folder description unless it is only a date/batch container."""
    folder_key = _folder_condition_key(folder_name)
    if folder_key != "未描述条件":
        return folder_key
    return _sequence_condition_key(sequence_name, result_name)


def _parse_acquisition_date(value: str) -> date:
    return datetime.fromisoformat(str(value)).date()


def _signal_columns_by_injection(dataset: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw_sheet in dataset.get("raw_sheets", []):
        for column in raw_sheet.get("columns", []):
            injection_id = str(column.get("injection_id") or "")
            if injection_id and injection_id not in result:
                result[injection_id] = column
    return result


def _quality_metrics(column: dict[str, Any] | None, config: dict[str, Any]) -> dict[str, float | None]:
    if not column:
        return {
            "point_count": 0,
            "baseline_noise_mau": None,
            "baseline_drift_mau": None,
            "maximum_signal_jump_mau": None,
        }
    time = np.asarray(column.get("time") or [], dtype=float)
    signal = np.asarray(column.get("signal") or [], dtype=float)
    thresholds = config["quality_thresholds"]
    start_window = thresholds["baseline_start_window_min"]
    end_window = thresholds["baseline_end_window_min"]
    start = signal[(time >= float(start_window[0])) & (time <= float(start_window[1]))]
    end = signal[(time >= float(end_window[0])) & (time <= float(end_window[1]))]
    if len(end) < 4 and len(time):
        tail_exclusion = float(thresholds["baseline_tail_exclusion_min"])
        tail_width = float(thresholds["baseline_tail_window_width_min"])
        tail_end = float(time[-1]) - tail_exclusion
        tail_start = max(float(time[0]), tail_end - tail_width)
        end = signal[(time >= tail_start) & (time <= tail_end)]
    noise = float(np.std(np.diff(start)) / math.sqrt(2.0)) if len(start) >= 4 else None
    drift = float(abs(np.median(end) - np.median(start))) if len(start) and len(end) else None
    jump = float(np.max(np.abs(np.diff(signal)))) if len(signal) >= 2 else None
    return {
        "point_count": int(len(signal)),
        "baseline_noise_mau": noise,
        "baseline_drift_mau": drift,
        "maximum_signal_jump_mau": jump,
    }


def _classify_injection_quality(
    injection: dict[str, Any],
    signal_column: dict[str, Any] | None,
    config: dict[str, Any],
) -> tuple[str, list[str], dict[str, float | None], bool]:
    reasons: list[str] = []
    review: list[str] = []
    quantifiable = signal_column is not None
    if str(injection.get("decode_status") or "") != "OK":
        reasons.append("原始信号解码状态不是 OK")
        quantifiable = False
    if not injection.get("time_monotonic", False) or not injection.get("signal_finite", False):
        reasons.append("色谱时间轴或信号完整性检查失败")
        quantifiable = False

    combined_name = " ".join(
        str(injection.get(key) or "")
        for key in ("sample_name", "sequence_name", "result_name", "result_set_folder")
    )
    if any(term in combined_name for term in config["name_rules"]["explicit_anomaly_terms"]):
        reasons.append("名称中含用户明确标注的异常标记")

    metrics = _quality_metrics(signal_column, config)
    thresholds = config["quality_thresholds"]
    if int(metrics["point_count"] or 0) < int(thresholds["minimum_signal_points"]):
        reasons.append("色谱信号点数不足")
        quantifiable = False
    metric_rules = (
        ("baseline_noise_mau", "baseline_noise_review_mau", "baseline_noise_abnormal_mau", "基线噪声"),
        ("baseline_drift_mau", "baseline_drift_review_mau", "baseline_drift_abnormal_mau", "基线漂移"),
        ("maximum_signal_jump_mau", "signal_jump_review_mau", "signal_jump_abnormal_mau", "信号突跳"),
    )
    for metric_key, review_key, abnormal_key, label in metric_rules:
        value = metrics[metric_key]
        if value is None:
            review.append(f"{label}无法评估")
        elif float(value) >= float(thresholds[abnormal_key]):
            reasons.append(f"{label}明显异常（{value:.6g}）")
        elif float(value) >= float(thresholds[review_key]):
            review.append(f"{label}接近人工复核阈值（{value:.6g}）")
    if reasons:
        return "异常", reasons + review, metrics, quantifiable
    if review:
        return "待人工复核", review, metrics, quantifiable
    return "正常", [], metrics, quantifiable


def match_target_peaks(
    peaks: Iterable[dict[str, Any]],
    config: dict[str, Any],
    *,
    missing_can_be_zero: bool,
    method_name: str = "",
) -> dict[str, dict[str, Any]]:
    """Match only the three user-specified RT windows to vendor peak rows."""
    peak_rows = [item for item in peaks if item.get("retention_time_min") is not None]
    result: dict[str, dict[str, Any]] = {}
    ambiguity_margin = float(config["quality_thresholds"]["ambiguous_rt_distance_margin_min"])
    for target_key in TARGET_ORDER:
        target = dict(config["targets"][target_key])
        rt_mapping_source = "default_target_window"
        for override in config.get("method_target_overrides", []):
            method_fragment = str(override.get("acquisition_method_contains") or "").strip()
            if not method_fragment or method_fragment.casefold() not in method_name.casefold():
                continue
            target_override = (override.get("targets") or {}).get(target_key)
            if isinstance(target_override, dict):
                target.update(target_override)
                rt_mapping_source = str(override.get("source") or "method_target_override")
        nominal = float(target["nominal_rt_min"])
        tolerance = float(target["rt_tolerance_min"])
        candidates = [
            item
            for item in peak_rows
            if abs(float(item["retention_time_min"]) - nominal) <= tolerance + 1e-12
        ]
        candidates.sort(
            key=lambda item: (
                abs(float(item["retention_time_min"]) - nominal),
                int(item.get("peak_ordinal") or 0),
            )
        )
        if not candidates:
            status = "正常未检出" if missing_can_be_zero else "数据异常导致无法定量"
            result[target_key] = {
                "target_key": target_key,
                "display_name": target["display_name"],
                "nominal_rt_min": nominal,
                "retention_time_min": None,
                "rt_deviation_min": None,
                "area": 0.0 if missing_can_be_zero else None,
                "match_status": status,
                "candidate_count": 0,
                "candidate_peak_ordinals": [],
                "candidate_retention_times_min": [],
                "ambiguous": False,
                "selected_peak_ordinal": None,
                "begin_time_min": None,
                "end_time_min": None,
                "height": None,
                "baseline_start": None,
                "baseline_end": None,
                "baseline_model": None,
                "rt_mapping_source": rt_mapping_source,
            }
            continue
        selected = candidates[0]
        ambiguous = (
            len(candidates) > 1
            and abs(
                abs(float(candidates[1]["retention_time_min"]) - nominal)
                - abs(float(selected["retention_time_min"]) - nominal)
            )
            <= ambiguity_margin
        )
        status = "目标峰匹配存在歧义" if ambiguous else (
            "多候选峰-按最近RT" if len(candidates) > 1 else "RT窗口匹配"
        )
        selected_rt = float(selected["retention_time_min"])
        result[target_key] = {
            "target_key": target_key,
            "display_name": target["display_name"],
            "nominal_rt_min": nominal,
            "retention_time_min": selected_rt,
            "rt_deviation_min": selected_rt - nominal,
            "area": float(selected["area"]) if selected.get("area") is not None else None,
            "match_status": status,
            "candidate_count": len(candidates),
            "candidate_peak_ordinals": [int(item.get("peak_ordinal") or 0) for item in candidates],
            "candidate_retention_times_min": [
                float(item["retention_time_min"]) for item in candidates
            ],
            "ambiguous": ambiguous,
            "selected_peak_ordinal": int(selected.get("peak_ordinal") or 0),
            "begin_time_min": selected.get("begin_time_min"),
            "end_time_min": selected.get("end_time_min"),
            "height": selected.get("height"),
            "baseline_start": selected.get("baseline_start"),
            "baseline_end": selected.get("baseline_end"),
            "baseline_model": selected.get("baseline_model"),
            "rt_mapping_source": rt_mapping_source,
        }
    return result


def _vendor_result_available(
    injection: dict[str, Any],
    vendor_peaks: list[dict[str, Any]],
    config: dict[str, Any],
) -> bool:
    """Return whether the paired .rx contains a usable vendor processing result."""
    state = str(injection.get("openlab_processing_state") or "").casefold()
    if state in {
        "nomethodprovided",
        "missing_rx",
        "missing_result",
        "vendor_result_unreadable",
    }:
        return False
    if vendor_peaks:
        return True
    success_states = {
        str(value).casefold()
        for value in config["peak_selection"].get("vendor_success_states", [])
    }
    return bool(state and state in success_states)


def _select_vendor_target(
    vendor_target: dict[str, Any],
    *,
    vendor_available: bool,
    vendor_result_origin: str = "stored_rx",
) -> dict[str, Any]:
    """Select only an Agilent-produced target; never synthesize a native fallback."""
    vendor_detected = vendor_target.get("retention_time_min") is not None
    selected = deepcopy(vendor_target)
    if vendor_available:
        reprocessed = vendor_result_origin == "agilent_processing_server_reprocessed_rx"
        selected.update(
            {
                "peak_source": "vendor_rx",
                "vendor_result_origin": vendor_result_origin,
                "integrator_name": (
                    "Agilent OpenLab Processing Server (complete PMX reprocessing)"
                    if reprocessed
                    else "Agilent OpenLab stored processing result"
                ),
                "integrator_version": (
                    "locally executed vendor Processing Server"
                    if reprocessed
                    else "paired .rx"
                ),
                "manual_check_required": True,
            }
        )
    else:
        selected.update(
            {
                "peak_source": "vendor_result_unavailable",
                "vendor_result_origin": None,
                "integrator_name": None,
                "integrator_version": None,
                "manual_check_required": True,
            }
        )
    selected.update(
        {
            "primary_peak_source": "vendor_rx" if vendor_available else "vendor_unavailable",
            "vendor_result_available": vendor_available,
            "vendor_detected": vendor_detected,
            "vendor_area": vendor_target.get("area") if vendor_detected else None,
            "vendor_retention_time_min": (
                vendor_target.get("retention_time_min") if vendor_detected else None
            ),
        }
    )
    return selected


def _calibrate_area(area: float | None, target: dict[str, Any], dilution: float) -> dict[str, Any]:
    if area is None:
        return {
            "raw_injection_concentration_mM": None,
            "injection_concentration_mM": None,
            "reaction_concentration_mM": None,
            "below_intercept": False,
        }
    raw = (float(area) - float(target["calibration_intercept"])) / float(target["calibration_slope"])
    final = max(0.0, raw)
    return {
        "raw_injection_concentration_mM": raw,
        "injection_concentration_mM": final,
        "reaction_concentration_mM": final * dilution,
        "below_intercept": raw < 0.0,
    }


def _rerun_evidence(
    left: dict[str, Any],
    right: dict[str, Any],
    result_profiles: dict[str, dict[str, Any]],
    config: dict[str, Any],
    *,
    sequence_similarities: dict[tuple[str, str], tuple[float, float]] | None = None,
) -> list[str]:
    same_sample = left["normalized_sample_name"] == right["normalized_sample_name"]
    same_supported_base = left["sample_identity_base"] == right["sample_identity_base"]
    if not same_sample and not same_supported_base:
        return []
    if left["batch_marker"] != right["batch_marker"]:
        return []
    maximum_gap = int(config["repeat_rules"]["maximum_automatic_day_gap"])
    gap = abs((left["acquisition_date"] - right["acquisition_date"]).days)
    if gap > maximum_gap:
        return []
    if left["repeat_condition_key"] != right["repeat_condition_key"]:
        return []
    if left["batch_condition_key"] != right["batch_condition_key"]:
        return []
    evidence: list[str] = []
    if left["result_set_id"] == right["result_set_id"]:
        left_order = left.get("sequence_order")
        right_order = right.get("sequence_order")
        if left_order is not None and right_order is not None:
            order_gap = abs(int(left_order) - int(right_order))
            if order_gap <= int(
                config["repeat_rules"]["adjacent_sequence_order_gap"]
            ):
                evidence.append("同一序列内相同样品连续进样")
            elif (
                order_gap <= int(config["repeat_rules"]["same_sequence_repeat_order_gap"])
                and left["normalized_sequence_name"] == right["normalized_sequence_name"]
            ):
                evidence.append("同一序列内相同样品在重复区段再次进样")
    if left["sample_has_explicit_rerun_word"] or right["sample_has_explicit_rerun_word"]:
        evidence.append("样品名含明确重打文字")
    for normalized_key, raw_key, label in (
        ("normalized_sequence_name", "sequence_name", "序列名重打标记"),
        ("normalized_result_name", "result_name", "OpenLab结果名重打标记"),
    ):
        if left[normalized_key] and left[normalized_key] == right[normalized_key]:
            if left[raw_key] != right[raw_key] and (
                has_rerun_marker(left[raw_key], config) or has_rerun_marker(right[raw_key], config)
            ):
                evidence.append(label)
    if any(
        has_rerun_marker(value, config)
        for value in (
            left.get("raw_file", ""),
            right.get("raw_file", ""),
            left.get("source_relative", ""),
            right.get("source_relative", ""),
        )
    ):
        evidence.append("数据文件名或目录含明确重打标记")

    if left["result_set_id"] != right["result_set_id"]:
        # Keep the pair ordered: SequenceMatcher can resolve matching ties
        # differently when its two input sequences are reversed.
        pair = (left["result_set_id"], right["result_set_id"])
        cached = sequence_similarities.get(pair) if sequence_similarities is not None else None
        if cached is None:
            left_profile = result_profiles.get(pair[0], {})
            right_profile = result_profiles.get(pair[1], {})
            left_samples = set(left_profile.get("samples", []))
            right_samples = set(right_profile.get("samples", []))
            ordered_similarity = SequenceMatcher(
                None,
                left_profile.get("samples", []),
                right_profile.get("samples", []),
                autojunk=False,
            ).ratio()
            union = left_samples | right_samples
            set_similarity = len(left_samples & right_samples) / len(union) if union else 0.0
            if sequence_similarities is not None:
                sequence_similarities[pair] = (ordered_similarity, set_similarity)
        else:
            ordered_similarity, set_similarity = cached
        similarity = max(ordered_similarity, set_similarity)
        same_sequence = bool(
            left["normalized_sequence_name"]
            and left["normalized_sequence_name"] == right["normalized_sequence_name"]
        )
        if same_sequence and similarity >= float(
            config["repeat_rules"]["sequence_sample_similarity_min"]
        ):
            evidence.append("同名序列连续运行且样品列表高度相似")
        elif ordered_similarity >= float(
            config["repeat_rules"]["sequence_sample_identity_min"]
        ):
            evidence.append("连续运行序列的有序样品列表完全或近乎完全一致")
        if any(
            has_rerun_marker(value, config)
            for value in (
                left["sequence_name"],
                right["sequence_name"],
                left["result_name"],
                right["result_name"],
            )
        ):
            evidence.append("结果结构含明确重打标记")
        if any(
            has_explicit_rerun_word(value, config)
            for value in (left["result_set_folder"], right["result_set_folder"])
        ):
            evidence.append("结果目录含明确重打文字")
        if gap == 1 and evidence:
            evidence.append("第二天同名同条件样品重打")
    if not same_sample and not evidence:
        return []
    return list(dict.fromkeys(evidence))


def _result_profiles(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[record["result_set_id"]].append(record)
    profiles: dict[str, dict[str, Any]] = {}
    for result_set_id, members in grouped.items():
        members.sort(key=lambda item: (item.get("sequence_order") or 10**9, item["acquisition_local"]))
        profiles[result_set_id] = {
            "samples": [item["normalized_sample_name"] for item in members if not item["is_wash"]],
            "first_acquisition": members[0]["acquisition_local"],
            "last_acquisition": members[-1]["acquisition_local"],
        }
    return profiles


def _repeat_hard_boundary_compatible(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    maximum_days: int,
) -> bool:
    gap = abs((left["acquisition_date"] - right["acquisition_date"]).days)
    return (
        gap <= maximum_days
        and left["batch_marker"] == right["batch_marker"]
        and left["repeat_condition_key"] == right["repeat_condition_key"]
        and left["batch_condition_key"] == right["batch_condition_key"]
    )


class _UnionFind:
    def __init__(self, values: Iterable[str], acquisition_dates: dict[str, date]):
        self.parent = {value: value for value in values}
        self.members = {value: {value} for value in values}
        self.acquisition_dates = acquisition_dates

    def find(self, value: str) -> str:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union_within_span(self, left: str, right: str, maximum_days: int) -> bool:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return True
        combined = self.members[left_root] | self.members[right_root]
        dates = [self.acquisition_dates[item] for item in combined]
        if (max(dates) - min(dates)).days > maximum_days:
            return False
        self.parent[right_root] = left_root
        self.members[left_root] = combined
        self.members.pop(right_root, None)
        return True


def _assign_repeat_groups(
    records: list[dict[str, Any]],
    config: dict[str, Any],
) -> tuple[dict[str, str], dict[str, list[str]], list[dict[str, Any]], list[dict[str, Any]]]:
    groupable = [
        item
        for item in records
        if not item["is_wash"]
        and not item.get("is_before_screening", False)
        and not item.get("is_light_boundary_uncertain", False)
    ]
    by_id = {item["injection_id"]: item for item in groupable}
    union = _UnionFind(
        by_id,
        {item["injection_id"]: item["acquisition_date"] for item in groupable},
    )
    profiles = _result_profiles(records)
    sequence_similarities: dict[tuple[str, str], tuple[float, float]] = {}
    edge_evidence: list[dict[str, Any]] = []
    uncertain: list[dict[str, Any]] = []
    maximum_gap = int(config["repeat_rules"]["maximum_automatic_day_gap"])
    grouped_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in groupable:
        grouped_by_name[item["sample_identity_base"]].append(item)
    for candidates in grouped_by_name.values():
        candidates.sort(key=lambda item: item["acquisition_local"])
        for left_index, left in enumerate(candidates):
            for right_index in range(left_index + 1, len(candidates)):
                right = candidates[right_index]
                gap = abs((left["acquisition_date"] - right["acquisition_date"]).days)
                if gap > maximum_gap:
                    # ISO acquisition timestamps are sorted above, so later
                    # records cannot re-enter this left record's date window.
                    break
                if not _repeat_hard_boundary_compatible(
                    left,
                    right,
                    maximum_days=maximum_gap,
                ):
                    continue
                evidence = _rerun_evidence(
                    left, right, profiles, config,
                    sequence_similarities=sequence_similarities,
                )
                if evidence and union.union_within_span(
                    left["injection_id"], right["injection_id"], maximum_gap
                ):
                    edge_evidence.append(
                        {
                            "left": left["injection_id"],
                            "right": right["injection_id"],
                            "evidence": evidence,
                        }
                    )
                elif not evidence and left["normalized_sample_name"] == right["normalized_sample_name"]:
                    uncertain.append(
                        {
                            "left": left["injection_id"],
                            "right": right["injection_id"],
                            "reason": "同名同条件且日期接近，但缺少足够的重打结构证据",
                        }
                    )

    override_groups = config.get("manual_overrides", {}).get("repeat_group_by_injection", {}) or {}
    override_members: dict[str, list[str]] = defaultdict(list)
    removed_by_override: set[str] = set()
    for injection_id, group_id in override_groups.items():
        if injection_id not in by_id:
            continue
        if group_id is None or str(group_id).strip() == "":
            removed_by_override.add(injection_id)
        else:
            override_members[str(group_id)].append(injection_id)
    for members in override_members.values():
        for member in members[1:]:
            left = by_id[members[0]]
            right = by_id[member]
            if not _repeat_hard_boundary_compatible(
                left,
                right,
                maximum_days=maximum_gap,
            ):
                raise ValueError(
                    "manual repeat-group override crosses a hard batch/condition/date boundary: "
                    f"{members[0]} vs {member}"
                )
            union.union_within_span(members[0], member, maximum_gap)

    components: list[list[str]] = []
    for members in union.members.values():
        kept = sorted(members - removed_by_override, key=lambda item: by_id[item]["acquisition_local"])
        if len(kept) > 1:
            components.append(kept)
    components.sort(key=lambda members: by_id[members[0]]["acquisition_local"])
    group_by_injection: dict[str, str] = {}
    evidence_by_group: dict[str, list[str]] = {}
    for index, members in enumerate(components, start=1):
        group_id = f"RG{index:03d}"
        for member in members:
            group_by_injection[member] = group_id
        evidence = [
            reason
            for edge in edge_evidence
            if edge["left"] in members and edge["right"] in members
            for reason in edge["evidence"]
        ]
        for override_id, override_injections in override_members.items():
            if set(override_injections) & set(members):
                evidence.append(f"人工覆盖重打组：{override_id}")
        evidence_by_group[group_id] = list(dict.fromkeys(evidence))
    return group_by_injection, evidence_by_group, edge_evidence, uncertain


def _mark_low_scale_repeat_outliers(
    members: list[dict[str, Any]],
    config: dict[str, Any],
) -> None:
    eligible = [item for item in members if item["quality"] == "正常" and item["quantifiable"]]
    totals = {
        item["injection_id"]: sum(
            float(item["targets"][key]["area"] or 0.0) for key in TARGET_ORDER
        )
        for item in eligible
    }
    if len(totals) < 2 or max(totals.values(), default=0.0) <= 0.0:
        return
    reference = max(totals.values())
    total_ratio_threshold = float(config["repeat_rules"]["low_total_area_ratio"])
    component_ratio_threshold = float(config["repeat_rules"]["low_component_area_ratio"])
    minimum_components = int(config["repeat_rules"]["minimum_scaled_components"])
    reference_member = max(eligible, key=lambda item: totals[item["injection_id"]])
    for item in eligible:
        if item is reference_member or totals[item["injection_id"]] / reference >= total_ratio_threshold:
            continue
        scaled_components = 0
        for key in TARGET_ORDER:
            reference_area = reference_member["targets"][key]["area"]
            candidate_area = item["targets"][key]["area"]
            if reference_area is not None and float(reference_area) > 0 and candidate_area is not None:
                if float(candidate_area) / float(reference_area) < component_ratio_threshold:
                    scaled_components += 1
        if scaled_components >= minimum_components:
            item["quality"] = "异常"
            item["quality_reasons"].append("多个目标峰同比例明显偏低，疑似取样量或进样量不足")


def _trend_score(
    member: dict[str, Any],
    previous: dict[str, float],
    following: dict[str, float],
    tolerance: float,
) -> int:
    score = 0
    values = {key: float(member["targets"][key]["area"] or 0.0) for key in TARGET_ORDER}
    substrate = values["thioanisole"]
    if substrate > previous["thioanisole"] * (1.0 + tolerance):
        score += 1
    if substrate < following["thioanisole"] * (1.0 - tolerance):
        score += 1
    sulfone = values["sulfone"]
    if sulfone < previous["sulfone"] * (1.0 - tolerance):
        score += 1
    if sulfone > following["sulfone"] * (1.0 + tolerance):
        score += 1
    sulfoxide = values["sulfoxide"]
    low = min(previous["sulfoxide"], following["sulfoxide"])
    high = max(previous["sulfoxide"], following["sulfoxide"])
    if sulfoxide < low * (1.0 - tolerance) or sulfoxide > high * (1.0 + tolerance):
        score += 1
    return score


def _choose_by_trend(
    members: list[dict[str, Any]],
    all_records: list[dict[str, Any]],
    config: dict[str, Any],
) -> tuple[dict[str, Any] | None, str]:
    if len(members) < 2 or any(item["reaction_time_h"] is None for item in members):
        return None, ""
    representative = members[0]
    time_h = float(representative["reaction_time_h"])
    member_ids = {member["injection_id"] for member in members}
    neighbors = [
        item
        for item in all_records
        if item["injection_id"] not in member_ids
        and item["quality"] == "正常"
        and item["quantifiable"]
        and item["experiment_batch"] == representative["experiment_batch"]
        and item["condition_key"] == representative["condition_key"]
        and item["reaction_time_h"] is not None
    ]
    previous_candidates = [item for item in neighbors if float(item["reaction_time_h"]) < time_h]
    following_candidates = [item for item in neighbors if float(item["reaction_time_h"]) > time_h]
    if not previous_candidates or not following_candidates:
        return None, ""
    previous_time = max(float(item["reaction_time_h"]) for item in previous_candidates)
    following_time = min(float(item["reaction_time_h"]) for item in following_candidates)
    previous_members = [item for item in previous_candidates if float(item["reaction_time_h"]) == previous_time]
    following_members = [item for item in following_candidates if float(item["reaction_time_h"]) == following_time]
    previous = {
        key: float(np.median([float(item["targets"][key]["area"] or 0.0) for item in previous_members]))
        for key in TARGET_ORDER
    }
    following = {
        key: float(np.median([float(item["targets"][key]["area"] or 0.0) for item in following_members]))
        for key in TARGET_ORDER
    }
    tolerance = float(config["repeat_rules"]["trend_relative_tolerance"])
    scores = [(item, _trend_score(item, previous, following, tolerance)) for item in members]
    scores.sort(key=lambda pair: pair[1])
    margin = int(config["repeat_rules"]["trend_score_margin"])
    if len(scores) >= 2 and scores[0][1] == 0 and scores[1][1] - scores[0][1] >= margin:
        chosen = scores[0][0]
        detail = (
            f"相邻时间点 {previous_time:g} h 与 {following_time:g} h 之间，"
            f"{chosen['injection_id']} 的趋势违例分数为 0；其他候选最低为 {scores[1][1]}"
        )
        return chosen, detail
    return None, ""


def _unique_text(values: Iterable[Any]) -> str:
    return "; ".join(dict.fromkeys(str(value) for value in values if value is not None and str(value).strip()))


def _data_group_text(members: Iterable[dict[str, Any]]) -> str:
    return "; ".join(f"{item['injection_id']} ({item['raw_file']})" for item in members)


def _representative_sample_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).strip()
    return re.sub(r"\s+", " ", normalized)


def _combine_final_result(
    members: list[dict[str, Any]],
    used: list[dict[str, Any]],
    discarded: list[dict[str, Any]],
    *,
    group_id: str,
    process_method: str,
    process_note: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    representative = min(members, key=lambda item: item["acquisition_local"])
    targets: dict[str, dict[str, Any]] = {}
    dilution = float(config["reaction"]["total_dilution_factor"])
    for key in TARGET_ORDER:
        target_config = config["targets"][key]
        areas = [item["targets"][key]["area"] for item in used]
        rts = [item["targets"][key]["retention_time_min"] for item in used]
        ordinals = [item["targets"][key].get("selected_peak_ordinal") for item in used]
        numeric_areas = [float(value) for value in areas if value is not None]
        numeric_rts = [float(value) for value in rts if value is not None]
        area = float(np.mean(numeric_areas)) if used and len(numeric_areas) == len(used) else None
        rt = float(np.mean(numeric_rts)) if numeric_rts else None
        calibration = _calibrate_area(area, target_config, dilution)
        statuses = [item["targets"][key]["match_status"] for item in used]
        if not used:
            status = "没有自动采用的数据"
        elif any("歧义" in status for status in statuses):
            status = "目标峰匹配存在歧义"
        elif all(status == "正常未检出" for status in statuses):
            status = "正常未检出"
        elif len(used) > 1:
            status = "重复进样目标峰平均"
        else:
            status = statuses[0]
        targets[key] = {
            "target_key": key,
            "display_name": target_config["display_name"],
            "nominal_rt_min": float(target_config["nominal_rt_min"]),
            "retention_time_min": rt,
            "rt_deviation_min": rt - float(target_config["nominal_rt_min"]) if rt is not None else None,
            "area": area,
            "selected_peak_ordinals": [int(value) for value in ordinals if value is not None],
            "match_status": status,
            "peak_source": " + ".join(
                dict.fromkeys(
                    str(item["targets"][key].get("peak_source") or "vendor_result_unavailable")
                    for item in used
                )
            ) or "vendor_result_unavailable",
            **calibration,
        }

    quality = "正常"
    if not used:
        quality = "待人工复核"
    elif discarded and process_method == "趋势择优":
        quality = "正常（趋势择优）"
    elif discarded:
        quality = "正常（已排除异常重打）"
    elif any(item["quality"] != "正常" for item in used):
        quality = "人工覆盖采用"
    experiment_date = min(item["experiment_date"] for item in members)
    light_source = classify_light_source(
        experiment_date,
        config,
        folder_name=representative["batch_folder"],
    )
    batch_marker = representative["batch_marker"]
    experiment_batch = f"{experiment_date:%Y%m%d}-{batch_marker}"
    provenance_members = used or members
    return {
        "experiment_date": experiment_date.isoformat(),
        "sample_name": _representative_sample_name(representative["sample_name"]),
        "normalized_sample_name": representative["normalized_sample_name"],
        "experiment_batch": experiment_batch,
        "experiment_batch_key": (
            f"{experiment_date.isoformat()}|{batch_marker}|{light_source}|"
            f"{representative['batch_condition_key']}"
        ),
        "batch_marker": batch_marker,
        "reaction_time_h": representative["reaction_time_h"],
        "light_source": light_source,
        "is_pre_reaction": any(item["is_pre_reaction"] for item in members),
        "folder_condition_key": representative["folder_condition_key"],
        "sequence_condition_key": representative["sequence_condition_key"],
        "batch_condition_key": representative["batch_condition_key"],
        "targets": targets,
        "c0_mM": None,
        "c0_source_injection_ids": [],
        "conversion_fraction": None,
        "sulfoxide_selectivity_fraction": None,
        "sulfoxide_yield_fraction": None,
        "material_recovery_fraction": None,
        "data_quality": quality,
        "process_method": process_method,
        "used_data_group": _data_group_text(used),
        "discarded_data_group": _data_group_text(discarded),
        "process_note": process_note,
        "rerun_group_id": group_id,
        "actual_acquisition_time": _unique_text(
            item["acquisition_local"] for item in provenance_members
        ),
        "acquisition_method": _unique_text(item["method_name"] for item in provenance_members),
        "sequence_name": _unique_text(item["sequence_name"] for item in provenance_members),
        "result_name": _unique_text(item["result_name"] for item in provenance_members),
        "batch_folder": _unique_text(item["batch_folder"] for item in provenance_members),
        "raw_file": _unique_text(item["raw_file"] for item in provenance_members),
        "source_relative": _unique_text(item["source_relative"] for item in provenance_members),
        "member_injection_ids": [item["injection_id"] for item in members],
        "used_injection_ids": [item["injection_id"] for item in used],
        "discarded_injection_ids": [item["injection_id"] for item in discarded],
    }


def _log_entry(
    generated_at: str,
    *,
    experiment_date: str,
    sample_name: str,
    group_id: str = "",
    raw_files: str = "",
    operation_type: str,
    basis: str,
    before_status: str,
    after_result: str,
    used_data: str = "",
    discarded_data: str = "",
    details: str = "",
) -> dict[str, Any]:
    return {
        "processed_at": generated_at,
        "experiment_date": experiment_date,
        "sample_name": sample_name,
        "rerun_group_id": group_id,
        "raw_files": raw_files,
        "operation_type": operation_type,
        "basis": basis,
        "before_status": before_status,
        "after_result": after_result,
        "used_data": used_data,
        "discarded_data": discarded_data,
        "details": details,
    }


def _manual_review(
    *,
    experiment_date: str,
    sample_name: str,
    injection_ids: str,
    issue_type: str,
    reason: str,
    recommended_action: str,
) -> dict[str, Any]:
    return {
        "experiment_date": experiment_date,
        "sample_name": sample_name,
        "injection_ids": injection_ids,
        "issue_type": issue_type,
        "reason": reason,
        "recommended_action": recommended_action,
        "status": "待人工复核",
    }


def _parameter_rows(config: dict[str, Any], generated_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in TARGET_ORDER:
        target = config["targets"][key]
        rows.extend(
            [
                {
                    "category": "目标峰",
                    "parameter": f"{target['display_name']} 标称RT",
                    "value": target["nominal_rt_min"],
                    "unit": "min",
                    "source": "用户提供",
                },
                {
                    "category": "目标峰",
                    "parameter": f"{target['display_name']} RT容差",
                    "value": target["rt_tolerance_min"],
                    "unit": "±min",
                    "source": "用户提供",
                },
                {
                    "category": "标曲",
                    "parameter": f"{target['display_name']} 标曲",
                    "value": f"y={target['calibration_slope']}x+{target['calibration_intercept']}; R²={target['calibration_r_squared']}",
                    "unit": "x=mM, y=峰面积",
                    "source": "用户提供",
                },
            ]
        )
    for override in config.get("method_target_overrides", []):
        method_fragment = str(override.get("acquisition_method_contains") or "")
        for target_key, target_override in (override.get("targets") or {}).items():
            target_name = config["targets"][target_key]["display_name"]
            rows.append(
                {
                    "category": "方法专用目标峰",
                    "parameter": f"{target_name} RT窗口（方法含 {method_fragment}）",
                    "value": (
                        f"{target_override['nominal_rt_min']} ± "
                        f"{target_override['rt_tolerance_min']}"
                    ),
                    "unit": "min",
                    "source": str(override.get("source") or "项目配置"),
                }
            )
    rows.append(
        {
            "category": "稀释",
            "parameter": "总稀释倍数",
            "value": config["reaction"]["total_dilution_factor"],
            "unit": "倍",
            "source": "用户提供的两步10倍稀释",
        }
    )
    date_rules = config["date_rules"]
    rows.extend(
        [
            {"category": "日期/光源", "parameter": "光源筛选日期", "value": date_rules["light_screening_date"], "unit": "", "source": "用户提供"},
            {"category": "日期/光源", "parameter": "306房间灯日期", "value": f"{date_rules['ordinary_306_start']} 至 {date_rules['ordinary_306_end']}", "unit": "", "source": "用户提供"},
            {"category": "日期/光源", "parameter": "301房间灯起始日期", "value": date_rules["ordinary_301_start"], "unit": "", "source": "用户提供"},
            {"category": "批次", "parameter": "批次识别规则", "value": "样品名优先，其次日期文件夹，再次序列/结果名称；显式第N批/batchN为硬边界", "unit": "", "source": "用户规则"},
            {"category": "重打", "parameter": "自动日期间隔", "value": config["repeat_rules"]["maximum_automatic_day_gap"], "unit": "day", "source": "用户规则"},
            {"category": "重打", "parameter": "识别证据", "value": "序列名/结果名/文件名明确重打标记、同序列相邻同名样品、同名序列样品列表、第二天同名同条件且有结构证据；批次硬边界优先", "unit": "", "source": "用户规则"},
        ]
    )
    peak_selection = config["peak_selection"]
    rows.extend(
        [
            {
                "category": "峰来源",
                "parameter": "正式定量峰来源优先级",
                "value": "仅使用OpenLab原厂 .rx；缺失/失败时必须运行原厂重处理，不再自研积分",
                "unit": "",
                "source": f"{peak_selection['primary_source']} -> {peak_selection['missing_result_action']}",
            },
            {
                "category": "原厂积分",
                "parameter": "积分器",
                "value": "Agilent OpenLab stored .rx or Processing Server complete-PMX reprocessing",
                "unit": "",
                "source": "原厂结果或项目内置原厂运行时",
            },
        ]
    )
    for key, value in config["quality_thresholds"].items():
        rows.append(
            {
                "category": "异常阈值",
                "parameter": key,
                "value": json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value,
                "unit": "见参数名",
                "source": "集中配置；依据本批真实信号分布采用保守阈值",
            }
        )
    rows.extend(
        [
            {"category": "计算公式", "parameter": "转化率", "value": "(C₀-C_茴香硫醚)/C₀", "unit": "fraction", "source": "用户确认"},
            {"category": "计算公式", "parameter": "茴香亚砜选择性", "value": "C_茴香亚砜/(C_茴香亚砜+C_茴香砜)", "unit": "fraction", "source": "用户确认"},
            {"category": "计算公式", "parameter": "茴香亚砜产率", "value": "转化率×茴香亚砜选择性", "unit": "fraction", "source": "用户确认"},
            {"category": "计算公式", "parameter": "物料回收率", "value": "(C_茴香硫醚+C_茴香亚砜+C_茴香砜)/C₀", "unit": "fraction", "source": "用户确认"},
            {"category": "程序", "parameter": "分析版本", "value": config["analysis_version"], "unit": "", "source": "项目配置"},
            {"category": "程序", "parameter": "数据处理时间", "value": generated_at, "unit": "", "source": "运行时"},
            {"category": "科学边界", "parameter": "结果状态", "value": "用户提供RT映射和标曲的候选定量；所有转化率/选择性/产率仍需人工复核", "unit": "", "source": "claim policy"},
            {"category": "科学边界", "parameter": "23.5 min未知峰", "value": "可保留在原厂全峰审计数据中，不参与三组分计算", "unit": "", "source": "用户提供"},
        ]
    )
    return rows


def analyze_hplc_openlab_dataset(
    dataset: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Build a traceable analysis product solely from the existing decoded dataset."""
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    vendor_peaks_by_injection: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for peak in dataset.get("peaks", []):
        vendor_peaks_by_injection[str(peak.get("injection_id") or "")].append(peak)
    signal_by_injection = _signal_columns_by_injection(dataset)
    records: list[dict[str, Any]] = []
    processing_log: list[dict[str, Any]] = []
    excluded_data: list[dict[str, Any]] = []
    manual_review: list[dict[str, Any]] = []

    for injection in dataset.get("injections", []):
        injection_id = str(injection["injection_id"])
        batch_folder = str(injection.get("batch_folder") or "")
        experiment_date = parse_folder_date(batch_folder, config)
        sample_name = str(injection.get("sample_name") or "")
        sequence_name = str(injection.get("sequence_name") or injection.get("result_set_folder") or "")
        result_name = str(injection.get("result_name") or injection.get("result_set_folder") or "")
        marker, marker_ambiguous, marker_values = detect_batch_marker(
            sample_name,
            batch_folder,
            sequence_name,
            result_name,
        )
        combined_identity = " ".join(
            (sample_name, sequence_name, result_name, batch_folder)
        )
        wash = is_wash_sample(combined_identity, config)
        explicit_pre_reaction = is_pre_reaction_sample(sample_name, config)
        reaction_time_h = extract_reaction_time_h(
            sample_name,
            pre_reaction=explicit_pre_reaction,
        )
        pre_reaction = explicit_pre_reaction or reaction_time_h == 0.0
        if pre_reaction:
            reaction_time_h = 0.0
        light_source = classify_light_source(
            experiment_date,
            config,
            folder_name=batch_folder,
        )
        screening_date = date.fromisoformat(config["date_rules"]["light_screening_date"])
        exclude_before_screening = bool(
            config["date_rules"].get("exclude_before_light_screening_date", True)
        )
        is_before_screening = experiment_date < screening_date and exclude_before_screening
        is_light_boundary_uncertain = light_source == "光源日期边界待确认"
        analysis_eligible = not wash and not is_before_screening and not is_light_boundary_uncertain
        signal_column = signal_by_injection.get(injection_id)
        quality, quality_reasons, metrics, quantifiable = _classify_injection_quality(
            injection,
            signal_column,
            config,
        )
        raw_signal_quantifiable = quantifiable
        injection_vendor_peaks = vendor_peaks_by_injection.get(injection_id, [])
        vendor_available = _vendor_result_available(
            injection,
            injection_vendor_peaks,
            config,
        )
        method_name = str(injection.get("acquisition_method") or injection.get("processing_method") or "")
        vendor_targets = match_target_peaks(
            injection_vendor_peaks if vendor_available else [],
            config,
            missing_can_be_zero=vendor_available,
            method_name=method_name,
        )
        if analysis_eligible and not vendor_available:
            quantifiable = False
            if quality == "正常":
                quality = "待人工复核"
            quality_reasons.append(
                "缺少可用原厂积分结果；必须使用 --vendor-reprocess 调用原厂 Processing Server"
            )
        targets: dict[str, dict[str, Any]] = {}
        for target_key in TARGET_ORDER:
            vendor_target = vendor_targets[target_key]
            target = _select_vendor_target(
                vendor_target,
                vendor_available=vendor_available,
                vendor_result_origin=str(
                    injection.get("vendor_result_origin") or "stored_rx"
                ),
            )
            targets[target_key] = target
        if any(item["ambiguous"] for item in targets.values()) and quality == "正常":
            quality = "待人工复核"
            quality_reasons.append("至少一个目标峰存在近距离多候选歧义")
        record = {
            "injection_id": injection_id,
            "result_set_id": str(injection.get("result_set_id") or ""),
            "experiment_date": experiment_date,
            "acquisition_date": _parse_acquisition_date(str(injection["acquisition_local"])),
            "acquisition_local": str(injection["acquisition_local"]),
            "sample_name": sample_name,
            "normalized_sample_name": normalize_hplc_name(
                sample_name,
                strip_rerun_suffix=False,
            ),
            "sample_identity_base": normalize_hplc_name(
                sample_name,
                strip_rerun_suffix=False,
            ),
            "sample_has_explicit_rerun_word": has_explicit_rerun_word(sample_name, config),
            "sequence_name": sequence_name,
            "normalized_sequence_name": normalize_hplc_name(sequence_name),
            "result_name": result_name,
            "normalized_result_name": normalize_hplc_name(result_name),
            "batch_folder": batch_folder,
            "folder_condition_key": _folder_condition_key(batch_folder),
            "sequence_condition_key": _sequence_condition_key(sequence_name, result_name),
            "batch_condition_key": _batch_condition_key(
                batch_folder, sequence_name, result_name
            ),
            "result_set_folder": str(injection.get("result_set_folder") or ""),
            "batch_marker": marker,
            "batch_marker_ambiguous": marker_ambiguous,
            "batch_marker_values": marker_values,
            "experiment_batch": f"{experiment_date:%Y%m%d}-{marker}",
            "light_source": light_source,
            "reaction_time_h": reaction_time_h,
            "condition_key": _condition_key(sample_name),
            "repeat_condition_key": _repeat_condition_key(sample_name),
            "is_wash": wash,
            "is_pre_reaction": pre_reaction,
            "is_before_screening": is_before_screening,
            "is_light_boundary_uncertain": is_light_boundary_uncertain,
            "quality": quality,
            "quality_reasons": quality_reasons,
            "quality_metrics": metrics,
            "raw_signal_quantifiable": raw_signal_quantifiable,
            "quantifiable": quantifiable,
            "targets": targets,
            "vendor_result_available": vendor_available,
            "primary_peak_source": "vendor_rx" if vendor_available else "vendor_unavailable",
            "sequence_order": injection.get("sequence_order"),
            "method_name": method_name,
            "raw_file": str(injection.get("raw_file") or ""),
            "source_relative": str(injection.get("source_relative") or ""),
            "openlab_processing_state": str(injection.get("openlab_processing_state") or ""),
            "openlab_processing_warning": str(injection.get("openlab_processing_warning") or ""),
        }
        records.append(record)
        if wash:
            excluded_data.append(
                {
                    "experiment_date": experiment_date.isoformat(),
                    "sample_name": sample_name,
                    "injection_id": record["injection_id"],
                    "reason": "冲柱或清洗柱子数据",
                    "details": "样品名命中集中配置的冲柱词；不进入主结果或定量",
                    "acquisition_time": record["acquisition_local"],
                    "sequence_name": sequence_name,
                    "result_name": result_name,
                    "batch_folder": batch_folder,
                    "raw_file": record["raw_file"],
                    "source_relative": record["source_relative"],
                }
            )
            processing_log.append(
                _log_entry(
                    generated_at,
                    experiment_date=experiment_date.isoformat(),
                    sample_name=sample_name,
                    raw_files=record["raw_file"],
                    operation_type="冲柱数据排除",
                    basis="名称上下文命中冲柱/洗柱词表",
                    before_status="已解码进样",
                    after_result="排除出主分析",
                    discarded_data=record["injection_id"],
                    details="原始信号仍保留在审计数据集；不执行目标峰定量",
                )
            )
        if record["is_before_screening"]:
            screening_date_text = str(config["date_rules"]["light_screening_date"])
            excluded_data.append(
                {
                    "experiment_date": experiment_date.isoformat(),
                    "sample_name": sample_name,
                    "injection_id": record["injection_id"],
                    "reason": "光源筛选前数据暂不处理",
                    "details": f"日期文件夹早于配置的 {screening_date_text} 光源筛选边界",
                    "acquisition_time": record["acquisition_local"],
                    "sequence_name": sequence_name,
                    "result_name": result_name,
                    "batch_folder": batch_folder,
                    "raw_file": record["raw_file"],
                    "source_relative": record["source_relative"],
                }
            )
            processing_log.append(
                _log_entry(
                    generated_at,
                    experiment_date=experiment_date.isoformat(),
                    sample_name=sample_name,
                    raw_files=record["raw_file"],
                    operation_type="光源筛选前数据暂不处理",
                    basis=f"实验日期 {experiment_date.isoformat()} 早于光源筛选日期",
                    before_status="已解码进样",
                    after_result="不进入本次主分析",
                    discarded_data=record["injection_id"],
                )
            )
        if record["is_light_boundary_uncertain"]:
            excluded_data.append(
                {
                    "experiment_date": experiment_date.isoformat(),
                    "sample_name": sample_name,
                    "injection_id": record["injection_id"],
                    "reason": "光源日期边界待确认",
                    "details": "日期为 2026-07-17，但日期文件夹未明确出现“光源选择”或“光源筛选”",
                    "acquisition_time": record["acquisition_local"],
                    "sequence_name": sequence_name,
                    "result_name": result_name,
                    "batch_folder": batch_folder,
                    "raw_file": record["raw_file"],
                    "source_relative": record["source_relative"],
                }
            )
            manual_review.append(
                _manual_review(
                    experiment_date=experiment_date.isoformat(),
                    sample_name=sample_name,
                    injection_ids=record["injection_id"],
                    issue_type="光源日期边界待确认",
                    reason="2026-07-17 文件夹未明确标注光源选择/光源筛选",
                    recommended_action="确认该记录是否属于光源筛选；确认前不进入主结果",
                )
            )
        if record["light_source"] == config["date_rules"]["screening_label"]:
            processing_log.append(
                _log_entry(
                    generated_at,
                    experiment_date=experiment_date.isoformat(),
                    sample_name=sample_name,
                    raw_files=record["raw_file"],
                    operation_type="光源筛选分类",
                    basis=f"日期文件夹“{batch_folder}”同时满足 2026-07-17 和明确光源选择/筛选文字",
                    before_status="普通日期进样候选",
                    after_result="独立标记为光源筛选",
                    used_data=record["injection_id"],
                )
            )
        if marker != "默认批次":
            processing_log.append(
                _log_entry(
                    generated_at,
                    experiment_date=experiment_date.isoformat(),
                    sample_name=sample_name,
                    raw_files=record["raw_file"],
                    operation_type="显式批次识别",
                    basis=f"名称中识别到：{', '.join(marker_values) or marker}",
                    before_status="未分批",
                    after_result=marker,
                    used_data=record["injection_id"],
                )
            )
        if marker_ambiguous:
            manual_review.append(
                _manual_review(
                    experiment_date=experiment_date.isoformat(),
                    sample_name=sample_name,
                    injection_ids=record["injection_id"],
                    issue_type="批次关系待确认",
                    reason=f"同一名称上下文含多个显式批次：{', '.join(marker_values)}",
                    recommended_action="确认该进样实际属于哪一实验批次后，通过集中配置中的人工覆盖重新运行",
                )
            )
        if analysis_eligible and not record["vendor_result_available"]:
            processing_log.append(
                _log_entry(
                    generated_at,
                    experiment_date=experiment_date.isoformat(),
                    sample_name=sample_name,
                    raw_files=record["raw_file"],
                    operation_type="原厂积分结果缺失",
                    basis=f"OpenLab状态={record['openlab_processing_state']}；未发现可用原厂 .rx 峰表",
                    before_status="原始.dx信号已解码但未作项目自研积分",
                    after_result="禁止自动定量，等待原厂 Processing Server 重处理",
                    discarded_data=record["injection_id"],
                    details="运行 hplc-openlab-export --vendor-reprocess 后再生成正式结果",
                )
            )
            manual_review.append(
                _manual_review(
                    experiment_date=experiment_date.isoformat(),
                    sample_name=sample_name,
                    injection_ids=record["injection_id"],
                    issue_type="原厂积分结果缺失",
                    reason=f"OpenLab状态={record['openlab_processing_state']}；自研积分已删除且不再回退",
                    recommended_action="使用 --vendor-reprocess 调用项目内置 Agilent Processing Server 和完整 PMX",
                )
            )
        if analysis_eligible and not record["raw_signal_quantifiable"]:
            manual_review.append(
                _manual_review(
                    experiment_date=experiment_date.isoformat(),
                    sample_name=sample_name,
                    injection_ids=record["injection_id"],
                    issue_type="原始色谱不可定量",
                    reason="；".join(quality_reasons) or "缺少可用原始信号",
                    recommended_action="检查.dx文件完整性和原始色谱；不得把数据缺失静默记为零峰",
                )
            )
            processing_log.append(
                _log_entry(
                    generated_at,
                    experiment_date=experiment_date.isoformat(),
                    sample_name=sample_name,
                    raw_files=record["raw_file"],
                    operation_type="原始信号完整性检查",
                    basis="；".join(quality_reasons),
                    before_status="信号解码完成",
                    after_result="保留审计记录但禁止自动定量",
                    discarded_data=record["injection_id"],
                )
            )
        elif analysis_eligible and vendor_available and quality != "正常":
            manual_review.append(
                _manual_review(
                    experiment_date=experiment_date.isoformat(),
                    sample_name=sample_name,
                    injection_ids=record["injection_id"],
                    issue_type="色谱质量或原厂积分待复核",
                    reason="；".join(quality_reasons),
                    recommended_action="核对原始色谱、目标峰峰形、积分边界及同组重复进样；确认前不自动采用",
                )
            )
            processing_log.append(
                _log_entry(
                    generated_at,
                    experiment_date=experiment_date.isoformat(),
                    sample_name=sample_name,
                    raw_files=record["raw_file"],
                    operation_type="色谱质量判断",
                    basis="；".join(quality_reasons),
                    before_status="原厂积分结果已读取",
                    after_result=quality,
                    used_data=record["injection_id"] if quality == "待人工复核" else "",
                    discarded_data=record["injection_id"] if quality == "异常" else "",
                )
            )
        for target in targets.values():
            if target["ambiguous"]:
                manual_review.append(
                    _manual_review(
                        experiment_date=experiment_date.isoformat(),
                        sample_name=sample_name,
                        injection_ids=record["injection_id"],
                        issue_type="目标峰匹配存在歧义",
                        reason=f"{target['display_name']}窗口内候选峰序号：{target['candidate_peak_ordinals']}",
                        recommended_action="在原色谱中核对峰形、积分边界和同批相邻时间点",
                    )
                )
                processing_log.append(
                    _log_entry(
                        generated_at,
                        experiment_date=experiment_date.isoformat(),
                        sample_name=sample_name,
                        raw_files=record["raw_file"],
                        operation_type="峰匹配歧义",
                        basis=f"{target['display_name']}候选峰序号：{target['candidate_peak_ordinals']}",
                        before_status="RT窗口内存在多个近距离候选",
                        after_result="待人工复核",
                        used_data=record["injection_id"],
                    )
                )

    group_by_injection, evidence_by_group, _, uncertain = _assign_repeat_groups(records, config)
    records_by_id = {item["injection_id"]: item for item in records}
    uncertain_edges = [
        item
        for item in uncertain
        if item["left"] not in group_by_injection and item["right"] not in group_by_injection
    ]
    uncertain_group_by_injection: dict[str, str] = {}
    uncertain_evidence_by_group: dict[str, list[str]] = {}
    uncertain_injection_ids = {
        injection_id
        for item in uncertain_edges
        for injection_id in (item["left"], item["right"])
    }
    if uncertain_injection_ids:
        uncertain_union = _UnionFind(
            uncertain_injection_ids,
            {
                injection_id: records_by_id[injection_id]["acquisition_date"]
                for injection_id in uncertain_injection_ids
            },
        )
        maximum_gap = int(config["repeat_rules"]["maximum_automatic_day_gap"])
        for item in uncertain_edges:
            uncertain_union.union_within_span(item["left"], item["right"], maximum_gap)
        uncertain_components = [
            sorted(members, key=lambda injection_id: records_by_id[injection_id]["acquisition_local"])
            for members in uncertain_union.members.values()
            if len(members) > 1
        ]
        uncertain_components.sort(
            key=lambda members: records_by_id[members[0]]["acquisition_local"]
        )
        for index, members in enumerate(uncertain_components, start=1):
            group_id = f"UG{index:03d}"
            for injection_id in members:
                uncertain_group_by_injection[injection_id] = group_id
            uncertain_evidence_by_group[group_id] = list(
                dict.fromkeys(
                    item["reason"]
                    for item in uncertain_edges
                    if item["left"] in members and item["right"] in members
                )
            )
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if (
            record["is_wash"]
            or record["is_before_screening"]
            or record["is_light_boundary_uncertain"]
        ):
            continue
        group_id = group_by_injection.get(record["injection_id"], "")
        uncertain_group_id = uncertain_group_by_injection.get(record["injection_id"], "")
        if group_id:
            container_id = group_id
        elif uncertain_group_id:
            container_id = f"UNCERTAIN:{uncertain_group_id}"
        else:
            container_id = f"SINGLE:{record['injection_id']}"
        groups[container_id].append(record)
    uncertain_ids: set[str] = set()
    for item in uncertain:
        uncertain_ids.update((item["left"], item["right"]))
        left = records_by_id[item["left"]]
        manual_review.append(
            _manual_review(
                experiment_date=left["experiment_date"].isoformat(),
                sample_name=left["sample_name"],
                injection_ids=f"{item['left']}; {item['right']}",
                issue_type="重打关系待确认",
                reason=item["reason"],
                recommended_action="核对序列设置和实验记录；确认后在 manual_overrides.repeat_group_by_injection 中指定或清除分组",
            )
        )

    for container_id, members in groups.items():
        if container_id.startswith("RG"):
            _mark_low_scale_repeat_outliers(members, config)

    final_rows: list[dict[str, Any]] = []
    rerun_details: list[dict[str, Any]] = []
    final_use_overrides = config.get("manual_overrides", {}).get("final_use_by_injection", {}) or {}
    for container_id, members in sorted(
        groups.items(), key=lambda item: min(member["acquisition_local"] for member in item[1])
    ):
        members.sort(key=lambda item: item["acquisition_local"])
        is_uncertain_group = container_id.startswith("UNCERTAIN:")
        group_id = (
            container_id.split(":", 1)[1]
            if is_uncertain_group
            else ""
            if container_id.startswith("SINGLE:")
            else container_id
        )
        evidence = (
            uncertain_evidence_by_group.get(group_id, [])
            if is_uncertain_group
            else evidence_by_group.get(group_id, [])
        )
        forced_true = [item for item in members if final_use_overrides.get(item["injection_id"]) is True]
        forced_false = [item for item in members if final_use_overrides.get(item["injection_id"]) is False]
        process_note = ""
        if forced_true or forced_false:
            used = forced_true or [item for item in members if item not in forced_false]
            discarded = [item for item in members if item not in used]
            process_method = "人工覆盖"
            process_note = "依据集中配置 manual_overrides.final_use_by_injection 重新计算"
        elif is_uncertain_group:
            used = []
            discarded = []
            process_method = "重打关系待确认"
            process_note = "候选记录合并显示为一行，但不平均、不择优且不自动定量"
        elif group_id:
            normal = [item for item in members if item["quality"] == "正常" and item["quantifiable"]]
            non_normal = [item for item in members if item not in normal]
            if normal:
                if len(normal) > 1:
                    trend_choice, trend_detail = _choose_by_trend(normal, records, config)
                    if trend_choice is not None:
                        used = [trend_choice]
                        discarded = [item for item in members if item is not trend_choice]
                        process_method = "趋势择优"
                        process_note = trend_detail
                    else:
                        used = normal
                        discarded = non_normal
                        if any("第二天" in item for item in evidence):
                            process_method = "第二天重打平均"
                        elif any("序列连续运行" in item or "结果名" in item or "序列名" in item for item in evidence):
                            process_method = "重复序列平均"
                        elif any("同一序列内" in item for item in evidence):
                            process_method = "同序列重复平均"
                        else:
                            process_method = "当天重打平均"
                        process_note = "三个目标峰面积及对应RT分别先平均，再代入各自标曲"
                else:
                    used = normal
                    discarded = non_normal
                    process_method = "舍弃异常重打" if discarded else "单次正常"
                    process_note = "优先采用唯一色谱质量正常且原厂积分可用的进样"
            else:
                used = []
                discarded = []
                process_method = "待人工复核"
                process_note = "重打组中没有可自动采用的正常、可定量进样；保留全部原始记录"
                manual_review.append(
                    _manual_review(
                        experiment_date=members[0]["experiment_date"].isoformat(),
                        sample_name=members[0]["sample_name"],
                        injection_ids="; ".join(item["injection_id"] for item in members),
                        issue_type="重打组全部异常或不可定量",
                        reason=_unique_text(reason for item in members for reason in item["quality_reasons"]),
                        recommended_action="检查原始色谱、原厂积分边界及重打关系后人工指定最终采用数据",
                    )
                )
        else:
            member = members[0]
            used = [member] if member["quality"] == "正常" and member["quantifiable"] else []
            discarded = []
            if member["injection_id"] in uncertain_ids:
                process_method = "重打关系待确认"
                process_note = "当前不与其他候选合并；本行保留独立原始结果"
            elif used:
                process_method = "正常未检出" if all(
                    member["targets"][key]["match_status"] == "正常未检出" for key in TARGET_ORDER
                ) else "单次正常"
                process_note = "单次正常进样"
            else:
                process_method = "待人工复核"
                process_note = "唯一进样异常或缺少可用原始信号/原厂积分，不自动定量"

        final_row = _combine_final_result(
            members,
            used,
            discarded,
            group_id=group_id,
            process_method=process_method,
            process_note=process_note,
            config=config,
        )
        final_rows.append(final_row)
        if group_id:
            processing_log.append(
                _log_entry(
                    generated_at,
                    experiment_date=final_row["experiment_date"],
                    sample_name=final_row["sample_name"],
                    group_id=group_id,
                    raw_files=final_row["raw_file"],
                    operation_type=process_method,
                    basis="；".join(evidence) or "人工覆盖",
                    before_status=f"{len(members)} 个重打/重复候选",
                    after_result=process_method,
                    used_data=_data_group_text(used),
                    discarded_data=_data_group_text(discarded),
                    details=process_note,
                )
            )
            for member in members:
                rerun_details.append(
                    {
                        "rerun_group_id": group_id,
                        "experiment_date": final_row["experiment_date"],
                        "sample_name": member["sample_name"],
                        "normalized_sample_name": member["normalized_sample_name"],
                        "injection_id": member["injection_id"],
                        "sequence_name": member["sequence_name"],
                        "result_name": member["result_name"],
                        "acquisition_time": member["acquisition_local"],
                        "evidence": "；".join(evidence),
                        "data_quality": member["quality"],
                        "participates_in_average": member in used and len(used) > 1,
                        "final_use": member in used,
                        "discard_reason": "；".join(member["quality_reasons"]) if member in discarded else "",
                        "raw_file": member["raw_file"],
                        "source_relative": member["source_relative"],
                    }
                )
                if member in discarded:
                    excluded_data.append(
                        {
                            "experiment_date": final_row["experiment_date"],
                            "sample_name": member["sample_name"],
                            "injection_id": member["injection_id"],
                            "reason": "异常重打未采用" if process_method != "趋势择优" else "趋势择优未采用",
                            "details": "；".join(member["quality_reasons"]) or process_note,
                            "acquisition_time": member["acquisition_local"],
                            "sequence_name": member["sequence_name"],
                            "result_name": member["result_name"],
                            "batch_folder": member["batch_folder"],
                            "raw_file": member["raw_file"],
                            "source_relative": member["source_relative"],
                        }
                    )

    c0_candidate_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in final_rows:
        if not row["is_pre_reaction"] or not row["used_injection_ids"]:
            continue
        c0_candidate_rows[row["experiment_batch_key"]].append(row)
    c0_areas: dict[str, list[tuple[float, str]]] = defaultdict(list)
    ambiguous_c0_keys: set[str] = set()
    for batch_key, candidate_rows in c0_candidate_rows.items():
        if len(candidate_rows) > 1:
            ambiguous_c0_keys.add(batch_key)
            candidate_ids = list(
                dict.fromkeys(
                    injection_id
                    for candidate_row in candidate_rows
                    for injection_id in candidate_row["used_injection_ids"]
                )
            )
            manual_review.append(
                _manual_review(
                    experiment_date=candidate_rows[0]["experiment_date"],
                    sample_name=_unique_text(item["sample_name"] for item in candidate_rows),
                    injection_ids="; ".join(candidate_ids),
                    issue_type="C₀来源关系待确认",
                    reason="同一批次条件内存在多个尚未确认为同一重打组的0 h/反应前最终样品",
                    recommended_action="确认这些反应前样品是否为重复进样；确认前不平均且不向反应样品分配C₀",
                )
            )
            continue
        for injection_id in candidate_rows[0]["used_injection_ids"]:
            source_record = records_by_id[injection_id]
            area = source_record["targets"]["thioanisole"]["area"]
            if area is not None:
                c0_areas[batch_key].append((float(area), injection_id))
    for row in final_rows:
        c0_candidates = c0_areas.get(row["experiment_batch_key"], [])
        if c0_candidates:
            mean_c0_area = float(np.mean([area for area, _ in c0_candidates]))
            c0_calibration = _calibrate_area(
                mean_c0_area,
                config["targets"]["thioanisole"],
                float(config["reaction"]["total_dilution_factor"]),
            )
            row["c0_mM"] = c0_calibration["reaction_concentration_mM"]
            row["c0_source_injection_ids"] = list(
                dict.fromkeys(injection_id for _, injection_id in c0_candidates)
            )
            processing_log.append(
                _log_entry(
                    generated_at,
                    experiment_date=row["experiment_date"],
                    sample_name=row["sample_name"],
                    group_id=row["rerun_group_id"],
                    raw_files=row["raw_file"],
                    operation_type="同批次C₀匹配",
                    basis=(
                        "实验日期、显式批次、光源及解析后的实验条件键完全一致；"
                        "反应前/0 h 正常进样先平均茴香硫醚峰面积再代入标曲"
                    ),
                    before_status=f"C₀候选峰面积数={len(c0_candidates)}",
                    after_result=f"C₀={row['c0_mM']:.8g} mM",
                    used_data="; ".join(row["c0_source_injection_ids"]),
                )
            )
        sulfoxide = row["targets"]["sulfoxide"]["reaction_concentration_mM"]
        sulfone = row["targets"]["sulfone"]["reaction_concentration_mM"]
        substrate = row["targets"]["thioanisole"]["reaction_concentration_mM"]
        if sulfoxide is not None and sulfone is not None and sulfoxide + sulfone > 0:
            row["sulfoxide_selectivity_fraction"] = sulfoxide / (sulfoxide + sulfone)
        if row["c0_mM"] is not None and row["c0_mM"] > 0 and all(
            value is not None for value in (sulfoxide, sulfone, substrate)
        ):
            c0 = float(row["c0_mM"])
            row["conversion_fraction"] = (c0 - float(substrate)) / c0
            if row["sulfoxide_selectivity_fraction"] is not None:
                row["sulfoxide_yield_fraction"] = (
                    row["conversion_fraction"]
                    * float(row["sulfoxide_selectivity_fraction"])
                )
            elif float(sulfoxide) == 0.0:
                row["sulfoxide_yield_fraction"] = 0.0
            row["material_recovery_fraction"] = (
                float(substrate) + float(sulfoxide) + float(sulfone)
            ) / c0
            low = float(config["quality_thresholds"]["recovery_review_low_fraction"])
            high = float(config["quality_thresholds"]["recovery_review_high_fraction"])
            anomaly_messages: list[str] = []
            if row["conversion_fraction"] < 0:
                anomaly_messages.append("负转化率")
            if row["sulfoxide_yield_fraction"] > 1:
                anomaly_messages.append("茴香亚砜产率超过100%")
            if row["material_recovery_fraction"] < low or row["material_recovery_fraction"] > high:
                anomaly_messages.append("物料回收率超出集中配置的复核范围")
            if anomaly_messages:
                manual_review.append(
                    _manual_review(
                        experiment_date=row["experiment_date"],
                        sample_name=row["sample_name"],
                        injection_ids="; ".join(row["member_injection_ids"]),
                        issue_type="定量结果异常",
                        reason="；".join(anomaly_messages),
                        recommended_action="核对C₀批次、重打分组、峰匹配、稀释和原厂积分；保留当前未截断计算值",
                    )
                )
                processing_log.append(
                    _log_entry(
                        generated_at,
                        experiment_date=row["experiment_date"],
                        sample_name=row["sample_name"],
                        group_id=row["rerun_group_id"],
                        raw_files=row["raw_file"],
                        operation_type="定量结果异常复核",
                        basis="；".join(anomaly_messages),
                        before_status="按未截断公式完成计算",
                        after_result="保留真实计算值并进入待人工复核",
                        used_data=row["used_data_group"],
                        details=(
                            f"conversion={row['conversion_fraction']}; "
                            f"yield={row['sulfoxide_yield_fraction']}; "
                            f"recovery={row['material_recovery_fraction']}"
                        ),
                    )
                )
        elif row["used_injection_ids"]:
            if "缺少同批次C₀" not in row["process_method"]:
                row["process_method"] += "；缺少同批次C₀"
            row["process_note"] += "；未从其他日期/批次/光源借用C₀"
            manual_review.append(
                _manual_review(
                    experiment_date=row["experiment_date"],
                    sample_name=row["sample_name"],
                    injection_ids="; ".join(row["member_injection_ids"]),
                    issue_type="缺少同批次C₀",
                    reason=(
                        "同批次C₀候选关系尚未确认"
                        if row["experiment_batch_key"] in ambiguous_c0_keys
                        else "本实验批次没有可用的0 h或SM反应前茴香硫醚定量结果"
                    ),
                    recommended_action="补充或确认同批次反应前样品；不得借用其他批次C₀",
                )
            )
            processing_log.append(
                _log_entry(
                    generated_at,
                    experiment_date=row["experiment_date"],
                    sample_name=row["sample_name"],
                    group_id=row["rerun_group_id"],
                    raw_files=row["raw_file"],
                    operation_type="缺少同批次C₀",
                    basis=(
                        "同日期、同显式批次、同光源及同实验条件键内"
                        "没有唯一可用的0 h/反应前来源"
                    ),
                    before_status="目标峰定量完成",
                    after_result="转化率、产率和回收率留空；不跨批次借用C₀",
                    used_data=row["used_data_group"],
                )
            )
        for key in TARGET_ORDER:
            if row["targets"][key]["below_intercept"]:
                processing_log.append(
                    _log_entry(
                        generated_at,
                        experiment_date=row["experiment_date"],
                        sample_name=row["sample_name"],
                        group_id=row["rerun_group_id"],
                        raw_files=row["raw_file"],
                        operation_type="峰面积低于标曲截距",
                        basis=f"{row['targets'][key]['display_name']} 平均峰面积低于标曲截距",
                        before_status=f"原始上机液浓度={row['targets'][key]['raw_injection_concentration_mM']}",
                        after_result="最终定量浓度显示为0",
                        used_data=row["used_data_group"],
                        details="内部保留未经截断的负浓度候选值",
                    )
                )

    final_rows.sort(
        key=lambda item: (
            item["experiment_date"],
            item["experiment_batch"],
            float(item["reaction_time_h"]) if item["reaction_time_h"] is not None else math.inf,
            item["sample_name"],
            item["actual_acquisition_time"],
        )
    )
    for index, row in enumerate(final_rows, start=1):
        row["sequence_number"] = index
    peak_details: list[dict[str, Any]] = []
    for detail_index, row in enumerate(final_rows, start=1):
        detail: dict[str, Any] = {
            "sequence_number": detail_index,
            "experiment_date": row["experiment_date"],
            "sample_name": row["sample_name"],
            "data_quality": row["data_quality"],
            "participates_in_final": bool(row["used_injection_ids"]),
            "process_method": row["process_method"],
            "actual_acquisition_time": row["actual_acquisition_time"],
            "acquisition_method": row["acquisition_method"],
            "sequence_name": row["sequence_name"],
            "result_name": row["result_name"],
            "raw_file": row["raw_file"],
        }
        for key in TARGET_ORDER:
            target = row["targets"][key]
            unique_peak_ordinals = list(
                dict.fromkeys(target["selected_peak_ordinals"])
            )
            peak_ordinal: int | str | None
            if len(unique_peak_ordinals) == 1:
                peak_ordinal = unique_peak_ordinals[0]
            elif unique_peak_ordinals:
                peak_ordinal = "; ".join(str(value) for value in unique_peak_ordinals)
            else:
                peak_ordinal = None
            detail[f"{key}_peak_ordinal"] = peak_ordinal
            detail[f"{key}_retention_time_min"] = target["retention_time_min"]
            detail[f"{key}_area"] = target["area"]
        peak_details.append(detail)

    summary = {
        "input_injection_count": len(records),
        "vendor_primary_injection_count": sum(
            item["primary_peak_source"] == "vendor_rx" for item in records
        ),
        "vendor_result_unavailable_injection_count": sum(
            item["primary_peak_source"] == "vendor_unavailable" for item in records
        ),
        "openlab_no_method_injection_count": sum(
            item["openlab_processing_state"].casefold() == "nomethodprovided" for item in records
        ),
        "wash_excluded_count": sum(item["is_wash"] for item in records),
        "repeat_group_count": len(evidence_by_group),
        "final_sample_row_count": len(final_rows),
        "final_quantified_row_count": sum(
            bool(item["used_injection_ids"])
            and all(item["targets"][key]["area"] is not None for key in TARGET_ORDER)
            for item in final_rows
        ),
        "missing_c0_row_count": sum(
            bool(item["used_injection_ids"]) and item["c0_mM"] is None for item in final_rows
        ),
        "manual_review_item_count": len(manual_review),
        "processing_log_count": len(processing_log),
    }
    field_mapping = {
        "色谱曲线数据": "raw_sheets[].columns[].time / signal",
        "正式峰面积/出峰时间": "仅来自OpenLab .rx原厂积分；缺失时必须运行 --vendor-reprocess",
        "厂商峰表": "peaks[]（OpenLab存量 .rx 或 Processing Server 完整PMX重处理结果）",
        "样品名称": "injections[].sample_name",
        "序列名称": "injections[].sequence_name（结果集 .acaml SampleContexts/Setup）",
        "OpenLab结果名称": "injections[].result_name（结果集 .acaml SampleContexts/MeasData）",
        "数据文件名": "injections[].raw_file",
        "原始文件路径": "injections[].source_relative（相对于原始数据根）",
        "所属日期文件夹": "injections[].batch_folder",
        "采集时间": "injections[].acquisition_local",
        "采集方法": "injections[].acquisition_method；Excel不重复列处理方法",
        "进样顺序": "injections[].sequence_order",
        "其他批次/重复证据": "result_set_id/result_set_folder、归一化名称、实际采集日期、序列样品列表、原始文件名",
    }
    return {
        "schema_version": "1.0",
        "analysis_version": config["analysis_version"],
        "generated_at": generated_at,
        "manual_check_required": True,
        "field_mapping": field_mapping,
        "summary": summary,
        "sample_results": final_rows,
        "peak_details": peak_details,
        "processing_log": processing_log,
        "excluded_data": excluded_data,
        "rerun_group_details": rerun_details,
        "manual_review": manual_review,
        "parameters": _parameter_rows(config, generated_at),
        "injection_analysis": [
            {
                **record,
                "experiment_date": record["experiment_date"].isoformat(),
                "acquisition_date": record["acquisition_date"].isoformat(),
            }
            for record in records
        ],
        "main_result_columns": list(MAIN_RESULT_COLUMNS),
        "peak_detail_columns": list(PEAK_DETAIL_COLUMNS),
        "manual_override_contract": {
            "repeat_group_by_injection": "在集中配置中把 injection_id 映射到人工组名；空值表示移出自动组",
            "final_use_by_injection": "在集中配置中把 injection_id 映射为 true/false；重新运行后按人工选择重算",
        },
    }


def attach_hplc_analysis(
    dataset: dict[str, Any],
    project_root: Path,
    *,
    copy_dataset: bool = True,
) -> dict[str, Any]:
    """Attach analysis, copying by default; owned pipeline datasets may opt out."""
    config = load_hplc_analysis_config(project_root)
    updated = deepcopy(dataset) if copy_dataset else dataset
    updated["analysis"] = analyze_hplc_openlab_dataset(updated, config)
    updated["analysis_config"] = {
        key: value for key, value in config.items() if key != "manual_overrides"
    }
    scientific_boundary = updated.setdefault("scientific_boundary", {})
    scientific_boundary.update(
        {
            "manual_check_required": True,
            "peak_source": (
                "Agilent OpenLab .rx vendor results only; missing or failed results require "
                "project-bundled Processing Server complete-PMX reprocessing; no native fallback"
            ),
            "target_identity_basis": "user-supplied nominal RT windows and tolerances",
            "quantification_basis": "user-supplied calibration equations and 100x dilution factor",
            "plots_created": False,
            "forbidden_outputs": [
                "unvalidated chemical identities outside the three user-mapped RT windows",
                "automatic mechanistic interpretation",
                "unreviewed final conversion, selectivity, yield, or recovery claims",
            ],
        }
    )
    return updated
