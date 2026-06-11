from __future__ import annotations

import json
from pathlib import Path

from src.core.remaining_opju_product_drafts import (
    load_remaining_pairings,
)


def test_load_remaining_pairings_selects_remaining_types_only(tmp_path: Path) -> None:
    roots = _root_map(tmp_path)
    for root in roots.values():
        root.mkdir(parents=True, exist_ok=True)
    pairing = tmp_path / "pairing.json"
    _write_pairing(
        pairing,
        [
            _pair("BET", ["BET/bet.csv"], "BET/style.opju"),
            _pair("EIS", ["EIS/eis.txt"], "EIS/style.opju"),
            _pair("Raman", ["Raman/raman.txt"], "Raman/style.opju"),
            _pair("Mott-Schottky", ["MS/ms.csv"], "MS/style.opju"),
            _pair("UV-vis DRS / Tauc", ["UV/uv.txt"], "UV/style.opju"),
            _pair("PL", ["PL/pl.txt"], "PL/style.opju"),
            _pair("photocurrent", ["PC/pc.txt"], "PC/style.opju"),
            _pair("FTIR", ["FTIR/a.dpt", "FTIR/b.dpt"], "FTIR/style.opju"),
            _pair("HPLC/LC exported data", ["LC/sample.pdf"], ""),
        ],
    )

    selected = load_remaining_pairings(pairing, roots)

    assert [item.product_key for item in selected] == [
        "EIS",
        "Raman",
        "Mott-Schottky",
        "UV-vis DRS / Tauc",
        "PL",
        "photocurrent",
        "FTIR",
    ]
    assert all(item.product_key != "BET" for item in selected)


def _root_map(tmp_path: Path) -> dict[str, Path]:
    return {
        "f_drive_detection": tmp_path / "f_drive",
        "workspace_xps_data": tmp_path / "workspace" / "XPS",
        "workspace_xps_reference": tmp_path / "xps_reference",
        "workspace_group_data": tmp_path / "workspace",
    }


def _pair(data_type: str, data_paths: list[str], opju_path: str) -> dict[str, object]:
    return {
        "data_type": data_type,
        "xps_subtype": "",
        "selected_data_root_label": "f_drive_detection",
        "selected_data_relative_paths": data_paths,
        "selected_opju_root_label": "f_drive_detection" if opju_path else "",
        "selected_opju_relative_path": opju_path,
        "opju_validation_status": "valid_exemplar" if opju_path else "missing_opju",
    }


def _write_pairing(path: Path, items: list[dict[str, object]]) -> None:
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
