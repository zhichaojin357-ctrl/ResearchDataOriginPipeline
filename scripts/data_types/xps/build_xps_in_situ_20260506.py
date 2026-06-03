from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.xps_in_situ import build_xps_in_situ_outputs


def main() -> int:
    parser = argparse.ArgumentParser(description="Build CWO/BOBC/Dark/Light in-situ fitted XPS panels.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs") / "xps_in_situ_20260506",
        help="Output directory under the project root.",
    )
    parser.add_argument("--with-origin", action="store_true", help="Also save an Origin OPJU project.")
    args = parser.parse_args()

    output_dir = args.output_dir if args.output_dir.is_absolute() else PROJECT_ROOT / args.output_dir
    result = build_xps_in_situ_outputs(PROJECT_ROOT, output_dir, with_origin=args.with_origin)
    print(f"output_dir={result.output_dir}")
    print("plotted=" + ",".join(panel.panel_title for panel in result.plotted_panels))
    print("origin_ok=" + str(result.origin_status.get("ok")))
    if result.missing:
        print("missing=" + "; ".join(f"{key}: {', '.join(value)}" for key, value in result.missing.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
