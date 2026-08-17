from __future__ import annotations

import re
from typing import Any

from docx.document import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from document_ai.learn.docx_io import iter_blocks, table_matrix

RESIDUAL_PATTERN = re.compile(
    r"Mindrium|mindrium|범불안|의료기기|환자|IEC\s*62304|ISO\s*14971|"
    r"인지행동|CBT|E06070|Electronic Medical|예시:\s*Mindrium|Dart/Flutter|"
    r"Android Studio,\s*X code|Python 3\.13|Chip\b",
    re.I,
)

STRUCTURAL_LABELS = frozenset(
    {
        "Req.",
        "설명",
        "목적",
        "기준",
        "제품명",
        "모델명",
        "소프트웨어명",
        "안전성 등급",
        "제조자",
        "Code language",
        "Platform",
        "Editor",
        "결재",
        "성명",
        "직책",
        "서명",
        "일자",
        "승인자",
        "검토자",
        "작성자",
        "개정번호",
        "개정일자",
        "개정내용",
    }
)

SECURITY_REQ_TITLES: dict[str, str] = {
    "IA-01": "사용자 식별 및 인증",
    "IA-02": "계정 관리",
    "IA-03": "식별정보 관리",
    "IA-04": "인증정보 관리",
    "IA-05": "비밀번호 강도 설정",
    "IA-06": "인증정보에 대한 피드백",
    "IA-07": "연속적인 로그인 시도 실패 시 로그인 제한",
    "IA-08": "시스템 사용 알림 메시지",
    "UC-01": "권한 부여",
    "UC-02": "모바일 코드 사용 통제",
    "UC-03": "세션 잠금",
    "UC-04": "감사기록 생성",
    "UC-05": "감사 처리 실패 대응",
    "UC-06": "타임스탬프",
    "UC-07": "부인 방지",
    "SI-01": "통신에 대한 무결성 보장",
    "SI-02": "악성코드로부터 보호",
    "SI-03": "보안 기능 검증",
    "SI-04": "입력값 검증",
    "SI-05": "오류 처리",
    "SI-06": "메모리 관리",
    "SI-07": "설정 관리",
    "SI-08": "자원 관리",
    "SI-09": "시스템 무결성 보장",
    "SI-10": "보호 메커니즘 우회 방지",
    "SI-11": "보안 기능 접근 통제",
    "DC-01": "데이터 기밀성",
    "DC-02": "데이터 무결성",
    "DC-03": "데이터 가용성",
    "RA-01": "DoS 공격 방어",
    "RA-02": "자원 관리",
    "RA-03": "시스템 백업",
    "RA-04": "통신 보호",
    "RA-05": "네트워크 보호",
}


def _write_table_cell(table: Table, ri: int, ci: int, value: str) -> None:
    """Write via table.cell() to avoid merged-cell aliasing in row.cells."""
    if not value:
        return
    try:
        table.cell(ri, ci).text = value
    except (IndexError, ValueError):
        if ri < len(table.rows) and ci < len(table.rows[ri].cells):
            table.rows[ri].cells[ci].text = value


def _set_cell(row, col: int, value: str) -> None:
    if col < len(row.cells):
        row.cells[col].text = value


