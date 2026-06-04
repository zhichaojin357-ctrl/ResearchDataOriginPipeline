# HPLC/LC Process Integration Review

Date: 2026-06-04

## Scope

This review covers synthetic no-Origin process-level integration for `HPLC/LC exported data`.

No real HPLC/LC files were used. No Origin process was started. No repository `output/` or `outputs/` directories were modified.

## Formal Path

The integration test uses:

- `src.core.process.run_process()`;
- `src.core.process.ProcessOptions(no_origin=True, only_type="HPLC/LC exported data")`;
- `src.core.runtime_paths.create_run_output_layout()`;
- `src.processors.base.process_table_dataset()`;
- `src.processors.calculations` HPLC/LC candidate helpers.

This confirms that HPLC/LC candidates are not limited to a direct helper call; they pass through the formal no-Origin process path.

## Synthetic Inputs

The process integration test creates temporary CSV files under `tmp_path/input/raw_data/LC/`:

- synthetic chromatogram export;
- synthetic peak table export;
- synthetic calibration export;
- synthetic no-calibration quantification-like export.

These files are generated at test time and are not real experimental data.

## Verified Behavior

- Synthetic chromatogram export produces `lc_export_mode = chromatogram` and chromatogram plot intent.
- Synthetic peak table export produces `lc_export_mode = peak_table`, candidate peaks, and no product identity.
- Synthetic calibration export produces `lc_export_mode = calibration_curve`, a manual-check linear candidate, and calibration plot intent.
- Synthetic no-calibration export records `requires_manual_calibration` and blocks conversion, selectivity, and yield candidates.
- Metadata and processed CSVs are written under the temporary run root.
- No Origin call is made.
- No repository `output/` or `outputs/` pollution is produced.

## Remaining Blockers

- Real exported HPLC/LC files are still required for real-data validation.
- User-provided calibration and analyte mapping are required before real quantification.
- Origin and visual acceptance remain outside this no-Origin module goal.
