from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.core.v3_real_template_rebuild import V3RealTemplateRebuildOptions, run_v3_real_template_rebuild_all_types


V4_STRICT_SCOPE = "unified_v4_strict_template_conformance_all_types"
V4_STRICT_COMMAND = "unified-v4-strict-template-conformance-all-types"
V4_STRICT_GLOBAL_STYLE_OVERRIDE: dict[str, object] = {
    "font_family": "Arial",
    "line_width_pt": 3.0,
    "axis_title_font_size": 36,
    "font_bold": True,
    "legend_no_frame": True,
}


@dataclass(frozen=True)
class V4StrictTemplateConformanceOptions:
    pairing_path: Path
    output_root: Path | None = None
    with_origin: bool = False
    timestamp: str | None = None
    f_drive_template_root: Path | None = None
    xps_reference_template_root: Path | None = None
    user_style_path: Path | None = None


def build_v4_strict_v3_options(options: V4StrictTemplateConformanceOptions) -> V3RealTemplateRebuildOptions:
    return V3RealTemplateRebuildOptions(
        pairing_path=options.pairing_path,
        output_root=options.output_root,
        with_origin=options.with_origin,
        timestamp=options.timestamp,
        f_drive_template_root=options.f_drive_template_root,
        xps_reference_template_root=options.xps_reference_template_root,
        user_style_path=options.user_style_path,
        run_scope=V4_STRICT_SCOPE,
        command_name=V4_STRICT_COMMAND,
        product_slug_version="v4_strict",
        global_style_override=V4_STRICT_GLOBAL_STYLE_OVERRIDE,
        eis_strict_semicircle_branch=True,
        xps_reference_templates_for_all_xps=True,
        xps_templates_from_reference_only=True,
        xps_smooth_gradient_fill=True,
        cleanup_empty_run_layout_dirs=True,
    )


def run_v4_strict_template_conformance_all_types(
    project_root: Path,
    options: V4StrictTemplateConformanceOptions,
) -> dict[str, object]:
    result = run_v3_real_template_rebuild_all_types(project_root, build_v4_strict_v3_options(options))
    summary = dict(result.get("summary", {}))
    accepted = int(summary.get("accepted_count", 0))
    summary["success_count"] = accepted
    result["summary"] = summary
    return result
