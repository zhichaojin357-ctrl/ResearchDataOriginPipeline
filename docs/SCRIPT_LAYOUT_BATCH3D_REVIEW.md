# Script Layout Batch 3D Review

Date: 2026-06-03

Scope: review the two remaining script-layout candidates and, if safe, commit
only those scripts plus this review document. This review did not modify script
contents, imports, `src/`, `config/`, `tests/`, `output/`, or `outputs/`.

## Candidate Files

- `scripts/maintenance/opju_exemplar_regression.py`
- `scripts/one_off/verify_jeol_epr_decode_against_exports.py`
- `docs/SCRIPT_LAYOUT_BATCH3D_REVIEW.md`

## Initial Status

Both candidate scripts were untracked before Batch 3D staging:

```text
?? scripts/maintenance/opju_exemplar_regression.py
?? scripts/one_off/verify_jeol_epr_decode_against_exports.py
```

Because they were untracked, `git diff --stat -- <paths>` and
`git diff -- <paths>` did not show content. The files were reviewed directly.

## Candidate Classification

### `scripts/maintenance/opju_exemplar_regression.py`

Classification: maintenance regression/comparison helper.

Intended role:

- compares generated project evidence against copied OPJU exemplar material.
- records OPJU exemplar comparison requirements and verdicts.
- is not a production data processor.
- is not a general queue pipeline entry.
- should not be used to automatically process new data.

Observed behavior:

- has a CLI entry via `if __name__ == "__main__": raise SystemExit(main())`.
- reads queue and processing report inputs.
- writes maintenance comparison reports when explicitly executed:
  - default JSON report under `output/reports/phase1_14_opju_exemplar_regression_comparison.json`
  - default Markdown report under `output/reports/phase1_14_opju_exemplar_regression_comparison.md`
- creates the reference export directory path when explicitly executed.
- imports `connect_origin` and can launch Origin only through the explicit
  `--export-reference` path.
- does not modify raw data.
- does not contain broad delete, move, or cleanup logic.

Review conclusion:

- keep as `maintenance`.
- do not present it as a formal pipeline entry.
- do not run it during layout cleanup unless the user explicitly authorizes
  Origin/reference export or report regeneration.

### `scripts/one_off/verify_jeol_epr_decode_against_exports.py`

Classification: one-off JEOL EPR decode verification/audit script.

Intended role:

- verifies JEOL cAcqu EPR decoding against known Excel exports.
- supports traceability for prior JEOL EPR decoding work.
- is not a production data processor.
- is not a general pipeline entry.

Observed behavior:

- has a CLI entry via `if __name__ == "__main__": raise SystemExit(run())`.
- reads configured/raw EPR roots and a reference export directory.
- writes one-off verification reports when explicitly executed:
  - default JSON report under `output/reports/jeol_epr_decode_reference_check.json`
  - default Markdown report under `output/reports/jeol_epr_decode_reference_check.md`
- writes decoded workbooks into a temporary directory by default.
- deletes only its own temporary decoded-test directory through
  `TemporaryDirectory.cleanup()`.
- can keep decoded workbooks only when explicitly invoked with `--keep-decoded`.
- does not launch Origin.
- does not modify raw source data.
- does not contain broad delete or move operations against project outputs.

Review conclusion:

- keep as `one_off`.
- use only for focused JEOL EPR decode audits.
- do not promote it to a formal pipeline.

## Reference Review

`git grep -n "opju_exemplar_regression"` found references in current docs,
script indexes, historical reports, and output reports. No formal source-code or
test dependency was found for the OPJU helper.

`git grep -n "verify_jeol_epr_decode_against_exports"` found documentation and
script-index references plus one targeted test reference:

- `tests/test_jeol_epr_decode.py::JeolEprDecodeTest::test_one_off_reference_verifier_cleans_decoded_test_outputs`

No formal production pipeline dependency was found for either candidate script.

## Verification

Syntax checks:

```powershell
D:\Python\python.exe -m py_compile scripts/maintenance/opju_exemplar_regression.py
D:\Python\python.exe -m py_compile scripts/one_off/verify_jeol_epr_decode_against_exports.py
```

Result: both commands exited successfully.

Targeted tests:

- OPJU helper: no explicit script-specific targeted test found.
- JEOL one-off helper: one explicit targeted test found and run.

```powershell
D:\Python\python.exe -m pytest tests/test_jeol_epr_decode.py::JeolEprDecodeTest::test_one_off_reference_verifier_cleans_decoded_test_outputs -q
```

Result: `1 passed in 0.59s`.

No full `pytest`, `validate`, `readiness`, Origin run, or output-generating
script run was performed.

## Risk Boundary

These scripts can write reports when explicitly executed, and the OPJU helper can
launch Origin when explicitly invoked with `--export-reference`. That behavior is
why they must stay classified as maintenance/one-off helpers rather than formal
pipeline entries.

For Batch 3D, the scripts are only being kept for traceability and classified
script layout. They were not run as workflows in this review.

## Staging Recommendation

Batch 3D is recommended for staging because:

- both scripts passed `py_compile`.
- the JEOL one-off targeted test passed.
- no dangerous broad delete or move operation was found.
- no automatic import-time Origin launch was found.
- no automatic import-time output processing was found.
- no formal pipeline dependency was found.
- the scope is limited to script classification and traceability.

Strict allowlist:

```powershell
git add -- scripts/maintenance/opju_exemplar_regression.py scripts/one_off/verify_jeol_epr_decode_against_exports.py docs/SCRIPT_LAYOUT_BATCH3D_REVIEW.md
```

Do not include:

- any other `.py` script.
- `src/`
- `config/`
- `tests/`
- `output/`
- `outputs/`
- Origin outputs, OPJU, TIF, PNG, XLSX, ZIP, or large JSON files.
- any plotting or data-type bug fix.
