"""Explicit CHI text-export branch: preserve acquisitions; Cs only, no EIS fits.

The generic capacitance / already-inverse-square table processor is unchanged.
BIN is deliberately opaque. Files with .csv.bin / .txt.bin remain binary.
"""
from __future__ import annotations

import csv
import filecmp
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
import io
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

from src.core.file_utils import ensure_safe_output_file_target
from src.core.project import ensure_output_path_separate_from_inputs, load_json_compatible_yaml, registry_path
from src.core.runtime_paths import resolve_output_root

DIRECTORIES = ["01_EIS阻抗原始数据", "02_MT莫特肖特基原始数据", "03_MT计算后数据",
               "04_MT Origin绘图工程", "05_MT高清图像", "06_汇总与核查报告", "07_自动化处理脚本"]
PLOT_FREQUENCIES = (2000, 3000, 4000, 5000)
FORMULA = "Cs_F = -1/(2*pi*frequency_Hz*Zimag_ohm); one_over_Cs_squared_F-2 = 1/(Cs_F*Cs_F)"


def historical_cs_evidence(path: Path) -> dict:
    """Read formulas directly from OOXML; do not execute or modify the workbook."""
    namespace = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    evidence = []
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if not re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name):
                continue
            sheet = ET.fromstring(archive.read(name))
            for cell in sheet.findall(".//s:c", namespace):
                formula = cell.find("s:f", namespace)
                if formula is not None and formula.text and ("-1/(2*" in formula.text or re.search(r"1/\(H\d+\*H\d+\)", formula.text)):
                    evidence.append({"sheet_xml": name, "cell": cell.attrib["r"], "formula": formula.text})
    if not any("-1/(2*" in item["formula"] for item in evidence):
        raise ValueError("Historical workbook does not contain the asserted Cs formula")
    return {"source": str(path), "model": "Cs", "formulas": evidence,
            "note": "Original OOXML formulas retained verbatim; impedance exports use ohm, potential uses V."}


def parse_chi_name(path: Path) -> dict:
    stem = path.stem
    if path.suffix.casefold() == ".bin" and Path(stem).suffix.casefold() in {".txt", ".csv"}:
        stem = Path(stem).stem
    match = re.fullmatch(r"(.+?)\s+(eis|mt)\s+(\d+(?:\.\d+)?)(s|hz)(?:-(\d+))?", stem, re.I)
    if not match:
        return {"kind": "unknown", "acquisition": stem, "ambiguity": "unrecognized filename"}
    material, kind, condition, unit, suffix_rep = match.groups()
    prefix = re.match(r"^(\d+)(?:-|\s*)([A-Za-z].*|\d+(?:\.\d+)?%.*)$", material)
    repeat, notation = 1, "unprefixed"
    if prefix:
        repeat, material = int(prefix[1]), prefix[2]
        notation = "prefix"
    ambiguity = ""
    if suffix_rep:
        if prefix and int(suffix_rep) != repeat:
            ambiguity = "prefix and suffix repeat numbers conflict"
        repeat, notation = int(suffix_rep), "suffix"
    kind = kind.upper()
    if (kind == "EIS" and unit.lower() != "s") or (kind == "MT" and unit.lower() != "hz"):
        ambiguity = "condition unit conflicts with test type"
    # Case-only canonicalization; wytbob is never merged with bob.
    material = {"bvo": "BVO", "bob": "BOB"}.get(material.casefold(), material)
    return {"kind": kind, "material": material, "repeat": repeat, "repeat_notation": notation,
            "condition": float(condition), "unit": unit.lower(), "acquisition": stem, "ambiguity": ambiguity}


def read_chi_impedance(path: Path) -> dict:
    if path.suffix.casefold() not in {".txt", ".csv"}:
        raise ValueError("BIN is not decoded by this branch")
    raw = path.read_bytes()
    if b"\x00" in raw:
        raise ValueError("Binary content in a text export")
    text = raw.decode("utf-8-sig")
    lines = text.splitlines()
    model = next((line.split(":", 1)[1].strip() for line in lines if line.startswith("Instrument Model:")), "")
    if model != "CHI660E":
        raise ValueError(f"Unverified CHI instrument model: {model!r}")
    header_index = next((i for i, line in enumerate(lines) if line.startswith(("Potential/", "Freq/"))), None)
    if header_index is None:
        raise ValueError("No CHI potential/impedance or frequency/impedance header")
    headers = [v.strip() for v in next(csv.reader([lines[header_index]]))]
    expected = ["Z'/ohm", 'Z"/ohm', "Z/ohm", "Phase/deg"]
    if headers[1:] != expected or headers[0] not in {"Potential/V", "Potential/mV", "Freq/Hz"}:
        raise ValueError(f"Unsupported units or columns: {headers}")
    parameters = {}
    for line in lines[:header_index]:
        if " = " in line:
            key, value = line.split(" = ", 1)
            try:
                parameters[key] = float(value)
            except ValueError:
                parameters[key] = value
    rows, source_lines = [], []
    for line_number, line in enumerate(lines[header_index + 1:], header_index + 2):
        if not line.strip():
            continue
        fields = next(csv.reader([line]))
        if len(fields) != len(headers):
            raise ValueError(f"Incomplete row on source line {line_number}")
        row = [float(v) for v in fields]
        if not all(math.isfinite(v) for v in row):
            raise ValueError(f"Non-finite source row on line {line_number}")
        rows.append(row)
        source_lines.append(line_number)
    if not rows:
        raise ValueError("Empty CHI table")
    return {"headers": headers, "rows": rows, "source_lines": source_lines, "parameters": parameters,
            "instrument": model, "timestamp": lines[0], "source": path.name}


