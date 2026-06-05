# User plot style override guide

The optional local file is `config/user_plot_style.yaml`. It is not required for
normal runs and should only contain manual calibration overrides.

Priority order:

1. Data-type override
2. Global override
3. Exemplar style readback
4. Project default

Supported keys are shown in `config/user_plot_style.example.yaml`.

Current required global policy:

- Curve line width: 3 pt
- X/Y axis titles: bold
- Export DPI: 600

For EIS v2, the override controls the cleaned-point marker size, fitted-curve
line width, axis title size, tick label size, legend size, and export DPI. It
does not change the fitting model or scientific interpretation policy.
