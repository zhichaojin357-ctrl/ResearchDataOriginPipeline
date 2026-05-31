# Phase 1.6 Material Color Verification

- Created: 2026-05-31 09:27:48
- Status: PASS
- Material/sample keys in registry: 15
- Recorded curve assignments: 210
- Keys with assignments: 20
- Verification mode: read existing color map; did not start Origin.

## Fixed Material Colors

| key | role | color | RGB | Origin OColor | assignments | manual review flags |
|---|---|---|---|---:|---:|---:|
| `CWO` | material | blue `#0072B2` | 0, 114, 178 | 28471808 | 38 | 0 |
| `BOBC` | material | orange `#E69F00` | 230, 159, 0 | 16818150 | 49 | 0 |
| `CWO+BOBC` | material_composite | bluish_green `#009E73` | 0, 158, 115 | 24354304 | 11 | 0 |
| `BOC` | material | sky_blue `#56B4E9` | 86, 180, 233 | 32093270 | 1 | 0 |
| `MCS` | material | vermillion `#D55E00` | 213, 94, 0 | 16801493 | 1 | 0 |
| `BM` | material_or_sample_code | reddish_purple `#CC79A7` | 204, 121, 167 | 27752908 | 13 | 0 |
| `BPO` | material_or_sample_code | black `#000000` | 0, 0, 0 | 16777216 | 6 | 0 |
| `BPOM` | material_or_sample_code | dark_teal `#117733` | 17, 119, 51 | 20150033 | 8 | 0 |
| `BOBCMS` | material_or_sample_code | wine `#882255` | 136, 34, 85 | 22356616 | 2 | 0 |
| `BC` | material_or_sample_code | teal `#44AA99` | 68, 170, 153 | 26847812 | 23 | 0 |
| `MS` | material_or_sample_code | dark_blue `#332288` | 51, 34, 136 | 25698867 | 27 | 0 |
| `MOSE2` | material_or_sample_code | purple `#AA4499` | 170, 68, 153 | 26821802 | 3 | 0 |
| `MOTE2` | material_or_sample_code | sand `#DDCC77` | 221, 204, 119 | 24628445 | 8 | 0 |
| `MB` | sample_series | olive `#999933` | 153, 153, 51 | 20158873 | 11 | 0 |
| `MT` | sample_series | brown `#661100` | 102, 17, 0 | 16781670 | 4 | 0 |

## Consistency Result

No material/sample key has more than one recorded Origin OColor value.

## Notes

- XPS repair exports are included in the current assignment count.
- Ambiguous sample-code keys remain marked by role and should be confirmed before expanding the registry.
