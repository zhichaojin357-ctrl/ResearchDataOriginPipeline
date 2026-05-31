from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from src.core.project import ensure_output_structure, load_json_compatible_yaml, output_dir, registry_path, report_path


@dataclass(frozen=True)
class Classification:
    id: str
    folder_name: str
    physical_presence: str
    inferred_data_type: str
    supported_in_phase_1: bool
    selected_processor: str
    expected_file_extensions: list[str]
    special_handling: str
    reason: str
    confidence: str
    folder_path: str | None
    folder_paths: list[str]
    files: list[str]

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "folder_name": self.folder_name,
            "physical_presence": self.physical_presence,
            "inferred_data_type": self.inferred_data_type,
            "supported_in_phase_1": self.supported_in_phase_1,
            "selected_processor": self.selected_processor,
            "expected_file_extensions": self.expected_file_extensions,
            "special_handling": self.special_handling,
            "reason": self.reason,
            "confidence": self.confidence,
            "folder_path": self.folder_path,
            "folder_paths": self.folder_paths,
            "files": self.files,
        }


def _matching_folders(raw_root: Path, entry: dict) -> list[Path]:
    if not raw_root.exists():
        return []
    matches: list[Path] = []
    exact = raw_root / entry["folder_name"]
    if exact.exists() and exact.is_dir():
        matches.append(exact)
    lowered_keywords = [str(k).lower() for k in entry.get("folder_keywords", [])]
    for child in raw_root.rglob("*"):
        if not child.is_dir() or child == exact:
            continue
        name = child.name.lower()
        if any(keyword and keyword.lower() in name for keyword in lowered_keywords):
            matches.append(child)
    deduped: list[Path] = []
    seen: set[str] = set()
    for folder in matches:
        key = str(folder.resolve()).lower()
        if key not in seen:
            seen.add(key)
            deduped.append(folder)
    return deduped


def scan_raw_data(project_root: Path, input_path: Path) -> dict:
    ensure_output_structure(project_root)
    registry = load_json_compatible_yaml(registry_path(project_root))
    input_path = input_path.absolute()
    classifications: list[Classification] = []
    all_files = []

    if input_path.exists():
        for file_path in input_path.rglob("*"):
            if file_path.is_file():
                all_files.append(
                    {
                        "path": str(file_path),
                        "relative_path": str(file_path.relative_to(input_path)),
                        "suffix": file_path.suffix.lower(),
                        "size": file_path.stat().st_size,
                    }
                )

    classified_paths: set[str] = set()
    unsupported_files_in_known_folders = []
    for entry in registry["entries"]:
        folders = _matching_folders(input_path, entry)
        files = []
        if folders:
            allowed = {ext.lower() for ext in entry.get("extensions", [])}
            for folder in folders:
                for path in folder.rglob("*"):
                    if not path.is_file():
                        continue
                    if not allowed or path.suffix.lower() in allowed:
                        files.append(str(path))
                    else:
                        unsupported_files_in_known_folders.append(
                            {
                                "path": str(path),
                                "relative_path": str(path.relative_to(input_path)),
                                "suffix": path.suffix.lower(),
                                "size": path.stat().st_size,
                                "matched_folder_name": entry["folder_name"],
                                "inferred_data_type": entry["inferred_data_type"],
                            }
                        )
            classified_paths.update(str(Path(path).resolve()) for path in files)
        classifications.append(
            Classification(
                id=entry["id"],
                folder_name=entry["folder_name"],
                physical_presence="present" if folders else "absent",
                inferred_data_type=entry["inferred_data_type"],
                supported_in_phase_1=bool(entry["supported_in_phase_1"]),
                selected_processor=entry["selected_processor"],
                expected_file_extensions=list(entry.get("extensions", [])),
                special_handling=entry["special_handling"],
                reason="registry match from Phase 1 configuration",
                confidence="high" if folders else "planning",
                folder_path=str(folders[0]) if folders else None,
                folder_paths=[str(folder) for folder in folders],
                files=files,
            )
        )

    unclassified_files = [
        item
        for item in all_files
        if str(Path(item["path"]).resolve()) not in classified_paths
    ]
    manifest = {
        "scan_root": str(input_path),
        "raw_file_count": len(all_files),
        "files": all_files,
        "unclassified_files": unclassified_files,
        "unsupported_files_in_known_folders": unsupported_files_in_known_folders,
        "classifications": [item.as_dict() for item in classifications],
    }
    reports = output_dir(project_root, "reports")
    (reports / "inventory_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_classification_report(project_root, manifest)
    _write_unclassified_manifest(project_root, manifest)
    return manifest


def _write_classification_report(project_root: Path, manifest: dict) -> None:
    lines = [
        "# Classification Report",
        "",
        f"Scan root: `{manifest['scan_root']}`",
        f"Raw file count: {manifest['raw_file_count']}",
        "",
        "| folder_name | physical_presence | inferred_data_type | supported_in_phase_1 | selected_processor | special_handling | file_count |",
        "|---|---:|---|---:|---|---|---:|",
    ]
    for item in manifest["classifications"]:
        lines.append(
            "| {folder_name} | {physical_presence} | {inferred_data_type} | {supported_in_phase_1} | {selected_processor} | {special_handling} | {count} |".format(
                count=len(item["files"]),
                **item,
            )
        )
    lines.extend(["", f"Unclassified file count: {len(manifest.get('unclassified_files', []))}"])
    for item in manifest.get("unclassified_files", []):
        lines.append(f"- `{item['relative_path']}` ({item['suffix'] or 'no suffix'})")
    lines.extend(["", f"Unsupported files in known folders: {len(manifest.get('unsupported_files_in_known_folders', []))}"])
    for item in manifest.get("unsupported_files_in_known_folders", []):
        lines.append(
            f"- `{item['relative_path']}` matched `{item['matched_folder_name']}` but suffix `{item['suffix'] or 'none'}` is unsupported"
        )
    report_path(project_root, "classification_report.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def _write_unclassified_manifest(project_root: Path, manifest: dict) -> None:
    unclassified_dir = output_dir(project_root, "unclassified")
    (unclassified_dir / "unclassified_manifest.json").write_text(
        json.dumps(
            {
                "scan_root": manifest["scan_root"],
                "unclassified_file_count": len(manifest.get("unclassified_files", [])),
                "files": manifest.get("unclassified_files", []),
                "unsupported_files_in_known_folders": manifest.get("unsupported_files_in_known_folders", []),
                "note": "Raw data files are not copied or moved; this manifest only records unclassified paths.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
