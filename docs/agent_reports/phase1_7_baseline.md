# Phase 1.7 Baseline

- Instruction SHA256: `5C2EB25FF55C65E7C5B552868F22468CAD3C4FC94646FEE662921CC96EDDBC28`
- Append triage-recognition instruction SHA256: `FE6C9E54F0EEF13B91A6B5177033446DED7AD815C2858494B1596AB936DDFBB1`
- Current Python interpreter: `D:\Python\python.exe`
- Workspace copy exists: True
- F drive backup exists: True
- Phase 1.6 package exists: True
- Phase 1.6 index.csv exists: True
- Phase 1.6 result_summary.json exists: True
- Origin processes before Phase 1.7 work: 0
- Forbidden items remain active: PPT disabled, kinetics processor disabled, SEM/TEM/NMR/MS scan-only, manual overrides not auto-applied.

## Commands
- git status --short --branch: exit 1; fatal: not a git repository
- D:\Python\python.exe -m pytest: exit 0; 111 passed, 2 warnings in 6.35s
- D:\Python\python.exe run.py deps-audit: exit 0; exit 0
- D:\Python\python.exe run.py validate: exit 0; exit 0
- D:\Python\python.exe run.py scan: exit 0; exit 0
- D:\Python\python.exe run.py triage --explain --force-refresh: exit 0; exit 0
- D:\Python\python.exe run.py origin-batch --manifest ... --dry-run: exit 0; 167 skipped, 0 planned, will_launch_origin false
