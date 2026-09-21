"""Rule-based field inference and text adaptation."""

from __future__ import annotations

import copy
import re
from typing import Any

# Longest phrases first — order matters for replace()
INVENTORY_B2B_REPLACEMENTS: list[tuple[str, str]] = [
    ("JM COLLECTION Co., Ltd.", "{author_org}"),
    ("EC-SW-MDSR(JM)", "EC-SW-MDSR({product_code})"),
    ("EC-SW-MDDR(JM)", "EC-SW-MDDR({product_code})"),
    ("EC-SW-SDP(JM)", "EC-SW-SDP({product_code})"),
    ("문서번호 JM-SRS-2026-001", "문서번호 {product_code}-SRS-{document_version}"),
    ("문서번호 JM-SDS-2026-001", "문서번호 {product_code}-SDD-{document_version}"),
    ("B2C 재고관리", "B2B 재고관리"),
    ("패션·잡화 전문 B2C 온라인 쇼핑몰", "B2B 재고·창고 관리 시스템"),
    ("패션·잡화 B2C 전자상거래", "B2B 재고·창고 관리"),
    ("B2C 패션·잡화 온라인 쇼핑몰", "B2B 재고·창고 관리 시스템"),
    ("회원/비회원 상품탐색·주문·결제·배송조회·반품", "거래처·내부사용자 품목조회·입출고·ERP정산·출고조회·반품입고"),
    ("회원·비회원 모두 상품 탐색, 장바구니, 주문, PG 결제, 배송 추적, 반품/환불", "거래처·내부사용자가 품목 조회, 출고 요청, 입출고 처리, ERP 정산 연동, 출고/납품 추적, 반품 입고를 이용"),
    ("비회원 사용자에게 상품", "외부 연동 시스템에 품목"),
    ("B2C 전자상거래 핵심 거래 기능을 제공하여 고객의 온라인 구매 경험을 보장하기 위함이다.", "B2B 재고관리 핵심 운영 기능을 제공하여 창고 운영 효율을 보장하기 위함이다."),
    ("상품 탐색·노출을 체계화하여 구매 전환율을 높이기 위함이다.", "품목 조회·분류를 체계화하여 재고 회전율을 높이기 위함이다."),
    ("장바구니에 옵션별 상품을 담고, 수량 변경·삭제·선택 결제를 지원해야 한다", "출고 요청 목록에 옵션별 품목을 담고, 수량 변경·삭제·선택 출고를 지원해야 한다"),
    ("주문·결제·배송 상태는", "입출고·ERP정산·납품 상태는"),
    ("주문·결제·재고 변경은", "입출고·ERP정산·재고 변경은"),
    ("주문·결제·개인정보 접근", "입출고·ERP정산·개인정보 접근"),
    ("주문·결제 API", "입출고 API"),
    ("주문·결제·배송", "입출고·ERP정산·납품"),
    ("주문·결제", "입출고·ERP정산"),
    ("PG 토큰 결제", "ERP 정산 연동"),
    ("PG 토큰·마스킹", "ERP 연동 토큰·마스킹"),
    ("PG 토큰", "ERP 연동 토큰"),
    ("PG 결제", "ERP 정산 연동"),
    ("결제 토큰", "ERP 연동 토큰"),
    ("상품 탐색", "품목 조회"),
    ("상품 목록·검색", "품목 목록·검색"),
    ("온라인 쇼핑몰", "재고·창고 관리 시스템"),
    ("전자상거래", "재고관리"),
    ("B2C 온라인", "B2B 창고"),
    ("B2C 전자상거래", "B2B 재고관리"),
    ("패션·잡화", "물류·유통"),
    ("온라인 구매 경험", "재고 운영 효율"),
    ("구매 전환율", "재고 회전율"),
    ("프로모션·쿠폰", "할인 정책"),
    ("반품/환불", "반품 입고"),
    ("배송 추적", "출고/납품 추적"),
    ("배송·반품", "출고/납품·반품"),
    ("회원등급", "거래처 등급"),
    ("고객몰", "웹 포털"),
    ("운영 백오피스", "운영 콘솔"),
    ("백오피스", "운영 콘솔"),
    ("장바구니", "출고 요청 목록"),
    ("쇼핑몰", "재고관리 시스템"),
    ("PG사", "ERP 시스템"),
    ("카드 데이터", "민감 데이터"),
    ("카드 PAN/CVC", "민감 식별정보"),
    ("택배사", "운송사"),
    ("일반 소비자(회원·비회원)", "내부 사용자·거래처 담당자"),
    ("회원·비회원", "내부 사용자·거래처"),
    ("상품·프로모션·주문·회원·재고", "품목·할인정책·입출고·거래처·재고"),
    ("상품·주문·CS·재고", "품목·입출고·운영·재고"),
    ("상품·주문·회원", "품목·입출고·거래처"),
    ("상품·주문", "품목·입출고"),
    ("상품", "품목"),
    ("주문", "입출고 요청"),
    ("결제", "ERP 정산"),
    ("배송", "출고/납품"),
    ("쿠폰", "할인 정책"),
    ("포인트", "거래처 크레딧"),
    ("리뷰", "품질 이력"),
    ("프로모션", "할인 정책"),
    ("PCI DSS", "ISO 27001"),
    ("ecommerce_b2c", "inventory_b2b"),
    ("JM COLLECTION", "{product_name}"),
    ("JM-web", "{product_code}-web"),
    ("JM-api", "{product_code}-api"),
    ("JM-admin", "{product_code}-admin"),
    ("JM-MALL-001", "{model_code}"),
    ("상품 탐색·장바구니·주문·PG 결제", "입고·출고·재고조정·발주"),
]

