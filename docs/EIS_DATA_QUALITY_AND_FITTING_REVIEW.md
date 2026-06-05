# EIS data quality and fitting review

- Data file copy: EIS/input_copies
- Previous EIS run: D:\Codex Project\科研数据处理\输出\runs\20260605_000310_remaining_opju_product_drafts
- Total points: 71
- Frequency range: 0.01 to 100000
- Z' range: -11239 to 6355.22
- -Z'' range: -8037.66 to 11558.5
- Negative Z' detected: True
- -Z'' sign flip detected: True
- Large adjacent jump detected: True
- Unstable low-frequency tail detected: True
- Cleaning rule: raw data is preserved, cleaned data excludes explicitly reported invalid/unstable tail points only.
- Fitting model choice: user-confirmed semicircle behavior; Model A Rs + (Rct || CPE) generates near-ideal or depressed semicircle candidates.
- Original data modified: no

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
