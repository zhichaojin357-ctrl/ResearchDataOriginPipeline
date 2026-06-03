from __future__ import annotations

import csv
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from src.core.runtime_paths import resolve_phase1_6_index


def norm_key(path_text: str) -> str:
    text = str(path_text).replace("\\", "/").casefold()
    parts = [part for part in text.split("/") if part]
    drop = {
        "raw_data",
        "processed_tables",
        "origin_project",
        "reports_notes",
        "metadata",
        "previews",
        "figures_preview",
        "figures_tif",
        "origin_files",
    }
    parts = [part for part in parts if part not in drop]
    if parts:
        parts[-1] = re.sub(r"\.[^.]+$", "", parts[-1])
    return re.sub(r"\s+", " ", "/".join(parts)).strip()


def short_reason(item: dict) -> str:
    reasons = item.get("decision_reasons") or []
    if "parser_probe_not_success" in reasons:
        status = item.get("parser_probe_status") or "未知"
        ext = item.get("extension") or "无扩展名"
        return f"解析未成功：{status}，格式 {ext}"
    if any("folder_header_type_conflict" in reason for reason in reasons):
        return "文件夹类型与表头类型不一致，需要确认数据类型"
    if "below_auto_process_threshold_or_ambiguous" in reasons:
        return "置信度或有效性不足，需要人工确认"
    if reasons:
        return "；".join(str(reason) for reason in reasons[:2])
    return "仍需人工确认"


def action_for(item: dict) -> str:
    dtype = item.get("data_type_candidate") or "unknown"
    ext = item.get("extension") or ""
    if dtype == "XPS":
        return "单独审查XPS，不自动归属价态"
    if dtype == "EPR":
        return "确认EPR曲线/样品，不自动归属自由基"
    if dtype == "Mott-Schottky":
        return "确认频率/拟合区间，不等同CB/VB"
    if dtype == "XRD":
        return "需要导出表格或人工确认物相，暂不自动处理"
    if dtype == "BET":
        return "确认吸附/脱附列和样品对应后再处理"
    if ext in {".raw", ".dql", ".vgd", ".vgp", ".smp", ".db3", ".bin"}:
        return "优先寻找同名导出表格；没有则人工转换"
    return "确认后可进入下一阶段 reviewed queue"


def phase16_keys(root: Path) -> set[str]:
    index_path = resolve_phase1_6_index(root)
    keys: set[str] = set()
    if not index_path.exists():
        return keys
    with index_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            for column in ("source_file", "selected_source_data", "processed_csv"):
                if row.get(column):
                    keys.add(norm_key(row[column]))
    return keys


def build_rows(root: Path) -> tuple[list[dict], list[dict], dict]:
    manifest_path = root / "output" / "reports" / "data_triage_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = manifest["items"]

    completed_keys = phase16_keys(root)
    representative_keys: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        if item.get("decision") in {"AUTO_PROCESS", "DUPLICATE_SUPPRESSED"}:
            representative_keys[norm_key(item.get("relative_path", ""))].append(item)

    kept: list[dict] = []
    excluded: list[dict] = []
    for item in items:
        if item.get("decision") != "MANUAL_REVIEW":
            continue
        key = norm_key(item.get("relative_path", ""))
        reason = ""
        representative = ""
        if key in completed_keys:
            reason = "Phase 1.6 已有成功成果代表"
        elif key in representative_keys:
            reason = "同一数据已有可自动处理/重复压制格式代表"
            representative = representative_keys[key][0].get("relative_path", "")

        if reason:
            excluded.append(
                {
                    "相对路径": item.get("relative_path", ""),
                    "数据类型": item.get("data_type_candidate", ""),
                    "扩展名": item.get("extension", ""),
                    "排除原因": reason,
                    "代表文件": representative,
                    "same_data_key": key,
                }
            )
            continue

        kept.append(
            {
                "相对路径": item.get("relative_path", ""),
                "数据类型": item.get("data_type_candidate", ""),
                "扩展名": item.get("extension", "") or "无扩展名",
                "解析状态": item.get("parser_probe_status", ""),
                "置信度": item.get("confidence_score", ""),
                "有效性": item.get("validity_score", ""),
                "主要原因": short_reason(item),
                "建议处理": action_for(item),
                "源文件哈希": item.get("source_hash", ""),
                "用户决定": "",
                "备注": "",
            }
        )

    kept.sort(key=lambda row: (row["数据类型"], row["相对路径"]))
    excluded.sort(key=lambda row: (row["数据类型"], row["相对路径"]))
    summary = {
        "manual_total": sum(1 for item in items if item.get("decision") == "MANUAL_REVIEW"),
        "kept": len(kept),
        "excluded": len(excluded),
    }
    return kept, excluded, summary


