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
- `src/core/origin_style_assets.py`: style harvest and replay verification; byte-identical reference-OPJU self-replays are explicitly separated from independent asset validation, and external source OPJU access is confined to these workflows.
- `src/core/template_product_common.py`: shared OPJU-backed product data structures and table helpers.
- `src/core/remaining_template_products.py`: remaining non-XPS/XRD template-product helpers with manual-review boundaries.
- `src/core/xps_in_situ.py`: quarantined legacy compatibility/test implementation; it is not reachable from the current formal XPS in-situ path.
- `src/core/xps_heterojunction.py`: maintained stacked XPS product workflow with candidate-only peak labels and transactional Origin artifacts.
- `src/core/xrd_overlay.py`: XRD overlay workflow.
- `src/core/xrd_no_card_overlay.py`: no-card XRD overlay workflow.
- `src/core/epr_jeol.py`: verified JEOL `cAcqu` decoder, data-only XLSX/metadata export, hash validation, and package transaction.
- `src/core/epr_overlay.py`: verified EPR condition overlays, explicit output-root routing, package transaction, and optional Origin export.
- `src/core/hplc_openlab.py`: Agilent OpenLab `.rslt/.dx/.rx` raw-data decode and verified Excel export workflow.
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
- `src/origin/style_registry.py`: schema v1/v2 style-manifest loading, project-local asset resolution, and SHA-256 integrity validation.
- `scripts/origin/origin_plot_from_template.ps1`: project-local helper used by formal Origin automation.

## Documentation Kept In Runtime

- `docs/CODEBASE_AUDIT_2026-07-31.md`
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
- `scripts/data_types/hplc_lc/plot_hplc_calibration_origin.ps1` (fixed-data calibration regression/rebuild helper, not a generic HPLC entrypoint)
- `scripts/data_types/hplc_lc/build_openlab_workbook.mjs`
- `scripts/data_types/hplc_lc/openlab_vendor_bridge/` (project bridge source plus the controlled runtime-bundle builder/verifier)
- `scripts/data_types/hplc_lc/verify_openlab_vendor_reprocessing.py` (JSON-only original-algorithm feasibility/equivalence check; no Excel or plot)
- `scripts/data_types/xrd/plot_xrd_no_card_overlay_origin.py`
- `scripts/validation/verify_jeol_epr_decode_against_exports.py`

Scripts are helpers or explicitly scoped regression tools only. New generic production behavior belongs in `src` and must be reachable from `run.py`.