def _is_structural(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    if re.match(r"^Req\.\s*\d+", t):
        return True
    if re.match(r"^[A-Z]{2}-\d+", t):
        return True
    return t in STRUCTURAL_LABELS or t.startswith("IA-") or t.startswith("UC-")


def sanitize_document(doc: Document) -> dict[str, int]:
    """Remove Mindrium/medical placeholder text; preserve structural labels."""
    stats = {"paragraphs": 0, "table_cells": 0}

    for block in iter_blocks(doc):
        if isinstance(block, Paragraph):
            text = block.text or ""
            if RESIDUAL_PATTERN.search(text) or "XX-XX-XXXX" in text:
                block.text = ""
                stats["paragraphs"] += 1
            continue

        if not isinstance(block, Table):
            continue
        for row in block.rows:
            for cell in row.cells:
                text = cell.text or ""
                if not text.strip():
                    continue
                if _is_structural(text):
                    continue
                if RESIDUAL_PATTERN.search(text) or text.strip() in {"2", "Mindrium"}:
                    cell.text = ""
                    stats["table_cells"] += 1
                elif "Mindrium" in text or "의료" in text or "환자" in text:
                    cell.text = ""
                    stats["table_cells"] += 1

    return stats


def apply_paragraphs_block_order(doc: Document, paragraphs: list[str]) -> int:
    """Set body paragraphs by block order (includes empty slots)."""
    para_blocks = [b for b in iter_blocks(doc) if isinstance(b, Paragraph)]
    count = 0
    for i, text in enumerate(paragraphs):
        if i >= len(para_blocks):
            break
        if text:
            para_blocks[i].text = text
            count += 1
    return count


def apply_approval_table(doc: Document, approval: dict[str, Any]) -> bool:
    date = approval.get("date", "")
    people = approval.get("people") or {}
    for block in iter_blocks(doc):
        if not isinstance(block, Table):
            continue
        labels = {row.cells[0].text.strip() for row in block.rows if row.cells}
        if not {"승인자", "검토자", "작성자"} & labels:
            continue
        for ri, row in enumerate(block.rows):
            label = row.cells[0].text.strip()
            if label not in people:
                continue
            info = people[label]
            if info.get("name"):
                _write_table_cell(block, ri, 1, info["name"])
            if info.get("title"):
                _write_table_cell(block, ri, 2, info["title"])
            if date:
                _write_table_cell(block, ri, 4, date)
        return True
    return False


def apply_revision_table(doc: Document, revision: dict[str, str]) -> bool:
    for block in iter_blocks(doc):
        if not isinstance(block, Table):
            continue
        matrix = table_matrix(block)
        if not matrix:
            continue
        header = " ".join(matrix[0])
        has_revision = "개정번호" in header or (
            len(matrix) > 1 and matrix[1][0].strip() in {"0", "1"}
        )
        if not has_revision:
            continue
        if len(block.rows) > 1:
            _write_table_cell(block, 1, 0, revision.get("number", "0"))
            _write_table_cell(block, 1, 1, revision.get("date", ""))
            _write_table_cell(block, 1, 2, revision.get("summary", "제정"))
            _write_table_cell(block, 1, 3, revision.get("author", ""))
        return True
    return False


def apply_matrix_table(doc: Document, anchor: str, matrix_data: list[list[str]]) -> bool:
    for block in iter_blocks(doc):
        if not isinstance(block, Table):
            continue
        m = table_matrix(block)
        if not m or m[0][0] != anchor:
            continue
        for ri, row_data in enumerate(matrix_data):
            if ri >= len(block.rows):
                break
            for ci, val in enumerate(row_data):
                _write_table_cell(block, ri, ci, val)
        return True
    return False


def apply_component_detail_table(doc: Document, rows: list[list[str]]) -> bool:
    seen_product = False
    for block in iter_blocks(doc):
        if not isinstance(block, Table):
            continue
        m = table_matrix(block)
        if not m:
            continue
        if m[0][0] == "제품명":
            seen_product = True
            continue
        if not seen_product:
            continue
        labels = {r[0].strip() for r in m if r}
        if "Code language" in labels:
            break
        for ri, row_data in enumerate(rows):
            if ri >= len(block.rows):
                break
            for ci, val in enumerate(row_data):
                _write_table_cell(block, ri, ci, val)
        return True
    return False


def apply_tech_stack_tables(doc: Document, stacks: list[dict[str, str]]) -> int:
    applied = 0
    stack_idx = 0
    for block in iter_blocks(doc):
        if not isinstance(block, Table):
            continue
        matrix = table_matrix(block)
        if not matrix:
            continue
        labels = {row[0].strip() for row in matrix if row}
        if "Code language" not in labels:
            continue
        if stack_idx >= len(stacks):
            break
        stack = stacks[stack_idx]
        header = stack.get("header")
        if header:
            _write_table_cell(block, 0, 1, header)
        for ri, row in enumerate(block.rows):
            label = row.cells[0].text.strip()
            if label == "Code language":
                _write_table_cell(block, ri, 1, stack.get("code_language", ""))
            elif label == "Platform":
                _write_table_cell(block, ri, 1, stack.get("platform", ""))
            elif label == "Editor":
                _write_table_cell(block, ri, 1, stack.get("editor", ""))
        stack_idx += 1
        applied += 1
    return applied


def apply_traceability_details(
    doc: Document, traceability: list[dict[str, Any]], *, default_applicability: str = "해당"
) -> int:
    from document_ai.render.requirements import _find_traceability_table_index

    trace_idx = _find_traceability_table_index(doc)
    if trace_idx is None:
        return 0

    table = doc.tables[trace_idx]
    by_id = {t["requirement"]: t for t in traceability}
    count = 0

    for ri, row in enumerate(table.rows):
        if not row.cells:
            continue
        key = row.cells[0].text.strip()
        if not re.match(r"^[A-Z]{2}-\d+", key):
            continue
        entry = by_id.get(key, {})
        title = entry.get("title") or SECURITY_REQ_TITLES.get(key, "")
        if title:
            _write_table_cell(table, ri, 1, title)
        app = entry.get("applicability")
        if not app:
            app = "비해당" if entry.get("linked_reqs") == "N/A" else default_applicability
        _write_table_cell(table, ri, 2, app)
        linked = entry.get("linked_reqs", "")
        _write_table_cell(table, ri, 3, linked if linked else "N/A")
        count += 1
    return count


def verify_completeness(doc: Document, requirements: list[dict[str, Any]]) -> dict[str, Any]:
    """Review pass: empty req values, residual text, empty traceability."""
    issues: list[str] = []
    residual: list[str] = []

    for block in iter_blocks(doc):
        if isinstance(block, Paragraph):
            t = block.text or ""
            if RESIDUAL_PATTERN.search(t):
                residual.append(f"paragraph: {t[:80]}")
        elif isinstance(block, Table):
            m = table_matrix(block)
            if m and re.match(r"^Req\.\s*\d+", m[0][0]):
                rid = m[0][0]
                has_content = any(
                    c.strip()
                    for ri, row in enumerate(m)
                    for ci, c in enumerate(row)
                    if ri > 0 and ci > 0
                )
                if not has_content:
                    issues.append(f"{rid}: no description/purpose filled")
            if any(r and r[0].startswith("IA-01") for r in m):
                for row in m:
                    if row and re.match(r"^[A-Z]{2}-\d+", row[0]):
                        if len(row) < 4 or not row[3].strip():
                            issues.append(f"traceability {row[0]}: missing linked reqs")

    for block in iter_blocks(doc):
        if not isinstance(block, Table):
            continue
        m = table_matrix(block)
        if not m or m[0][0] != "제품명":
            continue
        for ri, row in enumerate(m):
            label = row[0].strip() if row else ""
            for ci, c in enumerate(row):
                if ci == 0:
                    continue
                if label == "제조자" and ci > 1:
                    continue
                if not c.strip():
                    issues.append(f"product_table r{ri}c{ci} empty")
                if RESIDUAL_PATTERN.search(c):
                    residual.append(f"product r{ri}c{ci}: {c[:60]}")

    return {
        "issue_count": len(issues),
        "residual_count": len(residual),
        "issues": issues[:50],
        "residual": residual[:20],
        "requirements_expected": len(requirements),
    }


def apply_mdsr_content(doc: Document, content: dict[str, Any]) -> dict[str, Any]:
    stats: dict[str, Any] = {}
    stats["sanitized"] = sanitize_document(doc)

    if content.get("paragraphs"):
        stats["paragraphs"] = apply_paragraphs_block_order(doc, content["paragraphs"])
    elif content.get("paragraph_overrides"):
        parsed = {int(k): v for k, v in content["paragraph_overrides"].items()}
        paras = [b for b in iter_blocks(doc) if isinstance(b, Paragraph)]
        filled = 0
        for idx, text in parsed.items():
            if idx < len(paras) and text:
                paras[idx].text = text
                filled += 1
        stats["paragraphs"] = filled

    if content.get("approval"):
        stats["approval"] = apply_approval_table(doc, content["approval"])
    if content.get("revision"):
        stats["revision"] = apply_revision_table(doc, content["revision"])
    if content.get("product_matrix"):
        stats["product_matrix"] = apply_matrix_table(doc, "제품명", content["product_matrix"])
    elif content.get("product"):
        stats["product_matrix"] = apply_matrix_table(
            doc, "제품명", _product_dict_to_matrix(content["product"])
        )
    if content.get("component_detail_rows"):
        stats["component_detail"] = apply_component_detail_table(doc, content["component_detail_rows"])
    if content.get("tech_stacks"):
        stats["tech_stacks"] = apply_tech_stack_tables(doc, content["tech_stacks"])

    return stats


def _product_dict_to_matrix(product: dict[str, Any]) -> list[list[str]]:
    names = product.get("product_name") or ["", "", ""]
    models = product.get("model_name") or ["", "", ""]
    comps = product.get("software_components") or ["", "", ""]
    safety = product.get("safety_class") or ["A", "A", "A"]
    mfr = product.get("manufacturer", "")
    return [
        ["제품명", *names[:3]],
        ["모델명", *models[:3]],
        ["소프트웨어명", "고객몰", "API 서버", "운영 백오피스"],
        ["소프트웨어명", *comps[:3]],
        ["안전성 등급", *safety[:3]],
        ["제조자", mfr, mfr, mfr],
    ]


def apply_mdsr_full(
    doc: Document,
    content: dict[str, Any],
    requirements_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Sanitize Mindrium template then fill all MDSR sections."""
    from document_ai.render.requirements import apply_requirements_payload

    stats = apply_mdsr_content(doc, content)

    if requirements_payload:
        stats["requirements"] = apply_requirements_payload(
            doc, requirements_payload, overwrite_descriptions=True
        )
        stats["traceability"] = apply_traceability_details(
            doc, requirements_payload.get("traceability", [])
        )
        for _pass in range(1, 6):
            review = verify_completeness(doc, requirements_payload.get("requirements", []))
            stats[f"review_pass_{_pass}"] = review
            if review["issue_count"] == 0 and review["residual_count"] == 0:
                stats["review_passes_completed"] = _pass
                break
            sanitize_document(doc)
            apply_mdsr_content(doc, content)
            apply_requirements_payload(doc, requirements_payload, overwrite_descriptions=True)
            apply_traceability_details(doc, requirements_payload.get("traceability", []))
        else:
            stats["review_passes_completed"] = 5

    return stats
