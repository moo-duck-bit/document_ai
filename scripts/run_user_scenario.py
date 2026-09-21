# -*- coding: utf-8 -*-
"""CLI: run a user scenario end-to-end (CR + MDSR/MDDR → outputs).

Does not use expected_impact. Does not write into frozen Trial 1/2 directories.

Example:
  python scripts/run_user_scenario.py --scenario data/user_scenarios/scenario-001
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from document_ai.scenario.runner import run_user_scenario


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="User Scenario Runner (CR + MDSR/MDDR)")
    parser.add_argument(
        "--scenario",
        required=True,
        type=Path,
        help="Path to scenario directory (contains input/change_request.txt and input/reference/*.docx)",
    )
    parser.add_argument("--top-k", type=int, default=15)
    parser.add_argument(
        "--keep-output",
        action="store_true",
        help="Do not delete existing output/ before run",
    )
    args = parser.parse_args(argv)

    scenario = args.scenario
    if not scenario.is_dir():
        print(f"ERROR: scenario dir not found: {scenario}", file=sys.stderr)
        return 2

    # Hard refuse frozen trial trees as scenario roots
    norm = str(scenario.resolve()).replace("\\", "/")
    for banned in (
        "data/trials/trial-001-mindrium-xa",
        "data/trials/trial-002-lockout-multireq",
    ):
        if banned in norm:
            print(
                f"ERROR: refusing to run against frozen trial path ({banned})",
                file=sys.stderr,
            )
            return 3

    try:
        report = run_user_scenario(
            scenario, top_k=args.top_k, clean_output=not args.keep_output
        )
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1

    print(json.dumps({"status": report.get("status"), "outputs": report.get("outputs"), "summaries": report.get("summaries")}, ensure_ascii=False, indent=2))
    return 0 if str(report.get("status", "")).startswith("COMPLETED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