def calculate_chi_mott(table: dict, frequency_hz: float) -> dict:
    if table["headers"][0] not in {"Potential/V", "Potential/mV"}:
        raise ValueError("Mott-Schottky requires an explicit potential axis")
    actual = table["parameters"].get("Frequency (Hz)")
    if not actual or actual <= 0 or not math.isclose(actual, frequency_hz, rel_tol=1e-9):
        raise ValueError("Filename frequency disagrees with instrument frequency")
    potential_factor = .001 if table["headers"][0] == "Potential/mV" else 1.0
    points, checks = [], []
    for number, (row, source_line) in enumerate(zip(table["rows"], table["source_lines"]), 1):
        potential, real, imaginary, magnitude, phase = row
        status = "valid" if imaginary < 0 else ("zero_Zimag" if imaginary == 0 else "noncapacitive_Zimag")
        cs = -1 / (2 * math.pi * actual * imaginary) if status == "valid" else None
        inverse = 1 / (cs * cs) if cs is not None else None
        points.append({"source_row": source_line, "potential_V": potential * potential_factor,
                       "Zreal_ohm": real, "Zimag_ohm": imaginary, "Zabs_ohm": magnitude,
                       "phase_deg": phase, "frequency_Hz": actual, "Cs_F": cs,
                       "one_over_Cs_squared_F-2": inverse, "status": status, "source_file": table["source"]})
        # Algebraically independent check, not a second call to reciprocal square.
        if number in {1, (len(table["rows"]) + 1) // 2, len(table["rows"])} and cs is not None:
            independent = (math.tau * actual * imaginary) ** 2
            checks.append({"source_file": table["source"], "source_row": source_line,
                           "frequency_Hz": actual, "Zimag_ohm": imaginary, "Cs_F": cs,
                           "one_over_Cs_squared_F-2": inverse, "independent_F-2": independent,
                           "relative_error": abs(inverse - independent) / max(abs(inverse), 1e-300)})
    xs = [p["potential_V"] for p in points]
    diffs = [b - a for a, b in zip(xs, xs[1:])]
    warnings = []
    if any(p["status"] != "valid" for p in points):
        warnings.append("Noncapacitive or zero Zimag retained with blank calculated values")
    if not (all(d > 0 for d in diffs) or all(d < 0 for d in diffs)):
        warnings.append("Repeated potentials or scan reversal: plot withheld, no branches joined")
    params = table["parameters"]
    if all(k in params for k in ("Init E (V)", "Final E (V)", "Incr E (V)")):
        expected_n = round(abs(params["Final E (V)"] - params["Init E (V)"]) / abs(params["Incr E (V)"])) + 1
        if expected_n != len(points) or abs(xs[0] - params["Init E (V)"]) > 5e-4 or abs(xs[-1] - params["Final E (V)"]) > 5e-4:
            warnings.append("Point count or potential endpoints disagree with acquisition parameters")
    return {"points": points, "checks": checks, "warnings": warnings,
            "plot_eligible": not warnings, "frequency_Hz": actual, "model": "Cs", "formula": FORMULA}


def _json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def _csv(path: Path, headers: list, rows: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        writer.writerow(headers)
        writer.writerows(rows)
        if path.read_text(encoding="utf-8-sig") != stream.getvalue().replace("\r\n", "\n"):
            raise ValueError("Existing calculated CSV differs: " + str(path))
        return
    with path.open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def _workbook_export(project_root: Path, root: Path, definitions: list, node: Path, node_modules: Path,
                     *, only_paths: tuple[str, ...] | None = None) -> None:
    manifest = root / DIRECTORIES[6] / "workbooks.json"
    _json(manifest, definitions)
    previous_evidence = []
    if only_paths is not None:
        evidence_path = root / DIRECTORIES[5] / "Excel导出核查.json"
        if evidence_path.is_file():
            previous_evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        manifest = manifest.with_name("workbooks_update.json")
        _json(manifest, [d for d in definitions if d["path"] in only_paths])
    # Keep runtime dependencies outside source and outputs. Read-only bundled deps.
    with tempfile.TemporaryDirectory(prefix="chi-workbooks-", dir=root.parent) as temporary:
        sandbox = Path(temporary)
        script = sandbox / "build_chi_workbooks.mjs"
        shutil.copy2(project_root / "scripts/data_types/electrochem/build_chi_workbooks.mjs", script)
        junction = sandbox / "node_modules"
        subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(node_modules)], check=True, capture_output=True, text=True)
        try:
            subprocess.run([str(node), str(script), str(manifest), str(root)], check=True)
        finally:
            # Remove only the junction entry, never the dependency directory.
            if junction.exists():
                junction.rmdir()
    if previous_evidence:
        evidence_path = root / DIRECTORIES[5] / "Excel导出核查.json"
        current = json.loads(evidence_path.read_text(encoding="utf-8"))
        _json(evidence_path, [e for e in previous_evidence if e["path"] not in only_paths] + current)


