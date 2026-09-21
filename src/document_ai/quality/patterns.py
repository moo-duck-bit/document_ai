"""Regex and domain term patterns for document quality analysis."""

from __future__ import annotations

import re

from document_ai.render.mdsr import PLACEHOLDER_DOC_CODE_RE, RESIDUAL_PATTERN, UNIQUE_MINDRIUM_PATTERN

PLACEHOLDER_PATTERNS = [
    ("placeholder_xxxx", re.compile(r"\bX{3,}\b", re.I)),
    ("placeholder_doc_code", PLACEHOLDER_DOC_CODE_RE),
    ("placeholder_bracket", re.compile(r"\[(?:TBD|TODO|PLACEHOLDER|입력|작성)\]", re.I)),
    ("placeholder_dash", re.compile(r"[-–—]{3,}")),
    ("placeholder_doc_number", re.compile(r"문서번호\s*[:：]?\s*(?:XX|미정|TBD)", re.I)),
]

MINDRIUM_PATTERNS = [
    ("mindrium_brand", re.compile(r"\bJM[\s-]?(?:COLLECTION|web|api|admin|MALL)\b", re.I)),
    ("mindrium_residual", UNIQUE_MINDRIUM_PATTERN),
    ("medical_residual", RESIDUAL_PATTERN),
]

FIGURE_TABLE_PATTERNS = [
    ("figure_placeholder", re.compile(r"(?:Figure|FIG\.?|그림)\s*[\d.]+\s*(?:[:：]\s*)?(?:X{2,}|TBD|미작성|placeholder)?", re.I)),
    ("table_placeholder", re.compile(r"(?:Table|표)\s*[\d.]+\s*(?:[:：]\s*)?(?:X{2,}|TBD|미작성|placeholder)?", re.I)),
    ("caption_empty", re.compile(r"^(?:Figure|FIG\.?|그림|Table|표)\s*[\d.]+\s*[:：]?\s*$", re.I)),
]

BROKEN_SENTENCE_PATTERNS = [
    ("trailing_comma", re.compile(r",\s*$")),
    ("double_punct", re.compile(r"[。．]{2,}|\.{4,}")),
    ("incomplete_korean", re.compile(r"(?:하여|위하여|통해|대해)\s*$")),
]

DOMAIN_FOREIGN_TERMS: dict[str, list[tuple[str, re.Pattern[str]]]] = {
    "inventory_b2b": [
        ("ecommerce_b2c", re.compile(r"전자상거래|B2C\s*온라인|온라인\s*쇼핑몰|패션·잡화", re.I)),
        ("shopping_cart", re.compile(r"장바구니|PG\s*결제|결제\s*토큰|쇼핑몰", re.I)),
        ("order_payment", re.compile(r"상품\s*탐색|주문·결제|비회원\s*사용자에게\s*상품", re.I)),
    ],
    "hospital_reservation": [
        ("ecommerce", re.compile(r"쇼핑몰|장바구니|PG\s*결제|전자상거래|패션·잡화|B2C\s*온라인", re.I)),
        ("inventory", re.compile(r"재고관리\s*시스템|창고|입고·출고|WMS|품목\s*조회|ERP\s*정산", re.I)),
        ("shopping_flow", re.compile(r"상품\s*탐색|주문·결제|구매\s*전환", re.I)),
    ],
    "ecommerce_b2c": [
        ("inventory", re.compile(r"재고관리\s*시스템|창고\s*이동|발주\s*관리", re.I)),
        ("hospital", re.compile(r"병원\s*예약|진료과|접수\s*시스템", re.I)),
    ],
}

STRUCTURAL_SKIP = frozenset(
    {
        "설명",
        "목적",
        "기준",
        "Req.",
        "제품명",
        "승인자",
        "검토자",
        "작성자",
        "개정번호",
        "개정일자",
        "개정내용",
    }
)
