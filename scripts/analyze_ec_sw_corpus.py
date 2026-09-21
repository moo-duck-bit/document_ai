"""Analyze EC-SW completed DOCX corpus and copy to data/examples/ec_sw/."""
import json
import os
import re
import shutil
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

DESKTOP = Path(os.environ.get("EC_SW_SRC_DIR") or Path.home() / "Desktop")
PROJECT = Path(__file__).resolve().parents[1]
BASE = PROJECT / "data" / "examples" / "ec_sw"
BASE.mkdir(parents=True, exist_ok=True)

FILES = [
    ("report_xxcs", "EC-SW-XXCS(XA) 소프트웨어 보안 검증 보고서.docx", "report_security_verification"),
    ("spec_mddr", "EC-SW-MDDR(XA) 소프트웨어 설계 명세서.docx", "spec_design"),
    ("spec_mdsr", "EC-SW-MDSR(XA)_소프트웨어_요구사항명세서.docx", "spec_requirements"),
]


def iter_block_items(doc):
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, doc)
        elif child.tag == qn("w:tbl"):
            yield Table(child, doc)


def analyze_docx(path: Path) -> dict:
    doc = Document(str(path))
    headings = []
    paragraphs_sample = []
    tables_info = []
    all_text_parts = []
    placeholder_like = []

    for i, block in enumerate(iter_block_items(doc)):
        if isinstance(block, Paragraph):
            t = block.text.strip()
            if not t:
                continue
            all_text_parts.append(t)
            style = block.style.name if block.style else ""
            if "Heading" in style or re.match(r"^(\d+\.)+\s", t) or re.match(r"^제\d+", t):
                headings.append({"idx": i, "style": style, "text": t[:120]})
            if len(paragraphs_sample) < 15 and len(t) > 5:
                paragraphs_sample.append(t[:150])
            if "{{" in t or re.search(r"\[\s*\]|_{3,}|○{2,}|□", t):
                placeholder_like.append(t[:100])
        elif isinstance(block, Table):
            rows = len(block.rows)
            cols = len(block.columns) if block.rows else 0
            header = []
            if block.rows:
                header = [c.text.strip()[:40] for c in block.rows[0].cells[:6]]
            tables_info.append({"idx": i, "rows": rows, "cols": cols, "header": header})

    props = doc.core_properties
    return {
        "file": path.name,
        "size_kb": round(path.stat().st_size / 1024, 1),
        "meta": {
            "title": props.title or "",
            "author": props.author or "",
            "subject": props.subject or "",
        },
        "paragraph_count": len(all_text_parts),
        "table_count": len(tables_info),
        "headings": headings[:50],
        "headings_total": len(headings),
        "tables": tables_info[:20],
        "cover_lines": all_text_parts[:20],
        "paragraphs_sample": paragraphs_sample,
        "placeholder_like": placeholder_like[:10],
        "full_text_chars": sum(len(x) for x in all_text_parts),
    }


def main():
    results = {}
    for short_id, filename, template_id in FILES:
        src = DESKTOP / filename
        if not src.exists():
            raise FileNotFoundError(src)
        dest = BASE / f"{short_id}_{src.name}"
        shutil.copy2(src, dest)
        analysis = analyze_docx(dest)
        results[template_id] = {
            "short_id": short_id,
            "template_id": template_id,
            "doc_code": filename.split()[0],
            "display_name": filename.replace(".docx", ""),
            "dest_path": str(dest.relative_to(PROJECT)).replace("\\", "/"),
            **analysis,
        }

    out = BASE / "corpus_analysis.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out}")
    for tid, r in results.items():
        print(f"\n=== {tid} ===")
        print(f"  paragraphs: {r['paragraph_count']}, tables: {r['table_count']}, chars: {r['full_text_chars']}")
        print(f"  headings (first 8):")
        for h in r["headings"][:8]:
            print(f"    - {h['text'][:80]}")


if __name__ == "__main__":
    main()