def run_chi_electrochem(project_root: Path, *, input_dir: Path, output_root: Path,
                       package_name: str, with_origin: bool, workbook_node: Path,
                       node_modules: Path, historical_workbook: Path | None = None, resume: bool = False,
                       make_zip: bool = False) -> dict:
    project_root, input_dir = project_root.resolve(), input_dir.resolve()
    if not input_dir.is_dir() or not re.fullmatch(r"[\w.\-\u4e00-\u9fff]+", package_name):
        raise ValueError("Valid input directory and a safe package name are required")
    root_base = resolve_output_root(project_root, output_root)
    root = ensure_safe_output_file_target(root_base / package_name, output_root=root_base)
    ensure_output_path_separate_from_inputs(project_root, root, [input_dir])
    if root.exists() and resume:
        previous = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
        if previous["input_directory"] != str(input_dir) or previous.get("visual_review_status") == "passed":
            raise ValueError("Resume requires an incomplete matching package")
        for existing in root.rglob("*"):
            ensure_safe_output_file_target(existing, output_root=root)
            if existing.is_file() and existing.stat().st_nlink > 1:
                raise ValueError("Resume refuses hard-linked output files")
    elif root.exists() or root.with_suffix(".zip").exists():
        raise FileExistsError("A result package already exists; choose a new package name")
    registry = load_json_compatible_yaml(registry_path(project_root))
    entries = registry["entries"]
    if not any(e.get("inferred_data_type") == "Mott-Schottky" and e.get("supported_in_pipeline") for e in entries):
        raise ValueError("Mott-Schottky is not enabled in the current registry")
    root.mkdir(parents=True, exist_ok=resume)
    for directory in DIRECTORIES:
        (root / directory).mkdir(exist_ok=resume)
    for fmt in ("PNG", "TIFF", "SVG", "PDF"):
        (root / DIRECTORIES[4] / fmt).mkdir(exist_ok=resume)
    if historical_workbook:
        _json(root / DIRECTORIES[5] / "历史Cs模型依据.json", historical_cs_evidence(historical_workbook))
    files = sorted((p for p in input_dir.rglob("*") if p.is_file()), key=lambda p: str(p).casefold())
    records = {}
    for path in files:
        info = parse_chi_name(path)
        key = str(path.relative_to(input_dir).parent / info["acquisition"])
        if key not in records:
            records[key] = {**info, "id": f"M{len(records)+1:03d}", "files": [], "warnings": []}
        records[key]["files"].append(path)
    collisions = Counter((r.get("kind"), r.get("material"), r.get("repeat"), r.get("condition")) for r in records.values())
    inventory, checks, all_points, plots, frequency_report, anomalies = [], [], [], [], [], []
    for rec in records.values():
        warnings = rec["warnings"]
        if rec["ambiguity"]:
            warnings.append(rec["ambiguity"])
        collision_key = (rec.get("kind"), rec.get("material"), rec.get("repeat"), rec.get("condition"))
        if collisions[collision_key] > 1:
            warnings.append("Repeated acquisition label collision; kept as separate record " + rec["id"])
        if rec["kind"] == "EIS":
            folder = root / DIRECTORIES[0] / rec["material"] / f'{rec["condition"]:g}s' / f'第{rec["repeat"]}次'
        elif rec["kind"] == "MT":
            folder = root / DIRECTORIES[1] / rec["material"] / f'第{rec["repeat"]}次' / f'{rec["condition"]:g}Hz'
        else:
            folder = root / "待确认文件"
        if collisions[collision_key] > 1:
            folder /= rec["id"]
        folder.mkdir(parents=True, exist_ok=True)
        tables = []
        for source in rec["files"]:
            destination = ensure_safe_output_file_target(folder / source.name, output_root=root)
            if not destination.exists():
                shutil.copy2(source, destination)
            elif not resume:
                raise FileExistsError(destination)
            if not filecmp.cmp(source, destination, shallow=False):
                raise RuntimeError("Copied raw file differs from source")
            if source.suffix.casefold() in {".txt", ".csv"}:
                try:
                    tables.append(read_chi_impedance(source))
                except (ValueError, UnicodeError) as exc:
                    warnings.append(f"{source.name}: {exc}")
            elif source.name.lower().endswith((".csv.bin", ".txt.bin")):
                warnings.append(source.name + ": binary suffix; not a text export")
            inventory.append({"原文件": str(source.relative_to(input_dir)), "字节": source.stat().st_size,
                              "类型": rec["kind"], "材料": rec.get("material", ""), "重复标号": rec.get("repeat"),
                              "条件": rec.get("condition"), "单位": rec.get("unit", ""), "独立记录": rec["id"],
                              "整理后文件": str(destination.relative_to(root)), "复制逐字节核对": True})
        rec["formats"] = [p.suffix.lower() for p in rec["files"]]
        rec["source_files"] = [str(p.relative_to(input_dir)) for p in rec["files"]]
        rec.pop("files")
        if tables:
            rec["timestamp"] = tables[0]["timestamp"]
            rec["row_count"] = len(tables[0]["rows"])
            rec["parameters"] = tables[0]["parameters"]
            rec["txt_csv_agree"] = len(tables) >= 2 and all(t["headers"] == tables[0]["headers"] and t["rows"] == tables[0]["rows"] and t["parameters"] == tables[0]["parameters"] for t in tables[1:])
            if len(tables) > 1 and not rec["txt_csv_agree"]:
                warnings.append("TXT/CSV disagree: calculation withheld")
        else:
            warnings.append("No readable text export; BIN preserved without decoding")
        if rec["kind"] == "MT" and tables and not warnings:
            try:
                calc = calculate_chi_mott(tables[0], rec["condition"])
                rec["calculation"] = calc
                warnings.extend(calc["warnings"])
                invalid_count = sum(p["status"] != "valid" for p in calc["points"])
                if invalid_count:
                    warnings.append(f"{invalid_count}/{len(calc['points'])} points have nonnegative Zimag; Cs and 1/Cs² left blank")
                points = calc["points"]
                all_points.extend([dict(material=rec["material"], repeat=rec["repeat"], record=rec["id"], **p) for p in points])
                checks.extend(calc["checks"])
                _csv(root / DIRECTORIES[2] / rec["material"] / f'第{rec["repeat"]}次' / f'{rec["condition"]:g}Hz.csv', list(points[0]), [list(p.values()) for p in points])
            except ValueError as exc:
                warnings.append(str(exc))
        if rec["kind"] == "EIS" and tables:
            if tables[0]["headers"][0] != "Freq/Hz":
                warnings.append("EIS filename conflicts with potential table")
            imag = [row[2] for row in tables[0]["rows"]]
            rec["positive_Zimag_count"] = sum(v > 0 for v in imag)
            if rec["positive_Zimag_count"]:
                warnings.append(f'{rec["positive_Zimag_count"]} EIS point(s) with positive Zimag; retained, no fitting')
        anomalies.extend(f'{rec["id"]} {rec["acquisition"]}: {w}' for w in warnings)
    mt_groups = defaultdict(list)
    for rec in records.values():
        if rec["kind"] == "MT":
            mt_groups[(rec["material"], rec["repeat"])].append(rec)
    for (material, repeat), group in sorted(mt_groups.items()):
        selected = [r for r in group if r["condition"] in PLOT_FREQUENCIES and r.get("calculation", {}).get("plot_eligible")]
        selected.sort(key=lambda r: r["condition"])
        row = {"材料": material, "重复标号": repeat}
        for frequency in (1000, 1500, *PLOT_FREQUENCIES):
            matches = [r for r in group if r["condition"] == frequency]
            row[f"{frequency} Hz"] = ("缺失" if not matches else ("可计算" if all("calculation" in r for r in matches) else "仅BIN/待核查"))
            if matches and any(r.get("calculation") and any(p["status"] != "valid" for p in r["calculation"]["points"]) for r in matches):
                row[f"{frequency} Hz"] = "已读取；非电容响应点的Cs留空"
        row["绘图频率"] = ", ".join(f'{r["condition"]:g}' for r in selected)
        row["2000–5000 Hz齐全"] = len(selected) == 4
        frequency_report.append(row)
        if selected:
            # Every frequency owns its X/Y pair. No grid matching or interpolation.
            series = [{"frequency_Hz": r["condition"], "record": r["id"], "points": r["calculation"]["points"]} for r in selected]
            slug = re.sub(r"[^A-Za-z0-9]+", "_", material).strip("_") + f"_rep{repeat}"
            plot = {"material": material, "repeat": repeat, "slug": slug, "series": series}
            plots.append(plot)
            headers = [header for s in series for header in (f'Potential_{s["frequency_Hz"]:g}Hz_V', f'OneOverCs2_{s["frequency_Hz"]:g}Hz_F-2')]
            rows = [[v for s in series for v in ((s["points"][i]["potential_V"], s["points"][i]["one_over_Cs_squared_F-2"]) if i < len(s["points"]) else (None, None))] for i in range(max(len(s["points"]) for s in series))]
            _csv(root / DIRECTORIES[2] / material / f"第{repeat}次" / "Origin独立XY绘图数据.csv", headers, rows)
            plot["overlay_headers"], plot["overlay_rows"] = headers, rows
    metadata = {"data_type": "CHI electrochemistry batch", "input_directory": str(input_dir),
                "historical_Cs_workbook": str(historical_workbook) if historical_workbook else None,
                "model": "Cs", "formula": FORMULA, "pi": math.pi,
                "historical_pi_note": "Historical workbook used 3.1415926; math.pi changes 1/Cs² by about 3.41e-8 relative, with identical model and units.",
                "potential_reference": "not specified; no reference conversion", "area_normalized": False,
                "capacitance_unit": "F", "inverse_square_unit": "F^-2", "plot_frequencies_Hz": PLOT_FREQUENCIES,
                "instrument_precomputed_inverse_square_count": 0, "source_file_count": len(files),
                "source_counts_by_type": dict(Counter(r["类型"] for r in inventory)),
                "measurement_counts_by_type": dict(Counter(r["kind"] for r in records.values())),
                "materials": sorted({r["material"] for r in records.values() if "material" in r}),
                "readable_MT_count": sum("calculation" in r for r in records.values()),
                "calculated_MT_count": sum(any(p["status"] == "valid" for p in r.get("calculation", {}).get("points", [])) for r in records.values()),
                "MT_point_count": len(all_points), "valid_MT_point_count": sum(p["status"] == "valid" for p in all_points),
                "flagged_MT_point_count": sum(p["status"] != "valid" for p in all_points), "planned_plot_count": len(plots), "plot_count": 0,
                "records": list(records.values()), "frequency_report": frequency_report,
                "manual_check_required": True, "manual_checks": ["BIN-only text re-export", "reference electrode and electrode area", "repeat label collision"],
                "forbidden_claims": ["carrier type", "flat-band potential", "carrier concentration", "band edges"],
                "origin_status": "not_requested", "visual_review_status": "pending" if with_origin else "not_applicable"}
    _json(root / "metadata.json", metadata)
    if with_origin:
        from src.origin.chi_mott import plot_chi_mott
        try:
            metadata["origin_verification"] = plot_chi_mott(project_root, root, plots)
            metadata["origin_status"] = "saved_reopened_native_exported"
            metadata["plot_count"] = len(metadata["origin_verification"]["graphs"])
        except Exception as exc:
            metadata["origin_status"] = "failed"
            metadata["origin_error"] = str(exc)
            anomalies.append("Origin: " + str(exc))
        _json(root / "metadata.json", metadata)
    plot_index = []
    for p in plots:
        plot_index.append({"材料": p["material"], "重复标号": p["repeat"],
                           "频率_Hz": ", ".join(f'{s["frequency_Hz"]:g}' for s in p["series"]),
                           "OPJU": str(Path(DIRECTORIES[3]) / p["material"] / (p["slug"] + ".opju")),
                           "导出状态": metadata["origin_status"], "文件名前缀": p["slug"]})
    repeat_rows = []
    for material in metadata["materials"]:
        for kind in ("EIS", "MT"):
            group = [r for r in records.values() if r["kind"] == kind and r["material"] == material]
            repeat_rows.append({"材料": material, "类型": kind, "独立测试记录数": len(group),
                                "重复标号": ", ".join(str(n) for n in sorted({r["repeat"] for r in group})),
                                "重复标号种数": len({r["repeat"] for r in group}),
                                "原始文件数": sum(len(r["source_files"]) for r in group),
                                "条件": ", ".join(f'{v:g}' for v in sorted({r["condition"] for r in group}))})
    definitions = []
    for filename, rows in [("全部文件分类清单", inventory), ("材料及重复次数汇总", repeat_rows),
                           ("MT频率完整性检查", frequency_report), ("MT计算与单位核查", checks),
                           ("Origin绘图文件索引", plot_index)]:
        headers = list(rows[0]) if rows else ["无记录"]
        definitions.append({"path": f"{DIRECTORIES[5]}/{filename}.xlsx", "sheets": [{"name": "数据", "headers": headers, "rows": [[r.get(h) for h in headers] for r in rows]}]})
    calculation_audit = []
    for rec in records.values():
        if rec["kind"] != "MT":
            continue
        points = rec.get("calculation", {}).get("points", [])
        valid = [p for p in points if p["status"] == "valid"]
        calculation_audit.append({"独立记录": rec["id"], "材料": rec["material"], "重复标号": rec["repeat"],
                                  "频率_Hz": rec["condition"], "读取行数": len(points), "有效Cs点数": len(valid),
                                  "非电容响应点数": len(points)-len(valid), "TXT_CSV一致": rec.get("txt_csv_agree", "无文本对"),
                                  "电位单位": "V" if points else "未解析", "阻抗单位": "ohm" if points else "未解析",
                                  "电容模型": "Cs", "电容单位": "F", "纵坐标单位": "F^-2",
                                  "Cs最小_F": min((p["Cs_F"] for p in valid), default=None),
                                  "Cs最大_F": max((p["Cs_F"] for p in valid), default=None),
                                  "核查说明": "; ".join(rec["warnings"]), "来源": "; ".join(rec["source_files"])})
    audit = next(d for d in definitions if d["path"].endswith("MT计算与单位核查.xlsx"))
    audit["sheets"].insert(0, {"name": "记录核查", "headers": list(calculation_audit[0]), "rows": [list(r.values()) for r in calculation_audit]})
    audit["sheets"][1]["name"] = "独立复算点"
    if all_points:
        sheets = [{"name": "完整计算", "headers": list(all_points[0]), "rows": [list(p.values()) for p in all_points], "calculation_formulas": True}]
        sheets += [{"name": p["slug"][:31], "headers": p["overlay_headers"], "rows": p["overlay_rows"]} for p in plots]
        definitions.append({"path": f"{DIRECTORIES[2]}/MT完整计算及Origin数据.xlsx", "sheets": sheets})
    _workbook_export(project_root, root, definitions, workbook_node, node_modules)
    (root / DIRECTORIES[5] / "异常文件报告.txt").write_text("\n".join(anomalies) + "\n", encoding="utf-8")
    _write_report(root, metadata)
    _snapshot_scripts(project_root, root)
    _json(root / DIRECTORIES[6] / "run_parameters.json", {"command": "run.py chi-electrochem", "input_dir": str(input_dir), "output_root": str(root_base), "package_name": package_name, "with_origin": with_origin, "workbook_node": str(workbook_node), "node_modules": str(node_modules), "historical_workbook": str(historical_workbook) if historical_workbook else None})
    (root / DIRECTORIES[6] / "运行说明.txt").write_text("这是原工作流 run.py 的 chi-electrochem 专用分支。复现时在原 ResearchDataOriginPipeline 工作目录运行；参数见 run_parameters.json，选择新的 package-name，避免覆盖成果。\n依赖沿用 requirements.txt 与现有 artifact-tool Node 运行库；无需 GPU、联网或新安装。\nCs=-1/(2*pi*f*Zimag)，1/Cs²=1/(Cs*Cs)。BIN 未解码。EIS 不作图。\n本目录保存本次实际执行分支代码；共享 OriginOperations 仍由原工作流提供。\n", encoding="utf-8")
    _write_replay_script(project_root, root)
    _json(root / "metadata.json", metadata)
    if make_zip:
        package_zip(root)
    print(json.dumps({"output": str(root), "files": len(files), "records": metadata["measurement_counts_by_type"], "plots": metadata["plot_count"], "origin": metadata["origin_status"]}, ensure_ascii=False))
    return metadata


