from __future__ import annotations

from pathlib import Path

from PIL import Image

from src.adapters import (
    baseline_adapter,
    bet_pygaps_adapter,
    electrochem_import_adapter,
    eis_impedance_adapter,
    eis_pyimpspec_adapter,
    epr_adapter,
    hplc_adapter,
    image_metadata_adapter,
    ms_adapter,
    nmr_adapter,
    peak_detection_adapter,
    raman_adapter,
    xps_lmfitxps_adapter,
)
from src.adapters.common import contains_forbidden_claims
from src.processors.calculations import local_peak_positions, scipy_peak_positions, spectral_package_baseline_records


def test_baseline_adapter_smoke_and_fallback(monkeypatch):
    assert baseline_adapter.smoke_test()["ok"] is True
    monkeypatch.setattr(baseline_adapter, "import_optional", lambda _module: (None, "simulated missing"))
    result = baseline_adapter.process_or_analyze([0.0, 1.0, 2.0], [0.0, 1.0, 0.0])
    assert result["ok"] is False
    assert "simulated missing" in result["fallback_reason"]
    assert result["metadata_provenance"]["adapter"] == "baseline_adapter"


def test_peak_adapter_smoke_and_calculation_bridge():
    result = peak_detection_adapter.smoke_test()
    assert result["ok"] is True
    assert local_peak_positions([(0.0, 0.0), (1.0, 2.0), (2.0, 0.0)])
    baseline = spectral_package_baseline_records([(float(i), float(i % 3)) for i in range(8)])
    assert len(baseline) in {0, 8}


def test_processor_peak_bridge_uses_adapter_candidates(monkeypatch):
    def fake_process_or_analyze(x_values, y_values, **_kwargs):
        return {
            "ok": True,
            "candidate_peaks": [{"index": 1, "x": x_values[1], "y": y_values[1]}],
            "metadata_provenance": {"adapter": "peak_detection_adapter"},
        }

    monkeypatch.setattr(peak_detection_adapter, "process_or_analyze", fake_process_or_analyze)

    peaks = scipy_peak_positions([(0.0, 0.0), (1.0, 2.5), (2.0, 0.0)])

    assert peaks == [1.0]


def test_processor_peak_bridge_falls_back_without_adapter_candidates(monkeypatch):
    monkeypatch.setattr(
        peak_detection_adapter,
        "process_or_analyze",
        lambda *_args, **_kwargs: {"ok": False, "candidate_peaks": []},
    )

    peaks = scipy_peak_positions([(0.0, 0.0), (1.0, 0.0)])

    assert peaks == []


def test_processor_baseline_bridge_uses_adapter_corrected_signal(monkeypatch):
    def fake_process_or_analyze(x_values, y_values, **kwargs):
        assert kwargs["lam"] == 1e5
        assert kwargs["p"] == 0.01
        assert list(x_values) == [0.0, 1.0, 2.0]
        assert list(y_values) == [1.0, 2.0, 3.0]
        return {
            "ok": True,
            "baseline": [0.1, 0.2, 0.3],
            "corrected_signal": [0.9, 1.8, 2.7],
            "metadata_provenance": {"adapter": "baseline_adapter"},
        }

    monkeypatch.setattr(baseline_adapter, "process_or_analyze", fake_process_or_analyze)

    records = spectral_package_baseline_records([(0.0, 1.0), (1.0, 2.0), (2.0, 3.0)])

    assert records == [(0.1, 0.9), (0.2, 1.8), (0.3, 2.7)]


def test_processor_baseline_bridge_returns_empty_when_adapter_unavailable(monkeypatch):
    monkeypatch.setattr(
        baseline_adapter,
        "process_or_analyze",
        lambda *_args, **_kwargs: {
            "ok": False,
            "fallback_reason": "simulated missing",
            "baseline": [],
            "corrected_signal": [],
        },
    )

    records = spectral_package_baseline_records([(0.0, 1.0), (1.0, 2.0), (2.0, 3.0)])

    assert records == []


def test_eis_adapters_do_not_claim_circuits():
    result = eis_impedance_adapter.process_or_analyze([1000, 100], [10, 20], [-3, -4])
    assert result["ok"] is True
    assert result["bode"][0]["impedance_magnitude"] > 0
    assert eis_pyimpspec_adapter.smoke_test()["ok"] is True
    assert not contains_forbidden_claims([result["metadata_provenance"]["method"]])


def test_bet_xps_epr_and_raman_adapters_are_candidate_only():
    bet = bet_pygaps_adapter.process_or_analyze([0.05, 0.1], [1.0, 1.5])
    xps = xps_lmfitxps_adapter.smoke_test()["result"]
    epr = epr_adapter.process_or_analyze([330, 331, 332], [0.0, 1.0, -1.0])
    raman = raman_adapter.process_or_analyze([float(i) for i in range(20)], [0.0, 1.0, 0.0, *([0.1] * 17)])
    assert bet["manual_check_required"] is True
    assert xps["residual_labels_excluded"]
    assert epr["manual_check_required"] is True
    assert raman["manual_check_required"] is True


def test_image_metadata_adapter_probe_only(tmp_path: Path):
    image_path = tmp_path / "sem_preview.tif"
    Image.new("L", (32, 16), color=128).save(image_path, dpi=(600, 600))
    result = image_metadata_adapter.process_or_analyze(image_path, output_dir=tmp_path / "thumbs")
    assert result["ok"] is True
    assert result["metadata"]["width"] == 32
    assert Path(result["metadata"]["thumbnail"]).is_file()
    assert "morphology" in " ".join(image_metadata_adapter.capabilities()["forbidden_claims"])


def test_scan_only_import_adapters_smoke_without_scientific_assignment(tmp_path: Path):
    peaklist = tmp_path / "peaklist.xml"
    peaklist.write_text("<peaklist><peak ppm=\"1.23\" intensity=\"42\" /></peaklist>", encoding="utf-8")
    assert nmr_adapter.process_or_analyze(peaklist)["peaklist_entries"] == 1
    assert ms_adapter.process_or_analyze(tmp_path / "sample.mzML")["format_family"] == "mzML"
    assert electrochem_import_adapter.smoke_test()["ok"] is True
    assert hplc_adapter.smoke_test()["ok"] is True
    combined_claims = (
        nmr_adapter.capabilities()["forbidden_claims"]
        + ms_adapter.capabilities()["forbidden_claims"]
        + hplc_adapter.capabilities()["forbidden_claims"]
    )
    assert "no product identification" in combined_claims
