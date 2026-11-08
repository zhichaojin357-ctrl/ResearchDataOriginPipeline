from __future__ import annotations

from pathlib import Path

import pytest

import src.core.template_product_builder as builder
from src.core.template_product_builder import TemplateCandidate
from src.core.template_product_common import TargetPairing


class _FakeJadeIndex:
    calls: list[tuple[object, ...]] = []

    def __init__(self, database_dir: Path, stem: str) -> None:
        self.database_dir = database_dir
        self.stem = stem
        self.xid_path = database_dir / f"{stem}.xid"
        self.calls.append(("open", database_dir, stem))

    def __enter__(self) -> _FakeJadeIndex:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.calls.append(("close",))

    def index_for_pdf(self, identifier: str) -> int:
        self.calls.append(("index", identifier))
        if identifier == "missing":
            raise KeyError("Card is not present in ICSD-ALL: missing")
        return 7

    def metadata(self, index: int) -> dict[str, object]:
        self.calls.append(("metadata", index))
        return {"card_id": "97-000-0001", "formula": "C"}

    def peaks(
        self,
        index: int,
        *,
        wavelength_angstrom: float,
        x_min: float,
        x_max: float,
    ) -> list[dict[str, float]]:
        self.calls.append(("peaks", index, wavelength_angstrom, x_min, x_max))
        return [
            {"two_theta_deg": 10.2, "relative_intensity": 100.0},
            {"two_theta_deg": 25.4, "relative_intensity": 50.0},
        ]


def _pairing(tmp_path: Path, card: dict[str, object]) -> tuple[TargetPairing, TemplateCandidate, Path, Path]:
    data_dir = tmp_path / "data"
    database_dir = tmp_path / "jade"
    data_dir.mkdir()
    database_dir.mkdir()
    current = data_dir / "DQL-5-2.txt"
    sibling = data_dir / "unselected.txt"
    current.write_text("10 1\n20 2\n30 3\n", encoding="utf-8")
    sibling.write_text("10 90\n20 90\n30 90\n", encoding="utf-8")
    template = TemplateCandidate("XRD", tmp_path / "template.opju", "unit", graph_page="Graph4", plot_count=5)
    pairing = TargetPairing(
        "XRD",
        "XRD",
        "",
        "test",
        [current],
        "test",
        template.path,
        raw={"xrd_reference_card": {"database_dir": str(database_dir), **card}},
    )
    return pairing, template, current, database_dir


def test_explicit_jade_card_uses_only_the_configured_card_without_sibling_scan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pairing, template, current, database_dir = _pairing(
        tmp_path,
        {"card_id": "97-000-0001", "label": "Graphite"},
    )
    _FakeJadeIndex.calls = []
    monkeypatch.setattr(builder, "JadeIndex", _FakeJadeIndex)
    monkeypatch.setattr(
        builder,
        "_template_xrd_reference_card_files",
        lambda *args: pytest.fail("an explicit Jade card must not scan text-card siblings"),
    )

    assert builder._template_xrd_target_sample_series_count(pairing, template) == 4
    built = builder._build_template_xrd_multisource_table(pairing, template)

    assert built is not None
    reference_header = "Graphite_PDF_97-000-0001_candidate_JCPDS_card_sticks"
    assert built["headers"] == ["two_theta_deg", "DQL-5-2", reference_header]
    assert built["alignment"]["reference_card"]["card"]["card_id"] == "97-000-0001"
    assert built["alignment"]["reference_card"]["manual_check_required"] is True
    assert [Path(value) for value in built["alignment"]["used_files"]] == [
        current,
        database_dir / "ICSD-ALL.xid",
    ]
    assert built["alignment"]["original_pairing_files"] == [str(current)]
    reference_values = [float(row[2]) for row in built["rows"]]
    assert reference_values == pytest.approx([0.75, 0.0, 0.375])
    assert ("index", "97-000-0001") in _FakeJadeIndex.calls
    assert ("metadata", 7) in _FakeJadeIndex.calls
    assert any(call[0] == "peaks" and call[2] == 1.5406 for call in _FakeJadeIndex.calls)


def test_explicit_jade_card_failure_does_not_fall_back_to_text_cards(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pairing, template, _current, _database_dir = _pairing(tmp_path, {"card_id": "missing"})
    monkeypatch.setattr(builder, "JadeIndex", _FakeJadeIndex)
    monkeypatch.setattr(
        builder,
        "_template_xrd_reference_card_files",
        lambda *args: pytest.fail("a bad explicit card must not fall back to a discovered text card"),
    )

    with pytest.raises(KeyError, match="Card is not present"):
        builder._build_template_xrd_multisource_table(pairing, template)


def test_explicit_jade_card_requires_an_absolute_database_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pairing, template, _current, _database_dir = _pairing(tmp_path, {"card_id": "97-000-0001"})
    pairing = TargetPairing(
        **{**pairing.__dict__, "raw": {"xrd_reference_card": {"database_dir": "relative-jade", "card_id": "97-000-0001"}}}
    )
    monkeypatch.setattr(
        builder,
        "_template_xrd_reference_card_files",
        lambda *args: pytest.fail("invalid explicit config must not scan text-card siblings"),
    )

    with pytest.raises(ValueError, match="must be an absolute path"):
        builder._template_xrd_target_sample_series_count(pairing, template)


def test_explicit_jade_card_without_scan_range_peaks_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pairing, template, _current, _database_dir = _pairing(tmp_path, {"card_id": "97-000-0001"})
    monkeypatch.setattr(builder, "JadeIndex", _FakeJadeIndex)
    monkeypatch.setattr(_FakeJadeIndex, "peaks", lambda *args, **kwargs: [])
    with pytest.raises(ValueError, match="no positive peaks"):
        builder._build_template_xrd_multisource_table(pairing, template)
