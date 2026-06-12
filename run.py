"""CLI entry point for the maintained research-data pipeline."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).absolute().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cli import main


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError) as exc:
        print(f"run.py: error: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
