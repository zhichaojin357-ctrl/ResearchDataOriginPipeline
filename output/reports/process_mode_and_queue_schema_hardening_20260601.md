# Process Mode And Queue Schema Hardening

- Date: 2026-06-01
- `process --auto-select --with-origin` now hard-fails instead of silently becoming no-Origin.
- `process --auto-select --from-queue` now hard-fails instead of ignoring `--auto-select`.
- `reviewed-queue` decision CSV headers and rows are now schema-validated before planning.
- Blank decision CSV headers, CLI `ValueError` tracebacks, and missing-file tracebacks are handled explicitly.
- Queue/proposal JSON shape errors are handled explicitly before `.get("items")` access.
- Queue/proposal `items` entries are validated one by one, with concise item-numbered CLI errors when an entry is not an object.
- `auto-queue --queue` now validates the top-level JSON object, `items` list, and each `items` object before planning.
- Queue-driven artifact names now use a stable digest of the full queue id to avoid same-stem reviewed-queue collisions.
- `readiness --no-desktop-review-xlsx` can be used for portable checks without the desktop workbook copy.
- Full validation after this hardening: `D:\Python\python.exe -m pytest` passed 205 tests with 2 upstream openpyxl warnings; `deps-audit`, `validate`, default `readiness`, and `readiness --no-desktop-review-xlsx` all exited 0.
