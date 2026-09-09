from __future__ import annotations

from pathlib import Path, PureWindowsPath

from src.core.powershell_helpers import ps_array, ps_int_array, ps_quote


def test_ps_quote_escapes_single_quotes_without_changing_path_separators() -> None:
    assert ps_quote(PureWindowsPath("C:/Data/O'Brien/sample.csv")) == "'C:\\Data\\O''Brien\\sample.csv'"
    native = Path("data") / "O'Brien" / "sample.csv"
    assert ps_quote(native) == "'" + str(native).replace("'", "''") + "'"


def test_ps_array_quotes_each_value() -> None:
    assert ps_array(["alpha", "O'Brien"]) == "@('alpha', 'O''Brien')"


def test_ps_int_array_casts_values_to_int_literals() -> None:
    assert ps_int_array([1, 2.0, "3"]) == "@(1, 2, 3)"
