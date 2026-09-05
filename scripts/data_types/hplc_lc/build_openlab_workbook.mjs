import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const argv = process.argv.slice(2);
const options = {};
for (let index = 0; index < argv.length; index += 2) {
  options[argv[index]] = argv[index + 1];
}
for (const required of ["--input", "--output", "--preview-dir", "--verification"]) {
  if (!options[required]) {
    throw new Error(`Missing required argument ${required}`);
  }
}

const dataset = JSON.parse(await fs.readFile(options["--input"], "utf8"));
const outputPath = path.resolve(options["--output"]);
const outputDir = path.dirname(outputPath);
const previewRoot = path.resolve(options["--preview-dir"]);
const verificationPath = path.resolve(options["--verification"]);
await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(previewRoot, { recursive: true });
await fs.mkdir(path.dirname(verificationPath), { recursive: true });

const COLORS = {
  headerFill: "#E7E6E6",
  labelFill: "#F2F2F2",
  bodyFill: "#FFFFFF",
  border: "#B7B7B7",
  text: "#222222",
  muted: "#666666",
};

function excelColumn(indexZeroBased) {
  let index = indexZeroBased + 1;
  let letters = "";
  while (index > 0) {
    const remainder = (index - 1) % 26;
    letters = String.fromCharCode(65 + remainder) + letters;
    index = Math.floor((index - 1) / 26);
  }
  return letters;
}

function localDate(value) {
  if (!value) return null;
  const match = String(value).match(
    /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})?$/,
  );
  if (!match) return null;
  return new Date(Date.UTC(
    Number(match[1]),
    Number(match[2]) - 1,
    Number(match[3]),
    Number(match[4] || 0),
    Number(match[5] || 0),
    Number(match[6] || 0),
  ));
}

function uniqueText(values) {
  return [...new Set(values.filter((value) => value !== null && value !== undefined && String(value).trim()))]
    .map((value) => String(value))
    .join("; ");
}

function cleanMethodName(value) {
  return String(value || "").replace(/\.amx$/i, "").trim();
}

function methodText(item) {
  return cleanMethodName(item.processing_method || item.acquisition_method);
}

function methodListText(item) {
  const methods = (item.processing_methods || []).length
    ? item.processing_methods
    : (item.acquisition_methods || []);
  return uniqueText(methods.map((value) => cleanMethodName(value)));
}

function alignedIntegerText(values) {
  return values
    .map((value) => (value === null || value === undefined ? "" : String(value)))
    .join("\n");
}

function alignedNumberText(values, digits = 4) {
  return values
    .map((value) => {
      if (value === null || value === undefined || value === "") return "";
      const number = Number(value);
      if (!Number.isFinite(number)) return String(value);
      return number.toLocaleString("en-US", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      });
    })
    .join("\n");
}

