# EIS Randles-CPE fit review

- Default model: Model A, Rs + (Rct || CPE)
- Fitting algorithm: complex nonlinear least squares with simultaneous real and imaginary residuals
- Robust loss: soft_l1
- Weighting: impedance modulus weighting
- Bounds: Rs > 0, Rct > 0, Q > 0, 0.5 <= n <= 1.0
- Multistart: yes
- Model B Rs + CPE attempted: no; diagnostic fallback only
- Warburg model attempted: no
- Method: least_squares_randles_cpe
- Parameters: {'Rs': 8.72681344826923, 'Rct': 46525.708925066436, 'Q': 0.00013615677344406643, 'n': 0.8054177975139813}
- Residual SSE: 0.5498679257264858
- Robust cost: 0.2742590411247827
- Semicircle classification: depressed semicircle candidate
- Fit curve: EIS/processed_data/eis_randles_cpe_fit_curve.csv
- Warning: draft fit for visualization/manual review only
- Final equivalent-circuit conclusion: avoided
- Electrochemical mechanism conclusion: avoided
