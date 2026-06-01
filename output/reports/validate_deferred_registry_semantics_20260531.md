# Validate Deferred Registry Semantics

`run.py validate` now fails if SEM/TEM/NMR/MS/reference entries are not scan-only, if they are marked supported, or if they have a processor. This prevents accidental activation of deferred/reference data types.

Focused verification:

```text
D:\Python\python.exe -m pytest tests\test_phase1_contracts.py -q
14 passed in 6.97s
```