HOSPITAL_RESERVATION_REPLACEMENTS: list[tuple[str, str]] = [
    ("JM COLLECTION Co., Ltd.", "{author_org}"),
    ("EC-SW-MDSR(JM)", "EC-SW-MDSR({product_code})"),
    ("EC-SW-MDDR(JM)", "EC-SW-MDDR({product_code})"),
    ("EC-SW-SDP(JM)", "EC-SW-SDP({product_code})"),
    ("문서번호 JM-SRS-2026-001", "문서번호 {product_code}-SRS-{document_version}"),
    ("문서번호 JM-SDS-2026-001", "문서번호 {product_code}-SDD-{document_version}"),
    ("패션·잡화 전문 B2C 온라인 쇼핑몰", "병원 예약·접수 시스템"),
    ("패션·잡화 B2C 전자상거래", "병원 예약·접수 서비스"),
    ("B2C 패션·잡화 온라인 쇼핑몰", "병원 예약·접수 시스템"),
    ("회원/비회원 상품탐색·주문·결제·배송조회·반품", "환자·보호자 진료과조회·예약·수납·방문일정조회·취소"),
    (
        "회원·비회원 모두 상품 탐색, 장바구니, 주문, PG 결제, 배송 추적, 반품/환불",
        "환자·보호자가 진료과 조회, 예약 신청, 예약 확정, 수납 정산, 방문 일정 확인, 취소/변경을 이용",
    ),
    ("비회원 사용자에게 상품", "비회원 환자에게 진료과"),
    (
        "B2C 전자상거래 핵심 거래 기능을 제공하여 고객의 온라인 구매 경험을 보장하기 위함이다.",
        "병원 예약 핵심 서비스를 제공하여 환자 접근성과 진료 스케줄 효율을 보장하기 위함이다.",
    ),
    (
        "상품 탐색·노출을 체계화하여 구매 전환율을 높이기 위함이다.",
        "진료과·의료진 정보를 체계화하여 예약 전환율을 높이기 위함이다.",
    ),
    (
        "장바구니에 옵션별 상품을 담고, 수량 변경·삭제·선택 결제를 지원해야 한다",
        "예약 신청 목록에 진료과·의료진을 선택하고, 일정 변경·취소·확정 수납을 지원해야 한다",
    ),
    ("주문·결제·배송 상태는", "예약·수납·진료일정 상태는"),
    ("주문·결제·재고 변경은", "예약·수납·예약 슬롯 변경은"),
    ("주문·결제·개인정보 접근", "예약·수납·개인정보 접근"),
    ("주문·결제 API", "예약 API"),
    ("주문·결제·배송", "예약·수납·진료일정"),
    ("주문·결제", "예약·수납"),
    ("PG 토큰 결제", "수납 정산 연동"),
    ("PG 토큰·마스킹", "수납 연동 토큰·마스킹"),
    ("PG 토큰", "수납 연동 토큰"),
    ("PG 결제", "수납 정산"),
    ("결제 토큰", "수납 연동 토큰"),
    ("상품 탐색", "진료과 조회"),
    ("상품 목록·검색", "진료과 목록·검색"),
    ("온라인 쇼핑몰", "병원 예약·접수 시스템"),
    ("전자상거래", "병원 예약"),
    ("B2C 온라인", "병원 온라인"),
    ("B2C 전자상거래", "병원 예약 서비스"),
    ("패션·잡화", "의료 서비스"),
    ("온라인 구매 경험", "환자 접근성"),
    ("구매 전환율", "예약 전환율"),
    ("프로모션·쿠폰", "환자 안내"),
    ("반품/환불", "예약 취소/변경"),
    ("배송 추적", "방문 일정 확인"),
    ("배송·반품", "방문 일정·취소"),
    ("회원등급", "환자 등급"),
    ("고객몰", "환자 포털"),
    ("운영 백오피스", "병원 운영 콘솔"),
    ("백오피스", "병원 운영 콘솔"),
    ("장바구니", "예약 신청"),
    ("쇼핑몰", "병원 예약 시스템"),
    ("PG사", "수납 시스템"),
    ("카드 데이터", "민감 의료·결제 데이터"),
    ("카드 PAN/CVC", "민감 식별정보"),
    ("택배사", "진료 일정 연동"),
    ("일반 소비자(회원·비회원)", "환자·보호자(회원·비회원)"),
    ("회원·비회원", "환자·보호자"),
    ("입고·출고", "접수·배정"),
    ("재고관리", "예약 슬롯 관리"),
    ("창고", "진료 센터"),
    ("품목", "진료 서비스"),
    ("상품·프로모션·주문·회원·재고", "진료과·환자안내·예약·환자·예약슬롯"),
    ("상품·주문·CS·재고", "진료과·예약·상담·예약슬롯"),
    ("상품·주문·회원", "진료과·예약·환자"),
    ("상품·주문", "진료과·예약"),
    ("재고 연동", "예약 슬롯 연동"),
    ("재고", "예약 슬롯"),
    ("상품", "진료과"),
    ("주문", "예약"),
    ("결제", "수납"),
    ("배송", "방문/진료 일정"),
    ("쿠폰", "환자 안내"),
    ("포인트", "예약 이력"),
    ("리뷰", "만족도"),
    ("프로모션", "환자 안내"),
    ("PCI DSS", "개인정보보호법"),
    ("ecommerce_b2c", "hospital_reservation"),
    ("inventory_b2b", "hospital_reservation"),
    ("JM COLLECTION", "{product_name}"),
    ("JM-web", "{product_code}-web"),
    ("JM-api", "{product_code}-api"),
    ("JM-admin", "{product_code}-admin"),
    ("JM-MALL-001", "{model_code}"),
    ("Inventory Management System", "{product_name}"),
    ("IMS-web", "{product_code}-web"),
    ("IMS-api", "{product_code}-api"),
    ("IMS-admin", "{product_code}-admin"),
    ("입출고·ERP정산", "예약·수납"),
    ("입출고 요청", "예약 신청"),
    ("ERP 정산", "수납 정산"),
    ("출고 요청 목록", "예약 신청"),
    ("출고/납품", "방문/진료 일정"),
    ("거래처·내부사용자", "환자·보호자"),
    ("진료 서비스조회", "진료과 조회"),
    ("고객용 웹·모바일 몰", "환자용 웹·모바일 포털"),
    ("웹·모바일 몰", "웹·모바일 포털"),
    ("반품", "예약 취소"),
    ("서비스 서비스", "서비스"),
    ("환자·보호자(환자·보호자)", "환자·보호자"),
    ("B2C 병원 예약 시스템", "병원 예약 시스템"),
    ("B2C 병원 예약", "병원 예약"),
    ("B2C ", ""),
    ("CheckoutWizard", "ReservationWizard"),
    ("POST /orders/", "POST /appointments/"),
    ("promotions`, `coupons`", "patient_notices`, `appointment_rules`"),
    ("진료 서비스", "진료과"),
    ("상품 탐색·장바구니·주문·PG 결제", "진료과 조회·예약 신청·예약·수납 정산"),
]

