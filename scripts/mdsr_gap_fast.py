#!/usr/bin/env python3
"""Fast MDSR gap scan using stdlib zip+xml (fallback when docx_io hangs)."""
from __future__ import annotations

import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DOCS = {
    "template": ROOT / "data/templates/ec_sw/template_mdsr.docx",
    "filled": ROOT / "data/examples/ec_sw/spec_mdsr_EC-SW-MDSR(XA)_소프트웨어_요구사항명세서.docx",
    "output": ROOT / "data/cases/jm_collection/output_mdsr.docx",
}
OUT = ROOT / "data/cases/jm_collection/gap_analysis.txt"
REQ_SAMPLE = {1, 2, 10, 101, 105}
RESIDUAL = re.compile(
    r"mindrium|Mindrium|범불안|의료기기|환자|IEC\s*62304|ISO\s*14971|인지행동|E06070|"
    r"Electronic Medical|EC-SW-MDSR\(XA\)|식약처.*사이버",
    re.I,
)
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _text(el: ET.Element) -> str:
    parts = [t.text or "" for t in el.iter(f"{W}t")]
    return "".join(parts).strip()


def parse_docx(path: Path) -> tuple[list[str], list[list[list[str]]]]:
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))
    body = root.find(f"{W}body")
    if body is None:
        return [], []
    paras: list[str] = []
    tables: list[list[list[str]]] = []
    for child in body:
        tag = child.tag.split("}")[-1]
        if tag == "p":
            t = _text(child)
            if t:
                paras.append(t)
        elif tag == "tbl":
            matrix: list[list[str]] = []
            for tr in child.findall(f"{W}tr"):
                row: list[str] = []
                for tc in tr.findall(f"{W}tc"):
                    row.append(_text(tc))
                matrix.append(row)
            tables.append(matrix)
    return paras, tables


def empty(s: str) -> bool:
    return not (s or "").strip()


def req_num(matrix: list[list[str]]) -> int | None:
    for row in matrix:
        m = re.search(r"Req\.\s*(\d+)", row[0] if row else "", re.I)
        if m:
            return int(m.group(1))
    return None


def trace_index(tables: list[list[list[str]]]) -> int | None:
    for i, m in enumerate(tables):
        if any(r and (r[0] or "").startswith("IA-01") for r in m):
            return i
    return None


def count_cells(matrix: list[list[str]]) -> tuple[int, int]:
    f = e = 0
    for row in matrix:
        for c in row:
            if empty(c):
                e += 1
            else:
                f += 1
    return f, e


def analyze(name: str, path: Path, lines: list[str]) -> dict | None:
    lines.extend(["=" * 80, f"DOCUMENT: {name}", f"PATH: {path}"])
    if not path.is_file():
        lines.append("ERROR: not found")
        return None
    paras, tables = parse_docx(path)
    lines.append(f"Non-empty paragraphs: {len(paras)}")
    for i, t in enumerate(paras):
        lines.append(f"  P[{i}]: {t[:200]}")

    ti_trace = trace_index(tables)
    lines.append(f"Total tables: {len(tables)}")
    lines.append(f"Traceability table index: {ti_trace}")

    show = set(range(min(8, len(tables))))
    if ti_trace is not None:
        show.add(ti_trace)
    for ti in sorted(show):
        m = tables[ti]
        cols = len(m[0]) if m else 0
        lines.append(f"--- Table {ti}: {len(m)} rows x {cols} cols ---")
        for ri, row in enumerate(m):
            lines.append("  | " + " | ".join((c or "").replace("\n", " ")[:120] for c in row))

    req_tables = [(ti, req_num(m), m) for ti, m in enumerate(tables) if req_num(m)]
    rf = re_ = 0
    for _, _, m in req_tables:
        f, e = count_cells(m)
        rf += f
        re_ += e
    lines.append(f"Req tables={len(req_tables)} filled_cells={rf} empty_cells={re_}")

    for ti, rn, m in req_tables:
        if rn in REQ_SAMPLE:
            lines.append(f"Req.{rn} @ table {ti} (col0 labels + 4 rows):")
            for ri in range(min(4, len(m))):
                row = m[ri]
                c0 = row[0] if row else ""
                cells = " ; ".join(f"[{ri},{ci}]={(c or '')[:80]!r}" for ci, c in enumerate(row))
                lines.append(f"    row{ri} col0={c0!r} | {cells}")

    if ti_trace is not None:
        tf, te = count_cells(tables[ti_trace])
        lines.append(f"Traceability table {ti_trace}: filled={tf} empty={te}")

    return {"paras": paras, "tables": tables, "trace_i": ti_trace}


def compare(results: dict, lines: list[str]) -> None:
    out, fill, tmpl = results.get("output"), results.get("filled"), results.get("template")
    lines.extend(["=" * 80, "GAP ANALYSIS"])
    if not out:
        lines.append("No output doc to compare")
        return

    lines.append("--- Output EMPTY but filled example has content ---")
    if fill:
        for ti in range(min(len(out["tables"]), len(fill["tables"]))):
            om, fm = out["tables"][ti], fill["tables"][ti]
            for ri in range(max(len(om), len(fm))):
                orow = om[ri] if ri < len(om) else []
                frow = fm[ri] if ri < len(fm) else []
                for ci in range(max(len(orow), len(frow))):
                    oc = orow[ci] if ci < len(orow) else ""
                    fc = frow[ci] if ci < len(frow) else ""
                    if empty(oc) and not empty(fc):
                        lines.append(f"  table={ti} row={ri} col={ci}  example={fc[:80]!r}")

    lines.append("--- All EMPTY cells in OUTPUT ---")
    empty_count = 0
    for ti, m in enumerate(out["tables"]):
        for ri, row in enumerate(m):
            for ci, c in enumerate(row):
                if empty(c):
                    empty_count += 1
                    if ti <= 7 or ti == out.get("trace_i"):
                        lines.append(f"  table={ti} row={ri} col={ci}")
    lines.append(f"(total empty cells in output: {empty_count})")

    lines.append("--- Residual Mindrium/medical text in OUTPUT ---")
    hits = 0
    for ti, m in enumerate(out["tables"]):
        for ri, row in enumerate(m):
            for ci, c in enumerate(row):
                if c and RESIDUAL.search(c):
                    hits += 1
                    lines.append(f"  table={ti} row={ri} col={ci}: {c[:140]!r}")
    for i, t in enumerate(out["paras"]):
        if RESIDUAL.search(t):
            hits += 1
            lines.append(f"  para P[{i}]: {t[:140]!r}")
    if not hits:
        lines.append("  (none matched residual pattern)")

    if tmpl:
        req = [(ti, req_num(m), m) for ti, m in enumerate(tmpl["tables"]) if req_num(m)]
        if req:
            ti, rn, m = req[0]
            lines.append("--- Template req table row structure (col0) ---")
            for ri in range(min(4, len(m))):
                lines.append(f"  table={ti} row={ri} col0={(m[ri][0] if m[ri] else '')!r}")


def main() -> None:
    lines: list[str] = ["MDSR GAP ANALYSIS (stdlib zip/xml parser)", ""]
    results = {k: analyze(k, p, lines) for k, p in DOCS.items()}
    compare(results, lines)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT} ({len(lines)} lines)")


if __name__ == "__main__":
    main()
