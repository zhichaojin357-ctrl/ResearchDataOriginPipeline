# Post-generation targeted test health

## Commands

```powershell
D:\Python\python.exe -m pytest tests/test_origin_style_mimic.py tests/test_opju_backed_xps_xrd_epr_bet_pilot.py tests/test_opju_backed_remaining_product_pilot.py -q
```

Result: `9 passed in 1.14s`

```powershell
D:\Python\python.exe -m pytest tests/test_output_routing.py tests/test_origin_adapter.py tests/test_origin_operations.py tests/test_origin_plot_policy.py -q
```

Result: `55 passed, 7 subtests passed in 2.81s`

```powershell
D:\Python\python.exe -m pytest tests/test_hplc_lc_contracts.py tests/test_hplc_lc_process_integration.py tests/test_hplc_lc_output_routing.py -q
```

Result: `16 passed in 1.14s`

## Git Checks After Tests

```powershell
git status --short
```

Result: only post-generation audit documents were untracked.

```powershell
git diff --cached --name-status
```

Result: empty.

```powershell
git status --short -- output outputs
```

Result: empty.

## Conclusion

Targeted tests passed. No code fix was required from test health checks.
