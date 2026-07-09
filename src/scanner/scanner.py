from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from src.core.file_utils import is_under_or_equal as _is_under_or_equal
from src.core.output_sanitizer import render_output_path
from src.core.project import ensure_output_structure, load_json_compatible_yaml, output_dir, registry_path, report_path


@dataclass(frozen=True)
class Classification:
    id: str
    folder_name: str
    physical_presence: str
    inferred_data_type: str
    supported_in_pipeline: bool
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
            "supported_in_pipeline": self.supported_in_pipeline,
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


def scan_raw_data(project_root: Path, input_path: Path, *, output_root: Path | None = None) -> dict:
    ensure_output_structure(project_root, output_root=output_root)
    registry = load_json_compatible_yaml(registry_path(project_root))
    entries = list(registry["entries"])
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
    matched_folders_by_entry: dict[int, list[Path]] = {}
    file_candidates: dict[str, list[tuple[tuple[int, int, int, int, int], int, Path]]] = {}
    unsupported_candidates: dict[str, list[tuple[tuple[int, int, int, int, int], int, dict]]] = {}
    for entry_index, entry in enumerate(entries):
        folders = _matching_folders(input_path, entry)
        matched_folders_by_entry[entry_index] = folders
        if folders:
            allowed = {ext.lower() for ext in entry.get("extensions", [])}
            for folder in folders:
                for path in folder.rglob("*"):
                    if not path.is_file():
                        continue
                    score = _entry_path_score(input_path, path, entry, entry_index)
                    if not allowed or path.suffix.lower() in allowed:
                        file_candidates.setdefault(str(path.resolve()), []).append((score, entry_index, path))
                    else:
                        unsupported_candidates.setdefault(str(path.resolve()), []).append(
                            (
                                score,
                                entry_index,
                                {
                                    "path": str(path),
                                    "relative_path": str(path.relative_to(input_path)),
                                    "suffix": path.suffix.lower(),
                                    "size": path.stat().st_size,
                                    "matched_folder_name": entry["folder_name"],
                                    "inferred_data_type": entry["inferred_data_type"],
                                },
                            )
                        )

    files_by_entry: dict[int, list[Path]] = {index: [] for index in range(len(entries))}
    for resolved_path, candidates in file_candidates.items():
        _score, entry_index, path = max(candidates, key=lambda item: item[0])
        files_by_entry[entry_index].append(path)
        classified_paths.add(resolved_path)

    unsupported_files_in_known_folders = []
    unsupported_paths_by_entry: dict[int, list[Path]] = {index: [] for index in range(len(entries))}
    for resolved_path, candidates in unsupported_candidates.items():
        if resolved_path in classified_paths:
            continue
        _score, entry_index, item = max(candidates, key=lambda candidate: candidate[0])
        unsupported_files_in_known_folders.append(item)
        unsupported_paths_by_entry[entry_index].append(Path(str(item["path"])))

    for entry_index, entry in enumerate(entries):
        folders = matched_folders_by_entry.get(entry_index, [])
        files = sorted(files_by_entry.get(entry_index, []), key=lambda path: str(path).casefold())
        relevant_folders = _relevant_folders_for_entry(input_path, entry, folders, files + unsupported_paths_by_entry.get(entry_index, []))
        classifications.append(
            Classification(
                id=entry["id"],
                folder_name=entry["folder_name"],
                physical_presence="present" if folders else "absent",
                inferred_data_type=entry["inferred_data_type"],
                supported_in_pipeline=bool(entry["supported_in_pipeline"]),
                selected_processor=entry["selected_processor"],
                expected_file_extensions=list(entry.get("extensions", [])),
                special_handling=entry["special_handling"],
                reason="registry match from processor registry configuration",
                confidence="high" if folders else "planning",
                folder_path=str(relevant_folders[0]) if relevant_folders else None,
                folder_paths=[str(folder) for folder in relevant_folders],
                files=[str(path) for path in files],
            )
        )

    unclassified_files = [
        item
        for item in all_files
        if str(Path(str(item["path"])).resolve()) not in classified_paths
    ]
    manifest = {
        "scan_root": str(input_path),
        "raw_file_count": len(all_files),
        "files": all_files,
        "unclassified_files": unclassified_files,
        "unsupported_files_in_known_folders": unsupported_files_in_known_folders,
        "classifications": [item.as_dict() for item in classifications],
    }
    output_manifest = _render_manifest_for_output(manifest, project_root=project_root, output_root=output_root)
    reports = output_dir(project_root, "reports", output_root=output_root)
    (reports / "inventory_manifest.json").write_text(
        json.dumps(output_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_classification_report(project_root, output_manifest, output_root=output_root)
    _write_unclassified_manifest(project_root, output_manifest, output_root=output_root)
    return manifest


def _entry_path_score(raw_root: Path, path: Path, entry: dict, entry_index: int) -> tuple[int, int, int, int, int]:
    try:
        relative = path.relative_to(raw_root)
    except ValueError:
        relative = path
    segments = [_normalize_path_segment(part) for part in relative.parts[:-1]]
    keywords = [entry["folder_name"], *entry.get("folder_keywords", [])]
    best = (0, -1, 0, 0, -entry_index)
    for segment_index, segment in enumerate(segments):
        for keyword_index, keyword in enumerate(keywords):
            normalized_keyword = _normalize_path_segment(str(keyword))
            if not normalized_keyword:
                continue
            if segment == normalized_keyword:
                strength = 100 if keyword_index == 0 else 90
            elif _keyword_matches(normalized_keyword, segment):
                strength = 50 if keyword_index == 0 else 40
            else:
                continue
            best = max(best, (strength, segment_index, len(normalized_keyword), -keyword_index, -entry_index))
    return best


def _relevant_folders_for_entry(raw_root: Path, entry: dict, folders: list[Path], assigned_paths: list[Path]) -> list[Path]:
    exact = (raw_root / entry["folder_name"]).resolve()
    selected: list[Path] = []
    for folder in folders:
        resolved_folder = folder.resolve()
        if resolved_folder == exact or any(_is_under_or_equal(path.resolve(), resolved_folder) for path in assigned_paths):
            selected.append(folder)
    return selected


def _normalize_path_segment(value: str) -> str:
    return value.replace("\\", "/").casefold().strip()


def _keyword_matches(normalized_keyword: str, normalized_value: str) -> bool:
    if re.fullmatch(r"[a-z0-9]{1,4}", normalized_keyword):
        pattern = rf"(?<![a-z0-9]){re.escape(normalized_keyword)}(?![a-z0-9])"
        return re.search(pattern, normalized_value) is not None
    return normalized_keyword in normalized_value


def _render_manifest_for_output(manifest: dict, *, project_root: Path, output_root: Path | None = None) -> dict:
    rendered = dict(manifest)
    rendered["scan_root"] = render_output_path(manifest.get("scan_root"), project_root=project_root, output_root=output_root)
    rendered["files"] = [_render_file_entry(item, project_root=project_root, output_root=output_root) for item in manifest.get("files", [])]
    rendered["unclassified_files"] = [
        _render_file_entry(item, project_root=project_root, output_root=output_root)
        for item in manifest.get("unclassified_files", [])
    ]
    rendered["unsupported_files_in_known_folders"] = [
        _render_file_entry(item, project_root=project_root, output_root=output_root)
        for item in manifest.get("unsupported_files_in_known_folders", [])
    ]
    classifications = []
    for classification in manifest.get("classifications", []):
        item = dict(classification)
        item["folder_path"] = (
            render_output_path(item.get("folder_path"), project_root=project_root, output_root=output_root)
            if item.get("folder_path")
            else None
        )
        item["folder_paths"] = [
            render_output_path(path, project_root=project_root, output_root=output_root)
            for path in item.get("folder_paths", [])
        ]
        item["files"] = [
            render_output_path(path, project_root=project_root, output_root=output_root)
            for path in item.get("files", [])
        ]
        classifications.append(item)
    rendered["classifications"] = classifications
    return rendered


def _render_file_entry(item: dict, *, project_root: Path, output_root: Path | None = None) -> dict:
    rendered = dict(item)
    if "path" in rendered:
        rendered["path"] = render_output_path(rendered["path"], project_root=project_root, output_root=output_root)
    return rendered


def _write_classification_report(project_root: Path, manifest: dict, *, output_root: Path | None = None) -> None:
    lines = [
        "# Classification Report",
        "",
        f"Scan root: `{manifest['scan_root']}`",
        f"Raw file count: {manifest['raw_file_count']}",
        "",
        "| folder_name | physical_presence | inferred_data_type | supported_in_pipeline | selected_processor | special_handling | file_count |",
        "|---|---:|---|---:|---|---|---:|",
    ]
    for item in manifest["classifications"]:
        lines.append(
            "| {folder_name} | {physical_presence} | {inferred_data_type} | {supported_in_pipeline} | {selected_processor} | {special_handling} | {count} |".format(
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
    report_path(project_root, "classification_report.md", output_root=output_root).write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def _write_unclassified_manifest(project_root: Path, manifest: dict, *, output_root: Path | None = None) -> None:
    unclassified_dir = output_dir(project_root, "unclassified", output_root=output_root)
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
