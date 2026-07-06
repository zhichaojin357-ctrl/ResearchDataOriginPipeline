from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from openpyxl import load_workbook

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.epr_jeol import (  # noqa: E402
    DEFAULT_EXPORT_POINTS,
    decode_jeol_cacqu_series,
    looks_like_jeol_cwesr_file,
    max_abs_delta,
    rms_delta,
    write_data_xlsx,
)
from src.core.runtime_paths import resolve_workspace_root  # noqa: E402


DEFAULT_EPR_ROOT = resolve_workspace_root(PROJECT_ROOT) / "EPR"
DEFAULT_RAW_ROOTS = [
    DEFAULT_EPR_ROOT / "20260410-3",
    DEFAULT_EPR_ROOT / "20260421",
    DEFAULT_EPR_ROOT / "20260430-1",
]
DEFAULT_REFERENCE_DIR = DEFAULT_EPR_ROOT / "导出后的数据"


@dataclass(frozen=True)
class ExportedFile:
    source_root: Path
    source_path: Path
    output_path: Path
    x_values: list[float]
    y_values: list[float]

    @property
    def unique_id(self) -> str:
        return f"{self.source_root.name}/{self.source_path.relative_to(self.source_root).as_posix()}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Decode JEOL cAcqu EPR files and verify them against known Excel exports."
    )
    parser.add_argument("raw_roots", nargs="*", type=Path, help="Raw JEOL EPR directories. Defaults to the LL EPR batch.")
    parser.add_argument("--reference-dir", type=Path, default=DEFAULT_REFERENCE_DIR)
    parser.add_argument("--report-json", type=Path, default=PROJECT_ROOT / "output" / "reports" / "jeol_epr_decode_reference_check.json")
    parser.add_argument("--report-md", type=Path, default=PROJECT_ROOT / "output" / "reports" / "jeol_epr_decode_reference_check.md")
    parser.add_argument("--keep-decoded", action="store_true", help="Keep decoded test workbooks instead of deleting them.")
    parser.add_argument("--decoded-out", type=Path, default=None, help="Decoded workbook output directory when --keep-decoded is used.")
    return parser.parse_args(argv)


def collect_raw_files(roots: Iterable[Path]) -> list[tuple[Path, Path]]:
    raw_files: list[tuple[Path, Path]] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if looks_like_jeol_cwesr_file(path):
                raw_files.append((root, path))
    return raw_files


def decode_to_xlsx(raw_files: list[tuple[Path, Path]], output_root: Path) -> list[ExportedFile]:
    exported: list[ExportedFile] = []
    for source_root, source_path in raw_files:
        x_values, y_values = decode_jeol_cacqu_series(source_path)
        relative = source_path.relative_to(source_root)
        output_path = output_root / source_root.name / relative.parent / f"{relative.name}.xlsx"
        write_data_xlsx(output_path, x_values, y_values)
        exported.append(
            ExportedFile(
                source_root=source_root,
                source_path=source_path,
                output_path=output_path,
                x_values=x_values,
                y_values=y_values,
            )
        )
    return exported


def read_reference_xlsx(path: Path) -> tuple[list[float], list[float], int]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    skipped = 0
    try:
        worksheet = workbook.active
        x_values: list[float] = []
        y_values: list[float] = []
        for row in worksheet.iter_rows(values_only=True):
            if not row or row[0] is None or len(row) < 2 or row[1] is None:
                continue
            try:
                x_values.append(float(row[0]))
                y_values.append(float(row[1]))
            except (TypeError, ValueError):
                skipped += 1
        return x_values, y_values, skipped
    finally:
        workbook.close()


def best_matches(reference_dir: Path, exported: list[ExportedFile]) -> tuple[list[dict[str, object]], int]:
    matches: list[dict[str, object]] = []
    skipped_reference_rows = 0
    for reference in sorted(reference_dir.glob("*.xlsx")):
        ref_x, ref_y, skipped = read_reference_xlsx(reference)
        skipped_reference_rows += skipped
        candidate_rows: list[tuple[float, float, int, float, ExportedFile]] = []
        for export in exported:
            if len(ref_x) != len(export.x_values):
                continue
            same_stem_priority = 0 if reference.stem == export.source_path.stem else 1
            candidate_rows.append(
                (
                    max_abs_delta(ref_y, export.y_values),
                    max_abs_delta(ref_x, export.x_values),
                    same_stem_priority,
                    rms_delta(ref_y, export.y_values),
                    export,
                )
            )
        if not candidate_rows:
            matches.append(
                {
                    "reference": reference.name,
                    "reference_rows": len(ref_x),
                    "best_export": None,
                    "best_source": None,
                    "best_max_x_delta": None,
                    "best_max_y_delta": None,
                    "best_rms_y_delta": None,
                    "exact_content_match": False,
                }
            )
            continue
        candidate_rows.sort(key=lambda item: (item[0], item[1], item[2], item[3], item[4].unique_id))
        max_y, max_x, _same_stem_priority, rms_y, export = candidate_rows[0]
        matches.append(
            {
                "reference": reference.name,
                "reference_rows": len(ref_x),
                "best_export": export.output_path.name,
                "best_source": export.unique_id,
                "best_max_x_delta": max_x,
                "best_max_y_delta": max_y,
                "best_rms_y_delta": rms_y,
                "exact_content_match": len(ref_x) == DEFAULT_EXPORT_POINTS and max_x == 0 and max_y == 0,
                "same_stem": reference.stem == export.source_path.stem,
            }
        )
    return matches, skipped_reference_rows


