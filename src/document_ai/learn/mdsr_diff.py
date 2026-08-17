from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from docx.document import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from document_ai.learn.docx_io import iter_blocks, load_document, table_matrix

REQ_ID = re.compile(r"^Req\.\s*(\d+)\.?\s*$", re.I)
SECTION5 = re.compile(r"5\.\s*.*기능.*요구", re.I)
PURPOSE_BOILERPLATE = re.compile(
    r"기능을 안정적으로 제공하여|요구를 충족하여.*준수하기 위함|요구를 충족하여.*확보하기 위함"
)
REQ_LABELS = ("설명", "목적", "기준")


@dataclass
class ReqRow:
    label: str
    value: str
    row_index: int


@dataclass
class ReqBlock:
    req_id: str
    req_num: int
    block_index: int
    rows: list[ReqRow] = field(default_factory=list)

    @property
    def section(self) -> str:
        if self.req_num < 100:
            return "functional"
        if self.req_num < 200:
            return "security"
        return "non_functional"

    def by_label(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for row in self.rows:
            if row.label in REQ_LABELS:
                out[row.label] = row.value
        return out

    def unlabeled_values(self) -> list[str]:
        return [row.value for row in self.rows if row.label not in REQ_LABELS and row.value.strip()]

    def total_content_len(self) -> int:
        return sum(len(row.value.strip()) for row in self.rows)


@dataclass
class ReqGap:
    req_id: str
    section: str
    kind: str
    detail: str
    gold_len: int = 0
    output_len: int = 0


@dataclass
class DiffReport:
    gold_path: str
    output_path: str
    gold_req_count: int
    output_req_count: int
    section5_heading: str | None
    gaps: list[ReqGap] = field(default_factory=list)
    quality_issues: list[ReqGap] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gold_path": self.gold_path,
            "output_path": self.output_path,
            "gold_req_count": self.gold_req_count,
            "output_req_count": self.output_req_count,
            "section5_heading": self.section5_heading,
            "summary": self.summary,
            "gaps": [asdict(g) for g in self.gaps],
            "quality_issues": [asdict(q) for q in self.quality_issues],
        }


def _parse_req_id(text: str) -> tuple[str, int] | None:
    m = REQ_ID.match((text or "").strip())
    if not m:
        return None
    num = int(m.group(1))
    return f"Req. {num}", num


def find_section5_heading(doc: Document) -> str | None:
    for block in iter_blocks(doc):
        if isinstance(block, Paragraph):
            text = (block.text or "").strip()
            if SECTION5.search(text):
                return text
    return None


def extract_req_blocks(doc: Document) -> dict[str, ReqBlock]:
    blocks: dict[str, ReqBlock] = {}
    for block_index, block in enumerate(iter_blocks(doc)):
        if not isinstance(block, Table):
            continue
        matrix = table_matrix(block)
        if not matrix:
            continue
        parsed = _parse_req_id(matrix[0][0] if matrix[0] else "")
        if not parsed:
            continue
        req_id, req_num = parsed
        rows: list[ReqRow] = []
        for ri, row in enumerate(matrix[1:], start=1):
            label = row[0].strip() if row else ""
            value = row[1].strip() if len(row) > 1 else ""
            rows.append(ReqRow(label=label, value=value, row_index=ri))
        blocks[req_id] = ReqBlock(
            req_id=req_id,
            req_num=req_num,
            block_index=block_index,
            rows=rows,
        )
    return blocks


def _quality_check(block: ReqBlock) -> list[ReqGap]:
    issues: list[ReqGap] = []
    labels = block.by_label()
    unlabeled = block.unlabeled_values()

    if block.section != "functional":
        return issues

    if not labels and not unlabeled:
        issues.append(ReqGap(block.req_id, block.section, "empty_block", "기능 요구사항 표가 비어 있음"))
    if not labels.get("설명") and not (unlabeled and max(len(u) for u in unlabeled) > 20):
        issues.append(ReqGap(block.req_id, block.section, "missing_description", "설명(또는 본문) 내용 부족"))
    if not labels.get("기준"):
        issues.append(ReqGap(block.req_id, block.section, "missing_criteria", "기준(acceptance criteria) 비어 있음"))
    if not labels and unlabeled:
        issues.append(
            ReqGap(
                block.req_id,
                block.section,
                "unlabeled_rows",
                f"설명/목적/기준 라벨 없이 {len(unlabeled)}개 비라벨 행만 사용",
            )
        )
    for value in unlabeled + [labels.get("목적", "")]:
        if value and PURPOSE_BOILERPLATE.search(value):
            issues.append(
                ReqGap(
                    block.req_id,
                    block.section,
                    "boilerplate_purpose",
                    "목적이 템플릿 boilerplate 문구로 채워짐",
                )
            )
            break
    if labels.get("설명") and labels.get("목적") and labels["설명"][:40] == labels["목적"][:40]:
        issues.append(ReqGap(block.req_id, block.section, "duplicate_content", "설명과 목적 내용이 거의 동일"))

    return issues


