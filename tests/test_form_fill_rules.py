"""Tests for form_fill domain replacement and placeholder resolution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from document_ai.form_fill.rules import (
    adapt_text,
    build_mdsr_content_from_graph,
    build_requirements_from_graph,
    build_substitution_map,
    enrich_layout_from_intake,
    resolve_template_tokens,
)
from document_ai.quality.runner import run_document_quality


@pytest.fixture
def inventory_intake() -> dict:
    return json.loads(Path("data/cases/inventory_mgmt/input.json").read_text(encoding="utf-8"))


def test_resolve_template_tokens():
    mapping = build_substitution_map(
        {"facts": {"product_name": "IMS", "product_code": "IMS", "model_name": "IMS-Warehouse-001"}}
    )
    text = "{product_code}-api (주문·결제·회원 API)"
    result = resolve_template_tokens(text, mapping)
    assert "{product_code}" not in result
    assert "IMS-api" in result


def test_inventory_domain_replaces_ecommerce_terms(inventory_intake):
    mapping = build_substitution_map(inventory_intake)
    source = "B2C 온라인 쇼핑몰에서 장바구니, PG 결제, 상품 탐색, 주문·결제를 지원한다."
    result = adapt_text(source, mapping, "inventory_b2b")
    assert "쇼핑몰" not in result
    assert "장바구니" not in result
    assert "PG 결제" not in result
    assert "상품 탐색" not in result
    assert "주문·결제" not in result


def test_build_requirements_adapts_jm_payload(inventory_intake):
    jm_req = json.loads(Path("data/cases/jm_collection/requirements.json").read_text(encoding="utf-8"))
    adapted = build_requirements_from_graph(inventory_intake, {"requirements.json": jm_req})
    req1 = adapted["requirements"][0]["description"]
    assert "JM COLLECTION" not in req1
    assert "쇼핑몰" not in req1


def test_enrich_layout_sets_document_title(inventory_intake):
    enriched = enrich_layout_from_intake({}, inventory_intake, doc_kind="mdsr")
    assert "IMS" in enriched["document_title"]
    assert "문서번호" in enriched["document_version_line"]
    assert "XX-XX" not in enriched["document_version_line"]


def test_build_mdsr_content_adapts_product_overview(inventory_intake):
    jm_mdsr = json.loads(Path("data/cases/jm_collection/mdsr_content.json").read_text(encoding="utf-8"))
    adapted = build_mdsr_content_from_graph(inventory_intake, {"mdsr_content.json": jm_mdsr})
    overview = adapted["product_overview"]["usage_purpose"]
    assert "전자상거래" not in overview
    assert "패션·잡화" not in overview
    assert adapted["document_title"].startswith("EC-SW-MDSR(IMS)")


@pytest.mark.skipif(
    not Path("data/cases/inventory_mgmt/output_mdsr.docx").exists(),
    reason="inventory_mgmt outputs not generated",
)
def test_inventory_mgmt_quality_score_at_least_85():
    case = Path("data/cases/inventory_mgmt")
    result = run_document_quality(case)
    assert result["scores"]["terminology"] >= 80
    assert result["scores"]["overall"] >= 85
