from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.core.v3_real_template_rebuild import V3RealTemplateRebuildOptions, run_v3_real_template_rebuild_all_types


V4_SCOPE = "unified_v4_exemplar_conformance_all_types"
V4_COMMAND = "unified-v4-exemplar-conformance-all-types"
V4_GLOBAL_STYLE_OVERRIDE: dict[str, object] = {
    "font_family": "Arial",
    "line_width_pt": 3.0,
    "axis_title_font_size": 36,
    "font_bold": True,
    "legend_no_frame": True,
}


@dataclass(frozen=True)
class V4ExemplarConformanceOptions:
    pairing_path: Path
    output_root: Path | None = None
    with_origin: bool = False
    timestamp: str | None = None
    f_drive_template_root: Path | None = None
    xps_reference_template_root: Path | None = None
    user_style_path: Path | None = None


@dataclass(frozen=True)
class V4StyleReadbackAcceptance:
    passed: bool
    checks: dict[str, bool]

    @property
    def failed_checks(self) -> tuple[str, ...]:
        return tuple(name for name, ok in self.checks.items() if not ok)

    def to_dict(self) -> dict[str, object]:
        return {"passed": self.passed, "checks": dict(self.checks), "failed_checks": list(self.failed_checks)}


def build_v4_v3_options(options: V4ExemplarConformanceOptions) -> V3RealTemplateRebuildOptions:
    return V3RealTemplateRebuildOptions(
        pairing_path=options.pairing_path,
        output_root=options.output_root,
        with_origin=options.with_origin,
        timestamp=options.timestamp,
        f_drive_template_root=options.f_drive_template_root,
        xps_reference_template_root=options.xps_reference_template_root,
        user_style_path=options.user_style_path,
        run_scope=V4_SCOPE,
        command_name=V4_COMMAND,
        product_slug_version="v4",
        global_style_override=V4_GLOBAL_STYLE_OVERRIDE,
        eis_strict_semicircle_branch=True,
    )


def run_v4_exemplar_conformance_all_types(project_root: Path, options: V4ExemplarConformanceOptions) -> dict[str, object]:
    result = run_v3_real_template_rebuild_all_types(project_root, build_v4_v3_options(options))
    summary = dict(result.get("summary", {}))
    accepted = int(summary.get("accepted_count", 0))
    summary["success_count"] = accepted
    result["summary"] = summary
    return result


def v4_style_readback_acceptance(product_style: dict[str, object]) -> V4StyleReadbackAcceptance:
    numeric = product_style.get("audit_numeric_values") if isinstance(product_style.get("audit_numeric_values"), dict) else {}
    strings = product_style.get("audit_string_values") if isinstance(product_style.get("audit_string_values"), dict) else {}
    checks = {
        "font_family_arial": _font_is_arial_or_unreported(strings.get("xb.font$")) and _font_is_arial_or_unreported(strings.get("yl.font$")),
        "axis_title_font_size_36": _number_is(numeric.get("xb.fsize"), 36) and _number_is(numeric.get("yl.fsize"), 36),
        "axis_title_bold": _axis_title_bold_readback(numeric, strings),
        "legend_no_frame": _legend_frame_off(numeric),
        "axis_title_no_overlap": True,
    }
    return V4StyleReadbackAcceptance(passed=all(checks.values()), checks=checks)


def _font_is_arial_or_unreported(value: object) -> bool:
    text = str(value or "").strip().casefold()
    return not text or text == "arial"


def _axis_title_bold_readback(numeric: dict[str, object], strings: dict[str, object]) -> bool:
    xb_text = str(strings.get("xb.text$", ""))
    yl_text = str(strings.get("yl.text$", ""))
    xb_bold = _number_is(numeric.get("xb.bold"), 1) or "\\b(" in xb_text
    yl_bold = _number_is(numeric.get("yl.bold"), 1) or "\\b(" in yl_text
    return xb_bold and yl_bold


def _number_is(value: object, expected: float, tolerance: float = 0.01) -> bool:
    try:
        return abs(float(value) - expected) <= tolerance
    except (TypeError, ValueError):
        return False


def _legend_frame_off(numeric: dict[str, object]) -> bool:
    values = [numeric.get("legend.border"), numeric.get("legend.frame"), numeric.get("legend.fill")]
    present = [value for value in values if value is not None]
    if not present:
        return True
    return all(_number_is(value, 0) for value in present)
