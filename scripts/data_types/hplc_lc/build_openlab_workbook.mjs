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
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})/,
  );
  if (!match) return null;
  return new Date(Date.UTC(
    Number(match[1]),
    Number(match[2]) - 1,
    Number(match[3]),
    Number(match[4]),
    Number(match[5]),
    Number(match[6]),
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

function styleHeader(range) {
  range.format = {
    fill: COLORS.headerFill,
    font: { bold: true, color: COLORS.text },
    verticalAlignment: "center",
    horizontalAlignment: "center",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: COLORS.border },
  };
  range.format.rowHeight = 28;
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
    previewRows = 12,
  } = {},
) {
  const matrix = [headers, ...rows];
  const lastColumn = excelColumn(headers.length - 1);
  const lastRow = matrix.length;
  const target = sheet.getRange(`A1:${lastColumn}${lastRow}`);
  target.values = matrix;
  styleHeader(sheet.getRange(`A1:${lastColumn}1`));
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

const batchPlanByName = new Map(
  dataset.workbook_plan.batch_workbooks.map((item) => [item.batch_folder, item]),
);

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
  const batchInjections = dataset.injections.filter(
    (item) => item.batch_folder === batchPlan.batch_folder,
  );
  const resultSets = dataset.result_sets.filter(
    (item) => batchPlan.result_set_ids.includes(item.result_set_id),
  );
  const batchPeaks = dataset.peaks.filter(
    (item) => item.batch_folder === batchPlan.batch_folder,
  );
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
    ["OpenLab 原积分峰数", batchPeaks.length],
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
    const resultSetInjections = batchInjections.filter(
      (item) => item.result_set_id === resultSet.result_set_id,
    );
    const peaksByInjection = new Map();
    for (const peak of dataset.peaks.filter(
      (item) => item.result_set_id === resultSet.result_set_id,
    )) {
      const peaks = peaksByInjection.get(peak.injection_id) || [];
      peaks.push(peak);
      peaksByInjection.set(peak.injection_id, peaks);
    }
    const peakRows = resultSetInjections.map((injection) => {
      const peaks = (peaksByInjection.get(injection.injection_id) || [])
        .sort((left, right) => Number(left.peak_ordinal) - Number(right.peak_ordinal));
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
        tableMaxCols: 16,
        maxChars: 7000,
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
  title: "Agilent OpenLab HPLC split-workbook verification",
  summary: dataset.summary,
  output_layout: dataset.workbook_plan,
  workbooks: [],
};

const summary = summaryWorkbook();
verification.workbooks.push(
  await verifyAndRenderWorkbook(summary.workbook, {
    label: "总索引",
    kind: "summary",
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
