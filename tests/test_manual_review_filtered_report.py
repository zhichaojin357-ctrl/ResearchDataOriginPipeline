from __future__ import annotations

import csv
import json
from pathlib import Path

from openpyxl import load_workbook

from scripts.reports.regenerate_manual_review_filtered import build_rows, main as regenerate_main, write_csv, write_xlsx


def _item(relative_path: str, decision: str, *, data_type: str = "Mott-Schottky", suffix: str = ".csv") -> dict:
    return {
        "relative_path": relative_path,
        "decision": decision,
        "data_type_candidate": data_type,
        "extension": suffix,
        "parser_probe_status": "success" if decision != "MANUAL_REVIEW" else "skipped",
        "confidence_score": 0.85,
        "validity_score": 1.0,
        "decision_reasons": ["parser_probe_not_success"] if decision == "MANUAL_REVIEW" else ["high_confidence_valid_numeric_data"],
        "source_hash": f"hash-{relative_path}",
    }


def test_filtered_manual_review_excludes_same_data_represented_by_auto_process(tmp_path: Path):
    reports = tmp_path / "output" / "reports"
    reports.mkdir(parents=True)
    manifest = {
        "items": [
            _item("Mott/sample1.bin", "MANUAL_REVIEW", suffix=".bin"),
            _item("Mott/sample1.csv", "AUTO_PROCESS"),
            _item("BET/sample2.DB3", "MANUAL_REVIEW", data_type="BET", suffix=".db3"),
        ]
    }
    (reports / "data_triage_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    kept, excluded, summary = build_rows(tmp_path)

    assert summary == {"manual_total": 2, "kept": 1, "excluded": 1}
    assert kept[0]["相对路径"] == "BET/sample2.DB3"
    assert kept[0]["数据类型"] == "BET"
    assert excluded[0]["相对路径"] == "Mott/sample1.bin"
    assert excluded[0]["代表文件"] == "Mott/sample1.csv"


def test_filtered_manual_review_excludes_phase16_represented_source(tmp_path: Path):
    reports = tmp_path / "output" / "reports"
    reports.mkdir(parents=True)
    package = tmp_path / "output" / "phase1_6_origin_results_20260531_041538"
    package.mkdir(parents=True)
    (reports / "data_triage_manifest.json").write_text(
        json.dumps({"items": [_item("EIS/sampleA.bin", "MANUAL_REVIEW", data_type="EIS", suffix=".bin")]}),
        encoding="utf-8",
    )
    with (package / "index.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source_file", "processed_csv"])
        writer.writeheader()
        writer.writerow({"source_file": "EIS/sampleA.csv", "processed_csv": ""})

    kept, excluded, summary = build_rows(tmp_path)

    assert summary == {"manual_total": 1, "kept": 0, "excluded": 1}
    assert excluded[0]["排除原因"] == "Phase 1.6 已有成功成果代表"


def test_filtered_manual_review_outputs_keep_chinese_headers(tmp_path: Path):
    rows = [
        {
            "相对路径": "BET/sample.DB3",
            "数据类型": "BET",
            "扩展名": ".db3",
            "解析状态": "skipped",
            "置信度": 0.35,
            "有效性": 0.0,
            "主要原因": "解析未成功",
            "建议处理": "确认吸附/脱附列和样品对应后再处理",
            "源文件哈希": "abc",
            "用户决定": "",
            "备注": "",
        }
    ]
    csv_path = tmp_path / "review.csv"
    xlsx_path = tmp_path / "review.xlsx"

    write_csv(csv_path, rows, list(rows[0]))
    write_xlsx(xlsx_path, rows, "最新人工复核清单", list(rows[0]))

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        loaded = list(csv.DictReader(handle))
    workbook = load_workbook(xlsx_path, read_only=True)
    sheet = workbook["Review"]

    assert loaded[0]["数据类型"] == "BET"
    assert sheet.cell(1, 1).value == "相对路径"
    assert sheet.cell(2, 2).value == "BET"


def test_regenerate_manual_review_filtered_main_smoke(tmp_path: Path, monkeypatch):
    reports = tmp_path / "output" / "reports"
    reports.mkdir(parents=True)
    (reports / "data_triage_manifest.json").write_text(
        json.dumps({"items": [_item("BET/sample2.DB3", "MANUAL_REVIEW", data_type="BET", suffix=".db3")]}),
        encoding="utf-8",
    )
    fake_home = tmp_path / "home_without_desktop"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    monkeypatch.chdir(tmp_path)

    regenerate_main()

    assert (reports / "phase1_8_manual_review_required_filtered.csv").is_file()
    assert (reports / "phase1_8_manual_review_required_filtered.xlsx").is_file()
    assert (tmp_path / "docs" / "agent_reports" / "phase1_8_manual_review_required_filtered_report.md").is_file()
    assert not (fake_home / "Desktop" / "phase1_8_manual_review_required_filtered.xlsx").exists()
