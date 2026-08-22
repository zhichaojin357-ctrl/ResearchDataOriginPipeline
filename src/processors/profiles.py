from __future__ import annotations

from types import MappingProxyType


def _profile(
    data_type: str,
    selected_processor: str,
    manual_check_items: tuple[str, ...],
    forbidden_claims: tuple[str, ...],
    plot_type_hints: tuple[str, ...],
) -> dict[str, object]:
    return {
        "data_type": data_type,
        "selected_processor": selected_processor,
        "manual_check_items": manual_check_items,
        "forbidden_claims": forbidden_claims,
        "plot_type_hints": plot_type_hints,
    }


SUPPORTED_PROCESSOR_PROFILES = MappingProxyType(
    {
        "photocurrent": _profile(
            "photocurrent",
            "photocurrent_processor",
            ("confirm light on/off intervals and current units",),
            ("do not equate higher photocurrent with better carrier separation",),
            ("current-time line plot",),
        ),
        "BET": _profile(
            "BET",
            "bet_processor",
            ("confirm reported surface area, pore volume, and pore diameter source tables",),
            ("do not infer pore structure from exported tables alone",),
            ("adsorption-desorption isotherm", "pore size distribution if exported"),
        ),
        "EPR": _profile(
            "EPR",
            "epr_processor",
            (
                "confirm magnetic-field unit (G/gauss or mT), peak-to-peak intensity, "
                "and microwave frequency before using g candidates",
            ),
            ("do not assign radical species automatically",),
            ("magnetic-field intensity spectrum",),
        ),
        "PL": _profile(
            "PL",
            "pl_processor",
            ("confirm normalization and candidate peak positions",),
            ("do not equate lower PL intensity with reduced recombination",),
            ("wavelength-intensity overlay",),
        ),
        "XPS": _profile(
            "XPS",
            "xps_processor",
            ("confirm binding-energy calibration, peak positions, areas, and no valence assignment",),
            (
                "do not assign valence states automatically",
                "do not infer electron-transfer direction or heterojunction mechanism",
            ),
            ("binding-energy spectrum", "exported fit components if present"),
        ),
        "XRD": _profile(
            "XRD",
            "xrd_processor",
            (
                "confirm candidate peak positions, local Jade/PDF card identifiers, match tolerances, alternatives, and any normalization",
            ),
            ("do not label crystal planes or claim phase purity automatically",),
            ("2theta-intensity line plot", "stacked pattern overlay"),
        ),
        "UV-vis DRS": _profile(
            "UV-vis DRS",
            "uvvis_drs_processor",
            ("confirm Kubelka-Munk conversion and Tauc linear interval candidates",),
            ("do not confirm final band gap or band-structure mechanism automatically",),
            ("DRS spectrum", "Tauc candidate plot"),
        ),
        "photocurrent_response": _profile(
            "photocurrent_response",
            "photocurrent_processor",
            ("confirm response-cycle boundaries and current units",),
            ("do not equate response magnitude with carrier separation efficiency",),
            ("current-time response plot",),
        ),
        "reaction_condition_screening": _profile(
            "reaction_condition_screening",
            "condition_screening_processor",
            ("confirm condition grouping, replicates, and error information",),
            ("do not claim final optimal conditions automatically",),
            ("bar chart", "condition trend line plot"),
        ),
        "FTIR": _profile(
            "FTIR",
            "ftir_processor",
            ("confirm baseline correction and candidate peak or valley positions",),
            ("do not assign chemical bonds automatically",),
            ("wavenumber-intensity spectrum",),
        ),
        "Raman": _profile(
            "Raman",
            "raman_processor",
            ("confirm baseline correction, normalization, and candidate peaks",),
            ("do not infer defect type automatically",),
            ("Raman-shift intensity spectrum",),
        ),
        "Mott-Schottky": _profile(
            "Mott-Schottky",
            "mott_schottky_processor",
            ("confirm frequency grouping and flat-band candidate intervals",),
            ("do not equate flat-band potential with CB or VB automatically",),
            ("1/C^2-potential plot",),
        ),
        "HPLC/LC exported data": _profile(
            "HPLC/LC exported data",
            "lc_exported_data_processor",
            ("confirm exported peak table fields and calibration assumptions",),
            ("do not identify products or compute conversion without complete calibration input",),
            ("chromatogram", "peak table summary"),
        ),
        "HPLC/LC OpenLab raw data": _profile(
            "HPLC/LC OpenLab raw data",
            "hplc_openlab_raw_exporter",
            (
                "confirm acquisition cutoff, detector wavelength, OpenLab integration boundaries, "
                "and any calibration or analyte-role mapping",
            ),
            (
                "do not promote vendor peak rows or retention times to chemical identity",
                "do not compute conversion, selectivity, or yield without complete calibration and role mapping",
            ),
            ("no plot; compact summary and batch-specific data-only Excel workbooks",),
        ),
        "EIS": _profile(
            "EIS",
            "eis_processor",
            ("confirm imaginary-impedance sign convention plus frequency, impedance, and phase units",),
            ("do not select equivalent circuits or infer mechanism automatically",),
            ("Nyquist plot", "Bode magnitude and phase plots"),
        ),
    }
)
