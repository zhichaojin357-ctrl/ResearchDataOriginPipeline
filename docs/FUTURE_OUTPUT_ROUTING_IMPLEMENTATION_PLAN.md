# Future Output Routing Implementation Plan

## Contract

Future generated artifacts should be grouped by run:

```text
output/
  runs/
    YYYYMMDD_HHMMSS_<scope>/
      processed_data/
      metadata/
      origin_files/
      figures_tif/
      figures_preview/
      reports/
      logs/
      run_manifest.json
```

## Run ID

Run IDs use:

```text
YYYYMMDD_HHMMSS_<sanitized_scope>
```

The timestamp may be injected in tests for deterministic assertions.

## Manifest Fields

Each run manifest records:

- `run_id`
- `timestamp`
- `command`
- `mode`
- `scope`
- `project_root`
- `output_root`
- `input_paths`
- `no_origin`
- `dry_run`
- `produced_artifact_directories`
- `warnings`
- `compatibility_mode`

## Compatibility Policy

- Existing `output/phase1_6_origin_results_20260531_041538` and `output/final_locked_results` remain readable legacy packages.
- Existing reports remain historical references.
- This GOAL does not move or delete old output.
- Users may later manually inspect and delete old artifacts, but this implementation only prevents future runs from defaulting into mixed legacy folders once call sites are migrated.

## Batch Order

1. Add runtime path helpers and manifest creation.
2. Add process/metadata support for an explicit run output root.
3. Add triage/report routing support for an explicit run output root.
4. Add Origin adapter path acceptance without running Origin.
5. Document the policy and remaining legacy paths.
