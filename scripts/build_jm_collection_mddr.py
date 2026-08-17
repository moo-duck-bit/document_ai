#!/usr/bin/env python3
"""Build JM COLLECTION MDDR (설계명세서) payloads and generate output_mddr.docx."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

CASE = ROOT / "data" / "cases" / "jm_collection"
LOG = CASE / "mddr_build.log"


def _log(msg: str) -> None:
    CASE.mkdir(parents=True, exist_ok=True)
    line = f"{msg}\n"
    print(line, end="", flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line)


def _req_num(req_id: str) -> int:
    m = re.search(r"(\d+)", req_id)
    return int(m.group(1)) if m else 0


def _design_text(req_id: str, description: str) -> str:
    """Generate e-commerce design narrative from requirement description."""
    n = _req_num(req_id)
    lead = description.split(".")[0].strip()

    if n == 1:
        return (
            "JM COLLECTION은 3계층 구조(JM-web / JM-api / JM-admin)로 설계한다. "
            "JM-web은 React 18 SPA로 상품·주문·마이페이지 UI를 제공하고, "
            "JM-api는 Node.js(TypeScript) 기반 REST API로 회원·상품·주문·결제·배송 도메인을 분리한다. "
            "JM-admin은 RBAC 기반 백오피스로 상품·프로모션·주문·CS를 운영한다. "
            "데이터는 PostgreSQL(거래), Redis(세션·장바구니), S3(이미지)에 저장하며 CloudFront로 정적 자산을 배포한다."
        )
    if n == 2:
        return (
            "회원가입 플로우는 약관·개인정보·마케팅 동의 체크박스를 순차 검증한다. "
            "JM-api `POST /members/signup`에서 동의 이력(terms_version, privacy_version, marketing_opt_in)을 "
            "`member_consents` 테이블에 append-only 저장한다. "
            "JM-web은 미동의 시 제출을 차단하고 수집 항목·보유 기간을 모달로 고지한다."
        )
    if n == 3:
        return (
            "인증은 Local(email/password), SMS OTP, OAuth 2.0(카카오·네이버·Google) 전략 패턴으로 구현한다. "
            "JM-api AuthService가 JWT access(15분) + refresh(7일) 토큰을 발급하고, "
            "OAuth callback은 state/nonce 검증 후 기존 계정과 provider_id를 매핑한다. "
            "실패 코드(401/403/429)별 사용자 메시지는 i18n 리소스로 분리한다."
        )
    if n == 4:
        return (
            "비밀번호 정책은 서버·클라이언트 이중 검증(최소 8자, 2종류 조합)을 적용한다. "
            "저장은 bcrypt(cost 12) 해시, `password_history`에 최근 3개 해시를 보관하여 재사용을 거부한다. "
            "재설정은 이메일/SMS OTP 검증 후 `PATCH /members/password`로 처리하며 OTP는 5분 TTL Redis에 저장한다."
        )
    if n == 5:
        return (
            "상품 카탈로그는 `categories`(3-depth), `products`, `product_skus` 스키마로 모델링한다. "
            "JM-admin에서 기획전·베스트·신상 노출 슬롯을 `merchandising_slots`로 관리하고, "
            "JM-api `GET /catalog`는 품절·판매중지 SKU를 `availability` 필드로 구분 반환한다. "
            "JM-web 목록 카드는 재고 0일 때 '품절' 배지 및 CTA 비활성화를 적용한다."
        )
    if n == 6:
        return (
            "검색은 OpenSearch(또는 PostgreSQL FTS) 인덱스에 상품명·브랜드·태그를 색인한다. "
            "`GET /search?q=&filters=`는 facet(카테고리·가격·색상·사이즈·브랜드)과 sort를 지원하며 "
            "Redis 캐시(60s)로 인기 쿼리를 가속한다. "
            "95 percentile 2초 목표는 CDN·API autoscaling·쿼리 limit으로 달성하고, "
            "0건 시 `recommended_products` API로 대안 상품을 반환한다."
        )
    if n == 7:
        return (
            "상품 상세는 JM-web PDP 컴포넌트(ProductGallery, OptionPicker, PriceBlock)로 구성한다. "
            "JM-api `GET /products/{id}`는 images[], options[], stock_by_sku, related[]를 반환하고 "
            "할인가·정가·적립 포인트는 pricing 서비스에서 계산한다. "
            "배송·교환·반품 정책은 CMS 블록으로 관리하여 SKU 카테고리별 override가 가능하다."
        )
    if n == 8:
        return (
            "장바구니는 `cart_items(member_id|session_id, sku_id, qty)`로 저장한다. "
            "비회원은 HttpOnly session cookie, 회원은 DB 영구 저장; 로그인 시 merge API로 충돌 SKU는 수량 합산한다. "
            "JM-web CartPage는 선택 결제(checkbox)와 수량 stepper를 제공하고, "
            "JM-api는 재고 선점(soft reservation, 15분 TTL)을 Redis에 기록한다."
        )
    if n == 9:
        return (
            "주문서는 CheckoutWizard(배송지→쿠폰/포인트→결제)로 설계한다. "
            "`POST /orders/draft`에서 재고·쿠폰 유효성을 검증하고, 부족 시 409와 대체 안내를 반환한다. "
            "배송지는 `addresses` 다중 저장, 쿠폰·포인트는 pricing 모듈에서 원자적 차감 후 최종 금액을 확정한다."
        )
    if n == 10:
        return (
            "결제는 PG사(토스페이먼츠/이니시스) 서버-서버 연동으로 설계한다. "
            "카드 PAN은 PG 토큰화만 허용하며 JM-api는 `payment_tokens`와 승인 transaction_id만 저장(PCI DSS). "
            "`POST /payments/confirm`은 idempotency-key로 중복 승인을 방지하고, "
            "실패·타임아웃 시 주문 상태를 PAYMENT_PENDING으로 유지한다."
        )
    if n == 11:
        return (
            "주문 완료 후 NotificationService가 이메일/SMS(마케팅 동의 시)를 비동기 발송한다. "
            "주문 상태는 `orders.status` FSM(결제완료→상품준비→배송중→배송완료)으로 관리하고 "
            "마이페이지 `GET /orders`에서 타임라인 UI로 노출한다. "
            "영수증 PDF는 S3 presigned URL로 제공한다."
        )
    if n == 12:
        return (
            "취소·반품·교환은 `return_requests` 워크플로로 모델링한다. "
            "배송 전 취소는 재고 복원 + PG void, 수령 후 7일 이내 반품은 CS 승인 후 환불 API를 호출한다. "
            "상태(접수→수거→검수→환불완료)는 JM-web·JM-admin 양쪽에서 동기화 표시한다."
        )
    if n == 13:
        return (
            "CS 모듈은 FAQ·공지(`boards`), 1:1 문의(`inquiries`)로 구성한다. "
            "JM-api는 문의 등록 시 ticket_id를 발급하고, JM-admin 답변 시 webhook으로 알림 큐에 적재한다. "
            "욕설·PII 필터는 저장 전 moderation 서비스를 통과한다."
        )
    if n == 14:
        return (
            "알림은 NotificationService + message queue(SQS)로 이메일·SMS·웹푸시 채널을 추상화한다. "
            "템플릿은 주문/배송/프로모션/쿠폰만료 유형별로 분리하고, "
            "marketing_opt_in=false 회원에게 광고성 알림 발송을 API 레벨에서 차단한다."
        )
    if n == 15:
        return (
            "위시리스트는 `wishlists(member_id, sku_id)`와 `recent_views` Redis sorted set으로 구현한다. "
            "가격 변동·재입고 알림은 sku 단위 subscription을 저장하고, "
            "배치 job이 변경 감지 시 NotificationService를 호출한다."
        )
    if n == 16:
        return (
            "프로모션 엔진은 `promotions`, `coupons`, `rules`(정액/정률/묶음/무료배송)로 설계한다. "
            "JM-admin에서 기간·회원등급·카테고리·최소주문 조건을 rule DSL로 설정하고, "
            "checkout 시 pricing 서비스가 stackable 여부를 평가한다."
        )
    if n == 17:
        return (
            "등급·포인트는 `member_tiers`, `point_ledger` 이중부기 원장으로 관리한다. "
            "구매 확정 시 등급별 1~5% 적립, 12개월 expiry; 만료 30일 전 cron 알림을 발송한다. "
            "포인트 사용은 주문 결제 트랜잭션 내 원자적 차감한다."
        )
    if n == 18:
        return (
            "리뷰는 `reviews(order_item_id, rating, body, photos[])`로 저장하고 구매 확정 후에만 작성 가능하다. "
            "신고 시 moderation queue로 이동, JM-admin 검수 후 blind 플래그를 설정한다. "
            "욕설·연락처 regex 필터를 API gateway에서 1차 적용한다."
        )

    if 100 <= n < 200:
        return (
            f"【보안 설계 — {lead}】 "
            f"{description} "
            "인증·인가 미들웨어(JWT/RBAC), AWS Secrets Manager 키 보관, "
            "TLS 1.2+ 종단 간 암호화, AES-256 저장 암호화, WAF·rate limit, "
            "append-only 감사 로그(CloudWatch/S3)로 구현한다. "
            "OWASP ASVS·PCI DSS·개인정보보호법 통제 항목과의 매핑은 요구사항명세서 추적성 매트릭스를 따른다."
        )

    return (
        f"【비기능 설계 — {lead}】 "
        f"{description} "
        "AWS ECS Fargate autoscaling, RDS Multi-AZ, ElastiCache Redis, CloudFront CDN, "
        "Route53 health check, CloudWatch 대시보드·알람으로 운영한다. "
        "성능·가용성·접근성 목표는 부하 테스트 및 Lighthouse/WCAG 점검으로 검증한다."
    )


def _build_design_items(requirements: list[dict]) -> list[dict]:
    items: list[dict] = []
    for req in requirements:
        req_id = req["req_id"]
        desc = req.get("description", "")
        design = _design_text(req_id, desc)
        items.append(
            {
                "req_id": req_id,
                "block_kind": "table",
                "design_description": design,
                "fields": {
                    "설명": design,
                    "목적": req.get("purpose", ""),
                },
            }
        )

    # Template overflow slot Req. 111 → JM Req. 15 (위시리스트)
    req15 = next((r for r in requirements if r["req_id"] == "Req. 15"), None)
    if req15:
        items.append(
            {
                "req_id": "Req. 111",
                "block_kind": "table",
                "design_description": _design_text("Req. 15", req15["description"]),
                "fields": {"설명": _design_text("Req. 15", req15["description"])},
            }
        )
    return items


def _build_design_content() -> dict:
    return {
        "source": "scripts/build_jm_collection_mddr.py",
        "template_id": "spec_design",
        "fields": {
            "paragraph_0": "Software Design Specification",
            "승인자": "2026.03.20",
            "검토자": "2026.03.20",
            "작성자": "2026.03.20",
            "0": "0",
            "0_1_2": "2026.03.20",
            "0_1_3": "박민재",
            "table1_r3_c1": "JM-web",
            "table1_r3_c2": "JM-api",
            "table1_r3_c3": "JM-admin",
            "table1_r4_c1": "1.0.0",
            "table1_r4_c2": "1.0.0",
            "table1_r4_c3": "1.0.0",
            "table1_r5_c1": "A",
            "table1_r5_c2": "A",
            "table1_r5_c3": "A",
            "paragraph_2": "PCI DSS v4.0 Payment Card Industry Data Security Standard",
            "paragraph_3": "개인정보보호법 (대한민국) / OWASP ASVS v4.0 Application Security Verification Standard",
            "paragraph_5": "Figure 1. JM COLLECTION 시스템 구성도",
            "paragraph_6": (
                "전체 시스템 개요는 그림 1과 같다. 고객은 JM-web(React SPA)에서 상품을 탐색·주문·결제하고, "
                "JM-api(Node.js)가 회원·상품·주문·결제·배송 API를 제공한다. "
                "운영자는 JM-admin에서 상품·프로모션·주문·CS를 관리한다. "
                "데이터는 PostgreSQL(OLTP), Redis(세션·장바구니), S3(이미지·정적 자산)에 저장되며 "
                "CloudFront CDN으로 전 세계 사용자에게 배포된다."
            ),
            "paragraph_8": (
                "운영 버전은 Git tag + CI/CD(GitHub Actions) 파이프라인으로 ECS에 배포하며, "
                "blue/green 또는 rolling update로 무중단 배포를 수행한다. "
                "배포 전 SAST/단위·통합 테스트·스테이징 검증을 거친다."
            ),
            "paragraph_9": "TypeScript, React 18, Node.js 20 LTS, PostgreSQL 15, Redis 7, AWS ECS/RDS/S3/CloudFront",
        },
    }


def _build_mddr_content() -> dict:
    return {
        "paragraphs": [
            "Software Design Specification",
            "PCI DSS v4.0 Payment Card Industry Data Security Standard",
            "개인정보보호법 (대한민국) / OWASP ASVS v4.0 Application Security Verification Standard",
            "EC-SW-MDDR(JM) JM COLLECTION 소프트웨어 설계명세서",
            "Ver 1.0 / 문서번호 JM-SDS-2026-001",
            (
                "JM COLLECTION은 패션·잡화 B2C 온라인 쇼핑몰 소프트웨어이다. "
                "고객용 JM-web, 주문·결제 API JM-api, 운영 백오피스 JM-admin으로 구성되며 "
                "상품 탐색·장바구니·주문·PG 결제·배송·반품·CS·프로모션 기능을 제공한다."
            ),
            (
                "React SPA + Node.js 마이크로서비스 + PostgreSQL/Redis/S3/CloudFront 아키텍처를 따른다. "
                "결제 토큰화, 개인정보·결제 데이터 암호화, RBAC, OWASP Top 10 대응을 설계에 반영한다."
            ),
            "본 문서는 JM COLLECTION 소프트웨어의 아키텍처·컴포넌트·요구사항별 설계 사항을 정의한다.",
        ],
        "overview": {
            "purpose": (
                "JM COLLECTION 온라인 쇼핑몰 소프트웨어의 내부 구조, 모듈, 인터페이스, "
                "데이터 모델 및 보안·비기능 설계를 명세하여 개발·시험·운영의 기준을 제공한다."
            ),
            "users": [
                "일반 고객(회원·비회원): JM-web을 통해 상품 탐색, 주문, 결제, 배송 조회, 반품/환불, 1:1 문의를 수행한다.",
                "운영자·CS·물류 담당자: JM-admin을 통해 상품·재고·주문·프로모션·회원·문의를 관리한다.",
                "시스템 연동: PG사, SMS/이메일 게이트웨이, 택배사 배송 추적 API와 연동한다.",
            ],
            "system": (
                "JM-web → API Gateway → JM-api(회원/카탈로그/주문/결제/알림 서비스) → PostgreSQL·Redis·S3. "
                "JM-admin은 내부 VPC에서 JM-api 관리 API를 호출한다. "
                "외부 PG·알림·배송 API는 secrets manager 키와 TLS 상호인증으로 연동한다."
            ),
        },
        "approval": {
            "date": "2026.03.20",
            "people": {
                "승인자": {"name": "김준호", "title": "대표이사"},
                "검토자": {"name": "이서연", "title": "보안책임자(CISO)"},
                "작성자": {"name": "박민재", "title": "SI팀장"},
            },
        },
        "revision": {
            "number": "0",
            "date": "2026.03.20",
            "summary": "JM COLLECTION 쇼핑몰 설계명세서 최초 제정",
            "author": "박민재",
        },
        "product_matrix": [
            ["제품명", "JM COLLECTION", "JM COLLECTION", "JM COLLECTION"],
            ["모델명", "JM-MALL-001", "JM-MALL-001", "JM-MALL-001"],
            ["소프트웨어명", "고객몰", "API 서버", "운영 백오피스"],
            ["소프트웨어명", "JM-web", "JM-api", "JM-admin"],
            ["안전성 등급", "A", "A", "A"],
            ["제조자", "JM COLLECTION Co., Ltd.", "JM COLLECTION Co., Ltd.", "JM COLLECTION Co., Ltd."],
        ],
        "component_detail_rows": [
            ["", "JM-web", "JM-api", "JM-admin"],
            ["버전", "1.0.0", "1.0.0", "1.0.0"],
            ["Code language", "TypeScript / React 18", "TypeScript / Node.js 20", "TypeScript / React 18"],
            ["Platform", "AWS CloudFront, S3", "AWS ECS, RDS PostgreSQL", "AWS ECS (VPC)"],
            ["Editor", "VS Code", "VS Code", "VS Code"],
            ["운영 환경", "AWS Cloud (ECS, RDS, Redis, S3, CloudFront)", "동일", "동일"],
        ],
        "tech_stacks": [
            {
                "header": "JM-web (고객몰)",
                "code_language": "TypeScript / React 18",
                "platform": "AWS CloudFront, S3 (정적 호스팅)",
                "editor": "VS Code",
            },
            {
                "header": "JM-api (주문·결제·회원 API)",
                "code_language": "TypeScript / Node.js 20 LTS",
                "platform": "AWS ECS Fargate, API Gateway, RDS PostgreSQL, ElastiCache Redis",
                "editor": "VS Code",
            },
            {
                "header": "JM-admin (운영 백오피스)",
                "code_language": "TypeScript / React 18",
                "platform": "AWS ECS (내부 VPC), RBAC, MFA",
                "editor": "VS Code",
            },
        ],
    }


def main() -> int:
    CASE.mkdir(parents=True, exist_ok=True)
    if LOG.exists():
        LOG.unlink()

    _log("=== JM COLLECTION MDDR Build ===")

    req_path = CASE / "requirements.json"
    if not req_path.exists():
        _log("[ERROR] requirements.json not found — run build_jm_collection_mdsr.py first")
        return 1

    requirements_data = json.loads(req_path.read_text(encoding="utf-8"))
    requirements = requirements_data.get("requirements", [])

    design_content = _build_design_content()
    mddr_content = _build_mddr_content()
    design_items = {"source": "scripts/build_jm_collection_mddr.py", "items": _build_design_items(requirements)}

    (CASE / "design_content.json").write_text(
        json.dumps(design_content, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (CASE / "mddr_content.json").write_text(
        json.dumps(mddr_content, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (CASE / "design_items.json").write_text(
        json.dumps(design_items, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _log(f"Wrote design_content.json, mddr_content.json, design_items.json ({len(design_items['items'])} items)")

    input_path = CASE / "input.json"
    input_data = json.loads(input_path.read_text(encoding="utf-8"))
    templates = input_data.setdefault("templates_in_set", [])
    if "spec_design" not in templates:
        templates.append("spec_design")
    input_data.setdefault("facts", {})["mddr_content"] = mddr_content
    input_path.write_text(json.dumps(input_data, ensure_ascii=False, indent=2), encoding="utf-8")
    _log("Updated input.json with spec_design + mddr_content")

    if "--json-only" in sys.argv:
        _log("JSON payloads written (--json-only, skipping docx generation)")
        return 0

    from document_ai.paths import SCHEMAS_EC_SW, TEMPLATES_EC_SW
    from document_ai.render.fill import fill_from_facts

    schema = json.loads((SCHEMAS_EC_SW / "spec_design.schema.json").read_text(encoding="utf-8"))
    template = TEMPLATES_EC_SW / "template_mddr.docx"
    out_path = CASE / "output_mddr.docx"

    facts = input_data.get("facts", {})
    result = fill_from_facts(
        template,
        schema,
        facts,
        out_path,
        content_payload=design_content,
        design_items_payload=design_items,
    )
    _log(f"Fill result: {json.dumps(result, ensure_ascii=False)}")
    _log(f"Output: {out_path}")
    return 0 if out_path.exists() else 1


if __name__ == "__main__":
    raise SystemExit(main())