def write_csv(path: Path, rows: list[dict], fallback_headers: list[str]) -> None:
    headers = list(rows[0]) if rows else fallback_headers
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def write_xlsx(path: Path, rows: list[dict], title: str, fallback_headers: list[str]) -> None:
    workbook = Workbook()
    summary_sheet = workbook.active
    summary_sheet.title = "Summary"
    data_sheet = workbook.create_sheet("Review")

    counts = Counter(row.get("数据类型", "") for row in rows)
    summary_sheet.append([title])
    summary_sheet.append(["生成时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    summary_sheet.append(["条目数量", len(rows)])
    summary_sheet.append([])
    summary_sheet.append(["数据类型", "数量"])
    for dtype, count in counts.most_common():
        summary_sheet.append([dtype, count])

    headers = list(rows[0]) if rows else fallback_headers
    data_sheet.append(headers)
    for row in rows:
        data_sheet.append([row.get(header, "") for header in headers])

    for sheet in workbook.worksheets:
        sheet.freeze_panes = "A2"
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="1F4E78")
            cell.alignment = Alignment(horizontal="center", vertical="center")
        for row in sheet.iter_rows():
            for cell in row:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
                cell.border = Border(bottom=Side(style="thin", color="DDDDDD"))
        for index, column in enumerate(sheet.columns, 1):
            max_len = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column)
            sheet.column_dimensions[get_column_letter(index)].width = min(max(max_len + 2, 10), 70)

    workbook.save(path)


def write_report(path: Path, kept: list[dict], excluded: list[dict], summary: dict) -> None:
    counts = Counter(row["数据类型"] for row in kept)
    excluded_counts = Counter(row["数据类型"] for row in excluded)
    lines = [
        "# Phase 1.8 最新人工复核清单",
        "",
        f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 来源: `output/reports/data_triage_manifest.json` 最新 triage 结果",
        f"- 当前 MANUAL_REVIEW 总数: {summary['manual_total']}",
        f"- 已排除同数据已代表项: {summary['excluded']}",
        f"- 仍需人工复核: {summary['kept']}",
        "",
        "## 输出文件",
        "",
        "- CSV: `output/reports/phase1_8_manual_review_required_filtered.csv`",
        "- Excel: `output/reports/phase1_8_manual_review_required_filtered.xlsx`",
        "- 排除审计 CSV: `output/reports/phase1_8_manual_review_excluded_processed_sibling_formats.csv`",
        "- 排除审计 Excel: `output/reports/phase1_8_manual_review_excluded_processed_sibling_formats.xlsx`",
        "- 桌面副本: `C:\\Users\\lenovo\\Desktop\\phase1_8_manual_review_required_filtered.xlsx`",
        "",
        "## 保留复核统计",
        "",
        "| 数据类型 | 数量 |",
        "|---|---:|",
    ]
    for dtype, count in counts.most_common():
        lines.append(f"| {dtype} | {count} |")
    lines += ["", "## 排除统计", "", "| 数据类型 | 数量 |", "|---|---:|"]
    for dtype, count in excluded_counts.most_common():
        lines.append(f"| {dtype} | {count} |")
    lines += [
        "",
        "## 说明",
        "",
        "- 本清单只保留最新识别算法后仍无法安全自动分类或处理的文件。",
        "- 如果同一份数据已有可自动处理格式或 Phase 1.6 成功成果代表，则不再放入人工复核主表，只写入排除审计表。",
        "- 本步骤没有处理真实数据，没有启动 Origin，没有修改原始数据。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    root = Path.cwd()
    reports = root / "output" / "reports"
    docs_reports = root / "docs" / "agent_reports"
    docs_reports.mkdir(parents=True, exist_ok=True)

    kept, excluded, summary = build_rows(root)
    kept_headers = ["相对路径", "数据类型", "扩展名", "解析状态", "置信度", "有效性", "主要原因", "建议处理", "源文件哈希", "用户决定", "备注"]
    excluded_headers = ["相对路径", "数据类型", "扩展名", "排除原因", "代表文件", "same_data_key"]

    outputs = {
        "csv": reports / "phase1_8_manual_review_required_filtered.csv",
        "xlsx": reports / "phase1_8_manual_review_required_filtered.xlsx",
        "excluded_csv": reports / "phase1_8_manual_review_excluded_processed_sibling_formats.csv",
        "excluded_xlsx": reports / "phase1_8_manual_review_excluded_processed_sibling_formats.xlsx",
        "report": reports / "phase1_8_manual_review_required_filtered_report.md",
    }
    write_csv(outputs["csv"], kept, kept_headers)
    write_xlsx(outputs["xlsx"], kept, "最新人工复核清单", kept_headers)
    write_csv(outputs["excluded_csv"], excluded, excluded_headers)
    write_xlsx(outputs["excluded_xlsx"], excluded, "已排除同数据格式清单", excluded_headers)
    write_report(outputs["report"], kept, excluded, summary)

    for path in outputs.values():
        shutil.copy2(path, docs_reports / path.name)

    desktop = Path.home() / "Desktop"
    if desktop.exists():
        shutil.copy2(outputs["xlsx"], desktop / outputs["xlsx"].name)
        shutil.copy2(outputs["csv"], desktop / outputs["csv"].name)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(Counter(row["数据类型"] for row in kept), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
