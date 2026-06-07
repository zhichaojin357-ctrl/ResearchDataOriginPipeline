# V4 method-correctness audit

- Final audited run: `D:\Codex Project\科研数据处理\输出\runs\20260606_125645_unified_v4_strict_template_conformance_all_types`
- Scope: BET, XPS in-situ, XPS non-in-situ, XRD, EPR, EIS, Raman, UV-vis DRS / Tauc, PL, photocurrent, FTIR.
- Decision rule: do not invent scientific processing just to make a template look fuller. If the selected source data do not contain a needed reference card, comparison sample, Tauc transform, calibrated PL correction, or peak assignment, the product must remain a draft plot and the missing scientific step must stay manual.

## Per-type decision table

| Type | Current source and processing | Standard-method check | Decision for this product |
|---|---|---|---|
| BET | Selected one BOBC adsorption/desorption export. Origin imports the raw/staging isotherm columns and creates the final plotted columns. | BET surface-area calculation requires a valid BET equation range and is not the same as simply plotting the adsorption/desorption isotherm. ISO 9277 also limits BET applicability to appropriate isotherm classes. | Correct for an isotherm-style draft plot. Do not report BET surface area, pore-size distribution, or pore-structure interpretation from this product. |
| XPS in-situ | Selected already fitted XPS workbooks. Origin imports fitted-source measured/envelope/component/background curves, then normalizes, offsets, and creates fill-helper curves. | XPS background and peak fitting require explicit background type/endpoints, peak shapes, constraints, and calibration. Those choices are already embedded in the fitted workbooks and should not be re-created by the plotting script. | Correct for plotting existing fitted XPS curves. Do not claim new XPS fitting, valence assignment, charge transfer, or S-scheme mechanism. |
| XPS non-in-situ | Same as above, using fitted non-in-situ comparison workbooks. | Same XPS rule: plotting can reuse reviewed fitted curves, but scientific assignments require manual review of fitting parameters. | Correct for fitted-source stacked comparison. The selected template is visually useful but the non-in-situ OPJU still needs manual visual calibration for final publication use. |
| XRD | Selected one BOBC raw pattern. Origin imports two-theta/intensity columns and plots them. | Phase identification or Miller-index labels require reference-pattern comparison and manual validation; background modeling/refinement choices are not universal. | Correct for a raw XRD pattern draft. Do not automatically add JCPDS card, phase labels, or crystal-plane labels without the corresponding verified reference data. |
| EPR | Selected verified JEOL Excel exports for BC/CWO/BOBC OH group. Origin performs edge-region median baseline subtraction, adjacent-average smoothing, and vertical offsets. | EPR baseline correction is valid when signal-free baseline regions are chosen; smoothing is acceptable for visualization when reported and not used for quantitative spin counts. | Correct for a visual OH overlay draft. Radical assignment, g-value calibration, peak-to-peak intensity, and spin quantification remain manual. |
| EIS | Python reads raw EIS, keeps raw data, removes unstable low-frequency tail with explicit ignored-point report, and fits `Rs + (Rct || CPE)` by complex nonlinear least squares. Origin only plots cleaned data and the draft fit curve. | Robust bounded nonlinear least squares with real/imaginary residuals is appropriate for this user-approved Randles-CPE draft fit; the fit does not establish a final circuit. | Correct under the explicit EIS exception. Do not write final equivalent-circuit or mechanism conclusions. |
| Raman | Selected one BOBC raw Raman spectrum. Origin imports raw/staging XY data and plots it. | Raman preprocessing can include calibration, spike removal, baseline separation, smoothing, and normalization, but these choices are data- and goal-dependent and can alter peaks. | Correct for a raw Raman spectrum draft. Do not perform automatic baseline correction, normalization, peak labels, or defect/phase assignment without manual target regions and parameters. |
| UV-vis DRS / Tauc | Selected one BOBC solid UV-vis export. Origin imports wavelength/signal columns and plots the DRS-like raw signal. | A true Tauc/bandgap product requires reflectance handling, Kubelka-Munk or another justified transform, photon-energy conversion, exponent choice, and a manually selected linear interval. | Correct only as a UV-vis DRS raw-signal draft. It is not a Tauc plot and must not report bandgap. |
| PL | Selected one emission file. Origin imports wavelength/counts and plots it. | Quantitative PL comparison requires wavelength accuracy, detector response/spectral correction, linearity checks, and normalization choices when comparing intensities. | Correct for a raw emission draft. Do not infer recombination efficiency or compare absolute intensities without calibration/normalization review. |
| photocurrent | Selected one current-time file. Origin imports time/current columns and plots the transient. | Chopped-light transient interpretation requires light on/off boundaries and care with spikes/overshoots; magnitude alone does not prove carrier separation. | Correct for a raw current-time draft. Do not segment cycles, compute current density, or infer carrier dynamics without electrode area and light timing review. |
| FTIR | Selected BOBC and CWO DPT spectra. Origin imports aligned raw/staging wavenumber/transmittance columns and plots them. | FTIR preprocessing may use smoothing, normalization, and baseline correction, but there is no universal best method; choice depends on dataset and analysis goal. | Correct for a raw overlay draft. Do not assign bonds, baseline-correct, normalize, or label peaks automatically. |

