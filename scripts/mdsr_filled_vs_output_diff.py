#!/usr/bin/env python3
"""Compare Mindrium (gold) MDSR vs JM output — cell-level req diff + section 5 quality."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from document_ai.learn.mdsr_diff import compare_mdsr_documents, write_report  # noqa: E402

DEFAULT_GOLD = ROOT / "data/examples/ec_sw/spec_mdsr_EC-SW-MDSR(XA)_소프트웨어_요구사항명세서.docx"
DEFAULT_OUTPUT = ROOT / "data/cases/jm_collection/output_mdsr.docx"
DEFAULT_TXT = ROOT / "data/cases/jm_collection/mdsr_diff_report.txt"
DEFAULT_JSON = ROOT / "data/cases/jm_collection/mdsr_diff_report.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="MDSR gold vs output diff (section 5 focus)")
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD, help="Gold (Mindrium filled) DOCX")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Generated output DOCX")
    parser.add_argument("--txt", type=Path, default=DEFAULT_TXT, help="Text report path")
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON, help="JSON report path")
    parser.add_argument(
        "--section",
        choices=("functional", "security", "non_functional", "all"),
        default="all",
        help="Filter report section",
    )
    args = parser.parse_args()

    if not args.gold.is_file():
        print(f"Gold not found: {args.gold}", file=sys.stderr)
        return 1
    if not args.output.is_file():
        print(f"Output not found: {args.output}", file=sys.stderr)
        return 1

    section_filter = None if args.section == "all" else args.section
    report = compare_mdsr_documents(args.gold, args.output)
    write_report(report, args.txt, args.json, section_filter=section_filter)

    print(f"Wrote {args.txt}")
    print(f"Wrote {args.json}")
    print(
        f"Summary: gaps={report.summary.get('gap_count', 0)} "
        f"quality_issues={report.summary.get('quality_issue_count', 0)} "
        f"functional_boilerplate={report.summary.get('functional_boilerplate_purpose', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
