# Phase 1.9 Data Type Coverage Matrix

| Data type | Reader | Algorithm | External packages | Auto conclusions |
| --- | --- | --- | --- | --- |
| photocurrent/photoelectrochemistry | table/CHI TXT + optional ixdat | time-current, light marker, current density candidate | ixdat, scipy | blocked |
| BET | CSV/XLS/XLSX exported tables + optional pyGAPS | isotherm points and exported BET summary; BET fit candidate only | pygaps | blocked |
| EPR | JEOL decoder + optional cwepr | field-intensity, peak-to-peak, g candidate | cwepr | radical assignment blocked |
| PL/FTIR/Raman/UV-vis | tables | pybaselines ASLS candidate, scipy peaks, raw/corrected columns | pybaselines, scipy | defect/recombination/bond assignment blocked |
| SEM/TEM | image metadata/probe only | thumbnail/QC metadata only | pillow, tifffile, scikit-image | morphology/lattice interpretation blocked |
| XPS | tables + optional vgd-reader/lmfitxps | raw/background/envelope/component/residual handling; fitting helper optional | vgd-reader, lmfitxps | valence assignment blocked |
| XRD | CSV/TXT/XLSX tables; raw/dql probe only | peak candidates only | scipy | phase/plane assignment blocked |
| NMR | optional nmrglue for Bruker processed data | spectrum/peaklist index only | nmrglue | structure interpretation blocked |
| MS | mzML/mzXML/MGF/msp standard formats | spectrum index only | pymzml, pyteomics | product assignment blocked |
| EIS/LEVM | standard tables; LEVM lst parser planned | Nyquist/Bode candidates | scipy | equivalent-circuit conclusion blocked |
