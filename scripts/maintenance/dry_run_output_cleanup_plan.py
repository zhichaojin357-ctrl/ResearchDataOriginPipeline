from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from pathlib import Path


DIRECTORIES = {
    "output/phase1_6_origin_results_20260531_041538": (
        "locked/canonical package",
        "NEVER AUTO DELETE",
    ),
    "output/final_locked_results": (
        "release-freeze/provenance",
        "NEVER AUTO DELETE",
    ),
    "output/phase1_5_processed_results_20260531_005613": (
        "historical package",
        "KEEP UNTIL USER CONFIRMS",
    ),
    "output/processed_data": (
        "generated historical outputs",
        "USER CAN REVIEW FOR DELETE",
    ),
    "output/metadata": (
        "generated metadata",
        "USER CAN REVIEW FOR DELETE",
    ),
    "output/origin_files": (
        "generated OPJU outputs",
        "USER CAN REVIEW FOR DELETE",
    ),
    "output/figures_tif": (
        "generated figure outputs",
        "USER CAN REVIEW FOR DELETE",
    ),
    "output/figures_preview": (
        "generated preview outputs",
        "USER CAN REVIEW FOR DELETE",
    ),
    "output/reports": (
        "mixed report evidence store",
        "KEEP UNTIL USER CONFIRMS",
    ),
    "output/review_dashboard": (
        "review dashboard evidence",
        "KEEP UNTIL USER CONFIRMS",
    ),
    "output/material_collections": (
        "large material-selection package",
        "KEEP UNTIL USER CONFIRMS",
    ),
    "output/opju_exemplar_regression": (
        "regression/reference material",
        "KEEP UNTIL USER CONFIRMS",
    ),
    "output/bet_reference_compare": (
        "regression/reference material",
        "KEEP UNTIL USER CONFIRMS",
    ),
    "output/adapter_shadow_runs": (
        "generated shadow-run evidence",
        "USER CAN REVIEW FOR DELETE",
    ),
    "output/xps_heterojunction_stacked": (
        "dedicated XPS output evidence",
        "KEEP UNTIL USER CONFIRMS",
    ),
    "output/runs": (
        "future generated run output",
        "USER CAN REVIEW FOR DELETE",
    ),
    "output/regression": (
        "future regression output",
        "USER CAN REVIEW FOR DELETE",
    ),
    "outputs/xps_in_situ_20260506": (
        "historical XPS in-situ output",
        "KEEP UNTIL USER CONFIRMS",
    ),
}


@dataclass(frozen=True)
class DirectoryRow:
    path: str
    exists: bool
    files: int
    size_mb: float
    dirty: int
    role: str
    risk: str


def git_lines(root: Path, *args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or f"git {' '.join(args)} failed")
    return [line for line in result.stdout.splitlines() if line.strip()]


def dirty_counts(root: Path) -> dict[str, int]:
    counts = {path: 0 for path in DIRECTORIES}
    for line in git_lines(root, "status", "--porcelain=v1", "--", "output", "outputs"):
        path = line[3:].replace("\\", "/")
        for directory in counts:
            if path == directory or path.startswith(directory + "/"):
                counts[directory] += 1
    return counts


def inventory(root: Path) -> list[DirectoryRow]:
    dirty = dirty_counts(root)
    rows: list[DirectoryRow] = []
    for rel_path, (role, risk) in DIRECTORIES.items():
        path = root / rel_path
        files = [item for item in path.rglob("*") if item.is_file()] if path.exists() else []
        size = sum(item.stat().st_size for item in files)
        rows.append(
            DirectoryRow(
                path=rel_path,
                exists=path.exists(),
                files=len(files),
                size_mb=round(size / (1024 * 1024), 2),
                dirty=dirty[rel_path],
                role=role,
                risk=risk,
            )
        )
    return rows


def print_markdown_table(rows: list[DirectoryRow]) -> None:
    print("| path | exists | files | size MB | dirty | role | risk |")
    print("|---|---:|---:|---:|---:|---|---|")
    for row in rows:
        print(
            f"| `{row.path}` | {str(row.exists).lower()} | {row.files} | "
            f"{row.size_mb:.2f} | {row.dirty} | {row.role} | {row.risk} |"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dry-run output cleanup inventory. This script never deletes or moves files."
    )
    parser.add_argument("--root", type=Path, default=Path("."), help="Repository root.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Explicit no-op mode. Deletion is not implemented.",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    rows = inventory(root)
    print("# Dry-Run Output Cleanup Plan")
    print()
    print("This is read-only. No files were deleted, moved, restored, or modified.")
    print()
    print_markdown_table(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