def _snapshot_scripts(project_root: Path, root: Path) -> None:
    for relative in ["src/core/chi_electrochem.py", "src/origin/chi_mott.py", "src/origin/adapter.py", "src/origin/operations.py",
                     "src/origin/plot_policy.py", "src/cli.py", "run.py", "requirements.txt", "config/plot_style.yaml",
                     "scripts/origin/origin_plot_from_template.ps1", "scripts/origin/native_legend_layout.c",
                     "scripts/origin/native_legend.c", "scripts/data_types/electrochem/build_chi_workbooks.mjs"]:
        target = root / DIRECTORIES[6] / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(project_root / relative, target)


def _write_replay_script(project_root: Path, root: Path) -> None:
    p = json.loads((root / DIRECTORIES[6] / "run_parameters.json").read_text(encoding="utf-8"))
    arguments = ["run.py", "chi-electrochem", "--input-dir", p["input_dir"], "--output-root", p["output_root"],
                 "--workbook-node", p["workbook_node"], "--node-modules", p["node_modules"]]
    if p["historical_workbook"]:
        arguments += ["--historical-workbook", p["historical_workbook"]]
    if p["with_origin"]:
        arguments += ["--with-origin"]
    ps_quote = lambda value: "'" + str(value).replace("'", "''") + "'"
    replay = "$ErrorActionPreference = 'Stop'\nSet-Location -LiteralPath " + ps_quote(project_root) + "\n"
    replay += "$pipelineArguments = @(\n" + ",\n".join("    " + ps_quote(v) for v in arguments) + "\n)\n"
    replay += "$pipelineArguments += @('--package-name', (" + ps_quote(p["package_name"] + "_复现_") + " + (Get-Date -Format 'yyyyMMdd_HHmmss')))\n"
    replay += "& " + ps_quote(sys.executable) + " @pipelineArguments\nif ($LASTEXITCODE -ne 0) { throw 'Pipeline failed' }\n"
    (root / DIRECTORIES[6] / "复现.ps1").write_text(replay, encoding="utf-8-sig")


