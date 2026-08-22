"""Run GapBridge's network-free local demo preflight."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gapbridge.sprint5_demo import (  # noqa: E402
    format_preflight_report,
    run_demo_preflight,
)


def main() -> int:
    report = run_demo_preflight(PROJECT_ROOT)
    print(format_preflight_report(report))
    return 0 if report.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
