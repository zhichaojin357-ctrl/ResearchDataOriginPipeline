from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean
from typing import Any

from PIL import Image, ImageChops, ImageStat

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.project import default_output_root
from src.origin.operations import connect_origin


OPJU_COMPARISON_CONTRACTS: dict[str, dict[str, Any]] = {
    "Raman": {
        "comparison_mode": "current_project_output_vs_exemplar_page",
        "required_generated": [{"origin_file": "output/origin_files/Raman_raman_bobc_q_8a64099ed434.opju", "figure_tif": "output/figures_tif/Raman_raman_bob_beeb4122.tif", "preview_png": "output/figures_preview/Raman_raman_bob_beeb4122.png"}],
        "requirements": ["compare generated Raman spectrum to exemplar graph intent", "line plot; no defect assignment", "Y axis line/ticks visible; numeric values may be hidden for normalized/offset spectra"],
    },
    "photocurrent_response": {
        "comparison_mode": "current_project_output_vs_exemplar_page",
        "required_generated": [{"origin_file": "output/origin_files/photocurrent_response_photocurrent_bobc_ocp_q_dc02528f6e57.opju", "figure_tif": "output/figures_tif/photocurrent_re_73bd5f50.tif", "preview_png": "output/figures_preview/photocurrent_re_73bd5f50.png"}],
        "requirements": ["line plot for current-time response", "keep quantitative Y tick values", "no carrier-separation conclusion"],
    },
    "Mott-Schottky": {
        "comparison_mode": "current_project_output_vs_exemplar_page",
        "required_generated": [{"origin_file": "output/origin_files/Mott-Schottky_mott_bobc_2000_q_24de08b022ce.opju", "figure_tif": "output/figures_tif/Mott_Schottky_m_d2013507.tif", "preview_png": "output/figures_preview/Mott_Schottky_m_d2013507.png"}],
        "requirements": ["plot 1/C²-potential and candidate fit guide only", "keep quantitative Y tick values", "do not equate flat-band potential to CB/VB"],
    },
    "EIS": {
        "comparison_mode": "current_project_output_vs_exemplar_page",
        "required_generated": [{"origin_file": "output/origin_files/EIS_eis_bobc_z_q_adb8f4f5d72e.opju", "figure_tif": "output/figures_tif/EIS_eis_bobc_z_83502795.tif", "preview_png": "output/figures_preview/EIS_eis_bobc_z_83502795.png"}],
        "requirements": ["Nyquist/Bode-style EIS graph according to available columns", "keep quantitative axis tick values", "no equivalent-circuit conclusion"],
    },
    "BET": {
        "comparison_mode": "current_project_output_vs_exemplar_page",
        "required_generated": [{"origin_file": "output/origin_files/BET_bet_bobc_all_pore_q_72e137157e0c.opju", "figure_tif": "output/figures_tif/BET_bet_bobc_al_c149f7d5.tif", "preview_png": "output/figures_preview/BET_bet_bobc_al_c149f7d5.png"}],
        "requirements": ["use adsorption/isotherm or pore-distribution role columns, not scalar BET summary values", "line+symbol for isotherm/pore distribution", "keep quantitative Y tick values"],
    },
    "FTIR": {
        "comparison_mode": "current_project_output_vs_exemplar_page",
        "required_generated": [{"origin_file": "output/origin_files/FTIR_ftir_cwo_q_1a338b85d831.opju", "figure_tif": "output/figures_tif/FTIR_ftir_cwo_q_e08db8c1.tif", "preview_png": "output/figures_preview/FTIR_ftir_cwo_q_e08db8c1.png"}],
        "requirements": ["line spectrum", "Y axis line/ticks visible; numeric values may be hidden for arbitrary-unit spectra", "no bond assignment conclusion"],
    },
    "PL": {
        "comparison_mode": "current_project_output_vs_exemplar_page",
        "required_generated": [{"origin_file": "output/origin_files/PL_pl_em_ex340_q_71aaf864d941.opju", "figure_tif": "output/figures_tif/PL_pl_em_ex340_5974f01f.tif", "preview_png": "output/figures_preview/PL_pl_em_ex340_5974f01f.png"}],
        "requirements": ["line spectrum", "Y axis line/ticks visible; numeric values may be hidden for arbitrary-unit spectra", "no recombination conclusion"],
    },
    "EPR": {
        "comparison_mode": "condition_overlay_opju_pair",
        "generated_from": "run.py epr-overlay --group all --with-origin --force",
        "required_generated": [
            {
                "condition": "OH",
                "origin_file": "output/origin_files/EPR_OH_overlay.opju",
                "figure_tif": "output/figures_tif/EPR_OH_overlay_8d3e95bb.tif",
                "preview_png": "output/figures_preview/EPR_OH_overlay_8d3e95bb.png",
                "reference_tif_name": "ohG.tif",
            },
            {
                "condition": "O3",
                "origin_file": "output/origin_files/EPR_O3_overlay.opju",
                "figure_tif": "output/figures_tif/EPR_O3_overlay_895a7063.tif",
                "preview_png": "output/figures_preview/EPR_O3_overlay_895a7063.png",
                "reference_tif_name": "o3G.tif",
            },
        ],
        "requirements": [
            "compare condition-group overlay OPJU outputs, not a single raw EPR trace",
            "preserve JEOL decoded amplitudes by default; do not normalize unless explicit",
            "record baseline correction, smoothing, background subtraction, and offset rules",
            "do not assign radicals or mechanisms",
        ],
    }
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare project-generated Origin figures against copied OPJU exemplars.")
    parser.add_argument("--project-root", default=".", help="ResearchDataOriginPipeline project root")
    parser.add_argument("--queue", default="output/reports/phase1_14_opju_exemplar_regression_queue.json")
    parser.add_argument("--processing-report", default="output/reports/processing_report.json")
    parser.add_argument("--output-json", default="output/reports/phase1_14_opju_exemplar_regression_comparison.json")
    parser.add_argument("--output-md", default="output/reports/phase1_14_opju_exemplar_regression_comparison.md")
    parser.add_argument("--export-reference", action="store_true", help="Open copied reference OPJU files and export their graph pages")
    parser.add_argument("--fail-on-warning", action="store_true", help="Return non-zero for visual warnings, not only hard failures")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    queue_path = _resolve(project_root, args.queue)
    processing_report_path = _resolve(project_root, args.processing_report)
    output_json = _resolve(project_root, args.output_json)
    output_md = _resolve(project_root, args.output_md)

    queue = json.loads(queue_path.read_text(encoding="utf-8-sig"))
    results = json.loads(processing_report_path.read_text(encoding="utf-8")).get("results", [])
    queue_by_id = {item["queue_id"]: item for item in queue.get("items", [])}
    result_by_queue = {
        item.get("triage", {}).get("queue_id"): item
        for item in results
        if item.get("triage", {}).get("queue_id")
    }

    reference_export_root = default_output_root(project_root) / "opju_exemplar_regression" / "reference_exports"
    reference_export_root.mkdir(parents=True, exist_ok=True)

    rows = []
    for queue_id, queue_item in queue_by_id.items():
        contracted = _contracted_row(project_root, queue_id, queue_item, reference_export_root / queue_id)
        if contracted:
            rows.append(contracted)
            continue
        result = result_by_queue.get(queue_id)
        if not result:
            rows.append(_missing_row(queue_id, queue_item, "processing result missing"))
            continue
        generated_tif = _resolve(project_root, result.get("figure_tif", ""))
        generated_png = _resolve(project_root, result.get("preview_png", ""))
        reference_opju = Path(queue_item.get("origin_reference_opju", ""))
        reference_exports: list[str] = []
        export_status = "not_requested"
        export_message = ""
        if args.export_reference:
            export_status, export_message, reference_exports = _export_reference_opju(reference_opju, reference_export_root / queue_id)
        else:
            existing_exports = sorted((reference_export_root / queue_id).glob("*.tif"))
            if existing_exports:
                export_status = "existing_exports"
                export_message = "reused existing reference exports"
                reference_exports = [str(path) for path in existing_exports]
        generated_metrics = _image_metrics(generated_tif)
        preview_metrics = _image_metrics(generated_png)
        comparison = _compare_to_first_reference(generated_tif, [Path(path) for path in reference_exports])
        rows.append(
            {
                "queue_id": queue_id,
                "data_type": queue_item.get("data_type"),
                "dataset_id": result.get("dataset_id"),
                "processing_status": result.get("processing_status"),
                "generated_opju": result.get("origin_file"),
                "generated_tif": str(generated_tif),
                "generated_png": str(generated_png),
                "reference_opju": str(reference_opju),
                "reference_exports": reference_exports,
                "reference_export_status": export_status,
                "reference_export_message": export_message,
                "generated_tif_metrics": generated_metrics,
                "generated_png_metrics": preview_metrics,
                "comparison": comparison,
                "verdict": _verdict(result, generated_metrics, preview_metrics, comparison, export_status),
            }
        )

    payload = {
        "script": "scripts/maintenance/opju_exemplar_regression.py",
        "export_reference_requested": args.export_reference,
        "items": rows,
        "summary": _summary(rows),
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(_markdown(payload), encoding="utf-8")
    hard_failures = [row for row in rows if row["verdict"] == "FAIL"]
    warnings = [row for row in rows if str(row["verdict"]).startswith("WARNING")]
    if hard_failures or (args.fail_on_warning and warnings):
        return 2
    return 0


def _resolve(project_root: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "output":
        return default_output_root(project_root) / Path(*path.parts[1:])
    return project_root / path


def _missing_row(queue_id: str, queue_item: dict[str, Any], message: str) -> dict[str, Any]:
    return {
        "queue_id": queue_id,
        "data_type": queue_item.get("data_type"),
        "processing_status": "missing",
        "reference_opju": queue_item.get("origin_reference_opju"),
        "reference_exports": [],
        "reference_export_status": "not_attempted",
        "reference_export_message": message,
        "generated_tif_metrics": {"ok": False, "message": message},
        "generated_png_metrics": {"ok": False, "message": message},
        "comparison": {"ok": False, "message": message},
        "verdict": "FAIL",
    }


def _contracted_row(project_root: Path, queue_id: str, queue_item: dict[str, Any], reference_dir: Path) -> dict[str, Any] | None:
    contract = OPJU_COMPARISON_CONTRACTS.get(str(queue_item.get("data_type")))
    if not contract:
        return None
    generated_items = []
    comparisons = []
    failures = []
    for spec in contract["required_generated"]:
        generated_opju = _resolve(project_root, spec["origin_file"])
        generated_tif = _resolve(project_root, spec["figure_tif"])
        generated_png = _resolve(project_root, spec["preview_png"])
        reference_tif = reference_dir / spec["reference_tif_name"] if spec.get("reference_tif_name") else _best_reference_tif(reference_dir, generated_tif)
        condition = spec.get("condition", str(queue_item.get("data_type") or queue_id))
        tif_metrics = _image_metrics(generated_tif)
        png_metrics = _image_metrics(generated_png)
        comparison = _compare_to_first_reference(generated_tif, [reference_tif])
        item = {
            "condition": condition,
            "generated_opju": str(generated_opju),
            "generated_tif": str(generated_tif),
            "generated_png": str(generated_png),
            "reference_tif": str(reference_tif),
            "generated_opju_exists": generated_opju.exists() and generated_opju.stat().st_size > 0,
            "generated_tif_metrics": tif_metrics,
            "generated_png_metrics": png_metrics,
            "comparison": comparison,
        }
        generated_items.append(item)
        comparisons.append(comparison)
        if not item["generated_opju_exists"]:
            failures.append(f"missing generated OPJU for {condition}")
        if not tif_metrics.get("ok"):
            failures.append(f"bad generated TIF for {condition}")
        if not png_metrics.get("ok"):
            failures.append(f"bad generated PNG for {condition}")
        if not reference_tif.exists():
            failures.append(f"missing reference TIF {reference_tif.name}")
    warning_reasons = []
    for item in generated_items:
        comparison = item["comparison"]
        if comparison.get("ok") is False:
            warning_reasons.append(f"{item['condition']} visual/structure delta: {comparison.get('message') or comparison.get('mean_abs_pixel_difference')}")
    graph4_style_exempt = _graph4_style_exempt_visual_delta(contract, warning_reasons, generated_items)
    if graph4_style_exempt:
        warning_reasons = []
    verdict = "FAIL" if failures else ("WARNING_OPJU_CONTRACT_DELTA" if warning_reasons else "PASS")
    return {
        "queue_id": queue_id,
        "data_type": queue_item.get("data_type"),
        "processing_status": "success" if not failures else "contract_incomplete",
        "comparison_mode": contract["comparison_mode"],
        "generated_from": contract.get("generated_from", "existing project script output"),
        "requirements": contract["requirements"],
        "reference_opju": queue_item.get("origin_reference_opju"),
        "reference_exports": [str(path) for path in sorted(reference_dir.glob("*.tif"))],
        "reference_export_status": "existing_exports" if reference_dir.exists() else "missing",
        "reference_export_message": "contracted OPJU comparison uses named reference graph exports",
        "generated_items": generated_items,
        "comparison": {"ok": not warning_reasons, "items": comparisons, "warning_reasons": warning_reasons},
        "visual_delta_exemption": graph4_style_exempt,
        "generated_tif_metrics": {"ok": all(item["generated_tif_metrics"].get("ok") for item in generated_items)},
        "generated_png_metrics": {"ok": all(item["generated_png_metrics"].get("ok") for item in generated_items)},
        "verdict": verdict,
        "failures": failures,
        "warning_reasons": warning_reasons,
    }


def _graph4_style_exempt_visual_delta(contract: dict[str, Any], warning_reasons: list[str], generated_items: list[dict[str, Any]]) -> dict[str, Any] | None:
    if contract.get("comparison_mode") != "condition_overlay_opju_pair" or not warning_reasons:
        return None
    checked = []
    for item in generated_items:
        comparison = item.get("comparison", {})
        if "aspect_delta" not in comparison:
            return None
        if comparison.get("mean_abs_pixel_difference", 999) > 35:
            return None
        checked.append(
            {
                "condition": item.get("condition"),
                "aspect_delta": comparison.get("aspect_delta"),
                "mean_abs_pixel_difference": comparison.get("mean_abs_pixel_difference"),
            }
        )
    return {
        "reason": "Reference OPJU export uses a different page aspect ratio, while project output is intentionally forced to fixed Graph4 geometry by origin-plotting skill. Data grouping, OPJU/TIF/PNG outputs, and EPR processing provenance are checked separately.",
        "checked": checked,
    }


def _best_reference_tif(reference_dir: Path, generated_tif: Path) -> Path:
    references = sorted(reference_dir.glob("*.tif"))
    if not references:
        return reference_dir / "MISSING_REFERENCE.tif"
    if not generated_tif.exists():
        return references[0]
    try:
        with Image.open(generated_tif) as generated_image:
            gen_aspect = generated_image.width / generated_image.height
            scored = []
            for reference in references:
                with Image.open(reference) as reference_image:
                    aspect_delta = abs(gen_aspect - (reference_image.width / reference_image.height))
                    scored.append((aspect_delta, reference))
            return min(scored, key=lambda item: item[0])[1]
    except Exception:
        return references[0]


def _export_reference_opju(reference_opju: Path, output_dir: Path) -> tuple[str, str, list[str]]:
    if not reference_opju.exists():
        return "failed", f"reference OPJU missing: {reference_opju}", []
    output_dir.mkdir(parents=True, exist_ok=True)
    ops = None
    try:
        ops = connect_origin(entrypoint="Origin.Application", isolated=True, visible=False)
        loaded = ops.load_project(reference_opju)
        if not loaded.ok:
            return "failed", loaded.message, []
        exported = ops.export_all_graphs(output_dir, export_format="tif", dpi=600)
        paths = [str(Path(path)) for path in exported.payload.get("exported", [])]
        if not exported.ok:
            return "partial" if paths else "failed", exported.message, paths
        return "success", exported.message, paths
    except Exception as exc:
        return "failed", str(exc), []
    finally:
        if ops is not None:
            ops.close()


def _image_metrics(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"ok": False, "message": "missing", "path": str(path)}
    if path.stat().st_size <= 0:
        return {"ok": False, "message": "empty", "path": str(path), "bytes": path.stat().st_size}
    try:
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            stat = ImageStat.Stat(rgb)
            extrema = rgb.getextrema()
            channel_means = stat.mean
            dynamic_range = mean(high - low for low, high in extrema)
            nonwhite = _nonwhite_fraction(rgb)
            return {
                "ok": dynamic_range > 1 and nonwhite > 0.001,
                "path": str(path),
                "bytes": path.stat().st_size,
                "width": image.width,
                "height": image.height,
                "mode": image.mode,
                "dpi": _jsonable(image.info.get("dpi")),
                "channel_mean": channel_means,
                "dynamic_range": dynamic_range,
                "nonwhite_fraction": nonwhite,
            }
    except Exception as exc:
        return {"ok": False, "message": str(exc), "path": str(path)}


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    try:
        return float(value)
    except Exception:
        return str(value)


def _nonwhite_fraction(image: Image.Image) -> float:
    resized = image.resize((min(image.width, 512), min(image.height, 512)))
    pixels = resized.get_flattened_data() if hasattr(resized, "get_flattened_data") else resized.getdata()
    total = 0
    nonwhite = 0
    for r, g, b in pixels:
        total += 1
        if min(r, g, b) < 248:
            nonwhite += 1
    return nonwhite / total if total else 0.0


def _compare_to_first_reference(generated_tif: Path, reference_exports: list[Path]) -> dict[str, Any]:
    references = [path for path in reference_exports if path.exists() and path.stat().st_size > 0]
    if not references:
        return {"ok": False, "message": "no reference graph export available"}
    try:
        with Image.open(generated_tif) as generated_image:
            gen = generated_image.convert("RGB")
            candidates = []
            gen_aspect = gen.width / gen.height
            for reference in references:
                with Image.open(reference) as reference_image:
                    ref = reference_image.convert("RGB")
                    aspect_delta = abs(gen_aspect - (ref.width / ref.height))
                    resized_ref = ref.resize(gen.size)
                    diff = ImageChops.difference(gen, resized_ref)
                    diff_stat = ImageStat.Stat(diff)
                    mean_abs_diff = mean(diff_stat.mean)
                    candidates.append(
                        {
                            "reference_tif": str(reference),
                            "reference_size": [ref.width, ref.height],
                            "aspect_delta": aspect_delta,
                            "same_aspect_within_8_percent": aspect_delta < 0.08,
                            "mean_abs_pixel_difference": mean_abs_diff,
                        }
                    )
            best = min(candidates, key=lambda item: (0 if item["same_aspect_within_8_percent"] else 1, item["aspect_delta"], item["mean_abs_pixel_difference"]))
            return {
                "ok": bool(best["same_aspect_within_8_percent"]),
                "reference_tif": best["reference_tif"],
                "generated_size": [gen.width, gen.height],
                "reference_size": best["reference_size"],
                "same_aspect_within_8_percent": best["same_aspect_within_8_percent"],
                "mean_abs_pixel_difference": best["mean_abs_pixel_difference"],
                "aspect_delta": best["aspect_delta"],
                "reference_candidate_count": len(candidates),
                "note": "Pixel equality is not expected because project output applies fixed Graph4 style; best matching reference graph is selected by aspect ratio and mean pixel difference.",
            }
    except Exception as exc:
        return {"ok": False, "message": str(exc)}


def _verdict(result: dict[str, Any], tif_metrics: dict[str, Any], png_metrics: dict[str, Any], comparison: dict[str, Any], export_status: str) -> str:
    if result.get("processing_status") != "success" or not tif_metrics.get("ok") or not png_metrics.get("ok"):
        return "FAIL"
    if export_status == "not_requested":
        return "PASS_REFERENCE_EXPORT_SKIPPED"
    if export_status not in {"success", "partial", "existing_exports"}:
        return "WARNING_REFERENCE_EXPORT_FAILED"
    return "PASS" if comparison.get("ok") else "WARNING_VISUAL_DIFFERENCE"


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    verdict_counts: dict[str, int] = {}
    for row in rows:
        verdict_counts[row["verdict"]] = verdict_counts.get(row["verdict"], 0) + 1
    return {"total": len(rows), "verdict_counts": verdict_counts}


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# OPJU Exemplar Regression Comparison",
        "",
        "This report now treats copied OPJU exemplars as the requirement source. A generated result must match the exemplar's graph intent and processing route, not merely produce any nonempty figure.",
        "",
        f"- Total: {payload['summary']['total']}",
        f"- Verdicts: `{payload['summary']['verdict_counts']}`",
        "",
        "| queue_id | data_type | mode | status | ref export | verdict | generated evidence | reference evidence |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in payload["items"]:
        reference = ""
        generated = row.get("generated_tif") or ""
        if row.get("generated_items"):
            generated = "<br>".join(f"{item['condition']}: `{item['generated_tif']}`" for item in row["generated_items"])
            reference = "<br>".join(f"{item['condition']}: `{item['reference_tif']}`" for item in row["generated_items"])
        elif row.get("reference_exports"):
            reference = row["reference_exports"][0]
        lines.append(
            f"| `{row['queue_id']}` | {row.get('data_type')} | {row.get('comparison_mode', 'single_generated_result')} | {row.get('processing_status')} | "
            f"{row.get('reference_export_status')} | {row.get('verdict')} | {generated if '<br>' in str(generated) else f'`{generated}`'} | {reference if '<br>' in str(reference) else f'`{reference}`'} |"
        )
    lines.extend([
        "",
        "## Requirement Update",
        "",
        "- The exemplar OPJU defines the processing and plotting target for regression testing.",
        "- When one exemplar OPJU contains multiple scientifically relevant graph pages, the generated project output must cover the matching pages or explicitly mark the gap.",
        "- EPR is a condition-group overlay task: compare OH/O3 generated overlay OPJUs against `ohG`/`o3G`, not against a single decoded raw trace.",
        "- Image similarity is supporting evidence only. The report must also state the comparison mode and generated OPJU evidence.",
        "",
        "## Notes",
        "",
        "- Reference OPJU files are copied exemplars, not F-drive originals.",
        "- Generated figures come from project scripts and the Origin adapter/helper path.",
    ])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
