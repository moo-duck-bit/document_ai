import json
from pathlib import Path

import pytest

from document_ai.learn.extract_design import extract_design_content
from document_ai.learn.extract_security_tests import extract_security_tests_docx
from document_ai.learn.schema import export_schema_from_pair
from document_ai.paths import FILLED_PATHS, SCHEMAS_EC_SW, TEMPLATES_EC_SW
from document_ai.render.fill import create_xxcs_skeleton, fill_from_facts
from document_ai.render.xxcs import fill_xxcs_report


@pytest.fixture(scope="module")
def mdsr_schema(tmp_path_factory):
    out = SCHEMAS_EC_SW / "spec_requirements.schema.json"
    if not out.exists():
        export_schema_from_pair(
            "spec_requirements",
            TEMPLATES_EC_SW / "template_mdsr.docx",
            FILLED_PATHS["spec_requirements"],
            out,
        )
    return json.loads(out.read_text(encoding="utf-8"))


def test_mdsr_schema_has_fields(mdsr_schema):
    assert mdsr_schema["stats"]["field_count"] > 0


def test_mdsr_schema_has_requirements(mdsr_schema):
    assert len(mdsr_schema.get("requirements", [])) > 0


def test_generate_mdsr_with_requirements(mdsr_schema, tmp_path):
    from document_ai.learn.extract_requirements import extract_requirements_docx
    from document_ai.paths import FILLED_PATHS

    schema = json.loads((SCHEMAS_EC_SW / "spec_requirements.schema.json").read_text(encoding="utf-8"))
    req_data = extract_requirements_docx(FILLED_PATHS["spec_requirements"])
    facts = {"product_name": "TestProduct", "model_name": "TestProduct", "software_name": "TestProduct"}
    out = tmp_path / "out.docx"
    result = fill_from_facts(
        TEMPLATES_EC_SW / "template_mdsr.docx",
        schema,
        facts,
        out,
        requirements_payload=req_data,
    )
    assert out.exists()
    assert result["requirements"]["total_req_ids"] == 37
    assert len(result["requirements"]["req_tables_added"]) >= 1
    assert result["requirements"].get("req_tables_removed") == ["Req. 111"]
    assert result["requirements"]["traceability_rows_filled"] >= 30

    from document_ai.learn.docx_io import load_document
    import re

    doc = load_document(out)
    req_count = sum(
        1
        for t in doc.tables
        if t.rows and re.match(r"^Req\.\s*\d+", t.rows[0].cells[0].text.strip())
    )
    assert req_count == 37
    assert len(doc.tables) == 45


def test_xxcs_skeleton(tmp_path):
    filled = FILLED_PATHS["report_security_verification"]
    if not filled.exists():
        pytest.skip("XXCS filled example not present")
    out = tmp_path / "skel.docx"
    result = create_xxcs_skeleton(filled, out)
    assert out.exists()
    assert result["cells_cleared"] >= 0


def test_generate_mddr(tmp_path):
    if not FILLED_PATHS["spec_design"].exists():
        pytest.skip("MDDR filled example not present")

    schema = json.loads((SCHEMAS_EC_SW / "spec_design.schema.json").read_text(encoding="utf-8"))
    content = extract_design_content(FILLED_PATHS["spec_design"], schema)
    facts = {
        "product_name": "TestProduct",
        "model_name": "TestProduct",
        "software_name": "TestProduct",
        "approval_date": "2025.02.07",
        "standards": [
            "IEC 62304:2015 CSV Medical device software – Software life cycle processes",
            "ISO 14971:2019 Medical devices – Application of risk management to medical devices",
        ],
    }
    out = tmp_path / "out_mddr.docx"
    result = fill_from_facts(
        TEMPLATES_EC_SW / "template_mddr.docx",
        schema,
        facts,
        out,
        content_payload=content,
    )
    assert out.exists()
    assert "승인자" in result["applied"] or "제품명" in result["applied"]
    assert len(content["fields"]) >= 10


def test_generate_xxcs_with_security_tests(tmp_path):
    filled = FILLED_PATHS["report_security_verification"]
    if not filled.exists():
        pytest.skip("XXCS filled example not present")

    skel = tmp_path / "skel.docx"
    create_xxcs_skeleton(filled, skel)
    payload = extract_security_tests_docx(filled)
    out = tmp_path / "out_xxcs.docx"
    result = fill_xxcs_report(
        skel,
        {"product_name": "TestProduct"},
        payload,
        out,
    )
    assert out.exists()
    assert result["security_tests"]["tables_filled"] >= 1
    assert result["security_tests"]["cells_filled"] >= 1
