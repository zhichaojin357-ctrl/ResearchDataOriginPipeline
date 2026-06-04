# OPJU-Backed Real Data Pilot Review

Run root: `D:\Codex Project\科研数据处理\输出\runs\20260604_180334_opju_backed_real_data_pilot`

## Scope

This pilot scanned real data from `F:\课题\LL\检测`, scanned the task-scoped XPS data folder, inventoried OPJ/OPJU exemplars, validated OPJU graph presence through Origin, and produced a conservative pairing and dry-run plan.

Original F-drive data and original OPJ/OPJU files were not modified.

## Inventory

- Real data scan roots:
  - `F:\课题\LL\检测`
  - `D:\Codex Project\科研数据处理\26.6.3组会数据\XPS`
- OPJ/OPJU files inventoried: 100
- Valid OPJU exemplars with graph pages: 99
- Invalid data-only OPJU exemplars: 1
- Unreadable OPJU exemplars: 0

The data-only OPJU was `光反应的条件筛选\时间反应取样.opju`.

## Pairing Result

Valid exemplars were found for BET, EIS, Raman, XRD, XPS in-situ, XPS non-in-situ, EPR, Mott-Schottky, UV-vis DRS / Tauc, PL, photocurrent, and FTIR.

HPLC/LC was deferred because no OPJU exemplar was found for that data type.

## Dry-Run Decision

No Phase 9 Origin generation was executed. The dry-run blocked generation because the codebase can validate OPJU graph pages but does not yet contain a reviewed generic per-exemplar style-mapping implementation for arbitrary OPJU files. Several data types also need manual scientific or visual decisions before export.

Detailed artifacts are in the run root:

- `inventories/real_data_inventory.md`
- `inventories/opju_exemplar_inventory.md`
- `reports/opju_validity_report.md`
- `pairing/opju_data_pairing_plan.md`
- `reports/origin_generation_dry_run_plan.md`
- `reports/manual_review_checklist.md`