DOMAIN_REPLACEMENTS: dict[str, list[tuple[str, str]]] = {
    "inventory_b2b": INVENTORY_B2B_REPLACEMENTS,
    "hospital_reservation": HOSPITAL_RESERVATION_REPLACEMENTS,
}

TEMPLATE_TOKEN_RE = re.compile(r"\{[a-z_]+\}")


def build_substitution_map(intake: dict[str, Any]) -> dict[str, str]:
    facts = intake.get("facts") or {}
    product = str(facts.get("product_name") or intake.get("product_name") or "")
    code = str(facts.get("product_code") or intake.get("product_code") or "APP")
    org = str(facts.get("author_org") or product)
    model = str(facts.get("model_name") or f"{product} Platform")
    version = str(facts.get("document_version", "1.0"))
    ver_suffix = version.replace(".", "")
    return {
        "{product_name}": product,
        "{product_code}": code,
        "{author_org}": org,
        "{model_code}": model.replace(" ", "-")[:24],
        "{document_version}": ver_suffix,
        "JM COLLECTION Co., Ltd.": org,
        "JM COLLECTION": product,
        "JM-web": f"{code}-web",
        "JM-api": f"{code}-api",
        "JM-admin": f"{code}-admin",
        "JM-MALL-001": model.replace(" ", "-")[:24],
        "XX-XX-XXXX": f"{code}-DOC-{ver_suffix}",
        "XX-XX": f"{code}-DOC",
    }


