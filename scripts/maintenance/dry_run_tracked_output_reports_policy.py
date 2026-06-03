from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from pathlib import Path


PILOT_UNTRACK = {
    "output/reports/phase1_8_manual_review_excluded_processed_sibling_formats.xlsx",
    "output/reports/phase1_8_manual_review_required_filtered.xlsx",
    "output/reports/phase1_9_manual_review_required_final.xlsx",
}


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


@dataclass(frozen=True)
class ReportRow:
    path: str
    status: str
    extension: str
    classification: str
    proposed_action: str


def classify(path: str, status: str) -> tuple[str, str]:
    name = Path(path).name
    extension = Path(path).suffix.lower()
    if path in PILOT_UNTRACK:
        return "generated XLSX report artifact", "git rm --cached pilot"
    if name.startswith("_tmp_") or name.startswith("tmp_"):
        return "temporary/debug report", "ignore only unless tracked explicit path is approved"
    if "pip_" in name and extension == ".txt":
        return "generated pip log", "ignore only"
    if "HANDOFF_TO_CHATGPT_FOR_NEXT_DECISION" in name and extension == ".json":
        return "generated handoff JSON snapshot", "ignore only"
    if "_temp_" in name and "deleted_items" in name and extension == ".json":
        return "generated temp deleted-items report", "ignore only"
    if extension in {".json", ".csv"}:
        return "generated or evidence report", "user decision required"
    if extension == ".md":
        return "human-readable report", "keep tracked/visible until user decides"
    if status == "modified":
        return "tracked modified report", "keep tracked unless explicit policy changes"
    return "report file", "review"


def collect_rows(root: Path) -> list[ReportRow]:
    tracked = set(git_lines(root, "ls-files", "output/reports"))
    modified = set(git_lines(root, "ls-files", "-m", "output/reports"))
    untracked = set(git_lines(root, "ls-files", "--others", "--exclude-standard", "output/reports"))
    ignored = {
        line[3:].replace("\\", "/")
        for line in git_lines(root, "status", "--ignored", "--short", "--", "output/reports")
        if line.startswith("!!")
    }
    paths = sorted(tracked | untracked | ignored)
    rows: list[ReportRow] = []
    for path in paths:
        if path in modified:
            status = "modified"
        elif path in tracked:
            status = "tracked"
        elif path in untracked:
            status = "untracked"
        elif path in ignored:
            status = "ignored"
        else:
            status = "unknown"
        classification, action = classify(path, status)
        rows.append(
            ReportRow(
                path=path,
                status=status,
                extension=Path(path).suffix.lower() or "<none>",
                classification=classification,
                proposed_action=action,
            )
        )
    return rows


def print_rows(rows: list[ReportRow]) -> None:
    print("| path | status | extension | classification | proposed action |")
    print("|---|---|---|---|---|")
    for row in rows:
        print(
            f"| `{row.path}` | {row.status} | {row.extension} | "
            f"{row.classification} | {row.proposed_action} |"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dry-run tracked output/reports policy classifier. It never modifies Git or files."
    )
    parser.add_argument("--root", type=Path, default=Path("."), help="Repository root.")
    args = parser.parse_args()
    rows = collect_rows(args.root.resolve())
    print("# Dry-Run Tracked Output Reports Policy")
    print()
    print("Read-only classification. No files or Git index entries were modified.")
    print()
    print_rows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
