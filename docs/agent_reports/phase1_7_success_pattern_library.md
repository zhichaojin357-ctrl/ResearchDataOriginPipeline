# Phase 1.7 Success Pattern Library

- Total successes: 167

## EIS

- Success count: 22
- Processor: eis_processor
- File extensions: {'.txt': 13, '.csv': 4, '.xlsx': 5}
- Row count range: {'min': 71, 'max': 97}
- Safe fallbacks: folder-confirmed numeric table, header aliases with explicit units, headerless x/y numeric table after parser success
- Risky patterns: folder/header conflict, unnamed multi-column XPS fit tables, spectra needing scientific assignment
- Top headers: {'x': 22, 'y': 22}

## EPR

- Success count: 13
- Processor: epr_processor
- File extensions: {'.xlsx': 13}
- Row count range: {'min': 4095, 'max': 4095}
- Safe fallbacks: folder-confirmed numeric table, header aliases with explicit units, headerless x/y numeric table after parser success
- Risky patterns: folder/header conflict, unnamed multi-column XPS fit tables, spectra needing scientific assignment
- Top headers: {'magnetic_field': 13, 'intensity': 13, 'normalized_intensity': 13}

## Mott-Schottky

- Success count: 90
- Processor: mott_schottky_processor
- File extensions: {'.csv': 64, '.xlsx': 20, '.txt': 6}
- Row count range: {'min': 20, 'max': 88}
- Safe fallbacks: folder-confirmed numeric table, header aliases with explicit units, headerless x/y numeric table after parser success
- Risky patterns: folder/header conflict, unnamed multi-column XPS fit tables, spectra needing scientific assignment
- Top headers: {'potential': 90, 'one_over_c_squared': 90}

## Raman

- Success count: 30
- Processor: raman_processor
- File extensions: {'.txt': 30}
- Row count range: {'min': 276, 'max': 1911}
- Safe fallbacks: folder-confirmed numeric table, header aliases with explicit units, headerless x/y numeric table after parser success
- Risky patterns: folder/header conflict, unnamed multi-column XPS fit tables, spectra needing scientific assignment
- Top headers: {'x': 30, 'intensity': 30, 'normalized_intensity': 30}

## XPS

- Success count: 9
- Processor: xps_processor
- File extensions: {'.xlsx': 4, '.xls': 5}
- Row count range: {'min': 151, 'max': 1361}
- Safe fallbacks: folder-confirmed numeric table, header aliases with explicit units, headerless x/y numeric table after parser success
- Risky patterns: folder/header conflict, unnamed multi-column XPS fit tables, spectra needing scientific assignment
- Top headers: {'binding_energy_eV': 9, 'raw_intensity': 9, 'peak_candidate_flag': 9}

## photocurrent

- Success count: 3
- Processor: photocurrent_processor
- File extensions: {'.txt': 3}
- Row count range: {'min': 2600, 'max': 2600}
- Safe fallbacks: folder-confirmed numeric table, header aliases with explicit units, headerless x/y numeric table after parser success
- Risky patterns: folder/header conflict, unnamed multi-column XPS fit tables, spectra needing scientific assignment
- Top headers: {'time_s': 3, 'current': 3, 'cycle_candidate_id': 3}
