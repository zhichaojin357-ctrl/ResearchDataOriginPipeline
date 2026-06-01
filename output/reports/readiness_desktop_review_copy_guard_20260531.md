# Readiness Desktop Review Copy Guard

Date: 2026-05-31

`run.py readiness` now verifies that the desktop manual-review workbook matches the project copy by SHA256.

- Project copy: `output/reports/phase1_8_manual_review_required_filtered.xlsx`
- Desktop copy: `C:\Users\lenovo\Desktop\phase1_8_manual_review_required_filtered.xlsx`
- Current SHA256: `940945e6b6f9460df476b97aedb6d8b713c87802471c6fbea1373807daeebeb2`
- Current readiness: 14 checks, 0 failures, 0 warnings.
- Full pytest: passed, 162 tests, 2 warnings.
- validate/deps-audit: exit 0.
- Residual `python`, `EXCEL`, `Origin`, and `OriginPro` process check after verification: none found.
