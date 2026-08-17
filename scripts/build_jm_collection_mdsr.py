#!/usr/bin/env python3
"""Build JM COLLECTION case payloads and generate MDSR from blank template."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from document_ai.learn.extract_requirements import save_case_requirements
from document_ai.paths import SCHEMAS_EC_SW, TEMPLATES_EC_SW
from document_ai.render.fill import fill_from_facts
from document_ai.render.mdsr import SECURITY_REQ_TITLES

CASE = ROOT / "data" / "cases" / "jm_collection"
LOG = CASE / "build.log"


def _log(msg: str) -> None:
    CASE.mkdir(parents=True, exist_ok=True)
    line = f"{msg}\n"
    print(line, end="", flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line)


def _req(
    req_id: str,
    description: str,
    purpose: str | None = None,
    criteria: str | None = None,
) -> dict:
    item: dict = {"req_id": req_id, "description": description}
    if purpose:
        item["purpose"] = purpose
    if criteria:
        item["criteria"] = criteria
    return item


def _req_num(req_id: str) -> int:
    m = re.search(r"(\d+)", req_id)
    return int(m.group(1)) if m else 0


def _default_purpose(req_id: str, description: str) -> str:
    n = _req_num(req_id)
    if req_id in FUNCTIONAL_PURPOSES:
        return FUNCTIONAL_PURPOSES[req_id]
    if n < 100:
        return "해당 기능을 안정적으로 제공하여 JM COLLECTION 고객의 구매 경험을 제고하기 위함이다."
    if n < 200:
        return "개인정보·결제·운영 데이터를 보호하고 법규 및 보안 표준을 준수하기 위함이다."
    return "쇼핑몰 서비스의 성능·가용성·접근성을 확보하기 위함이다."


def _default_criteria(req_id: str, description: str) -> str:
    if req_id in FUNCTIONAL_CRITERIA:
        return FUNCTIONAL_CRITERIA[req_id]
    n = _req_num(req_id)
    if n < 100:
        return "해당 기능이 명세된 동작·예외·UI 플로우를 통합 테스트 및 UAT에서 검증 가능해야 한다."
    return ""


FUNCTIONAL_PURPOSES: dict[str, str] = {
    "Req. 1": "B2C 전자상거래 핵심 거래 기능을 제공하여 고객의 온라인 구매 경험을 보장하기 위함이다.",
    "Req. 2": "회원 가입 시 법적 고지·동의 절차를 준수하고 개인정보 처리 투명성을 확보하기 위함이다.",
    "Req. 3": "안전한 로그인·소셜 연동으로 계정 접근성과 보안을 동시에 제공하기 위함이다.",
    "Req. 4": "계정 도용을 방지하고 비밀번호 정책을 일관 적용하기 위함이다.",
    "Req. 5": "상품 탐색·노출을 체계화하여 구매 전환율을 높이기 위함이다.",
    "Req. 6": "빠르고 정확한 검색·필터로 원하는 상품 발견을 돕기 위함이다.",
    "Req. 7": "상품 정보를 충분히 제공하여 구매 결정을 지원하기 위함이다.",
    "Req. 8": "장바구니·선택 결제로 구매 전환을 유도하기 위함이다.",
    "Req. 9": "주문·할인·배송 정보를 정확히 확정하기 위함이다.",
    "Req. 10": "PG 연동 결제와 PCI DSS 준수를 통해 안전한 결제를 제공하기 위함이다.",
    "Req. 11": "주문·배송 상태를 투명히 안내하여 고객 신뢰를 확보하기 위함이다.",
    "Req. 12": "취소·반품·환불 절차를 표준화하기 위함이다.",
    "Req. 13": "고객 문의·FAQ로 CS 채널을 제공하기 위함이다.",
    "Req. 14": "주문·프로모션 알림으로 고객 커뮤니케이션을 자동화하기 위함이다.",
    "Req. 15": "위시리스트·최근 본 상품으로 재구매·관심 유지를 돕기 위함이다.",
    "Req. 16": "프로모션·쿠폰으로 마케팅·매출을 운영하기 위함이다.",
    "Req. 17": "등급·포인트로 고객 충성도를 제고하기 위함이다.",
    "Req. 18": "리뷰·평점으로 구매 후기와 신뢰를 축적하기 위함이다.",
}

FUNCTIONAL_CRITERIA: dict[str, str] = {
    "Req. 1": "회원/비회원 상품탐색·주문·결제·배송조회·반품 E2E 시나리오 통과",
    "Req. 2": "약관·개인정보·마케팅 동의 UI 및 동의 이력 저장·조회 검증",
    "Req. 3": "이메일/SMS/OAuth 로그인 성공·실패 케이스 및 세션 발급 검증",
    "Req. 4": "비밀번호 정책·재설정 OTP·재사용 금지(3회) 검증",
    "Req. 5": "카테고리·기획전 노출 및 품절 상품 구매 차단 검증",
    "Req. 6": "검색·필터·정렬 2초 이내(95p) 및 0건 대안 제안 검증",
    "Req. 7": "PDP 이미지·옵션·재고·가격·포인트 표시 검증",
    "Req. 8": "장바구니 CRUD·회원 병합·선택 결제 검증",
    "Req. 9": "주문서 배송지·쿠폰/포인트·재고 차단 검증",
    "Req. 10": "PG 토큰 결제·PAN 미저장·PCI 통제 검증",
    "Req. 11": "주문 알림·마이페이지 상태 FSM 검증",
    "Req. 12": "취소·반품 7일·환불 상태 추적 검증",
    "Req. 13": "FAQ·1:1 문의·답변 알림 검증",
    "Req. 14": "주문/프로모션 알림 및 마케팅 수신 거부 준수 검증",
    "Req. 15": "위시리스트·최근 본 상품·재입고 알림 검증",
    "Req. 16": "쿠폰/할인 규칙·조건부 적용 검증",
    "Req. 17": "등급별 적립·포인트 만료 알림 검증",
    "Req. 18": "구매 확정 후 리뷰·신고·블라인드 검증",
}


SECURITY_CRITERIA: dict[str, str] = {
    "Req. 100": "개인정보보호법 제17조~36조, OWASP ASVS V8",
    "Req. 101": "OWASP ASVS V4.1 Access Control",
    "Req. 102": "OWASP ASVS V3 Session Management",
    "Req. 103": "OWASP ASVS V7.1 Audit Logging",
    "Req. 104": "PCI DSS Req 3·4, OWASP ASVS V6 Cryptography",
    "Req. 105": "OWASP ASVS V2.2 Brute-force / Rate Limiting",
    "Req. 106": "OWASP Top 10 2021, ASVS V5 Validation",
    "Req. 107": "OWASP ASVS V11.1 Backup, RPO/RTO 내부 SLA",
    "Req. 108": "PCI DSS Req 8.3, OWASP ASVS V13 API Security",
    "Req. 109": "OWASP ASVS V14 Security Testing",
    "Req. 110": "OWASP ASVS V1.2 Admin Access Control",
}


REQUIREMENTS = [
    _req(
        "Req. 1",
        "JM COLLECTION 온라인 쇼핑몰은 B2C 전자상거래 플랫폼으로, 회원·비회원 사용자에게 상품 탐색, 주문, 결제, 배송 조회, 반품/환불 기능을 제공해야 한다. "
        "본 시스템은 웹(반응형)과 모바일 웹을 주요 채널로 하며, 관리자 백오피스를 통해 상품·주문·회원·프로모션을 운영한다.",
    ),
    _req(
        "Req. 2",
        "회원가입 시 이용약관, 개인정보 처리방침, 마케팅 수신 동의(선택)를 명시적으로 확인받아야 한다. "
        "수집 항목(이름, 이메일, 휴대전화, 배송지)과 보유 기간을 고지하고, 동의 이력을 저장·조회할 수 있어야 한다.",
    ),
    _req(
        "Req. 3",
        "사용자는 이메일 또는 휴대전화 인증을 통해 로그인할 수 있어야 한다. "
        "소셜 로그인(카카오, 네이버, Google) OAuth 2.0 연동을 지원하며, 실패 시 구체적 오류 메시지를 표시해야 한다.",
    ),
    _req(
        "Req. 4",
        "비밀번호는 최소 8자, 영문·숫자·특수문자 중 2종류 이상 조합을 요구해야 한다. "
        "비밀번호 재설정은 본인 인증(이메일/SMS OTP) 후에만 가능하며, 최근 3개 비밀번호 재사용을 금지해야 한다.",
    ),
    _req(
        "Req. 5",
        "상품은 카테고리(대·중·소)별로 탐색 가능해야 하며, 메인·기획전·신상·베스트 영역에 노출할 수 있어야 한다. "
        "품절·판매중지 상품은 목록에서 구분 표시하고 구매 불가 상태로 처리해야 한다.",
    ),
    _req(
        "Req. 6",
        "키워드 검색, 카테고리·가격·색상·사이즈·브랜드 필터 및 정렬(인기, 신상, 가격순)을 지원해야 한다. "
        "검색 결과는 2초 이내(95 percentile) 응답을 목표로 하며, 결과 없음 시 대안 상품을 제안할 수 있어야 한다.",
    ),
    _req(
        "Req. 7",
        "상품 상세 페이지는 다중 이미지, 옵션(색상/사이즈), 재고 수량, 배송·교환·반품 안내, 관련 상품을 표시해야 한다. "
        "할인가·정가·적립 예정 포인트를 명확히 구분하여 표시해야 한다.",
    ),
    _req(
        "Req. 8",
        "장바구니에 옵션별 상품을 담고, 수량 변경·삭제·선택 결제를 지원해야 한다. "
        "비회원 장바구니는 세션 기반, 회원은 계정에 영구 저장하며 로그인 시 병합할 수 있어야 한다.",
    ),
    _req(
        "Req. 9",
        "주문서 작성 시 배송지 입력(다중 배송지 저장), 배송 메시지, 쿠폰/포인트 적용, 최종 결제 금액 확인을 제공해야 한다. "
        "재고 부족 시 결제 전 차단하고 사용자에게 안내해야 한다.",
    ),
    _req(
        "Req. 10",
        "결제는 PG사(토스페이먼츠/이니시스 등) 연동을 통해 신용카드, 계좌이체, 간편결제를 지원해야 한다. "
        "카드 정보는 PG사 토큰화 처리하며, 쇼핑몰 서버에 PAN을 저장하지 않아야 한다(PCI DSS 준수).",
    ),
    _req(
        "Req. 11",
        "주문 완료 후 주문번호, 결제 영수증, 예상 배송일을 이메일·SMS(동의 시)로 발송해야 한다. "
        "마이페이지에서 주문·배송 상태(결제완료→상품준비→배송중→배송완료)를 조회할 수 있어야 한다.",
    ),
    _req(
        "Req. 12",
        "주문 취소는 배송 시작 전까지 가능해야 하며, 반품·교환은 수령 후 7일 이내 신청을 허용해야 한다. "
        "환불은 PG사 정책 및 내부 승인 워크플로에 따라 처리하고, 처리 상태를 사용자에게 표시해야 한다.",
    ),
    _req(
        "Req. 13",
        "1:1 문의, FAQ, 공지사항 게시판을 제공해야 한다. "
        "문의 답변 시 사용자 알림(이메일/앱 푸시)을 발송할 수 있어야 한다.",
    ),
    _req(
        "Req. 14",
        "주문·배송·프로모션·쿠폰 만료 알림을 이메일, SMS, 웹 푸시(선택)로 발송할 수 있어야 한다. "
        "마케팅 수신 거부 사용자에게는 광고성 알림을 발송하지 않아야 한다.",
    ),
    _req(
        "Req. 15",
        "회원은 관심 상품(위시리스트)을 저장하고, 최근 본 상품 목록을 조회할 수 있어야 한다. "
        "위시리스트 상품의 가격 변동·재입고 시 알림 설정을 지원할 수 있어야 한다.",
    ),
    _req(
        "Req. 16",
        "관리자는 쿠폰(정액/정률), 기간 한정 할인, 묶음 할인, 무료배송 프로모션을 생성·적용할 수 있어야 한다. "
        "쿠폰은 회원 등급·카테고리·최소 주문 금액 조건을 설정할 수 있어야 한다.",
    ),
    _req(
        "Req. 17",
        "회원 등급(일반·실버·골드·VIP)과 구매 적립 포인트(결제 금액의 1~5%)를 운영할 수 있어야 한다. "
        "포인트는 유효기간(12개월)을 두며, 만료 30일 전 알림을 발송할 수 있어야 한다.",
    ),
    _req(
        "Req. 18",
        "구매 확정 후 상품 리뷰(별점, 텍스트, 사진) 작성을 허용해야 한다. "
        "욕설·개인정보 포함 리뷰는 신고·관리자 검수 후 블라인드 처리할 수 있어야 한다.",
    ),
    _req(
        "Req. 100",
        "개인정보는 수집 목적에 필요한 최소 항목만 수집하고, 목적 달성 후 지체 없이 파기해야 한다. "
        "마이페이지에서 개인정보 열람·수정·삭제(회원 탈퇴)를 지원해야 한다.",
    ),
    _req(
        "Req. 101",
        "관리자 기능은 RBAC(최고관리자, 운영, CS, 물류) 기반 권한으로 분리해야 한다. "
        "권한 없는 메뉴 접근 시 거부하고, 시도 이력을 로그에 기록해야 한다.",
    ),
    _req(
        "Req. 102",
        "로그인 세션은 JWT 또는 secure cookie 기반으로 관리하고, HttpOnly·Secure·SameSite 속성을 적용해야 한다. "
        "동시 세션 수 제한(기본 3대) 및 원격 로그아웃 기능을 제공할 수 있어야 한다.",
    ),
    _req(
        "Req. 103",
        "주문·결제·로그인·관리자 작업에 대한 감사 로그를 1년 이상 보관해야 한다. "
        "로그는 변조 방지를 위해 append-only 저장소 또는 WORM 정책을 적용해야 한다.",
    ),
    _req(
        "Req. 104",
        "결제 및 개인정보 처리 구간은 TLS 1.2 이상으로 암호화하고, 저장 데이터는 AES-256 등 강력한 알고리즘으로 암호화해야 한다.",
    ),
    _req(
        "Req. 105",
        "로그인·API 엔드포인트에 rate limiting을 적용하여 brute force 및 DDoS를 완화해야 한다. "
        "연속 로그인 실패 5회 시 15분 계정 잠금을 적용해야 한다.",
    ),
    _req(
        "Req. 106",
        "OWASP Top 10(XSS, CSRF, SQL Injection) 대응을 위해 입력 검증, 출력 인코딩, parameterized query, CSRF 토큰을 적용해야 한다.",
    ),
    _req(
        "Req. 107",
        "일일 전체 DB 백업 및 트랜잭션 로그 백업을 수행하고, RPO 24시간, RTO 4시간 이내 복구를 목표로 한다.",
    ),
    _req(
        "Req. 108",
        "PG, SMS, 배송 추적 등 외부 API 연동 시 API Key는 secrets manager에 저장하고, IP 화이트리스트·키 로테이션 정책을 적용해야 한다.",
    ),
    _req(
        "Req. 109",
        "분기 1회 이상 취약점 스캔(SAST/DAST) 및 의존성(CVE) 점검을 수행하고, Critical/High 취약점은 30일 이내 조치해야 한다.",
    ),
    _req(
        "Req. 110",
        "관리자·CS 페이지 접근은 사내 VPN 또는 IP 제한 및 2FA(MFA)를 권장/적용해야 한다.",
    ),
    _req(
        "Req. 200",
        "메인 페이지 및 상품 목록은 3G 환경 기준 LCP 3초 이내를 목표로 하며, CDN을 통해 정적 자산을 제공해야 한다.",
    ),
    _req(
        "Req. 201",
        "서비스 가용성은 월 99.9% 이상을 목표로 하며, 장애 시 상태 페이지 또는 공지를 통해 사용자에게 안내해야 한다.",
    ),
    _req(
        "Req. 202",
        "UI는 모바일(320px~)·태블릿·데스크톱에 반응형으로 동작해야 하며, 터치·키보드 접근성(WCAG 2.1 AA)을 준수해야 한다.",
    ),
    _req(
        "Req. 203",
        "최신 2버전 Chrome, Safari, Edge, Firefox 및 iOS/Android 기본 브라우저를 지원해야 한다.",
    ),
    _req(
        "Req. 204",
        "관리자 대시보드에서 일·주·월 매출, 주문 건수, 인기 상품, 재고 부족 알림을 조회할 수 있어야 한다.",
    ),
    _req(
        "Req. 205",
        "모든 사용자·관리자 통신은 HTTPS(TLS 1.2+)를 강제하고, HSTS 헤더를 적용해야 한다.",
    ),
    _req(
        "Req. 206",
        "사용자 세션은 30분 비활성 시 자동 만료되며, 만료 5분 전 연장 안내를 표시할 수 있어야 한다.",
    ),
    _req(
        "Req. 207",
        "휴면 계정(1년 미접속)은 별도 분리 보관하고, 재접속 시 본인 인증 후 복구해야 한다. "
        "탈퇴 회원 개인정보는 30일 이내 파기(법령 보존 예외 제외)해야 한다.",
    ),
]

TRACEABILITY = [
    {"requirement": "IA-01", "linked_reqs": "Req. 2, Req. 3, Req. 102, Req. 201"},
    {"requirement": "IA-02", "linked_reqs": "Req. 2, Req. 3, Req. 102, Req. 202"},
    {"requirement": "IA-03", "linked_reqs": "Req. 2, Req. 100, Req. 102, Req. 207"},
    {"requirement": "IA-04", "linked_reqs": "Req. 3, Req. 4, Req. 102, Req. 105, Req. 205"},
    {"requirement": "IA-05", "linked_reqs": "Req. 4, Req. 102, Req. 202"},
    {"requirement": "IA-06", "linked_reqs": "Req. 4, Req. 102, Req. 201"},
    {"requirement": "IA-07", "linked_reqs": "Req. 4, Req. 105, Req. 201"},
    {"requirement": "IA-08", "linked_reqs": "Req. 2, Req. 14, Req. 201"},
    {"requirement": "UC-01", "linked_reqs": "Req. 101, Req. 110, Req. 204"},
    {"requirement": "UC-02", "linked_reqs": "N/A", "applicability": "비해당 (웹 SPA, 모바일 네이티브 코드 미사용)"},
    {"requirement": "UC-03", "linked_reqs": "Req. 102, Req. 206"},
    {"requirement": "UC-04", "linked_reqs": "Req. 100, Req. 103, Req. 110"},
    {"requirement": "UC-05", "linked_reqs": "Req. 103, Req. 107"},
    {"requirement": "UC-06", "linked_reqs": "Req. 103"},
    {"requirement": "UC-07", "linked_reqs": "Req. 103, Req. 110"},
    {"requirement": "SI-01", "linked_reqs": "Req. 104, Req. 205"},
    {"requirement": "SI-02", "linked_reqs": "Req. 106, Req. 109"},
    {"requirement": "SI-03", "linked_reqs": "Req. 106, Req. 109, Req. 205"},
    {"requirement": "SI-04", "linked_reqs": "Req. 1"},
    {"requirement": "SI-05", "linked_reqs": "Req. 2, Req. 14, Req. 100, Req. 207"},
    {"requirement": "SI-06", "linked_reqs": "Req. 6, Req. 7, Req. 106"},
    {"requirement": "SI-07", "linked_reqs": "Req. 8, Req. 9, Req. 106"},
    {"requirement": "SI-08", "linked_reqs": "Req. 1"},
    {"requirement": "SI-09", "linked_reqs": "Req. 1"},
    {"requirement": "SI-10", "linked_reqs": "N/A", "applicability": "비해당"},
    {"requirement": "SI-11", "linked_reqs": "N/A", "applicability": "비해당"},
    {"requirement": "DC-01", "linked_reqs": "Req. 10, Req. 11, Req. 12, Req. 104, Req. 108"},
    {"requirement": "DC-02", "linked_reqs": "Req. 2, Req. 3"},
    {"requirement": "DC-03", "linked_reqs": "Req. 100, Req. 102, Req. 104, Req. 205"},
    {"requirement": "RA-01", "linked_reqs": "Req. 105"},
    {"requirement": "RA-02", "linked_reqs": "Req. 107"},
    {"requirement": "RA-03", "linked_reqs": "Req. 107"},
    {"requirement": "RA-04", "linked_reqs": "Req. 104, Req. 205"},
    {"requirement": "RA-05", "linked_reqs": "Req. 104, Req. 205"},
]

for _item in REQUIREMENTS:
    _item.setdefault("purpose", _default_purpose(_item["req_id"], _item["description"]))
    _rid = _item["req_id"]
    if _rid in SECURITY_CRITERIA:
        _item.setdefault("criteria", SECURITY_CRITERIA[_rid])
    elif _req_num(_rid) < 100:
        _item.setdefault("criteria", _default_criteria(_rid, _item["description"]))

for _row in TRACEABILITY:
    _row["title"] = SECURITY_REQ_TITLES.get(_row["requirement"], "")
    _row["applicability"] = "해당" if _row.get("linked_reqs") not in ("", "N/A") else "비해당"

INPUT = {
    "case_id": "jm_collection",
    "document_set": "ec_sw",
    "product_name": "JM COLLECTION",
    "product_code": "JM",
    "domain": "ecommerce_b2c",
    "standards": [
        "PCI DSS v4.0 Payment Card Industry Data Security Standard",
        "개인정보보호법 (대한민국)",
        "OWASP ASVS v4.0 Application Security Verification Standard",
    ],
    "templates_in_set": ["spec_requirements"],
    "facts": {
        "product_name": "JM COLLECTION",
        "model_name": "JM COLLECTION Mall",
        "software_name": "JM COLLECTION",
        "product_code": "JM",
        "document_version": "1.0",
        "author_org": "JM COLLECTION Co., Ltd.",
        "code_language": "TypeScript / Node.js, React",
        "platform": "AWS (ECS, RDS PostgreSQL, S3, CloudFront)",
        "editor": "VS Code",
        "approval_date": "2026.03.20",
    },
    "free_text_hints": {
        "system_overview": (
            "JM COLLECTION은 패션·잡화 B2C 온라인 쇼핑몰이다. "
            "고객은 웹/모바일에서 상품을 탐색·주문·결제하고, 관리자는 백오피스에서 상품·재고·주문·프로모션을 운영한다. "
            "아키텍처: React SPA → API Gateway → Node.js 마이크로서비스 → PostgreSQL / Redis / S3."
        ),
        "architecture_narrative": (
            "결제는 PG사 토큰화 연동, 개인정보·결제 데이터는 암호화 저장, "
            "전 구간 HTTPS 및 OWASP 보안 가이드라인을 준수한다."
        ),
    },
    "source_documents": [],
    "intake_channel": "manual_authoring",
    "confirmed": True,
    "confirmed_at": "2026-06-30",
}


def main() -> int:
    CASE.mkdir(parents=True, exist_ok=True)
    if LOG.exists():
        LOG.unlink()
    _log("JM COLLECTION MDSR build started")
    _log("Writing input.json")
    (CASE / "input.json").write_text(json.dumps(INPUT, ensure_ascii=False, indent=2), encoding="utf-8")

    req_payload = {
        "source": "scripts/build_jm_collection_mdsr.py",
        "requirements": REQUIREMENTS,
        "traceability": TRACEABILITY,
    }
    _log("Writing requirements.json")
    save_case_requirements(req_payload, CASE / "requirements.json")

    template = TEMPLATES_EC_SW / "template_mdsr.docx"
    if not template.exists():
        _log(f"ERROR: missing template {template}")
        return 1
    _log(f"Template OK: {template}")

    schema_path = SCHEMAS_EC_SW / "spec_requirements.schema.json"
    _log(f"Loading schema {schema_path}")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    facts = dict(INPUT["facts"])
    facts["standards"] = INPUT["standards"]
    facts["free_text_hints"] = INPUT["free_text_hints"]
    mdsr_content_path = CASE / "mdsr_content.json"
    if mdsr_content_path.exists():
        facts["mdsr_content"] = json.loads(mdsr_content_path.read_text(encoding="utf-8"))
        _log("Loaded mdsr_content.json")

    out = CASE / "output_mdsr.docx"
    tmp_out = Path(__import__("tempfile").gettempdir()) / "jm_collection" / "output_mdsr.docx"
    tmp_out.parent.mkdir(parents=True, exist_ok=True)
    _log(f"Filling document -> {tmp_out}")
    result = fill_from_facts(
        template,
        schema,
        facts,
        tmp_out,
        requirements_payload=req_payload,
        overwrite_requirements=True,
    )
    _log("fill_from_facts complete")
    if tmp_out.exists():
        import shutil

        shutil.copy2(tmp_out, out)
        result["output"] = str(out)
        result["temp_output"] = str(tmp_out)
        _log(f"Copied to {out} ({out.stat().st_size} bytes)")
    else:
        _log("ERROR: temp output not created")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    review = result.get("requirements", {}).get("review_pass_5") or result.get(
        "requirements", {}
    ).get("review_pass_1")
    if review:
        _log(
            f"Review: issues={review.get('issue_count')} "
            f"residual={review.get('residual_count')} "
            f"passes={result.get('requirements', {}).get('review_passes_completed', '?')}"
        )
        if review.get("issues"):
            for issue in review["issues"][:10]:
                _log(f"  ISSUE: {issue}")
        gap_path = CASE / "gap_analysis.txt"
        gap_lines = [
            "JM COLLECTION MDSR verify_completeness (post-build)",
            f"issues={review.get('issue_count')} residual={review.get('residual_count')}",
            "",
            "Issues:",
            *[f"  {x}" for x in review.get("issues", [])],
            "",
            "Residual:",
            *[f"  {x}" for x in review.get("residual", [])],
        ]
        gap_path.write_text("\n".join(gap_lines), encoding="utf-8")
        _log(f"Wrote {gap_path}")
    _log("Done")
    print(f"\nGenerated: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