def compare_mdsr_documents(gold_path: Path, output_path: Path) -> DiffReport:
    gold_doc = load_document(gold_path)
    out_doc = load_document(output_path)
    gold_blocks = extract_req_blocks(gold_doc)
    out_blocks = extract_req_blocks(out_doc)

    report = DiffReport(
        gold_path=str(gold_path),
        output_path=str(output_path),
        gold_req_count=len(gold_blocks),
        output_req_count=len(out_blocks),
        section5_heading=find_section5_heading(out_doc) or find_section5_heading(gold_doc),
    )

    all_ids = sorted(
        set(gold_blocks) | set(out_blocks),
        key=lambda rid: gold_blocks.get(rid, out_blocks[rid]).req_num,  # type: ignore[union-attr]
    )

    for req_id in all_ids:
        gold = gold_blocks.get(req_id)
        out = out_blocks.get(req_id)
        section = (out or gold).section  # type: ignore[union-attr]

        if gold is None:
            report.gaps.append(ReqGap(req_id, section, "extra_in_output", "output에만 존재 (gold에 없음)"))
            continue
        if out is None:
            report.gaps.append(ReqGap(req_id, section, "missing_in_output", "output에 없음 (gold에는 존재)"))
            continue

        g_len = gold.total_content_len()
        o_len = out.total_content_len()
        if g_len > 30 and o_len < max(20, int(g_len * 0.4)):
            report.gaps.append(
                ReqGap(
                    req_id,
                    section,
                    "shorter_than_gold",
                    f"gold 대비 내용 부족 (gold={g_len}자, output={o_len}자)",
                    gold_len=g_len,
                    output_len=o_len,
                )
            )
        elif g_len == 0 and o_len > 0:
            report.gaps.append(
                ReqGap(
                    req_id,
                    section,
                    "filled_vs_empty_gold",
                    f"gold는 비어 있으나 output은 {o_len}자 (repo gold 미채움 가능)",
                    gold_len=g_len,
                    output_len=o_len,
                )
            )
        elif g_len > 0 and o_len == 0:
            report.gaps.append(
                ReqGap(
                    req_id,
                    section,
                    "empty_in_output",
                    f"gold {g_len}자 있으나 output 비어 있음",
                    gold_len=g_len,
                    output_len=o_len,
                )
            )

        for label in REQ_LABELS:
            gv = gold.by_label().get(label, "")
            ov = out.by_label().get(label, "")
            if gv.strip() and not ov.strip():
                report.gaps.append(
                    ReqGap(
                        req_id,
                        section,
                        f"gold_has_{label}",
                        f"gold {label} {len(gv)}자 → output 비어 있음",
                        gold_len=len(gv),
                        output_len=len(ov),
                    )
                )

        if section == "functional":
            report.quality_issues.extend(_quality_check(out))

    func_out = [b for b in out_blocks.values() if b.section == "functional"]
    gold_empty_filled = sum(1 for g in report.gaps if g.kind == "filled_vs_empty_gold")
    report.summary = {
        "functional_req_count": len(func_out),
        "functional_with_labels": sum(1 for b in func_out if b.by_label()),
        "functional_empty": sum(1 for b in func_out if b.total_content_len() == 0),
        "functional_boilerplate_purpose": sum(
            1
            for b in func_out
            if any(PURPOSE_BOILERPLATE.search(v) for v in b.unlabeled_values() + list(b.by_label().values()))
        ),
        "gap_count": len(report.gaps),
        "gold_empty_filled_output_count": gold_empty_filled,
        "quality_issue_count": len(report.quality_issues),
    }
    return report


def format_report_text(report: DiffReport, *, section_filter: str | None = None) -> str:
    lines: list[str] = [
        "MDSR Gold vs Output Diff Report",
        "=" * 72,
        f"Gold:   {report.gold_path}",
        f"Output: {report.output_path}",
        f"Section 5 heading: {report.section5_heading or '(not found in body)'}",
        "",
        "Summary:",
        f"  gold req blocks: {report.gold_req_count}",
        f"  output req blocks: {report.output_req_count}",
    ]
    for key, val in report.summary.items():
        lines.append(f"  {key}: {val}")

    def _append(title: str, items: list[ReqGap]) -> None:
        filtered = [g for g in items if not section_filter or g.section == section_filter]
        lines.extend(["", title, "-" * 72])
        if not filtered:
            lines.append("  (none)")
            return
        for g in filtered:
            extra = ""
            if g.gold_len or g.output_len:
                extra = f" [{g.gold_len}->{g.output_len} chars]"
            lines.append(f"  {g.req_id} [{g.section}] {g.kind}: {g.detail}{extra}")

    _append("GAPS (gold vs output)", report.gaps)
    _append("QUALITY (output structure / section 5)", report.quality_issues)

    lines.extend(["", "Section 5 — Functional requirements (Req. 1-99)", "-" * 72])
    func_gaps = [g for g in report.gaps + report.quality_issues if g.section == "functional"]
    if not func_gaps:
        lines.append("  No functional gaps flagged.")
    else:
        by_req: dict[str, list[ReqGap]] = {}
        for g in func_gaps:
            by_req.setdefault(g.req_id, []).append(g)
        for req_id in sorted(by_req, key=lambda r: int(re.search(r"(\d+)", r).group(1))):  # type: ignore[union-attr]
            lines.append(f"  {req_id}:")
            for g in by_req[req_id]:
                lines.append(f"    - {g.kind}: {g.detail}")

    return "\n".join(lines) + "\n"


def write_report(
    report: DiffReport,
    txt_path: Path,
    json_path: Path | None = None,
    *,
    section_filter: str | None = None,
) -> None:
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    txt_path.write_text(format_report_text(report, section_filter=section_filter), encoding="utf-8")
    if json_path:
        json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
