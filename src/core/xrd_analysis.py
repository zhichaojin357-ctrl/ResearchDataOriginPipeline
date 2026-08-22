from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.core.project import (
    ensure_output_path_separate_from_inputs,
    load_json_compatible_yaml,
    registry_path,
)
from src.core.xrd_jade import DEFAULT_DATABASE_STEM, XrdPhaseMatchOptions
from src.processors.base import process_table_dataset, safe_name


RAW_BINARY_MAGICS = (b"RAW1.01", b"RAW2", b"RAW ")


@dataclass(frozen=True)
class XrdAnalysisOptions:
    source: Path
    database_dir: Path
    output_root: Path
    database_stem: str = DEFAULT_DATABASE_STEM
    card_ids: tuple[str, ...] = ()
    card_queries: tuple[str, ...] = ()
    full_library_screen: bool = False
    query_limit: int = 20
    result_limit: int = 20
    wavelength_angstrom: float = 1.5406
    peak_prominence_normalized: float = 0.05
    minimum_peak_distance_deg: float = 0.10
    card_tolerance_deg: float = 0.20
    minimum_card_relative_intensity: float = 10.0
    force: bool = False


def run_xrd_analysis(project_root: Path, options: XrdAnalysisOptions) -> dict[str, object]:
    project_root = project_root.resolve()
    source = options.source if options.source.is_absolute() else project_root / options.source
    source = source.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"XRD source is not a file: {source}")
    _reject_binary_raw(source)

    output_root = options.output_root if options.output_root.is_absolute() else project_root / options.output_root
    output_root = output_root.resolve()
    database_dir = options.database_dir if options.database_dir.is_absolute() else project_root / options.database_dir
    database_dir = database_dir.resolve()
    ensure_output_path_separate_from_inputs(project_root, output_root, [source, database_dir])
    phase_options = XrdPhaseMatchOptions(
        database_dir=database_dir,
        database_stem=options.database_stem,
        card_ids=options.card_ids,
        card_queries=options.card_queries,
        full_library_screen=options.full_library_screen,
        query_limit=options.query_limit,
        result_limit=options.result_limit,
        wavelength_angstrom=options.wavelength_angstrom,
        peak_prominence_normalized=options.peak_prominence_normalized,
        minimum_peak_distance_deg=options.minimum_peak_distance_deg,
        card_tolerance_deg=options.card_tolerance_deg,
        minimum_card_relative_intensity=options.minimum_card_relative_intensity,
    )
    phase_options.validate()

    classification = _xrd_classification(project_root)
    metadata = process_table_dataset(
        project_root,
        classification,
        source,
        no_origin=True,
        force=options.force,
        output_root=output_root,
        xrd_phase_options=phase_options,
    )
    slug = safe_name(source.stem)
    return {
        "ok": metadata.get("processing_status") == "processed_no_origin",
        "processing_status": metadata.get("processing_status"),
        "processed_data": output_root / "processed_data" / "XRD" / f"{slug}_processed.csv",
        "metadata": output_root / "metadata" / "XRD" / slug / "metadata.json",
        "card_match_candidates": output_root / "metadata" / "XRD" / slug / "card_match_candidates.json",
        "origin_launched": False,
        "plot_generated": False,
    }


def _xrd_classification(project_root: Path) -> dict[str, object]:
    registry = load_json_compatible_yaml(registry_path(project_root))
    for entry in registry.get("entries", []):
        if entry.get("inferred_data_type") == "XRD":
            if entry.get("supported_in_pipeline") is not True:
                raise ValueError("XRD is not enabled in the current processor registry")
            return dict(entry)
    raise KeyError("XRD entry is missing from processor_registry.yaml")


def _reject_binary_raw(source: Path) -> None:
    with source.open("rb") as handle:
        prefix = handle.read(16)
    if source.suffix.casefold() == ".raw" or prefix.startswith(RAW_BINARY_MAGICS):
        magic = prefix[:8].split(b"\x00", 1)[0].decode("latin-1", errors="replace")
        raise ValueError(
            f"Binary vendor RAW is detected ({magic or 'unknown magic'}) but is not decoded by the XRD processor. "
            "Use the instrument-exported same-name TXT/CSV/XY/XLSX file."
        )
