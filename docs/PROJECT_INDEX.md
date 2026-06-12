# Project Index

## Entrypoints

- `run.py`: thin launcher for the CLI.
- `src/cli.py`: formal command parser and command dispatch.

## Core Runtime

- `src/core/process.py`: queue and input processing orchestration.
- `src/core/triage.py`: classification, parser probes, and processing decisions.
- `src/core/auto_queue.py`: dry-run AUTO_PROCESS queue builder.
- `src/core/reviewed_queue.py`: user-reviewed queue template and dry-run planner.
- `src/core/origin_batch.py`: manifest-backed Origin batch dry-run/execution planner.
- `src/core/template_format_executor.py`: all-types template-format product command wrapper.
- `src/core/template_product_builder.py`: template-backed product generation and comparison reports.
- `src/core/xrd_overlay.py`: XRD overlay workflow.
- `src/core/origin_governance.py`: Origin plotting governance and journal-ready report generation.
- `src/core/readiness.py`: project readiness checks.
- `src/core/validate.py`: configuration, dependency, output, safety, and Origin contract validation.

## Data Processing

- `src/processors/`: supported data processors and shared table readers.
- `src/adapters/`: optional package adapters used only when reliable and available.
- `config/processor_registry.yaml`: supported and scan-only data-type registry.
- `config/plot_style.yaml`: Origin plotting style contract.
- `config/default.yaml`: default paths and runtime configuration.

## Origin

- `src/origin/adapter.py`: Origin job construction and plot policy integration.
- `src/origin/operations.py`: Origin COM operations, project saving, export, and metadata sanitization.
- `scripts/origin/origin_plot_from_template.ps1`: project-local helper used by formal Origin automation.

## Documentation Kept In Runtime

- `docs/REAL_DATA_INTAKE_GUIDE.md`
- `docs/REAL_DATA_COMPATIBILITY_MATRIX.md`
- `docs/DATA_TYPE_ACCEPTANCE_MATRIX_FINAL.md`
- `docs/HPLC_LC_ACCEPTANCE_CRITERIA.md`
- `docs/ORIGIN_STYLE_ASSETS.md`
- `docs/TEMPLATE_FORMAT_PRODUCTS.md`
- `docs/TEMPLATE_VISUAL_ACCEPTANCE_CONTRACT.md`
- `docs/USER_PLOT_STYLE_OVERRIDE_GUIDE.md`
- `docs/method_cards/`
- `docs/data_format_notes/`
- `docs/reuse_audit/`
- `docs/indexes/scripts_index.md`

## Script Set

- `scripts/reports/regenerate_manual_review_filtered.py`
- `scripts/origin/origin_plot_from_template.ps1`
- `scripts/data_types/hplc_lc/plot_hplc_calibration_origin.ps1`
- `scripts/one_off/verify_jeol_epr_decode_against_exports.py`

Scripts are helpers only. New production behavior belongs in `src` and must be reachable from `run.py`.
