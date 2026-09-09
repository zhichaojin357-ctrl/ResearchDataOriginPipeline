from __future__ import annotations

import re


_CHEMICAL_TOKEN = re.compile(r"\b[A-Za-z][A-Za-z0-9().]*\b")
_SUBSCRIPT_STOICHIOMETRY = re.compile(r"(?<=[A-Za-z)])(\d+(?:\.\d+)?)")
_ELEMENTS = {
    "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne",
    "Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar",
    "K", "Ca", "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn",
    "Ga", "Ge", "As", "Se", "Br", "Kr",
    "Rb", "Sr", "Y", "Zr", "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd",
    "In", "Sn", "Sb", "Te", "I", "Xe",
    "Cs", "Ba", "La", "Ce", "Pr", "Nd", "Pm", "Sm", "Eu", "Gd", "Tb", "Dy",
    "Ho", "Er", "Tm", "Yb", "Lu", "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt",
    "Au", "Hg", "Tl", "Pb", "Bi", "Po", "At", "Rn",
}


def origin_chemical_subscripts(text: object) -> str:
    """Return Origin rich text where chemical-formula digits are subscripts."""
    value = "" if text is None else str(text)

    def replace_token(match: re.Match[str]) -> str:
        token = match.group(0)
        if "\\-(" in token or not any(ch.isdigit() for ch in token):
            return token
        if not _looks_like_formula_token(token):
            return token
        return _SUBSCRIPT_STOICHIOMETRY.sub(r"\\-(\1)", token)

    return _CHEMICAL_TOKEN.sub(replace_token, value)


def origin_bold_text(text: object) -> str:
    value = origin_chemical_subscripts(text)
    if not value.strip() or "\\b(" in value:
        return value
    return f"\\b({value})"


def _looks_like_formula_token(token: str) -> bool:
    if token.casefold() in {"xrd", "epr", "xps", "pl", "ftir", "raman"}:
        return False
    stripped = re.sub(r"[\d.]+", "", token)
    if not any(ch.isupper() for ch in stripped):
        return False
    return _can_parse_formula_letters(stripped.replace("(", "").replace(")", ""))


def _can_parse_formula_letters(value: str) -> bool:
    index = 0
    while index < len(value):
        char = value[index]
        if not char.isalpha():
            return False
        if char.islower():
            return False
        two = value[index : index + 2]
        if len(two) == 2:
            candidate = two[0].upper() + two[1].lower()
            if candidate in _ELEMENTS:
                index += 2
                continue
        one = char.upper()
        if one not in _ELEMENTS:
            return False
        index += 1
    return True