def resolve_template_tokens(text: str, mapping: dict[str, str]) -> str:
    if not text:
        return text
    result = text
    for token in sorted({m.group(0) for m in TEMPLATE_TOKEN_RE.finditer(text)}, key=len, reverse=True):
        if token in mapping:
            result = result.replace(token, mapping[token])
    return result


def adapt_text(text: str, mapping: dict[str, str], domain: str = "") -> str:
    if not text:
        return text
    result = text
    for pattern, replacement in DOMAIN_REPLACEMENTS.get(domain, []):
        repl = mapping.get(replacement, replacement)
        if pattern in result:
            result = result.replace(pattern, repl)
    for src, dst in sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True):
        if src.startswith("{"):
            continue
        result = result.replace(src, dst)
    result = resolve_template_tokens(result, mapping)
    return result


def adapt_json_value(value: Any, mapping: dict[str, str], domain: str) -> Any:
    if isinstance(value, str):
        return adapt_text(value, mapping, domain)
    if isinstance(value, list):
        return [adapt_json_value(item, mapping, domain) for item in value]
    if isinstance(value, dict):
        return {k: adapt_json_value(v, mapping, domain) for k, v in value.items()}
    return value


def enrich_layout_from_intake(payload: dict[str, Any], intake: dict[str, Any], *, doc_kind: str) -> dict[str, Any]:
    """Fill cover/layout fields from input.json facts when missing."""
    facts = intake.get("facts") or {}
    product = str(facts.get("product_name") or intake.get("product_name") or "")
    code = str(facts.get("product_code") or intake.get("product_code") or "APP")
    version = str(facts.get("document_version", "1.0"))
    org = str(facts.get("author_org") or product)
    model = str(facts.get("model_name") or f"{product} Platform").replace(" ", "-")[:24]
    approval_date = str(facts.get("approval_date", ""))
    ver_suffix = version.replace(".", "")

    if doc_kind == "mdsr":
        default_title = f"EC-SW-MDSR({code}) {product} 소프트웨어 요구사항명세서"
        doc_number = f"{code}-SRS-{ver_suffix}"
    else:
        default_title = f"EC-SW-MDDR({code}) {product} 소프트웨어 설계명세서"
        doc_number = f"{code}-SDD-{ver_suffix}"

    payload["document_title"] = facts.get(f"document_title_{doc_kind}") or default_title
    payload["document_title_sdp"] = (
        facts.get("document_title_sdp") or f"EC-SW-SDP({code}) {product} 소프트웨어 개발 계획서"
    )
    payload["document_version_line"] = (
        facts.get("document_version_line") or f"Ver {version} / 문서번호 {doc_number}"
    )
    payload["cover_product_line"] = org
    payload["domain"] = intake.get("domain", "")

    revision = dict(payload.get("revision") or {})
    if approval_date:
        revision.setdefault("date", approval_date)
    if product and not revision.get("summary"):
        revision.setdefault("summary", f"{product} {'요구사항' if doc_kind == 'mdsr' else '설계'}명세서 최초 제정")
    payload["revision"] = revision

    paragraphs = payload.get("paragraphs")
    if isinstance(paragraphs, list):
        if len(paragraphs) >= 4:
            paragraphs[3] = payload["document_title"]
        if len(paragraphs) >= 5:
            paragraphs[4] = payload["document_version_line"]

    matrix = payload.get("product_matrix")
    if isinstance(matrix, list):
        for row in matrix:
            if not row:
                continue
            label = str(row[0]).strip()
            for index in range(1, len(row)):
                cell = str(row[index])
                if label == "모델명" and cell in {"JM-MALL-001", "{model_code}", ""}:
                    row[index] = model
                elif label == "제품명" and ("JM COLLECTION" in cell or cell == "{product_name}"):
                    row[index] = product
                elif label == "제조자" and ("JM COLLECTION" in cell or cell == "{author_org}"):
                    row[index] = org
                elif label == "소프트웨어명" and cell in {"고객몰", "JM-web"}:
                    row[index] = f"{code}-web"
                elif label == "소프트웨어명" and cell in {"API 서버", "JM-api"}:
                    row[index] = f"{code}-api"
                elif label == "소프트웨어명" and cell in {"운영 백오피스", "JM-admin"}:
                    row[index] = f"{code}-admin"

    return payload


