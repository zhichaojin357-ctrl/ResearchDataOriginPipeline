from __future__ import annotations

import pytest

from src.origin.text_format import origin_bold_text, origin_chemical_subscripts


@pytest.mark.parametrize(
    ("formula", "expected"),
    [
        ("CuWO4", r"CuWO\-(4)"),
        ("(NH4)2SO4", r"(NH\-(4))\-(2)SO\-(4)"),
        ("BiOBr0.5Cl0.5", r"BiOBr\-(0.5)Cl\-(0.5)"),
    ],
)
def test_chemical_subscripts_include_decimal_stoichiometry(
    formula: str,
    expected: str,
) -> None:
    assert origin_chemical_subscripts(formula) == expected


def test_chemical_subscripts_preserve_sample_suffixes_and_existing_markup() -> None:
    assert origin_bold_text("BiCu-30") == r"\b(BiCu-30)"
    assert origin_bold_text("b3") == r"\b(b3)"
    assert origin_bold_text("EIS_b3") == r"\b(EIS_b3)"
    rich_text = r"\b(BiOBr\-(0.5)Cl\-(0.5))"
    assert origin_bold_text(rich_text) == rich_text
