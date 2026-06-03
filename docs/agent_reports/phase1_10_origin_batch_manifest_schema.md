# Phase 1.10 Origin Batch Manifest Schema

```json
{
  "manifest_version": "phase1_10_origin_batch_manifest_v1",
  "generated_at": "2026-06-02T01:14:19",
  "csv_compatible": true,
  "sidecar_json_recommended": true,
  "required_or_canonical_columns": [
    "manifest_version",
    "package_id",
    "package_role",
    "generated_at",
    "source_package",
    "item_id",
    "result_id",
    "queue_id",
    "data_type",
    "source_file",
    "source_hash",
    "processed_csv",
    "metadata",
    "origin_file",
    "figure_tif",
    "preview_png",
    "contact_sheet",
    "qc_status",
    "manual_check_required",
    "forbidden_claims",
    "origin_export_status",
    "origin_export_allowed",
    "already_origin_exported",
    "safe_for_origin_batch",
    "notes"
  ],
  "backward_compatibility": "origin-batch accepts legacy origin_status and canonical origin_export_status aliases."
}
```