def apply_rules_to_intake(intake: dict[str, Any]) -> dict[str, Any]:
    """Deterministic cover/meta fields from facts — no LLM."""
    payload = copy.deepcopy(intake)
    facts = payload.setdefault("facts", {})
    product = facts.get("product_name", "")
    code = facts.get("product_code", "APP")
    org = facts.get("author_org", product)
    version = facts.get("document_version", "1.0")
    ver_suffix = version.replace(".", "")

    if product and not payload.get("product_name"):
        payload["product_name"] = product

    facts.setdefault("document_title_mdsr", f"EC-SW-MDSR({code}) {product} 소프트웨어 요구사항명세서")
    facts.setdefault("document_title_mddr", f"EC-SW-MDDR({code}) {product} 소프트웨어 설계명세서")
    facts.setdefault("document_title_sdp", f"EC-SW-SDP({code}) {product} 소프트웨어 개발 계획서")
    facts.setdefault("document_version_line", f"Ver {version} / 문서번호 {code}-SRS-{ver_suffix}")

    standards = payload.get("standards")
    if standards and not facts.get("standards"):
        facts["standards"] = standards

    hints = payload.setdefault("free_text_hints", {})
    if not hints.get("system_overview") and product:
        domain = payload.get("domain", "")
        if "inventory" in domain:
            hints["system_overview"] = (
                f"{product}은 창고·유통센터 재고를 실시간 관리하는 B2B 재고관리 소프트웨어이다. "
                f"입고·출고·재고조정·발주·창고이동을 웹·API·운영 콘솔({code}-web/{code}-api/{code}-admin)로 제공한다."
            )
            hints.setdefault(
                "architecture_narrative",
                "웹 포털, REST API, 운영 콘솔 3계층 구조이며 ERP·WMS 연동을 지원한다.",
            )
        elif "hospital" in domain:
            hints["system_overview"] = (
                f"{product}은 병원 예약·접수·스케줄 관리 소프트웨어이다. "
                f"환자 포털({code}-web), 진료 API({code}-api), 병원 운영 콘솔({code}-admin)로 구성된다."
            )
            hints.setdefault(
                "architecture_narrative",
                "환자 포털, REST API, 병원 운영 콘솔 3계층 구조이며 EMR·수납 시스템 연동을 지원한다.",
            )

    facts["cover_product_line"] = org
    return payload


def build_mdsr_content_from_graph(intake: dict[str, Any], graph_payloads: dict[str, Any]) -> dict[str, Any]:
    mapping = build_substitution_map(intake)
    domain = intake.get("domain", "")
    base = copy.deepcopy(graph_payloads.get("mdsr_content.json") or {})
    if not base:
        return {}
    adapted = adapt_json_value(base, mapping, domain)
    return enrich_layout_from_intake(adapted, intake, doc_kind="mdsr")


def build_mddr_content_from_graph(intake: dict[str, Any], graph_payloads: dict[str, Any]) -> dict[str, Any]:
    mapping = build_substitution_map(intake)
    domain = intake.get("domain", "")
    base = copy.deepcopy(graph_payloads.get("mddr_content.json") or {})
    if not base:
        return {}
    adapted = adapt_json_value(base, mapping, domain)
    return enrich_layout_from_intake(adapted, intake, doc_kind="mddr")


def build_requirements_from_graph(intake: dict[str, Any], graph_payloads: dict[str, Any]) -> dict[str, Any]:
    mapping = build_substitution_map(intake)
    domain = intake.get("domain", "")
    base = copy.deepcopy(graph_payloads.get("requirements.json") or {})
    if not base:
        return {}
    adapted = adapt_json_value(base, mapping, domain)
    adapted["source"] = f"harness/form_fill from {adapted.get('source', 'retrieval')}"
    return adapted


def build_design_items_from_graph(intake: dict[str, Any], graph_payloads: dict[str, Any]) -> dict[str, Any]:
    mapping = build_substitution_map(intake)
    domain = intake.get("domain", "")
    base = copy.deepcopy(graph_payloads.get("design_items.json") or {})
    if not base:
        return {}
    return adapt_json_value(base, mapping, domain)


def build_design_content_from_graph(intake: dict[str, Any], graph_payloads: dict[str, Any]) -> dict[str, Any]:
    mapping = build_substitution_map(intake)
    domain = intake.get("domain", "")
    base = copy.deepcopy(graph_payloads.get("design_content.json") or {})
    if not base:
        return {}
    adapted = adapt_json_value(base, mapping, domain)
    return enrich_layout_from_intake(adapted, intake, doc_kind="mddr")
