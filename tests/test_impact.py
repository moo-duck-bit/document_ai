import json
from pathlib import Path

import pytest

from document_ai.impact.graph import TraceabilityGraph, normalize_req_id, parse_linked_reqs, xxcs_test_ids
from document_ai.impact.orchestrator import apply_change, compute_impact
from document_ai.learn.extract_design_items import DesignItemIndex, extract_design_items_docx
from document_ai.learn.docx_io import load_document
from document_ai.learn.extract_requirements import extract_requirements_docx
from document_ai.learn.extract_security_tests import extract_security_tests_docx
from document_ai.paths import FILLED_PATHS, SCHEMAS_EC_SW, TEMPLATES_EC_SW
from document_ai.render.fill import create_xxcs_skeleton, fill_from_facts
from document_ai.render.design_items import patch_mddr_design_items
from document_ai.render.xxcs import fill_xxcs_report


@pytest.fixture(scope="module")
def traceability_rows():
    req_path = Path("data/cases/mindrium_xa/requirements.json")
    payload = json.loads(req_path.read_text(encoding="utf-8"))
    return payload["traceability"]


def test_parse_linked_reqs_variants():
    assert parse_linked_reqs("Req. 2, Req. 102, Req.201") == ["Req. 2", "Req. 102", "Req. 201"]
    assert parse_linked_reqs("Req.2, Req.102, Req.202") == ["Req. 2", "Req. 102", "Req. 202"]
    assert parse_linked_reqs("N/A") == []
    assert normalize_req_id("req.6") == "Req. 6"


def test_req6_impact_includes_mddr_when_indexed(traceability_rows):
    graph = TraceabilityGraph(traceability_rows)
    index = DesignItemIndex(
        [
            {"req_id": "Req. 6", "block_kind": "table", "design_description": "existing design"},
            {"req_id": "Req. 99", "block_kind": "table", "design_description": "other"},
        ]
    )
    impact = graph.impact(["Req. 6"], design_index=index)
    assert impact["documents"]["spec_design"]["action"] == "patch"
    assert impact["documents"]["spec_design"]["req_ids"] == ["Req. 6"]


def test_req6_impact(traceability_rows):
    graph = TraceabilityGraph(traceability_rows)
    impact = graph.impact(["Req. 6"])

    security_ids = set(impact["linked_security_ids"])
    assert "IA-04" in security_ids
    assert "IA-06" in security_ids
    assert "IA-07" in security_ids
    assert "SI-06" in security_ids

    xxcs_ids = impact["documents"]["report_security_verification"]["security_req_ids"]
    assert "IA-04" in xxcs_ids
    assert "SI-06" in xxcs_ids
    assert all(item.startswith(("IA-", "UC-", "SI-")) for item in xxcs_ids)


def test_xxcs_test_ids_filters_non_test_rows():
    ids = xxcs_test_ids(["IA-01", "DC-01", "SI-03", "RA-01"])
    assert ids == ["IA-01", "SI-03"]


def test_apply_change_patches_mdsr_only_when_xxcs_missing(tmp_path, traceability_rows):
    if not FILLED_PATHS["spec_requirements"].exists():
        pytest.skip("MDSR filled example not present")

    case_dir = tmp_path / "case"
    case_dir.mkdir()
    changes_dir = case_dir / "changes"
    changes_dir.mkdir()

    schema = json.loads((SCHEMAS_EC_SW / "spec_requirements.schema.json").read_text(encoding="utf-8"))
    req_data = extract_requirements_docx(FILLED_PATHS["spec_requirements"])
    (case_dir / "requirements.json").write_text(json.dumps(req_data, ensure_ascii=False, indent=2), encoding="utf-8")

    out = case_dir / "output_mdsr.docx"
    fill_from_facts(
        TEMPLATES_EC_SW / "template_mdsr.docx",
        schema,
        {"product_name": "TestProduct", "model_name": "TestProduct", "software_name": "TestProduct"},
        out,
        requirements_payload=req_data,
    )

    new_description = "PATCHED Req. 6 description for incremental update test."
    change = {
        "change_id": "test-req6",
        "summary": "test",
        "requirement_changes": [{"req_id": "Req. 6", "description": new_description}],
    }
    change_path = changes_dir / "req6.json"
    change_path.write_text(json.dumps(change, ensure_ascii=False, indent=2), encoding="utf-8")

    dry = compute_impact(case_dir, change)
    assert "IA-04" in dry["impact"]["linked_security_ids"]

    result = apply_change(case_dir, change_path, dry_run=False)
    assert "Req. 6" in result["patches"]["spec_requirements"]["req_ids_patched"]

    doc = load_document(out)
    found = False
    for table in doc.tables:
        if table.rows and table.rows[0].cells[0].text.strip() == "Req. 6":
            body = "\n".join(cell.text for row in table.rows for cell in row.cells)
            assert new_description in body
            found = True
            break
    assert found

    updated = json.loads((case_dir / "requirements.json").read_text(encoding="utf-8"))
    req6 = next(r for r in updated["requirements"] if r["req_id"] == "Req. 6")
    assert req6["description"] == new_description


