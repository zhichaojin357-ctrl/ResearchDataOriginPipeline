# HPLC/LC Output Routing Review

Date: 2026-06-04

## Scope

This review covers run-scoped no-Origin output routing and metadata plot intent for synthetic HPLC/LC exported data.

## Verified Run-Scoped Contract

The output routing tests call `process_table_dataset()` with `output_root=layout.root`, where `layout` is created by `create_run_output_layout()`.

For every synthetic case, the tests assert:

- `run_output_root` starts with `output/runs/`;
- `metadata_path` is under the run root metadata directory;
- `processed_data` is under the run root processed-data directory;
- `origin_file` is `None`;
- `figure_tif` is `None`;
- `preview_png` is `None`;
- no root `output/metadata`;
- no root `output/processed_data`;
- no root `output/origin_files`;
- no root `output/figures_tif`;
- no root `output/figures_preview`.

## Verified Plot Intents

Chromatogram:

- candidate: true;
- plot type: `chromatogram`;
- x-axis: `retention_time_min`;
- y-axis: `signal`;
- manual check required.

Peak table:

- candidate: true;
- plot type: `peak_table_summary`;
- x-axis: `retention_time_min`;
- y-axis: `peak_area_optional`;
- peak names preserved only as labels, not identities;
- no conversion candidate.

Calibration:

- candidate: true;
- plot type: `calibration_curve`;
- x-axis: `concentration`;
- y-axis: `response`;
- slope, intercept, and R squared are candidate values;
- manual check required.

No-calibration peak table:

- peak-table plot intent only;
- `requires_manual_calibration` boundary;
- no conversion, selectivity, or yield candidate.

Ambiguous table:

- processing status: `manual_review`;
- plot type: `manual_review`;
- no plot candidate;
- missing fields recorded.

## Safety Conclusion

The no-Origin HPLC/LC module can record candidate plot intent in run-scoped metadata without writing real output artifacts or invoking Origin.
