# Product No-Codex-Label Audit For Real Product Pilot

## Policy

Final product filenames, visible graph text, preview text, and user-facing run
reports must not include the forbidden labels listed in the run-level audit.
Internal development documents may discuss this policy by name.

## Audit Outputs

The product pilot writes these run-level audit files:

- `reports/product_no_codex_label_audit.json`
- `reports/product_no_codex_label_audit.md`

The audit checks product filenames and readable product/report text while
excluding its own required audit files from self-matching.
