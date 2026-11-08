// Structured Excel export used only by the formal chi-electrochem branch.
import fs from 'node:fs/promises';
import path from 'node:path';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const [manifest, root] = process.argv.slice(2);
const definitions = JSON.parse(await fs.readFile(manifest, 'utf8'));
const evidence = [];
for (const definition of definitions) {
  const workbook = Workbook.create();
  for (const data of definition.sheets) {
    const sheet = workbook.worksheets.add(data.name);
    const n = data.headers.length;
    const rows = data.rows.length + 1;
    sheet.getRangeByIndexes(0, 0, rows, n).values = [data.headers, ...data.rows];
    const used = sheet.getRangeByIndexes(0, 0, rows, n);
    used.format.font = { name: 'Microsoft YaHei', size: 10 };
    used.format.rowHeight = 20;
    used.format.columnWidth = 19;
    sheet.getRangeByIndexes(0, 0, 1, n).format = { fill: '#E7E6E6', font: { bold: true }, wrapText: true, rowHeight: 36, horizontalAlignment: 'center' };
    sheet.showGridLines = false;
    sheet.freezePanes.freezeRows(1);
    data.headers.forEach((header, col) => {
      if (/文件|OPJU|原文件|整理后|source_file|条件|频率_Hz/.test(header)) sheet.getRangeByIndexes(0, col, rows, 1).format.columnWidth = /文件/.test(header) ? 48 : 30;
      if (/Cs_F|F-2|relative_error/.test(header) && data.rows.length) sheet.getRangeByIndexes(1, col, data.rows.length, 1).setNumberFormat('0.0000000000E+00');
    });
    if (data.calculation_formulas) {
      const freq = data.headers.indexOf('frequency_Hz');
      const zimag = data.headers.indexOf('Zimag_ohm');
      const cs = data.headers.indexOf('Cs_F');
      const inv = data.headers.indexOf('one_over_Cs_squared_F-2');
      const letter = n => String.fromCharCode(65+n);
      sheet.getRangeByIndexes(1, cs, data.rows.length, 1).formulas = data.rows.map((p, i) => [p[cs] === null ? '' : `=-1/(2*PI()*${letter(freq)}${i+2}*${letter(zimag)}${i+2})`]);
      sheet.getRangeByIndexes(1, inv, data.rows.length, 1).formulas = data.rows.map((p, i) => [p[inv] === null ? '' : `=1/(${letter(cs)}${i+2}*${letter(cs)}${i+2})`]);
    }
  }
  workbook.recalculate();
  for (const data of definition.sheets) {
    const sheet = workbook.worksheets.getItem(data.name);
    const actual = sheet.getRangeByIndexes(1, 0, data.rows.length, data.headers.length).values;
    for (let i=0; i<data.rows.length; i++) for (let j=0; j<data.headers.length; j++) {
      const expected = data.rows[i][j], got = actual[i][j];
      if (typeof expected === 'number' ? (typeof got !== 'number' || Math.abs(got-expected) > Math.max(1e-20, Math.abs(expected)*1e-12)) : got !== expected && !(expected===null && got==='')) throw new Error(`Workbook round-trip mismatch ${definition.path}/${data.name}/${i}/${j}: ${got} vs ${expected}`);
    }
  }
  evidence.push({path: definition.path, verification: (await workbook.inspect({kind:'table', range:`'${definition.sheets[0].name}'!A1:F4`, include:'values,formulas', tableMaxRows:4, tableMaxCols:6, maxChars:1600})).ndjson});
  const output = path.join(root, definition.path);
  await fs.mkdir(path.dirname(output), {recursive:true});
  await (await SpreadsheetFile.exportXlsx(workbook)).save(output);
}
await fs.writeFile(path.join(root, '06_汇总与核查报告', 'Excel导出核查.json'), JSON.stringify(evidence, null, 2));
console.log(JSON.stringify({workbooks: definitions.length, cellsVerified:true}));
