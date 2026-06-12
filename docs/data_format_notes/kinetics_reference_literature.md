# Data Format Note: 动力学 Reference Literature Handling

## the current automated pipeline Classification
- Folder: `动力学`
- Inferred data type: `reference_literature`
- Supported in the current automated pipeline: `false`
- Selected processor: `none`
- Special handling: `scan_only`
- Deferred reason: `文献资料文件夹，不是实验动力学数据`

## Common File Formats
- `.pdf`, `.docx`, `.doc`, `.caj`, `.ris`, `.bib`, `.enl`, `.txt`, `.xlsx`
- Reference-manager exports or downloaded literature files.

## Automatic Recognition Signals
- Folder keyword: `动力学`.
- Literature/document extensions rather than numeric experiment exports.
- Citation metadata files such as RIS, BibTeX, or EndNote libraries.

## the current automated pipeline Handling
1. Register file paths, extensions, size, and hashes in inventory output.
2. Preserve folder and filename metadata.
3. Mark as `reference_literature`.
4. Do not analyze document body text.
5. Do not import into Origin and do not generate plots.

## Manual Checks Required
- Confirm folder is literature/reference material, not raw kinetic experiment data.
- Confirm whether any file should later be reclassified by explicit user override.

## Forbidden Actions and Claims
- Do not create a kinetics processor.
- Do not fit kinetic curves.
- Do not extract rate constants.
- Do not plot kinetics data.
- Do not treat this folder as supported experimental data in the current automated pipeline.
