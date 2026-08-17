from docx import Document
from docx.table import Table

from document_ai.render.mdsr import apply_mdsr_content, apply_traceability_details
from document_ai.render.requirements import _fill_req_table_full, fill_traceability_matrix


def _req_table(*rows: tuple[str, str]) -> Table:
    doc = Document()
    table = doc.add_table(rows=len(rows), cols=2)
    for ri, (a, b) in enumerate(rows):
        table.rows[ri].cells[0].text = a
        table.rows[ri].cells[1].text = b
    return table


def test_fill_req_table_labeled_rows():
    table = _req_table(
        ("Req. 105", ""),
        ("설명", ""),
        ("목적", ""),
        ("기준", ""),
    )
    req = {
        "description": "desc text",
        "purpose": "purpose text",
        "criteria": "criteria text",
    }
    assert _fill_req_table_full(table, req, overwrite=True)
    assert table.rows[1].cells[1].text == "desc text"
    assert table.rows[2].cells[1].text == "purpose text"
    assert table.rows[3].cells[1].text == "criteria text"


def test_fill_req_table_unlabeled_functional_gets_labels():
    table = _req_table(
        ("Req. 2", ""),
        ("", ""),
        ("", ""),
        ("", ""),
    )
    req = {
        "description": "main desc",
        "purpose": "main purpose",
        "criteria": "main criteria",
    }
    assert _fill_req_table_full(table, req, overwrite=True)
    assert table.rows[1].cells[0].text == "설명"
    assert table.rows[1].cells[1].text == "main desc"
    assert table.rows[2].cells[0].text == "목적"
    assert table.rows[2].cells[1].text == "main purpose"
    assert table.rows[3].cells[0].text == "기준"
    assert table.rows[3].cells[1].text == "main criteria"


def test_traceability_fills_title_and_applicability():
    doc = Document()
    table = doc.add_table(rows=2, cols=4)
    table.rows[0].cells[0].text = "IA-01"
    table.rows[1].cells[0].text = "UC-02"
    doc._body._body.insert(-1, table._tbl)

    trace = [
        {"requirement": "IA-01", "title": "사용자 식별 및 인증", "linked_reqs": "Req. 2", "applicability": "해당"},
        {"requirement": "UC-02", "title": "모바일 코드 사용 통제", "linked_reqs": "N/A", "applicability": "비해당"},
    ]
    count = apply_traceability_details(doc, trace)
    assert count >= 2
    assert "사용자" in table.rows[0].cells[1].text
    assert table.rows[0].cells[2].text == "해당"
    assert table.rows[0].cells[3].text == "Req. 2"
    assert table.rows[1].cells[2].text == "비해당"