## Local evidence checked

- Product metadata for all 11 types was read from the final run.
- All non-EIS product metadata records Origin-side processing.
- EIS metadata records raw data, cleaned data, ignored points, and Randles-CPE draft fit parameters.
- Side-by-side template/product previews were visually checked for high-risk semantics:
  - UV-vis template is a wavelength/absorbance style plot, not a Tauc-bandgap panel.
  - XRD template includes multi-sample and JCPDS-style reference content, but the selected source is one BOBC pattern; no reference card was fabricated.
  - XPS products reuse fitted-source curves and add current peak labels from component maxima; the fitted chemistry remains manual.
  - EPR uses the verified OH overlay group and Origin-side baseline/smoothing, not the old single O3 seed file.

## Sources consulted

- BET: ISO 9277 gas-adsorption BET method page (`https://www.iso.org/cms/%20render/live/en/sites/isoorg/contents/data/standard/04/49/44941.html?browse=ics`) and IUPAC physisorption reporting recommendations (`https://publications.iupac.org/pac/57/4/0603/index.html`).
- XPS: AVS/JVST practical guide to quantitative XPS (`https://mmrc.caltech.edu/XPS%20Info/Practical%20Guides%20to%20XPS/XPS%20guide%20Quantitative%20XPS.pdf`) and XPS spectra-base processing guidance (`https://xpsdatabase.com/peak-fittiting-and-data-processing/`).
- Origin: OriginLab worksheet Set Values/LabTalk expression documentation (`https://docs.originlab.com/origin-help/wks-setcolval-expression/`), smoothing documentation (`https://docs.originlab.com/originc/ref/smooth/`), and fill-to-next-plot guidance (`https://docs.originlab.com/quick-help/fill-area-two-curve/`).
- XRD: IUCr Rietveld/refinement guideline discussion of powder-pattern data collection and background treatment (`https://journals.iucr.org/j/issues/1999/01/00/gl0561/`).
- Raman: Raman workflow and chemometrics references on calibration, baseline separation, smoothing, and normalization (`https://www.spectroscopyonline.com/view/key-steps-in-the-workflow-to-analyze-raman-spectra`, `https://journals.sagepub.com/doi/10.1177/00037028221094070`).
- UV-vis DRS/Tauc: RSC Analyst article comparing Kubelka-Munk/Tauc-based bandgap estimation (`https://pubs.rsc.org/en/content/articlehtml/2019/an/c8an02257g`).
- PL: NIST fluorescence spectroscopy standardization guidance for wavelength, intensity, detector response, and correction (`https://nvlpubs.nist.gov/nistpubs/Legacy/IR/nistir7457.pdf`).
- FTIR: practical FTIR pre-processing review covering smoothing, normalization, and baseline correction choices (`https://strathprints.strath.ac.uk/77072/1/Theakstone_etal_TB_2021_Fourier_transform_infrared_spectroscopy_of_biofluids.pdf`).
- EPR: Xenon EPR data-processing reference for baseline correction, selected baseline regions, and integration sensitivity (`https://www.nmrcenter.buffalo.edu/EPR_Processing.pdf`).
- EIS: SciPy `least_squares` documentation for bounded robust nonlinear least-squares fitting (`https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html`).
- Photocurrent: literature on chopped-light photocurrent transients and the nontrivial interpretation of spikes/overshoots (`https://www.sciencedirect.com/science/article/pii/S1572665720304628`).

## Bottom line

The current products are method-correct as draft plots because they avoid unsupported automatic scientific conclusions. The main remaining work is manual calibration and optional future analysis-specific processing, not silent automatic fitting.
