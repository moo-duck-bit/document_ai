"""Natural-language case intake — draft input.json from chat-style text."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = ("product_name", "product_code", "domain", "author_org", "confirmed")

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "hospital_reservation": [
        "병원",
        "예약",
        "진료과",
        "환자",
        "접수",
        "수납",
        "의료",
        "hospital",
        "reservation",
        "clinic",
    ],
    "inventory_b2b": [
        "재고",
        "창고",
        "입고",
        "출고",
        "wms",
        "erp",
        "inventory",
        "warehouse",
        "물류",
    ],
    "ecommerce_b2c": [
        "쇼핑몰",
        "장바구니",
        "전자상거래",
        "b2c",
        "온라인",
        "결제",
        "배송",
        "ecommerce",
        "쇼핑",
    ],
}

DOMAIN_DEFAULTS: dict[str, dict[str, str]] = {
    "hospital_reservation": {
        "product_name": "Hospital Reservation System",
        "product_code": "HRS",
        "model_name": "HRS-Clinic-001",
        "author_org": "Sample Medical IT Co., Ltd.",
    },
    "inventory_b2b": {
        "product_name": "Inventory Management System",
        "product_code": "IMS",
        "model_name": "IMS-Warehouse-001",
        "author_org": "Acme Logistics Co., Ltd.",
    },
    "ecommerce_b2c": {
        "product_name": "JM COLLECTION",
        "product_code": "JM",
        "model_name": "JM-MALL-001",
        "author_org": "JM COLLECTION Co., Ltd.",
    },
}

DOMAIN_STANDARDS: dict[str, list[str]] = {
    "hospital_reservation": [
        "개인정보보호법 (대한민국)",
        "OWASP ASVS v4.0 Application Security Verification Standard",
        "의료기기법 및 의료기기 소프트웨어 가이드라인 (참고)",
    ],
    "inventory_b2b": [
        "ISO 27001 Information Security Management",
        "개인정보보호법 (대한민국)",
        "OWASP ASVS v4.0 Application Security Verification Standard",
    ],
    "ecommerce_b2c": [
        "PCI DSS Payment Card Industry Data Security Standard",
        "개인정보보호법 (대한민국)",
        "OWASP ASVS v4.0 Application Security Verification Standard",
    ],
}

PRODUCT_NAME_PATTERNS = [
    re.compile(r"(?:product|제품|시스템)\s*(?:명|이름)?\s*[:：]\s*([^\n,;.]+)", re.I),
    re.compile(r"([A-Za-z][A-Za-z0-9\s]{2,40}\s+System)\b", re.I),
    re.compile(r"([가-힣A-Za-z0-9·\s]{2,30}시스템)", re.I),
]

PRODUCT_CODE_PATTERNS = [
    re.compile(r"(?:product[_\s-]?code|제품\s*코드)\s*[:：]\s*([A-Z]{2,8})\b", re.I),
    re.compile(r"\b([A-Z]{2,6})-(?:web|api|admin)\b", re.I),
]

AUTHOR_ORG_PATTERNS = [
    re.compile(r"(?:author|제조자|회사|기관)\s*[:：]\s*([^\n,;.]+)", re.I),
    re.compile(r"([A-Za-z0-9가-힣\s.&]+(?:Co\.,?\s*Ltd\.?|Inc\.?|주식회사|㈜))", re.I),
]

KOREAN_PRODUCT_NAMES = {
    "병원 예약": "Hospital Reservation System",
    "병원예약": "Hospital Reservation System",
    "재고 관리": "Inventory Management System",
    "재고관리": "Inventory Management System",
    "온라인 쇼핑몰": "JM COLLECTION",
    "전자상거래": "JM COLLECTION",
}


@dataclass
class IntakeDraft:
    case_id: str
    payload: dict[str, Any]
    missing_fields: list[str] = field(default_factory=list)
    inferred: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "payload": self.payload,
            "missing_fields": self.missing_fields,
            "inferred": self.inferred,
            "ready": not self.missing_fields and self.payload.get("confirmed") is True,
        }


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def infer_domain(text: str, *, explicit: str = "") -> tuple[str, dict[str, str]]:
    if explicit:
        return explicit, {"domain": explicit, "domain_source": "explicit"}
    lowered = text.lower()
    scores: dict[str, int] = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in lowered)
        if score:
            scores[domain] = score
    if not scores:
        return "", {}
    best = max(scores, key=scores.get)
    return best, {"domain": best, "domain_source": "keyword", "domain_score": str(scores[best])}


def _korean_product_name(text: str) -> str:
    for phrase, english in KOREAN_PRODUCT_NAMES.items():
        if phrase in text:
            return english
    return ""


def extract_product_name(text: str, *, explicit: str = "", domain: str = "") -> tuple[str, dict[str, str]]:
    if explicit:
        return explicit, {"product_name": explicit, "product_name_source": "explicit"}
    korean = _korean_product_name(text)
    if korean:
        return korean, {"product_name": korean, "product_name_source": "korean_phrase"}
    for pattern in PRODUCT_NAME_PATTERNS:
        match = pattern.search(text)
        if match:
            name = _normalize(match.group(1))
            if len(name) >= 3:
                mapped = KOREAN_PRODUCT_NAMES.get(name.replace(" ", ""), "")
                if not mapped:
                    for phrase, english in KOREAN_PRODUCT_NAMES.items():
                        if phrase in name:
                            mapped = english
                            break
                if mapped:
                    return mapped, {"product_name": mapped, "product_name_source": "korean_phrase"}
                return name, {"product_name": name, "product_name_source": "pattern"}
    if domain and domain in DOMAIN_DEFAULTS:
        default = DOMAIN_DEFAULTS[domain]["product_name"]
        return default, {"product_name": default, "product_name_source": "domain_default"}
    return "", {}


def _acronym_from_name(name: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", name)
    if not words:
        return ""
    letters = "".join(word[0] for word in words if word[0].isalnum())
    return letters.upper()[:6]


def extract_product_code(
    text: str,
    *,
    explicit: str = "",
    product_name: str = "",
    domain: str = "",
) -> tuple[str, dict[str, str]]:
    if explicit:
        return explicit.upper(), {"product_code": explicit.upper(), "product_code_source": "explicit"}
    for pattern in PRODUCT_CODE_PATTERNS:
        match = pattern.search(text)
        if match:
            code = match.group(1).upper()
            return code, {"product_code": code, "product_code_source": "pattern"}
    if domain and domain in DOMAIN_DEFAULTS:
        default = DOMAIN_DEFAULTS[domain]["product_code"]
        return default, {"product_code": default, "product_code_source": "domain_default"}
    acronym = _acronym_from_name(product_name)
    if acronym:
        return acronym, {"product_code": acronym, "product_code_source": "acronym"}
    return "", {}


def extract_author_org(text: str, *, explicit: str = "", domain: str = "") -> tuple[str, dict[str, str]]:
    if explicit:
        return explicit, {"author_org": explicit, "author_org_source": "explicit"}
    for pattern in AUTHOR_ORG_PATTERNS:
        match = pattern.search(text)
        if match:
            org = _normalize(match.group(1))
            if len(org) >= 3:
                return org, {"author_org": org, "author_org_source": "pattern"}
    return "", {"author_org": "", "author_org_source": "missing"}


def build_free_text_hints(text: str, *, product_name: str, domain: str) -> dict[str, str]:
    cleaned = _normalize(text)
    hints: dict[str, str] = {}
    if cleaned:
        hints["system_overview"] = cleaned[:500]
    if domain == "hospital_reservation":
        hints["architecture_narrative"] = (
            f"{product_name}은 환자 포털, REST API, 병원 운영 콘솔 3계층 구조이며 "
            "EMR·수납 시스템 연동을 지원한다."
        )
    elif domain == "inventory_b2b":
        hints["architecture_narrative"] = (
            f"{product_name}은 웹 포털, REST API, 운영 콘솔 3계층 구조이며 ERP·WMS 연동을 지원한다."
        )
    elif domain == "ecommerce_b2c":
        hints["architecture_narrative"] = (
            f"{product_name}은 고객 웹·모바일, API, 운영 백오피스 3계층 구조이며 "
            "PG·택배·재고 연동을 지원한다."
        )
    return hints


def detect_missing_fields(payload: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    facts = payload.get("facts") or {}
    if not facts.get("product_name") and not payload.get("product_name"):
        missing.append("product_name")
    if not facts.get("product_code") and not payload.get("product_code"):
        missing.append("product_code")
    if not payload.get("domain"):
        missing.append("domain")
    if not facts.get("author_org") and not payload.get("author_org"):
        missing.append("author_org")
    if payload.get("confirmed") is not True:
        missing.append("confirmed")
    return missing


def parse_intake_text(
    text: str,
    *,
    case_id: str = "",
    domain: str = "",
    product_name: str = "",
    product_code: str = "",
    author_org: str = "",
    confirm: bool = False,
) -> IntakeDraft:
    text = _normalize(text)
    inferred: dict[str, str] = {}

    resolved_domain, domain_meta = infer_domain(text, explicit=domain)
    inferred.update(domain_meta)

    resolved_name, name_meta = extract_product_name(text, explicit=product_name, domain=resolved_domain)
    inferred.update(name_meta)

    resolved_code, code_meta = extract_product_code(
        text,
        explicit=product_code,
        product_name=resolved_name,
        domain=resolved_domain,
    )
    inferred.update(code_meta)

    resolved_org, org_meta = extract_author_org(text, explicit=author_org, domain=resolved_domain)
    inferred.update(org_meta)

    defaults = DOMAIN_DEFAULTS.get(resolved_domain, {})
    model_name = defaults.get("model_name", f"{resolved_code or 'APP'}-001")
    today = date.today().isoformat()

    facts: dict[str, Any] = {
        "product_name": resolved_name,
        "model_name": model_name,
        "product_code": resolved_code,
        "document_version": "1.0",
        "author_org": resolved_org,
        "code_language": "TypeScript / Node.js, React",
        "platform": "AWS (ECS, RDS PostgreSQL, S3)",
        "approval_date": today.replace("-", "."),
    }

    payload: dict[str, Any] = {
        "case_id": case_id or "new_case",
        "document_set": "ec_sw",
        "domain": resolved_domain,
        "templates_in_set": ["spec_requirements", "spec_design", "report_security_verification"],
        "facts": facts,
        "standards": DOMAIN_STANDARDS.get(resolved_domain, []),
        "free_text_hints": build_free_text_hints(text, product_name=resolved_name, domain=resolved_domain),
        "source_documents": [],
        "intake_channel": "chat",
        "confirmed": confirm,
        "confirmed_at": today if confirm else None,
    }

    missing = detect_missing_fields(payload)
    return IntakeDraft(
        case_id=payload["case_id"],
        payload=payload,
        missing_fields=missing,
        inferred=inferred,
    )


def save_intake_draft(draft: IntakeDraft, out_path: Path) -> Path:
    out_path = out_path.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(draft.payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log_path = out_path.parent / "intake_log.json"
    log_path.write_text(
        json.dumps(
            {
                "case_id": draft.case_id,
                "output": str(out_path),
                "missing_fields": draft.missing_fields,
                "inferred": draft.inferred,
                "ready": draft.to_dict()["ready"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return out_path
