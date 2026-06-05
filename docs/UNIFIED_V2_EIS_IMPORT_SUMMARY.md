# EIS v2 cleaning and draft fitting summary

- Raw data: EIS/processed_data/raw_eis_data.csv
- Cleaned data: EIS/processed_data/cleaned_eis_data.csv
- Ignored points table: EIS/processed_data/ignored_eis_points.csv
- Fit curve: EIS/processed_data/eis_randles_cpe_fit_curve.csv
- Raw points: 71
- Cleaned points: 62
- Ignored points: 9
- Fit method: least_squares_randles_cpe
- Fit model: Model A: Rs + (Rct || CPE)
- Parameters: {'Rs': 8.72681344826923, 'Rct': 46525.708925066436, 'Q': 0.00013615677344406643, 'n': 0.8054177975139813}
- Semicircle classification: depressed semicircle candidate
- Residual SSE: 0.5498679257264858
- Fit policy: draft fit for visualization/manual review only
- Manual circuit ambiguity: yes

## Ignored points
- index 63: invalid_negative_z_real_unstable_low_frequency_tail;unstable_low_frequency_tail_after_first_invalid;large_jump_unstable_low_frequency_tail
- index 64: invalid_negative_z_real_unstable_low_frequency_tail;unstable_low_frequency_tail_after_first_invalid;large_jump_unstable_low_frequency_tail
- index 65: sign_flip_negative_minus_z_imag_unstable_low_frequency_tail;unstable_low_frequency_tail_after_first_invalid;large_jump_unstable_low_frequency_tail
- index 66: sign_flip_negative_minus_z_imag_unstable_low_frequency_tail;unstable_low_frequency_tail_after_first_invalid;large_jump_unstable_low_frequency_tail
- index 67: invalid_negative_z_real_unstable_low_frequency_tail;unstable_low_frequency_tail_after_first_invalid;large_jump_unstable_low_frequency_tail
- index 68: sign_flip_negative_minus_z_imag_unstable_low_frequency_tail;unstable_low_frequency_tail_after_first_invalid;large_jump_unstable_low_frequency_tail
- index 69: invalid_negative_z_real_unstable_low_frequency_tail;unstable_low_frequency_tail_after_first_invalid;large_jump_unstable_low_frequency_tail
- index 70: invalid_negative_z_real_unstable_low_frequency_tail;unstable_low_frequency_tail_after_first_invalid;large_jump_unstable_low_frequency_tail
- index 71: invalid_negative_z_real_unstable_low_frequency_tail;unstable_low_frequency_tail_after_first_invalid;large_jump_unstable_low_frequency_tail