def write_reports(report: dict[str, object], report_json: Path, report_md: Path) -> None:
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_md.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# JEOL EPR 解码验证",
        "",
        f"- 原始目录数：{report['raw_root_count']}",
        f"- JEOL cAcqu 候选文件：{report['raw_file_count']}",
        f"- 成功解码 Excel：{report['decoded_file_count']}",
        f"- 正确 Excel 参考：{report['reference_file_count']}",
        f"- 参考精确匹配：{report['exact_reference_match_count']}/{report['reference_file_count']}",
        f"- 每个解码文件行数（verified JEOL cAcqu 默认导出）：{DEFAULT_EXPORT_POINTS}",
        f"- 临时导出已清理：{report['decoded_test_outputs_cleaned']}",
        f"- 验证结论：{report['status']}",
        "",
        "## 原始目录",
    ]
    lines.extend(f"- {item}" for item in report["raw_roots"])
    lines.extend(["", "## 参考匹配"])
    for item in report["reference_matches"]:
        flag = "PASS" if item["exact_content_match"] else "FAIL"
        lines.append(
            f"- {flag} {item['reference']} -> {item['best_source']} "
            f"(max_x={item['best_max_x_delta']}, max_y={item['best_max_y_delta']})"
        )
    lines.extend(["", "## 未有正确 Excel 覆盖的解码文件"])
    uncovered = report["decoded_without_reference_exact_match"]
    if uncovered:
        lines.extend(f"- {item}" for item in uncovered)
    else:
        lines.append("- 无")
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    raw_roots = args.raw_roots or DEFAULT_RAW_ROOTS
    raw_roots = [path.resolve() for path in raw_roots]
    reference_dir = args.reference_dir.resolve()
    report_json = args.report_json.resolve()
    report_md = args.report_md.resolve()

    raw_files = collect_raw_files(raw_roots)
    temp_dir_obj: tempfile.TemporaryDirectory[str] | None = None
    decoded_root: Path
    cleaned = False
    if args.keep_decoded:
        decoded_root = (args.decoded_out or PROJECT_ROOT / "output" / "epr_jeol_decoded").resolve()
        decoded_root.mkdir(parents=True, exist_ok=True)
    else:
        temp_dir_obj = tempfile.TemporaryDirectory(prefix="jeol_epr_decode_check_")
        decoded_root = Path(temp_dir_obj.name) / "decoded"

    try:
        exported = decode_to_xlsx(raw_files, decoded_root)
        reference_files = sorted(reference_dir.glob("*.xlsx")) if reference_dir.exists() else []
        matches, skipped_reference_rows = best_matches(reference_dir, exported) if reference_files else ([], 0)
        exact_sources = {item["best_source"] for item in matches if item["exact_content_match"]}
        uncovered = [item.unique_id for item in exported if item.unique_id not in exact_sources]
        rows_ok = all(len(item.x_values) == DEFAULT_EXPORT_POINTS and len(item.y_values) == DEFAULT_EXPORT_POINTS for item in exported)
        references_ok = bool(reference_files) and all(item["exact_content_match"] for item in matches)
        status = "PASS" if raw_files and rows_ok and references_ok else "FAIL"
        report: dict[str, object] = {
            "status": status,
            "raw_roots": [str(path) for path in raw_roots],
            "reference_dir": str(reference_dir),
            "raw_root_count": len(raw_roots),
            "raw_file_count": len(raw_files),
            "decoded_file_count": len(exported),
            "reference_file_count": len(reference_files),
            "exact_reference_match_count": sum(1 for item in matches if item["exact_content_match"]),
            "skipped_reference_rows": skipped_reference_rows,
            "decoded_test_output_root": str(decoded_root),
            "decoded_test_outputs_cleaned": False,
            "reference_matches": matches,
            "decoded_without_reference_exact_match": uncovered,
            "decoded_files": [item.unique_id for item in exported],
        }
    finally:
        if temp_dir_obj is not None:
            cleanup_path = Path(temp_dir_obj.name)
            temp_dir_obj.cleanup()
            cleaned = not cleanup_path.exists()

    report["decoded_test_outputs_cleaned"] = cleaned
    if not args.keep_decoded and not cleaned:
        report["status"] = "FAIL"
    write_reports(report, report_json, report_md)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(run())