def test_apply_change_patches_xxcs_subset(tmp_path):
    if not FILLED_PATHS["report_security_verification"].exists():
        pytest.skip("XXCS filled example not present")
    if not FILLED_PATHS["spec_requirements"].exists():
        pytest.skip("MDSR filled example not present")

    case_dir = tmp_path / "case_xxcs"
    case_dir.mkdir()
    changes_dir = case_dir / "changes"
    changes_dir.mkdir()

    req_data = extract_requirements_docx(FILLED_PATHS["spec_requirements"])
    (case_dir / "requirements.json").write_text(json.dumps(req_data, ensure_ascii=False, indent=2), encoding="utf-8")

    security_payload = extract_security_tests_docx(FILLED_PATHS["report_security_verification"])
    (case_dir / "security_tests.json").write_text(
        json.dumps(security_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    skel = case_dir / "xxcs_skel.docx"
    create_xxcs_skeleton(FILLED_PATHS["report_security_verification"], skel)
    xxcs_out = case_dir / "output_xxcs.docx"
    fill_xxcs_report(skel, {"product_name": "TestProduct"}, security_payload, xxcs_out)

    change = {
        "change_id": "test-req6-xxcs",
        "requirement_changes": [{"req_id": "Req. 6", "description": "Req6 patch trigger"}],
    }
    change_path = changes_dir / "req6.json"
    change_path.write_text(json.dumps(change, ensure_ascii=False, indent=2), encoding="utf-8")

    result = apply_change(case_dir, change_path)
    xxcs_patch = result["patches"]["report_security_verification"]
    assert xxcs_patch["stats"]["tables_filled"] >= 1
    assert "IA-04" in xxcs_patch["security_req_ids"]


def test_extract_and_patch_mddr_design_items(tmp_path):
    if not FILLED_PATHS["spec_design"].exists():
        pytest.skip("MDDR filled example not present")

    case_dir = tmp_path / "case_mddr"
    case_dir.mkdir()

    design_payload = extract_design_items_docx(FILLED_PATHS["spec_design"])
    if not design_payload["items"]:
        pytest.skip("No Req. design blocks found in filled MDDR")

    (case_dir / "design_items.json").write_text(
        json.dumps(design_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    schema = json.loads((SCHEMAS_EC_SW / "spec_design.schema.json").read_text(encoding="utf-8"))
    out = case_dir / "output_mddr.docx"
    fill_from_facts(
        TEMPLATES_EC_SW / "template_mddr.docx",
        schema,
        {"product_name": "TestProduct", "model_name": "TestProduct", "software_name": "TestProduct"},
        out,
        design_items_payload=design_payload,
    )
    assert out.exists()
    assert design_payload["items"]

    target = design_payload["items"][0]
    new_text = "UPDATED DESIGN TEXT FOR PATCH TEST"
    from document_ai.learn.docx_io import load_document

    doc = load_document(out)
    patched = patch_mddr_design_items(
        doc,
        [{"req_id": target["req_id"], "design_description": new_text}],
    )
    doc.save(str(out))
    assert target["req_id"] in patched

    verify = load_document(out)
    found = False
    for table in verify.tables:
        if table.rows and table.rows[0].cells[0].text.strip() == target["req_id"]:
            body = " ".join(row.cells[1].text for row in table.rows[1:] if len(row.cells) > 1)
            if new_text in body:
                found = True
                break
    if not found:
        from document_ai.learn.docx_io import iter_blocks
        from docx.text.paragraph import Paragraph

        for block in iter_blocks(verify):
            if isinstance(block, Paragraph) and new_text in block.text:
                found = True
                break
    assert found
