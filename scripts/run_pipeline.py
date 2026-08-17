#!/usr/bin/env python3
"""Run full EC-SW pipeline for mindrium_xa case."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASE = "data/cases/mindrium_xa"


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)


def main() -> int:
    py = sys.executable
    run([py, "-m", "document_ai.cli", "export-schema"])
    run([py, "-m", "document_ai.cli", "extract-requirements", "--case", CASE])
    run([py, "-m", "document_ai.cli", "extract-design", "--case", CASE])
    run([py, "-m", "document_ai.cli", "extract-design-items", "--case", CASE])
    run([py, "-m", "document_ai.cli", "extract-security-tests", "--case", CASE])
    run([py, "-m", "document_ai.cli", "xxcs-skeleton"])
    run([py, "-m", "document_ai.cli", "generate-all", "--case", CASE])
    print("\nDone. Outputs:")
    print("  schemas: data/schemas/ec_sw/*.schema.json")
    print("  case:    data/cases/mindrium_xa/")
    print("    requirements.json, design_content.json, security_tests.json")
    print("    design_items.json")
    print("    output_mdsr.docx, output_mddr.docx, output_xxcs.docx")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