function safePreviewName(value) {
  return String(value)
    .replace(/[<>:"/\\|?*\u0000-\u001f]+/g, "_")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 90) || "sheet";
}

function styleHeader(range, rowHeight = 28) {
  range.format = {
    fill: COLORS.headerFill,
    font: { bold: true, color: COLORS.text },
    verticalAlignment: "center",
    horizontalAlignment: "center",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: COLORS.border },
  };
  range.format.rowHeight = rowHeight;
}

function styleBody(range) {
  range.format = {
    fill: COLORS.bodyFill,
    font: { color: COLORS.text },
    verticalAlignment: "center",
    borders: { preset: "all", style: "thin", color: COLORS.border },
  };
}

function setColumnWidths(sheet, widths) {
  widths.forEach((width, index) => {
    sheet.getRange(`${excelColumn(index)}:${excelColumn(index)}`).format.columnWidth = width;
  });
}

function writeDataSheet(
  sheet,
  headers,
  rows,
  {
    widths,
    wrapColumns = [],
    rowHeight = 24,
    headerRowHeight = 28,
    previewRows = 12,
    tableName = null,
  } = {},
) {
  const matrix = [headers, ...rows];
  const lastColumn = excelColumn(headers.length - 1);
  const lastRow = matrix.length;
  const target = sheet.getRange(`A1:${lastColumn}${lastRow}`);
  target.values = matrix;
  if (tableName) {
    const table = sheet.tables.add(`A1:${lastColumn}${lastRow}`, true, tableName);
    table.style = "TableStyleLight1";
    table.showFilterButton = true;
    table.showBandedRows = false;
    table.showBandedColumns = false;
  }
  styleHeader(sheet.getRange(`A1:${lastColumn}1`), headerRowHeight);
  if (lastRow > 1) {
    styleBody(sheet.getRange(`A2:${lastColumn}${lastRow}`));
    sheet.getRange(`A2:${lastColumn}${lastRow}`).format.rowHeight = rowHeight;
  }
  if (widths) setColumnWidths(sheet, widths);
  for (const column of wrapColumns) {
    sheet.getRange(`${column}1:${column}${lastRow}`).format.wrapText = true;
  }
  sheet.freezePanes.freezeRows(1);
  sheet.showGridLines = true;
  return {
    lastColumn,
    lastRow,
    previewRange: `A1:${lastColumn}${Math.min(lastRow, previewRows)}`,
  };
}

function writeKeyValueSheet(sheet, rows) {
  const spec = writeDataSheet(
    sheet,
    ["项目", "内容"],
    rows,
    {
      widths: [30, 96],
      wrapColumns: ["A", "B"],
      rowHeight: 34,
      previewRows: rows.length + 1,
    },
  );
  if (spec.lastRow > 1) {
    sheet.getRange(`A2:A${spec.lastRow}`).format = {
      fill: COLORS.labelFill,
      font: { bold: true, color: COLORS.text },
      verticalAlignment: "center",
      wrapText: true,
      borders: { preset: "all", style: "thin", color: COLORS.border },
    };
    sheet.getRange(`B2:B${spec.lastRow}`).format = {
      fill: COLORS.bodyFill,
      font: { color: COLORS.text },
      verticalAlignment: "center",
      wrapText: true,
      borders: { preset: "all", style: "thin", color: COLORS.border },
    };
  }
  return spec;
}

function formatRange(sheet, range, numberFormat) {
  if (!range) return;
  sheet.getRange(range).format.numberFormat = numberFormat;
}

function detectorText(item) {
  const detectors = uniqueText(item.detectors || []);
  const wavelengths = (item.wavelengths_nm || [])
    .filter((value) => value !== null && value !== undefined)
    .map((value) => `${Number(value).toFixed(0)} nm`);
  return uniqueText([detectors, ...wavelengths]);
}

const ANALYSIS_MAIN_COLUMNS = [
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
];

const ANALYSIS_PEAK_COLUMNS = [
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
];

const ANALYSIS_LOG_COLUMNS = [
  "处理时间",
  "实验日期",
  "样品名",
  "重打组ID",
  "原始文件",
  "操作类型",
  "判断依据",
  "处理前状态",
  "处理后结果",
  "使用的数据",
  "舍弃的数据",
  "详细说明",
];

const ANALYSIS_EXCLUDED_COLUMNS = [
  "实验日期",
  "样品名",
  "进样ID",
  "排除原因",
  "详细说明",
  "实际采集时间",
  "序列名称",
  "OpenLab结果名称",
  "日期文件夹",
  "原始文件名",
  "原始文件路径",
];

const ANALYSIS_RERUN_COLUMNS = [
  "重打组ID",
  "实验日期",
  "样品名",
  "归一化样品名",
  "进样ID",
  "序列名称",
  "OpenLab结果名称",
  "实际采集时间",
  "重打判断依据",
  "数据质量",
  "是否参与平均",
  "是否最终采用",
  "舍弃原因",
  "原始文件名",
  "原始文件路径",
];

const ANALYSIS_REVIEW_COLUMNS = [
  "实验日期",
  "样品名",
  "进样ID",
  "问题类型",
  "问题原因",
  "建议操作",
  "状态",
];

const ANALYSIS_PARAMETER_COLUMNS = ["分类", "参数", "值", "单位", "来源"];

function firstPresent(record, keys, fallback = null) {
  for (const key of keys) {
    if (Object.prototype.hasOwnProperty.call(record, key)) {
      const value = record[key];
      if (value !== undefined) return value;
    }
  }
  return fallback;
}

function targetValue(record, targetKey, field) {
  const targets = record.targets || {};
  return targets[targetKey]?.[field] ?? null;
}

function normalizeAnalysisCell(header, value) {
  if (value === undefined) return null;
  if (
    ["实验日期", "实际采集时间", "采集时间", "处理时间"].includes(header)
    && typeof value === "string"
  ) {
    return localDate(value) || value;
  }
  return value;
}

function mainResultValue(record, header) {
  if (["采集方法", "方法"].includes(header)) {
    const value = firstPresent(
      record,
      [header, "采集方法", "方法", "acquisition_method", "method_name", "method", "processing_method", "处理方法"],
    );
    return value === null || value === undefined ? value : cleanMethodName(value);
  }
  if (Object.prototype.hasOwnProperty.call(record, header)) return record[header];
  const direct = {
    序号: ["sequence_number", "index"],
    实验日期: ["experiment_date"],
    样品名: ["sample_name"],
    实验批次: ["experiment_batch"],
    "反应时间（h）": ["reaction_time_h"],
    光源: ["light_source"],
    "C₀（mM）": ["c0_mM"],
    "转化率（%）": ["conversion_fraction", "conversion"],
    "茴香亚砜选择性（%）": ["sulfoxide_selectivity_fraction", "sulfoxide_selectivity"],
    "茴香亚砜产率（%）": ["sulfoxide_yield_fraction", "sulfoxide_yield"],
    "物料回收率（%）": ["material_recovery_fraction", "material_recovery"],
    数据质量: ["data_quality"],
    处理方式: ["process_method"],
    使用数据组: ["used_data_group"],
    舍弃数据组: ["discarded_data_group"],
    处理说明: ["process_note"],
    重打组ID: ["rerun_group_id"],
    实际采集时间: ["actual_acquisition_time"],
    采集方法: ["采集方法", "方法", "acquisition_method", "method_name", "method", "processing_method", "处理方法"],
    方法: ["方法", "采集方法", "acquisition_method", "method_name", "method", "processing_method", "处理方法"],
    序列名称: ["sequence_name"],
    OpenLab结果名称: ["result_name"],
    日期文件夹: ["batch_folder"],
    原始文件名: ["raw_file"],
    原始文件路径: ["source_relative", "source_path"],
  };
  if (direct[header]) return firstPresent(record, direct[header]);
  const targetColumns = {
    "茴香亚砜 RT（min）": ["sulfoxide", "retention_time_min"],
    茴香亚砜峰面积: ["sulfoxide", "area"],
    "茴香亚砜原液浓度（mM）": ["sulfoxide", "reaction_concentration_mM"],
    "茴香砜 RT（min）": ["sulfone", "retention_time_min"],
    茴香砜峰面积: ["sulfone", "area"],
    "茴香砜原液浓度（mM）": ["sulfone", "reaction_concentration_mM"],
    "茴香硫醚 RT（min）": ["thioanisole", "retention_time_min"],
    茴香硫醚峰面积: ["thioanisole", "area"],
    "茴香硫醚原液浓度（mM）": ["thioanisole", "reaction_concentration_mM"],
  };
  if (targetColumns[header]) {
    const [targetKey, field] = targetColumns[header];
    return targetValue(record, targetKey, field);
  }
  return null;
}

function peakDetailValue(record, header) {
  if (["采集方法", "方法"].includes(header)) {
    const value = firstPresent(
      record,
      [header, "采集方法", "方法", "acquisition_method", "method_name", "method", "processing_method", "处理方法"],
    );
    return value === null || value === undefined ? value : cleanMethodName(value);
  }
  if (Object.prototype.hasOwnProperty.call(record, header)) return record[header];
  const direct = {
    序号: ["sequence_number", "index"],
    实验日期: ["experiment_date"],
    样品名: ["sample_name"],
    组分名称: ["component_name"],
    峰序号: ["peak_ordinal", "selected_peak_ordinal"],
    "出峰时间(min)": ["retention_time_min", "RT（min）"],
    茴香亚砜峰序号: ["sulfoxide_peak_ordinal"],
    "茴香亚砜出峰时间(min)": ["sulfoxide_retention_time_min"],
    茴香亚砜峰面积: ["sulfoxide_area"],
    茴香砜峰序号: ["sulfone_peak_ordinal"],
    "茴香砜出峰时间(min)": ["sulfone_retention_time_min"],
    茴香砜峰面积: ["sulfone_area"],
    茴香硫醚峰序号: ["thioanisole_peak_ordinal"],
    "茴香硫醚出峰时间(min)": ["thioanisole_retention_time_min"],
    茴香硫醚峰面积: ["thioanisole_area"],
    "RT（min）": ["retention_time_min"],
    "标称 RT（min）": ["nominal_rt_min"],
    "RT 偏差（min）": ["rt_deviation_min"],
    峰面积: ["area"],
    "上机液浓度（mM）": ["injection_concentration_mM"],
    "原反应液浓度（mM）": ["reaction_concentration_mM"],
    峰匹配状态: ["match_status"],
    数据质量: ["data_quality"],
    是否参与最终计算: ["participates_in_final"],
    处理方式: ["process_method"],
    实际采集时间: ["actual_acquisition_time"],
    采集方法: ["采集方法", "方法", "acquisition_method", "method_name", "method", "processing_method", "处理方法"],
    方法: ["方法", "采集方法", "acquisition_method", "method_name", "method", "processing_method", "处理方法"],
    序列名称: ["sequence_name"],
    OpenLab结果名称: ["result_name"],
    原始文件名: ["raw_file"],
  };
  return direct[header] ? firstPresent(record, direct[header]) : null;
}

function processingLogValue(record, header) {
  if (Object.prototype.hasOwnProperty.call(record, header)) return record[header];
  const direct = {
    处理时间: ["processed_at"],
    实验日期: ["experiment_date"],
    样品名: ["sample_name"],
    重打组ID: ["rerun_group_id"],
    原始文件: ["raw_files", "raw_file"],
    操作类型: ["operation_type"],
    判断依据: ["basis"],
    处理前状态: ["before_status"],
    处理后结果: ["after_result"],
    使用的数据: ["used_data"],
    舍弃的数据: ["discarded_data"],
    详细说明: ["details"],
  };
  return direct[header] ? firstPresent(record, direct[header]) : null;
}

function excludedDataValue(record, header) {
  if (Object.prototype.hasOwnProperty.call(record, header)) return record[header];
  const direct = {
    实验日期: ["experiment_date"],
    样品名: ["sample_name"],
    进样ID: ["injection_id"],
    排除原因: ["reason"],
    详细说明: ["details"],
    实际采集时间: ["acquisition_time", "actual_acquisition_time"],
    序列名称: ["sequence_name"],
    OpenLab结果名称: ["result_name"],
    日期文件夹: ["batch_folder"],
    原始文件名: ["raw_file"],
    原始文件路径: ["source_relative", "source_path"],
  };
  return direct[header] ? firstPresent(record, direct[header]) : null;
}

function rerunDetailValue(record, header) {
  if (Object.prototype.hasOwnProperty.call(record, header)) return record[header];
  const direct = {
    重打组ID: ["rerun_group_id"],
    实验日期: ["experiment_date"],
    样品名: ["sample_name"],
    归一化样品名: ["normalized_sample_name"],
    进样ID: ["injection_id"],
    序列名称: ["sequence_name"],
    OpenLab结果名称: ["result_name"],
    实际采集时间: ["acquisition_time", "actual_acquisition_time"],
    重打判断依据: ["evidence"],
    数据质量: ["data_quality"],
    是否参与平均: ["participates_in_average"],
    是否最终采用: ["final_use"],
    舍弃原因: ["discard_reason"],
    原始文件名: ["raw_file"],
    原始文件路径: ["source_relative", "source_path"],
  };
  return direct[header] ? firstPresent(record, direct[header]) : null;
}

function manualReviewValue(record, header) {
  if (Object.prototype.hasOwnProperty.call(record, header)) return record[header];
  const direct = {
    实验日期: ["experiment_date"],
    样品名: ["sample_name"],
    进样ID: ["injection_ids", "injection_id"],
    问题类型: ["issue_type"],
    问题原因: ["reason"],
    建议操作: ["recommended_action"],
    状态: ["status"],
  };
  return direct[header] ? firstPresent(record, direct[header]) : null;
}

function parameterValue(record, header) {
  const direct = {
    分类: ["category"],
    参数: ["parameter"],
    值: ["value"],
    单位: ["unit"],
    来源: ["source"],
  };
  const value = Object.prototype.hasOwnProperty.call(record, header)
    ? record[header]
    : (direct[header] ? firstPresent(record, direct[header]) : null);
  if (
    header === "值"
    && typeof value === "string"
    && String(firstPresent(record, ["参数", "parameter"], "")).includes("时间")
  ) {
    return localDate(value) || value;
  }
  return value;
}

function resolveAnalysisSource(analysis, rowKeys, columnKeys, defaultColumns) {
  let source = null;
  for (const key of rowKeys) {
    if (analysis[key] !== undefined && analysis[key] !== null) {
      source = analysis[key];
      break;
    }
  }
  let rows = [];
  let embeddedColumns = null;
  if (Array.isArray(source)) {
    rows = source;
  } else if (source && typeof source === "object") {
    rows = Array.isArray(source.rows) ? source.rows : [];
    embeddedColumns = Array.isArray(source.columns) ? source.columns : null;
  }
  let columns = embeddedColumns;
  if (!columns) {
    for (const key of columnKeys) {
      if (Array.isArray(analysis[key])) {
        columns = analysis[key];
        break;
      }
    }
  }
  return {
    rows,
    sourceColumns: columns || defaultColumns,
  };
}

function normalizePeakColumns(columns) {
  const source = Array.from(columns || ANALYSIS_PEAK_COLUMNS);
  if (!source.includes("组分名称")) return source;
  const foundComponentIndex = source.indexOf("组分名称");
  const componentIndex = foundComponentIndex >= 0
    ? foundComponentIndex
    : Math.min(3, Math.max(0, source.length - 1));
  const prefix = source.slice(0, componentIndex + 1);
  const suffix = source.filter((header, index) => (
    index > componentIndex
    && !["峰序号", "RT（min）", "出峰时间(min)", "出峰时间（min）"].includes(header)
  ));
  return [...prefix, "峰序号", "出峰时间(min)", ...suffix];
}

function normalizeSingleMethodColumn(columns) {
  const methodHeaders = new Set(["采集方法", "方法", "处理方法"]);
  let methodWritten = false;
  const normalized = [];
  for (const header of columns) {
    if (!methodHeaders.has(header)) {
      normalized.push(header);
      continue;
    }
    if (methodWritten) continue;
    normalized.push(header === "方法" ? "方法" : "采集方法");
    methodWritten = true;
  }
  return normalized;
}

function analysisColumnWidth(header) {
  if (header === "序号" || header.endsWith("峰序号")) return 10;
  if (header === "实验日期") return 12;
  if (["实际采集时间", "采集时间", "处理时间"].includes(header)) return 20;
  if (header.includes("RT") || header.includes("出峰时间")) return 14;
  if (header.includes("峰面积")) return 16;
  if (header.includes("浓度") || header.startsWith("C₀")) return 18;
  if (header.includes("（%）") || header.includes("(%)")) return 15;
  if (header.includes("原始文件路径")) return 48;
  if (header.includes("原始文件")) return 32;
  if (["处理说明", "详细说明", "判断依据", "问题原因", "建议操作"].includes(header)) return 42;
  if (["使用数据组", "舍弃数据组", "使用的数据", "舍弃的数据", "重打判断依据"].includes(header)) return 34;
  if (["序列名称", "OpenLab结果名称", "日期文件夹", "采集方法", "方法"].includes(header)) return 30;
  if (["样品名", "归一化样品名"].includes(header)) return 24;
  if (["数据质量", "处理方式", "峰匹配状态", "排除原因", "问题类型"].includes(header)) return 20;
  return 16;
}

function isAnalysisNumericHeader(header) {
  return (
    ["序号", "反应时间（h）"].includes(header)
    || header.endsWith("峰序号")
    || header.includes("RT")
    || header.includes("出峰时间")
    || header.includes("峰面积")
    || header.includes("浓度")
    || header.startsWith("C₀")
    || header.includes("（%）")
    || header.includes("(%)")
  );
}

function applyAnalysisFormats(sheet, headers, lastRow) {
  if (lastRow <= 1) return;
  headers.forEach((header, index) => {
    const column = excelColumn(index);
    const range = `${column}2:${column}${lastRow}`;
    if (header === "实验日期") formatRange(sheet, range, "yyyy-mm-dd");
    else if (["实际采集时间", "采集时间", "处理时间"].includes(header)) {
      formatRange(sheet, range, "yyyy-mm-dd hh:mm:ss");
    } else if (header.includes("（%）") || header.includes("(%)")) {
      formatRange(sheet, range, "0.00%");
    } else if (header.includes("RT") || header.includes("出峰时间")) {
      formatRange(sheet, range, "0.000");
    } else if (header.includes("峰面积")) {
      formatRange(sheet, range, "#,##0.000");
    } else if (header.includes("浓度") || header.startsWith("C₀")) {
      formatRange(sheet, range, "0.0000");
    } else if (header === "反应时间（h）") {
      formatRange(sheet, range, "0.###");
    } else if (header === "序号" || header.endsWith("峰序号")) {
      formatRange(sheet, range, "#,##0");
    }
    if (isAnalysisNumericHeader(header)) {
      sheet.getRange(range).format.horizontalAlignment = "right";
    }
  });
}

function writeAnalysisTable(
  workbook,
  analysis,
  {
    sheetName,
    rowKeys,
    columnKeys,
    defaultColumns,
    valueGetter,
    tableName,
    peakColumns = false,
    singleMethodColumn = false,
    postFormat = null,
  },
) {
  const source = resolveAnalysisSource(analysis, rowKeys, columnKeys, defaultColumns);
  let headers = peakColumns ? normalizePeakColumns(source.sourceColumns) : source.sourceColumns;
  if (singleMethodColumn) headers = normalizeSingleMethodColumn(headers);
  const records = source.rows.map((row) => {
    if (!Array.isArray(row)) return row || {};
    return Object.fromEntries(source.sourceColumns.map((header, index) => [header, row[index] ?? null]));
  });
  const rows = records.map((record) => headers.map((header) => (
    normalizeAnalysisCell(header, valueGetter(record, header))
  )));
  const sheet = workbook.worksheets.add(sheetName);
  const wrapColumns = headers
    .map((header, index) => (
      analysisColumnWidth(header) >= 30 ? excelColumn(index) : null
    ))
    .filter(Boolean);
  const spec = writeDataSheet(sheet, headers, rows, {
    widths: headers.map((header) => analysisColumnWidth(header)),
    wrapColumns,
    rowHeight: 24,
    headerRowHeight: 26,
    previewRows: 10,
    tableName,
  });
  applyAnalysisFormats(sheet, headers, spec.lastRow);
  if (postFormat) postFormat(sheet, headers, records, spec.lastRow);
  return {
    name: sheetName,
    range: spec.previewRange,
    inspectMaxCols: headers.length,
  };
}

function applyParameterFormats(sheet, headers, records, lastRow) {
  if (lastRow <= 1) return;
  const valueColumnIndex = headers.indexOf("值");
  if (valueColumnIndex < 0) return;
  const valueColumn = excelColumn(valueColumnIndex);
  records.forEach((record, index) => {
    const parameter = String(firstPresent(record, ["参数", "parameter"], ""));
    if (parameter.includes("时间")) {
      formatRange(sheet, `${valueColumn}${index + 2}`, "yyyy-mm-dd hh:mm:ss");
    }
  });
}

function analysisWorkbook() {
  const workbook = Workbook.create();
  const analysis = dataset.analysis;
  const sheetSpecs = [
    writeAnalysisTable(workbook, analysis, {
      sheetName: "样品结果",
      rowKeys: ["sample_result_rows", "sample_results"],
      columnKeys: ["sample_result_columns", "main_result_columns"],
      defaultColumns: ANALYSIS_MAIN_COLUMNS,
      valueGetter: mainResultValue,
      tableName: "HplcSampleResults",
      singleMethodColumn: true,
    }),
    writeAnalysisTable(workbook, analysis, {
      sheetName: "峰明细",
      rowKeys: ["peak_detail_rows", "peak_details"],
      columnKeys: ["peak_detail_columns"],
      defaultColumns: ANALYSIS_PEAK_COLUMNS,
      valueGetter: peakDetailValue,
      tableName: "HplcPeakDetails",
      peakColumns: true,
      singleMethodColumn: true,
    }),
    writeAnalysisTable(workbook, analysis, {
      sheetName: "数据处理记录",
      rowKeys: ["processing_log_rows", "processing_log"],
      columnKeys: ["processing_log_columns"],
      defaultColumns: ANALYSIS_LOG_COLUMNS,
      valueGetter: processingLogValue,
      tableName: "HplcProcessingLog",
    }),
    writeAnalysisTable(workbook, analysis, {
      sheetName: "排除数据",
      rowKeys: ["excluded_data_rows", "excluded_data"],
      columnKeys: ["excluded_data_columns"],
      defaultColumns: ANALYSIS_EXCLUDED_COLUMNS,
      valueGetter: excludedDataValue,
      tableName: "HplcExcludedData",
    }),
    writeAnalysisTable(workbook, analysis, {
      sheetName: "重打分组明细",
      rowKeys: ["rerun_group_detail_rows", "rerun_group_details"],
      columnKeys: ["rerun_group_detail_columns"],
      defaultColumns: ANALYSIS_RERUN_COLUMNS,
      valueGetter: rerunDetailValue,
      tableName: "HplcRerunGroups",
    }),
    writeAnalysisTable(workbook, analysis, {
      sheetName: "待人工复核",
      rowKeys: ["manual_review_rows", "manual_review"],
      columnKeys: ["manual_review_columns"],
      defaultColumns: ANALYSIS_REVIEW_COLUMNS,
      valueGetter: manualReviewValue,
      tableName: "HplcManualReview",
    }),
    writeAnalysisTable(workbook, analysis, {
      sheetName: "分析参数",
      rowKeys: ["parameter_rows", "parameters"],
      columnKeys: ["parameter_columns"],
      defaultColumns: ANALYSIS_PARAMETER_COLUMNS,
      valueGetter: parameterValue,
      tableName: "HplcAnalysisParameters",
      postFormat: applyParameterFormats,
    }),
  ];
  return { workbook, sheetSpecs };
}

const batchPlanByName = new Map(
  dataset.workbook_plan.batch_workbooks.map((item) => [item.batch_folder, item]),
);

function appendIndexValue(index, key, value) {
  let values = index.get(key);
  if (!values) {
    values = [];
    index.set(key, values);
  }
  values.push(value);
}

function buildWorkbookIndexes() {
  const batches = new Map();
  const resultSetsByPlan = new Map();
  const plansByResultSet = new Map();
  const peaksByResultSetAndInjection = new Map();
  function batchIndex(batchFolder) {
    let batch = batches.get(batchFolder);
    if (!batch) {
      batch = { injections: [], injectionsByResultSet: new Map(), peakCount: 0 };
      batches.set(batchFolder, batch);
    }
    return batch;
  }
  for (const plan of dataset.workbook_plan.batch_workbooks) {
    batchIndex(plan.batch_folder);
    resultSetsByPlan.set(plan, []);
    for (const resultSetId of new Set(plan.result_set_ids)) {
      appendIndexValue(plansByResultSet, resultSetId, plan);
    }
  }
  // Scan source arrays in order so indexes retain the previous filter ordering.
  for (const resultSet of dataset.result_sets) {
    for (const plan of plansByResultSet.get(resultSet.result_set_id) || []) {
      resultSetsByPlan.get(plan).push(resultSet);
    }
  }
  for (const injection of dataset.injections) {
    const batch = batchIndex(injection.batch_folder);
    batch.injections.push(injection);
    appendIndexValue(batch.injectionsByResultSet, injection.result_set_id, injection);
  }
  for (const peak of dataset.peaks) {
    batchIndex(peak.batch_folder).peakCount += 1;
    let peaksByInjection = peaksByResultSetAndInjection.get(peak.result_set_id);
    if (!peaksByInjection) {
      peaksByInjection = new Map();
      peaksByResultSetAndInjection.set(peak.result_set_id, peaksByInjection);
    }
    appendIndexValue(peaksByInjection, peak.injection_id, peak);
  }
  for (const peaksByInjection of peaksByResultSetAndInjection.values()) {
    for (const peaks of peaksByInjection.values()) {
      peaks.sort((left, right) => Number(left.peak_ordinal) - Number(right.peak_ordinal));
    }
  }
  return { batches, resultSetsByPlan, peaksByResultSetAndInjection };
}

const workbookIndexes = buildWorkbookIndexes();

function summaryWorkbook() {
  const workbook = Workbook.create();
  const usage = workbook.worksheets.add("使用说明");
  const batchIndex = workbook.worksheets.add("批次索引");
  const sampleIndex = workbook.worksheets.add("样品索引");
  const batchCount = dataset.workbook_plan.batch_workbooks.length;

  const usageSpec = writeKeyValueSheet(usage, [
    ["输出用途", "快速查看各进样批次、样品信息、方法及 OpenLab 原积分峰面积。"],
    ["筛选起始日期（含）", dataset.cutoff_date],
    ["文件拆分规则", `1 个总索引工作簿 + ${batchCount} 个顶层采集批次工作簿。`],
    [
      "工作表拆分规则",
      "每个批次工作簿含“样品信息”，并按每个 .rslt 结果集建立独立峰面积表；"
      + "峰面积表每个进样/样品只占一行，峰序号、出峰时间、峰面积和面积百分比按换行一一对齐。",
    ],
    ["顶层采集批次数", dataset.summary.batch_count],
    ["OpenLab 结果集数", dataset.summary.result_set_count],
    ["进样数", dataset.summary.selected_injection_count],
    ["OpenLab 原积分峰数", dataset.summary.peak_count],
    [
      "原始信号处理",
      `${dataset.summary.signal_point_count.toLocaleString("en-US")} 个原始信号点已完整解码和校验，`
      + "为避免 Excel 杂乱，不在用户工作簿中逐点列出；审计数据仍保存在 processed_data 数据集中。",
    ],
    [
      "科学边界",
      "峰表仅保留 OpenLab 原积分结果；保留时间和峰名不自动等同于化学身份，"
      + "未提供标曲与角色映射时不计算转化率、选择性或产率。",
    ],
  ]);

  const batchHeaders = [
    "批次ID",
    "批次文件夹",
    "结果集ID",
    "结果集文件夹",
    "首次采集",
    "末次采集",
    "进样数",
    "OpenLab峰数",
    "方法",
    "批次工作簿",
  ];
  const batchRows = dataset.result_sets.map((item) => {
    const plan = batchPlanByName.get(item.batch_folder);
    return [
      plan.batch_id,
      item.batch_folder,
      item.result_set_id,
      item.result_set_folder,
      localDate(item.first_acquisition_local),
      localDate(item.last_acquisition_local),
      item.injection_count,
      item.peak_count,
      methodListText(item),
      plan.relative_path,
    ];
  });
  const batchSpec = writeDataSheet(
    batchIndex,
    batchHeaders,
    batchRows,
    {
      widths: [9, 30, 10, 34, 19, 19, 10, 12, 42, 52],
      wrapColumns: ["B", "D", "I", "J"],
      rowHeight: 42,
    },
  );
  formatRange(batchIndex, `E2:F${batchSpec.lastRow}`, "yyyy-mm-dd hh:mm:ss");
  formatRange(batchIndex, `G2:H${batchSpec.lastRow}`, "#,##0");

  const sampleHeaders = [
    "批次文件夹",
    "结果集ID",
    "进样ID",
    "样品名",
    "采集时间",
    "方法",
    "OpenLab峰数",
    "峰面积合计",
    "面积百分比合计(%)",
    "瓶位",
    "进样体积(µL)",
    "检测器/波长",
    "结果集文件夹",
  ];
  const sampleRows = dataset.injections.map((item) => [
    item.batch_folder,
    item.result_set_id,
    item.injection_id,
    item.sample_name,
    localDate(item.acquisition_local),
    methodText(item),
    item.vendor_peak_count,
    item.vendor_peak_area_total,
    item.vendor_area_percent_sum,
    item.vial_position,
    item.injection_volume_ul,
    detectorText(item),
    item.result_set_folder,
  ]);
  const sampleSpec = writeDataSheet(
    sampleIndex,
    sampleHeaders,
    sampleRows,
    {
      widths: [30, 10, 10, 28, 19, 42, 12, 17, 19, 10, 14, 18, 34],
      wrapColumns: ["A", "D", "F", "L", "M"],
      rowHeight: 42,
    },
  );
  formatRange(sampleIndex, `E2:E${sampleSpec.lastRow}`, "yyyy-mm-dd hh:mm:ss");
  formatRange(sampleIndex, `G2:G${sampleSpec.lastRow}`, "#,##0");
  formatRange(sampleIndex, `H2:I${sampleSpec.lastRow}`, "0.0000");
  formatRange(sampleIndex, `K2:K${sampleSpec.lastRow}`, "0.0");

  return {
    workbook,
    sheetSpecs: [
      { name: "使用说明", range: usageSpec.previewRange },
      { name: "批次索引", range: batchSpec.previewRange },
      { name: "样品索引", range: sampleSpec.previewRange },
    ],
  };
}

function batchWorkbook(batchPlan) {
  const workbook = Workbook.create();
  const batch = workbookIndexes.batches.get(batchPlan.batch_folder);
  const batchInjections = batch.injections;
  const resultSets = workbookIndexes.resultSetsByPlan.get(batchPlan);
  const firstAcquisition = batchInjections[0]?.acquisition_local || "";
  const lastAcquisition = batchInjections.at(-1)?.acquisition_local || "";

  const description = workbook.worksheets.add("批次说明");
  const descriptionSpec = writeKeyValueSheet(description, [
    ["批次ID", batchPlan.batch_id],
    ["批次文件夹", batchPlan.batch_folder],
    ["结果集", resultSets.map((item) => `${item.result_set_id}: ${item.result_set_folder}`).join("；")],
    ["首次采集", firstAcquisition.replace("T", " ")],
    ["末次采集", lastAcquisition.replace("T", " ")],
    ["进样数", batchInjections.length],
    ["OpenLab 原积分峰数", batch.peakCount],
    ["方法", uniqueText(batchInjections.map((item) => methodText(item)))],
    ["原始信号", "已完整解码和校验，但按简洁输出要求不在 Excel 中逐点列出。"],
    ["人工复核", "所有峰身份、积分边界及后续定量结论均需人工复核。"],
  ]);

  const samples = workbook.worksheets.add("样品信息");
  const sampleHeaders = [
    "结果集ID",
    "进样ID",
    "样品名",
    "采集时间",
    "方法",
    "OpenLab峰数",
    "峰面积合计",
    "面积百分比合计(%)",
    "瓶位",
    "进样体积(µL)",
    "检测器/波长",
    "结果集文件夹",
    "原始数据文件",
  ];
  const sampleRows = batchInjections.map((item) => [
    item.result_set_id,
    item.injection_id,
    item.sample_name,
    localDate(item.acquisition_local),
    methodText(item),
    item.vendor_peak_count,
    item.vendor_peak_area_total,
    item.vendor_area_percent_sum,
    item.vial_position,
    item.injection_volume_ul,
    detectorText(item),
    item.result_set_folder,
    item.raw_file,
  ]);
  const sampleSpec = writeDataSheet(
    samples,
    sampleHeaders,
    sampleRows,
    {
      widths: [10, 10, 28, 19, 42, 12, 17, 19, 10, 14, 18, 34, 32],
      wrapColumns: ["C", "E", "K", "L", "M"],
      rowHeight: 42,
    },
  );
  formatRange(samples, `D2:D${sampleSpec.lastRow}`, "yyyy-mm-dd hh:mm:ss");
  formatRange(samples, `F2:F${sampleSpec.lastRow}`, "#,##0");
  formatRange(samples, `G2:H${sampleSpec.lastRow}`, "0.0000");
  formatRange(samples, `J2:J${sampleSpec.lastRow}`, "0.0");

  const sheetSpecs = [
    { name: "批次说明", range: descriptionSpec.previewRange },
    { name: "样品信息", range: sampleSpec.previewRange },
  ];
  const peakHeaders = [
    "进样批次名",
    "结果集文件夹",
    "样品名",
    "进样ID",
    "采集时间",
    "方法",
    "峰数",
    "峰序号",
    "出峰时间(min)",
    "峰面积",
    "面积单位",
    "面积百分比(%)",
    "需要人工复核",
  ];
  for (const resultSet of resultSets) {
    const sheetName = `${resultSet.result_set_id}_峰面积`;
    const sheet = workbook.worksheets.add(sheetName);
    const resultSetInjections = batch.injectionsByResultSet.get(resultSet.result_set_id) || [];
    const peaksByInjection = workbookIndexes.peaksByResultSetAndInjection
      .get(resultSet.result_set_id) || new Map();
    const peakRows = resultSetInjections.map((injection) => {
      const peaks = peaksByInjection.get(injection.injection_id) || [];
      return [
        injection.batch_folder,
        injection.result_set_folder,
        injection.sample_name,
        injection.injection_id,
        localDate(injection.acquisition_local),
        methodText(injection),
        peaks.length,
        alignedIntegerText(peaks.map((item) => item.peak_ordinal)),
        alignedNumberText(peaks.map((item) => item.retention_time_min)),
        alignedNumberText(peaks.map((item) => item.area)),
        uniqueText(peaks.map((item) => item.area_unit)),
        alignedNumberText(peaks.map((item) => item.area_percent)),
        peaks.some((item) => item.manual_check_required) ? "是" : "否",
      ];
    });
    const peakSpec = writeDataSheet(
      sheet,
      peakHeaders,
      peakRows,
      {
        widths: [28, 32, 26, 10, 19, 42, 8, 10, 16, 18, 12, 18, 15],
        wrapColumns: ["A", "B", "C", "F", "H", "I", "J", "L"],
        rowHeight: 42,
      },
    );
    formatRange(sheet, `E2:E${peakSpec.lastRow}`, "yyyy-mm-dd hh:mm:ss");
    formatRange(sheet, `G2:G${peakSpec.lastRow}`, "#,##0");
    resultSetInjections.forEach((injection, index) => {
      const peakCount = (peaksByInjection.get(injection.injection_id) || []).length;
      const rowNumber = index + 2;
      const rowRange = sheet.getRange(`A${rowNumber}:M${rowNumber}`);
      rowRange.format.rowHeight = Math.min(140, Math.max(34, 18 + peakCount * 16));
      rowRange.format.verticalAlignment = "top";
    });
    sheetSpecs.push({ name: sheetName, range: peakSpec.previewRange });
  }

  return { workbook, sheetSpecs };
}

async function verifyAndRenderWorkbook(
  workbook,
  {
    label,
    output,
    previewDirectory,
    sheetSpecs,
    kind,
    batchFolder = null,
  },
) {
  await fs.mkdir(previewDirectory, { recursive: true });
  const inspections = {};
  const previewFiles = [];
  for (let index = 0; index < sheetSpecs.length; index += 1) {
    const spec = sheetSpecs[index];
    inspections[spec.name] = (
      await workbook.inspect({
        kind: "table",
        range: `${spec.name}!${spec.range}`,
        include: "values,formulas",
        tableMaxRows: 12,
        tableMaxCols: spec.inspectMaxCols || 16,
        maxChars: spec.inspectMaxCols > 16 ? 12000 : 7000,
      })
    ).ndjson;
    const rendered = await workbook.render({
      sheetName: spec.name,
      range: spec.range,
      scale: 1,
      format: "png",
    });
    const previewPath = path.join(
      previewDirectory,
      `${String(index + 1).padStart(2, "0")}_${safePreviewName(spec.name)}.png`,
    );
    await fs.writeFile(previewPath, new Uint8Array(await rendered.arrayBuffer()));
    previewFiles.push(previewPath);
  }
  inspections.formulaErrors = (
    await workbook.inspect({
      kind: "match",
      searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
      options: { useRegex: true, maxResults: 300 },
      summary: `${label} final formula error scan`,
    })
  ).ndjson;

  // Rendering/inspection must not weaken the exported navigation contract.
  // Re-apply the frozen header immediately before serialization.
  for (const spec of sheetSpecs) {
    workbook.worksheets.getItem(spec.name).freezePanes.freezeRows(1);
  }

  const exported = await SpreadsheetFile.exportXlsx(workbook);
  await exported.save(output);
  return {
    label,
    kind,
    batch_folder: batchFolder,
    path: output,
    sheet_count: sheetSpecs.length,
    sheets: sheetSpecs.map((item) => item.name),
    preview_files: previewFiles,
    inspections,
  };
}

const verification = {
  title: dataset.analysis
    ? "Agilent OpenLab HPLC analysis-workbook verification"
    : "Agilent OpenLab HPLC split-workbook verification",
  summary: dataset.summary,
  output_layout: dataset.workbook_plan,
  workbooks: [],
};

const summary = dataset.analysis ? analysisWorkbook() : summaryWorkbook();
verification.workbooks.push(
  await verifyAndRenderWorkbook(summary.workbook, {
    label: dataset.analysis ? "HPLC分析结果" : "总索引",
    kind: dataset.analysis ? "analysis" : "summary",
    output: outputPath,
    previewDirectory: path.join(previewRoot, "00_总索引"),
    sheetSpecs: summary.sheetSpecs,
  }),
);

for (const batchPlan of dataset.workbook_plan.batch_workbooks) {
  const built = batchWorkbook(batchPlan);
  const batchOutput = path.resolve(outputDir, batchPlan.relative_path);
  if (
    batchOutput !== outputDir
    && !batchOutput.startsWith(`${outputDir}${path.sep}`)
  ) {
    throw new Error(`Batch workbook path escapes output root: ${batchPlan.relative_path}`);
  }
  await fs.mkdir(path.dirname(batchOutput), { recursive: true });
  verification.workbooks.push(
    await verifyAndRenderWorkbook(built.workbook, {
      label: `${batchPlan.batch_id} ${batchPlan.batch_folder}`,
      kind: "batch",
      batchFolder: batchPlan.batch_folder,
      output: batchOutput,
      previewDirectory: path.join(
        previewRoot,
        `${batchPlan.batch_id}_${safePreviewName(batchPlan.batch_folder)}`,
      ),
      sheetSpecs: built.sheetSpecs,
    }),
  );
}

verification.workbook_count = verification.workbooks.length;
verification.sheet_count = verification.workbooks.reduce(
  (total, item) => total + item.sheet_count,
  0,
);
verification.preview_count = verification.workbooks.reduce(
  (total, item) => total + item.preview_files.length,
  0,
);
await fs.writeFile(verificationPath, JSON.stringify(verification, null, 2), "utf8");

console.log(`workbook=${outputPath}`);
console.log(`workbook_count=${verification.workbook_count}`);
console.log(`sheet_count=${verification.sheet_count}`);
console.log(`injections=${dataset.summary.selected_injection_count}`);
console.log(`peaks=${dataset.summary.peak_count}`);