def _write_report(root: Path, m: dict) -> None:
    text = ["2026-10-30 CHI660E 电化学数据处理报告", "",
            f'原始文件：{m["source_file_count"]}；按类型文件数：{m["source_counts_by_type"]}；独立记录：{m["measurement_counts_by_type"]}。',
            "材料：" + ", ".join(m["materials"]),
            f'已读取MT：{m["readable_MT_count"]}个频率记录、{m["MT_point_count"]}个点；其中{m["calculated_MT_count"]}个频率记录有有效Cs，共{m["valid_MT_point_count"]}个有效计算点；MT图：{m["plot_count"]}张。',
            f'{m["flagged_MT_point_count"]}个非电容响应点保留原阻抗，Cs与1/Cs²留空，详见完整计算表status列。',
            "", "采用 Cs 串联等效电容，历史处理表中的 H/I 列公式可核对：", str(m["historical_Cs_workbook"]),
            FORMULA, "电位V、阻抗Ω、电容F、1/Cs²为F⁻²；未按面积归一化，未作参比换算。",
            m["historical_pi_note"],
            "本批可读表为原始阻抗，无仪器已计算的1/C²列。每个文本记录与CSV逐点核对，首/中/末点独立复算。",
            "EIS的160s/800s仅按文件命名分类，未将其解释为阻抗频率扫描的实际总用时。" + (f'已按原Origin脚本绘制{m["eis_plot_count"]}张实测Nyquist图，未拟合或删点。' if m.get("eis_plot_count") else "EIS不拟合、不平滑、不作图。"),
            "重复标号只代表命名线索。BOB第3次存在不同命名记录时，按独立记录分别保留，不能推定其真实采集顺序。",
            "", "频率完整性："]
    for r in m["frequency_report"]:
        text.append(f'{r["材料"]} 第{r["重复标号"]}次：' + "；".join(f"{f}Hz={r[f'{f} Hz']}" for f in (1000,1500,2000,3000,4000,5000)))
    text += ["", "1000Hz及实际存在的1500Hz均保留；本次仅绘制2000/3000/4000/5000Hz。",
             "仅BIN的频率未解码、未计算，不以其他重复测量补齐。不把.csv.bin或.txt.bin当成文本。",
             "所有原始文件以复制方式保留，并逐字节比较，不计算哈希。没有发现输入ZIP，本次输入为已解压文件夹。",
             "不进行线性拟合、载流子类型、浓度、平带电位或能带结论。非线性和频率色散如实保留。",
             "Origin状态：" + m["origin_status"], "视觉核查：" + m["visual_review_status"],
             "异常明细见异常文件报告.txt；BIN-only记录需在CHI软件重新导出TXT/CSV后才能补齐。"]
    text += ["", "各材料的重复标号（非推定的真实采集顺序）："]
    for material in m["materials"]:
        for kind in ("EIS", "MT"):
            group = [r for r in m["records"] if r["kind"] == kind and r["material"] == material]
            text.append(f'{material} {kind}：重复标号' + ", ".join(str(v) for v in sorted({r["repeat"] for r in group})) + f'；{len(group)}条独立频率/条件记录。')
    text += ["", *m.get("data_review_notes", [])]
    (root / DIRECTORIES[5] / "处理报告.txt").write_text("\n".join(text) + "\n", encoding="utf-8")


