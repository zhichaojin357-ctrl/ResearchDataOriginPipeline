# Synthetic Fixture Golden Index

These are synthetic-only examples for pipeline regression tests. They are not real experimental data.

| fixture | expected data_type | expected processor | expected no-Origin status |
|---|---|---|---|
| `tests/fixtures/synthetic_pipeline/raw_data/XRD/synthetic_xrd.csv` | XRD | xrd_processor | processed_no_origin |
| `tests/fixtures/synthetic_pipeline/raw_data/固体紫外/synthetic_uvvis_reflectance.csv` | UV-vis DRS | uvvis_drs_processor | processed_no_origin |
| `tests/fixtures/synthetic_pipeline/raw_data/固体紫外/synthetic_uvvis_absorbance.csv` | UV-vis DRS | uvvis_drs_processor | processed_no_origin |
| `tests/fixtures/synthetic_pipeline/raw_data/阻抗EIS/synthetic_eis.csv` | EIS | eis_processor | processed_no_origin |
| `tests/fixtures/synthetic_pipeline/raw_data/20260109 光电流/synthetic_photocurrent.csv` | photocurrent | photocurrent_processor | processed_no_origin |
| `tests/fixtures/synthetic_pipeline/raw_data/光电流响应/synthetic_photocurrent_response.csv` | photocurrent_response | photocurrent_processor | processed_no_origin |
| `tests/fixtures/synthetic_pipeline/raw_data/XPS/synthetic_xps.csv` | XPS | xps_processor | processed_no_origin |
| `tests/fixtures/synthetic_pipeline/raw_data/PL/synthetic_pl.csv` | PL | pl_processor | processed_no_origin |
| `tests/fixtures/synthetic_pipeline/raw_data/红外/synthetic_ftir.csv` | FTIR | ftir_processor | processed_no_origin |
| `tests/fixtures/synthetic_pipeline/raw_data/拉曼/synthetic_raman.csv` | Raman | raman_processor | processed_no_origin |
| `tests/fixtures/synthetic_pipeline/raw_data/光反应的条件筛选/synthetic_condition_screening.csv` | reaction_condition_screening | condition_screening_processor | processed_no_origin |
| `tests/fixtures/synthetic_pipeline/raw_data/液相/synthetic_lc_chromatogram.csv` | HPLC/LC exported data | lc_exported_data_processor | processed_no_origin |
| `tests/fixtures/synthetic_pipeline/raw_data/液相/synthetic_lc_peak_table.csv` | HPLC/LC exported data | lc_exported_data_processor | processed_no_origin |
| `tests/fixtures/synthetic_pipeline/raw_data/BET/synthetic_bet.csv` | BET | bet_processor | processed_no_origin |
| `tests/fixtures/synthetic_pipeline/raw_data/EPR/synthetic_epr.csv` | EPR | epr_processor | processed_no_origin |
| `tests/fixtures/synthetic_pipeline/raw_data/莫特肖特基/synthetic_mott_schottky.csv` | Mott-Schottky | mott_schottky_processor | processed_no_origin |
