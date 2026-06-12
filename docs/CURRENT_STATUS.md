# Current Status

The project is being cleaned into a final runtime pipeline. The active code path is `run.py` -> `src/cli.py` -> `src/core`/`src/processors`/`src/origin`.

## Active Scope

- Scan and classify characterization data.
- Build triage and reviewed queues.
- Process supported numeric data into normalized CSV plus `metadata.json`.
- Generate OriginPro products, save `.opju`, export 600 dpi `.tif`, and write preview/report artifacts.
- Keep uncertain or high-risk interpretation as manual-review fields.

## Output Root

All formal runs should write under:

```text
D:\Codex Project\科研数据处理\输出
```

Project-local `output/` is not the default runtime destination.

## Supported Runtime Types

The processor registry currently supports 14 automatic pipeline entries:

- photocurrent
- BET
- EPR
- PL
- XPS
- XRD
- UV-vis DRS
- photocurrent_response
- reaction_condition_screening
- FTIR
- Raman
- Mott-Schottky
- HPLC/LC exported data
- EIS

SEM, TEM, NMR, MS, and kinetics/reference folders remain scan-only.

## Origin Requirements

- Use OriginPro through the formal Origin modules.
- Use template-backed plotting when a template exists.
- Save `.opju` and export 600 dpi `.tif` for successful Origin products.
- Do not write full source paths, Codex labels, or comments into OPJU-facing workbook names/comments.
- For template conformance work, a current run must provide strict one-to-one comparison evidence, not only cached or manual-check artifacts.

## Validation Commands

```powershell
D:\Python\python.exe -m pytest
D:\Python\python.exe run.py validate
D:\Python\python.exe run.py readiness --no-desktop-review-xlsx
```

For plot-format changes, additionally run the relevant formal Origin commands and inspect their reports under the generated run root in `输出\runs`.
