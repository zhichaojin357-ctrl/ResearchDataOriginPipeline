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
    xps_vgd_reader_adapter,
)
from src.adapters.common import contains_forbidden_claims
from src.processors.calculations import (
    local_peak_positions,
    scipy_peak_positions,
    spectral_package_baseline_records,
    type_specific_results,
    xps_export_results,
)
from src.processors.eis import EisPoint, draft_fit_eis_randles_cpe


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


def test_eis_draft_fit_uses_impedance_adapter_when_available(monkeypatch):
    calls = []

    def fake_fit(frequency, z_real, minus_z_imag, *, fit_points=240):
        calls.append((list(frequency), list(z_real), list(minus_z_imag), fit_points))
        return {
            "ok": True,
            "method": "impedance_custom_circuit_R0_p_R1_CPE1_candidate",
            "parameters": {"Rs": 8.0, "Rct": 55.0, "Q": 0.00025, "n": 0.92},
            "residual_sse": 0.42,
            "fit_points": [(8.0, 0.0), (35.0, 20.0), (63.0, 0.0)],
            "semicircle_classification": "depressed semicircle candidate",
            "metadata_provenance": {"adapter": "eis_impedance_adapter"},
        }

    monkeypatch.setattr(eis_impedance_adapter, "fit_randles_cpe_candidate", fake_fit)

    fit = draft_fit_eis_randles_cpe(
        [
            EisPoint(1, 1000.0, 8.0, 0.1),
            EisPoint(2, 100.0, 18.0, 12.0),
            EisPoint(3, 10.0, 42.0, 15.0),
            EisPoint(4, 1.0, 63.0, 0.2),
        ],
        fit_points=120,
    )

    assert calls == [([1000.0, 100.0, 10.0, 1.0], [8.0, 18.0, 42.0, 63.0], [0.1, 12.0, 15.0, 0.2], 120)]
    assert fit.method == "impedance_custom_circuit_R0_p_R1_CPE1_candidate"
    assert fit.parameters["Rct"] == 55.0
    assert fit.adapter_provenance["adapter"] == "eis_impedance_adapter"


def test_epr_processor_metrics_are_sourced_from_epr_adapter(monkeypatch):
    def fake_process(field, intensity, *, microwave_frequency_ghz=None):
        assert list(field) == [330.0, 331.0, 332.0]
        assert list(intensity) == [0.0, 1.0, -1.0]
        assert microwave_frequency_ghz == [9.8, 9.8, 9.8]
        return {
            "ok": True,
            "peak_to_peak_intensity_candidate": 99.0,
            "minimum_intensity_field": 332.0,
            "maximum_intensity_field": 331.0,
            "g_candidate_at_max_intensity": 2.11,
            "metadata_provenance": {"adapter": "epr_adapter"},
        }

    monkeypatch.setattr(epr_adapter, "process_or_analyze", fake_process)

    result = type_specific_results(
        "EPR",
        [(330.0, 0.0), (331.0, 1.0), (332.0, -1.0)],
        [
            {"magnetic field G": "330", "intensity": "0", "microwave frequency GHz": "9.8"},
            {"magnetic field G": "331", "intensity": "1", "microwave frequency GHz": "9.8"},
            {"magnetic field G": "332", "intensity": "-1", "microwave frequency GHz": "9.8"},
        ],
    )

    assert result["peak_to_peak_intensity_candidate"] == 99.0
    assert result["maximum_intensity_field"] == 331.0
    assert result["adapter_results"]["EPR"]["metadata_provenance"]["adapter"] == "epr_adapter"


def test_xps_export_results_are_sourced_from_lmfitxps_adapter(monkeypatch):
    def fake_process(curves):
        assert set(curves) == {"raw_intensity", "Backgnd.", "Envelope", "Bi 4f component"}
        return {
            "ok": True,
            "component_count": 1,
            "component_labels": ["Bi 4f component"],
            "residual_labels_excluded": [],
            "metadata_provenance": {"adapter": "xps_lmfitxps_adapter"},
        }

    monkeypatch.setattr(xps_lmfitxps_adapter, "process_or_analyze", fake_process)

    result = xps_export_results(
        [
            {
                "Binding Energy": "165",
                "raw_intensity": "10",
                "Backgnd.": "1",
                "Envelope": "9",
                "Bi 4f component": "4",
            }
        ]
    )

    assert result["xps_component_count"] == 1
    assert result["xps_component_columns"] == ["Bi 4f component"]
    assert result["adapter_results"]["XPS"]["metadata_provenance"]["adapter"] == "xps_lmfitxps_adapter"


def test_xps_vgd_reader_adapter_converts_spectrum_to_rows(monkeypatch, tmp_path: Path):
    class FakeSpectrum:
        core_level = "Bi4f"
        binding_energy = [165.0, 164.5]
        corrected_intensity = [100.0, 120.0]
        intensity = [90.0, 110.0]
        pass_energy = 20.0

    class FakeVgd:
        spectra = [FakeSpectrum()]
        num_spectra = 1

    monkeypatch.setattr(xps_vgd_reader_adapter, "read_vgd", lambda path: FakeVgd())

    result = xps_vgd_reader_adapter.read_vgd_rows(tmp_path / "Bi4f.vgd")

    assert result.rows == [
        {"binding energy": "165.0", "intensity": "100.0", "raw_intensity_optional": "90.0", "core_level": "Bi4f"},
        {"binding energy": "164.5", "intensity": "120.0", "raw_intensity_optional": "110.0", "core_level": "Bi4f"},
    ]
    assert result.warnings == ["VGD spectrum pass energy requires manual review: 20.0"]
    assert result.metadata_provenance["adapter"] == "xps_vgd_reader_adapter"


def test_bet_xps_epr_and_raman_adapters_are_candidate_only():
    bet = bet_pygaps_adapter.process_or_analyze([0.05, 0.1], [1.0, 1.5])
    xps = xps_lmfitxps_adapter.smoke_test()["result"]
    epr = epr_adapter.process_or_analyze([330, 331, 332], [0.0, 1.0, -1.0], microwave_frequency_ghz=[9.8, 9.8, 9.8])
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