def package_zip(root: Path) -> None:
    archive = root.with_suffix(".zip")
    ensure_safe_output_file_target(archive, output_root=root.parent)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as handle:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                handle.write(path, path.relative_to(root.parent))


def replot_chi_electrochem(project_root: Path, root: Path, *, with_eis: bool, force: bool,
                         stage: Path | None = None, redraw_kinds: tuple[str, ...] | None = None) -> dict:
    """Reuse verified tables and existing Origin helper; no new data processing."""
    from src.origin.chi_mott import render_chi_with_existing_helper
    if not force:
        raise ValueError("Replacing CHI graph products requires --force")
    root = ensure_safe_output_file_target(root, output_root=resolve_output_root(project_root))
    m = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
    groups = defaultdict(list)
    eis = []
    for rec in m["records"]:
        if rec["kind"] == "MT" and rec["condition"] in PLOT_FREQUENCIES and rec.get("calculation", {}).get("plot_eligible"):
            groups[(rec["material"], rec["repeat"])].append(rec)
        if rec["kind"] == "EIS" and with_eis:
            eis.append(dict(rec, input_directory=m["input_directory"]))
    plots = []
    for (material, repeat), records in sorted(groups.items()):
        records.sort(key=lambda r: r["condition"])
        plots.append({"material": material, "repeat": repeat,
                      "slug": re.sub(r"[^A-Za-z0-9]+", "_", material).strip("_") + f"_rep{repeat}",
                      "series": [{"frequency_Hz": r["condition"], "record": r["id"], "points": r["calculation"]["points"]} for r in records]})
    result = render_chi_with_existing_helper(project_root, root, plots, eis, stage=stage, redraw_kinds=redraw_kinds)
    _json(root / DIRECTORIES[5] / "Origin重绘核查.json", result)
    print(json.dumps({"MT_graphs": len(plots), "EIS_graphs": len(eis), "stage": result["stage"], "visual_review": "pending"}, ensure_ascii=False))
    return result


