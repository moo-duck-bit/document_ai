#!/usr/bin/env python3
"""MDSR template vs filled vs output gap analysis."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from docx.table import Table
from docx.text.paragraph import Paragraph

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from document_ai.learn.docx_io import iter_blocks, load_document, table_matrix  # noqa: E402

DOCS = {
    "template": ROOT / "data/templates/ec_sw/template_mdsr.docx",
    "filled": ROOT / "data/examples/ec_sw/spec_mdsr_EC-SW-MDSR(XA)_소프트웨어_요구사항명세서.docx",
    "output": ROOT / "data/cases/jm_collection/output_mdsr.docx",
}
OUT = ROOT / "data/cases/jm_collection/gap_analysis.txt"
RESIDUAL = re.compile(
    r"mindrium|범불안|의료기기|환자|IEC\s*62304|ISO\s*14971|인지행동|E06070|Electronic Medical",
    re.I,
)


def _empty(t: str) -> bool:
    return not (t or "").strip()


def _req_num(matrix: list[list[str]]) -> int | None:
    for row in matrix:
        m = re.search(r"Req\.\s*(\d+)", row[0] if row else "", re.I)
        if m:
            return int(m.group(1))
    return None


def analyze(name: str, path: Path, lines: list[str]) -> dict | None:
    lines.extend(["=" * 80, f"DOCUMENT: {name}", f"PATH: {path}"])
    if not path.is_file():
        lines.append("ERROR: not found")
        return None

    doc = load_document(path)
    paras: list[str] = []
    tables: list[list[list[str]]] = []
    for block in iter_blocks(doc):
        if isinstance(block, Paragraph):
            paras.append((block.text or "").strip())
        elif isinstance(block, Table):
            tables.append(table_matrix(block))

    lines.append(f"Paragraph blocks: {len(paras)} (non-empty={sum(1 for p in paras if p)})")
    for i, t in enumerate(paras):
        if t:
            lines.append(f"  P[{i}]: {t[:180]}")

    trace_i = next((i for i, m in enumerate(tables) if any(r and r[0].startswith("IA-01") for r in m)), None)
    lines.append(f"Traceability index: {trace_i}")

    for ti in sorted(set(list(range(min(8, len(tables)))) + ([trace_i] if trace_i is not None else []))):
        m = tables[ti]
        lines.append(f"--- Table {ti} ({len(m)}x{len(m[0]) if m else 0}) ---")
        for ri, row in enumerate(m):
            lines.append("  | " + " | ".join((c or "").replace("\n", " ")[:100] for c in row))

    req_tables = [(ti, _req_num(m), m) for ti, m in enumerate(tables) if _req_num(m)]
    rf = sum(sum(1 for c in row if not _empty(c)) for _, _, m in req_tables for row in m)
    re_ = sum(sum(1 for c in row if _empty(c)) for _, _, m in req_tables for row in m)
    lines.append(f"Req tables={len(req_tables)} filled_cells={rf} empty_cells={re_}")

    for ti, rn, m in req_tables:
        if rn in {1, 2, 10, 101, 105}:
            lines.append(f"Req.{rn} @ table {ti}:")
            for ri, row in enumerate(m[:4]):
                lines.append(f"    r{ri}: {row}")

    return {"paras": paras, "tables": tables, "trace_i": trace_i}


def compare(results: dict, lines: list[str]) -> None:
    out, fill = results.get("output"), results.get("filled")
    if not out or not fill:
        return
    lines.append("=" * 80)
    lines.append("GAPS: output empty but filled has content")
    for ti in range(min(len(out["tables"]), len(fill["tables"]))):
        om, fm = out["tables"][ti], fill["tables"][ti]
        for ri in range(max(len(om), len(fm))):
            orow = om[ri] if ri < len(om) else []
            frow = fm[ri] if ri < len(fm) else []
            for ci in range(max(len(orow), len(frow))):
                oc = orow[ci] if ci < len(orow) else ""
                fc = frow[ci] if ci < len(frow) else ""
                if _empty(oc) and not _empty(fc):
                    lines.append(f"  table={ti} row={ri} col={ci}  filled={fc[:80]!r}")

    lines.append("RESIDUAL Mindrium/medical in OUTPUT:")
    for ti, m in enumerate(out["tables"]):
        for ri, row in enumerate(m):
            for ci, c in enumerate(row):
                if c and RESIDUAL.search(c):
                    lines.append(f"  table={ti} r={ri} c={ci}: {c[:120]!r}")
    for i, t in enumerate(out["paras"]):
        if t and RESIDUAL.search(t):
            lines.append(f"  para[{i}]: {t[:120]!r}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output-only", action="store_true", help="Analyze output doc only (fast)")
    args = parser.parse_args()

    lines: list[str] = []
    docs = {"output": DOCS["output"]} if args.output_only else DOCS
    results = {k: analyze(k, p, lines) for k, p in docs.items()}
    if not args.output_only:
        compare(results, lines)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