def accept_chi_origin_redraw(project_root: Path, root: Path, *, review_note: str) -> dict:
    from src.origin.chi_mott import install_verified_chi_redraw
    from src.core.file_utils import plan_safe_owned_directory_removal, apply_safe_owned_directory_removal
    result_path = root / DIRECTORIES[5] / "Origin重绘核查.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    install_verified_chi_redraw(root, result, review_note=review_note)
    m = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
    m.update(origin_verification=result, origin_status="saved_reopened_native_exported", visual_review_status="passed", visual_review_note=review_note)
    m["plot_count"] = sum(g["kind"] == "MT" for g in result["graphs"])
    m["eis_plot_count"] = sum(g["kind"] == "EIS" for g in result["graphs"])
    m["total_plot_count"] = len(result["graphs"])
    m["final_validation"] = {"graphs": len(result["graphs"]), "origin_projects": len({g["project"] for g in result["graphs"]}),
                             "style": "existing origin_plot_from_template.ps1 cached Graph4", "visual_review": "passed",
                             "all_graphs_saved_reopened": True, "native_raster_dpi": 600}
    _json(root / "metadata.json", m)
    _json(result_path, result)
    _write_report(root, m)
    _snapshot_scripts(project_root, root)
    archive = ensure_safe_output_file_target(root.with_suffix(".zip"), output_root=root.parent)
    if archive.is_file():
        archive.unlink()
    stage = Path(result["stage"])
    for name in ["origin_files", "figures_preview", "figures_tif", "export_png", "export_tif", "export_svg", "export_pdf"]:
        folder = stage / name
        if folder.exists():
            plan = plan_safe_owned_directory_removal(folder, output_root=stage)
            apply_safe_owned_directory_removal(plan, output_root=stage)
    return m


def record_visual_review(root: Path, note: str, *, data_notes: list[str] | None = None, make_zip: bool = False) -> None:
    """Called only after an operator has actually inspected every exported PNG."""
    metadata_path = ensure_safe_output_file_target(root / "metadata.json", output_root=root.parent)
    m = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not note.strip() or m["origin_status"] != "saved_reopened_native_exported":
        raise ValueError("A reviewed native Origin export is required")
    m["visual_review_status"], m["visual_review_note"] = "passed", note
    if data_notes:
        m["data_review_notes"] = data_notes
        anomaly_path = root / DIRECTORIES[5] / "异常文件报告.txt"
        with anomaly_path.open("a", encoding="utf-8") as handle:
            handle.write("\n" + "\n".join(data_notes) + "\n")
    _json(metadata_path, m)
    _write_report(root, m)
    if make_zip:
        package_zip(root)
