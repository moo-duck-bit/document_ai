# Document Quality Report — data\trials\trial-001-mindrium-xa\workdir\case

**Overall:** FAIL (52.9/100)

**Product:** Mindrium | **Domain:** medical_device_software

## Scores

| Dimension | Score | Status |
|-----------|------:|--------|
| Structure | 36.0 | FAIL |
| Terminology | 100.0 | PASS |
| Completeness | 78.4 | WARNING |
| Consistency | 0.0 | FAIL |
| Traceability | 100.0 | PASS |
| Residual Text | 0.0 | FAIL |
| Overall | 52.9 | FAIL |

## Findings

### FAIL
- [mindrium] paragraph[10]: Residual reference text (mindrium_brand) (auto-fix)
  - excerpt: `JM COLLECTION Co., Ltd.`
- [mindrium] paragraph[11]: Residual reference text (mindrium_brand) (auto-fix)
  - excerpt: `JM COLLECTION Co., Ltd.`
- [mindrium] paragraph[12]: Residual reference text (mindrium_brand) (auto-fix)
  - excerpt: `JM COLLECTION Co., Ltd.`
- [mindrium] paragraph[13]: Residual reference text (mindrium_brand) (auto-fix)
  - excerpt: `JM COLLECTION Co., Ltd.`
- [mindrium] paragraph[14]: Residual reference text (mindrium_brand) (auto-fix)
  - excerpt: `JM COLLECTION Co., Ltd.`
- [mindrium] paragraph[15]: Residual reference text (mindrium_brand) (auto-fix)
  - excerpt: `JM COLLECTION Co., Ltd.`
- [mindrium] paragraph[44]: Residual reference text (mindrium_brand) (auto-fix)
  - excerpt: `EC-SW-MDSR(JM) JM COLLECTION 소프트웨어 요구사항명세서`
- [mindrium] paragraph[46]: Residual reference text (mindrium_brand) (auto-fix)
  - excerpt: `JM COLLECTION은 패션·잡화 전문 B2C 온라인 쇼핑몰 소프트웨어이다. 고객용 웹·모바일 몰(JM-web), 주문·결제·재고 API(JM-api), 운영·CS 백오피스(J`
- [mindrium] paragraph[48]: Residual reference text (mindrium_brand) (auto-fix)
  - excerpt: `본 문서는 JM COLLECTION 소프트웨어의 기능·보안·비기능 요구사항과 PCI DSS·OWASP ASVS·개인정보보호법 추적성 매트릭스를 정의한다.`
- [mindrium] paragraph[49]: Residual reference text (mindrium_brand) (auto-fix)
  - excerpt: `JM COLLECTION은 패션·잡화 전문 B2C 온라인 쇼핑몰 소프트웨어이다. 고객용 웹·모바일 몰(JM-web), 주문·결제·재고 API(JM-api), 운영·CS 백오피스(J`
- [mindrium] paragraph[51]: Residual reference text (mindrium_brand) (auto-fix)
  - excerpt: `본 문서는 JM COLLECTION 소프트웨어의 기능·보안·비기능 요구사항과 PCI DSS·OWASP ASVS·개인정보보호법 추적성 매트릭스를 정의한다.`
- [mindrium] paragraph[52]: Residual reference text (mindrium_brand) (auto-fix)
  - excerpt: `JM COLLECTION은 패션·잡화 전문 B2C 온라인 쇼핑몰 소프트웨어이다. 고객용 웹·모바일 몰(JM-web), 주문·결제·재고 API(JM-api), 운영·CS 백오피스(J`
- [mindrium] paragraph[54]: Residual reference text (mindrium_brand) (auto-fix)
  - excerpt: `본 문서는 JM COLLECTION 소프트웨어의 기능·보안·비기능 요구사항과 PCI DSS·OWASP ASVS·개인정보보호법 추적성 매트릭스를 정의한다.`
- [mindrium] paragraph[55]: Residual reference text (mindrium_brand) (auto-fix)
  - excerpt: `JM COLLECTION은 패션·잡화 전문 B2C 온라인 쇼핑몰 소프트웨어이다. 고객용 웹·모바일 몰(JM-web), 주문·결제·재고 API(JM-api), 운영·CS 백오피스(J`
- [mindrium] paragraph[57]: Residual reference text (mindrium_brand) (auto-fix)
  - excerpt: `JM COLLECTION은 B2C 패션·잡화 온라인 쇼핑몰 소프트웨어로, 고객용 웹·모바일 몰(JM-web), 주문·결제·재고 API(JM-api), 운영 백오피스(JM-admin`
- ... and 81 more

### WARNING
- [figure_table] paragraph[65]: Figure/table placeholder (figure_placeholder) (human review)
  - excerpt: `그림 1. JM COLLECTION 소프트웨어 상호 관계도`
- [figure_table] paragraph[181]: Figure/table placeholder (table_placeholder) (human review)
  - excerpt: `PCI DSS v4.0 및 OWASP ASVS v4.0 기본 원칙과 [표3. 사이버 보안 요구사항]을 충족하여야 하며, 카드 데이터 보호·접근 통제·취약점 관리·침해 대응 요구사항`
- [duplicate_paragraph] document: Duplicate paragraph appears 6 times (human review)
  - excerpt: `jm collection은 패션·잡화 전문 b2c 온라인 쇼핑몰 소프트웨어이다. 고객용 웹·모바일 몰(jm-web), 주문·결제·재고 api(jm-api), 운영·cs 백오피스(j`
- [duplicate_paragraph] document: Duplicate paragraph appears 6 times (human review)
  - excerpt: `시스템은 react spa + node.js(typescript) 마이크로서비스 + postgresql/redis/s3/cloudfront 아키텍처를 따른다. 결제는 pg사 토큰화`
- [duplicate_paragraph] document: Duplicate paragraph appears 6 times (human review)
  - excerpt: `본 문서는 jm collection 소프트웨어의 기능·보안·비기능 요구사항과 pci dss·owasp asvs·개인정보보호법 추적성 매트릭스를 정의한다.`
- [duplicate_paragraph] document: Duplicate paragraph appears 3 times (human review)
  - excerpt: `jm-web(react spa, cloudfront/s3), jm-api(node.js 마이크로서비스, ecs/rds/redis), jm-admin(react spa, 내부 vpc`
- [duplicate_paragraph] document: Duplicate paragraph appears 2 times (human review)
  - excerpt: `jm-web 사용자는 일반 소비자(회원·비회원)이다. jm-admin 사용자는 jm collection 운영·cs·물류 담당자이며 rbac 역할(관리자·상품·주문·cs)에 따라 접`
- [duplicate_paragraph] document: Duplicate paragraph appears 2 times (human review)
  - excerpt: `규제: pci dss v4.0, 개인정보보호법, owasp asvs v4.0. 하드웨어: html5 지원 브라우저 및 https 네트워크. 운영: aws ap-northeast-2`
- [duplicate_paragraph] document: Duplicate paragraph appears 2 times (human review)
  - excerpt: `pg사·택배사·이메일/sms 게이트웨이 api 가용, aws 인프라 sla, 고객 단말 tls 1.2+ 지원, 운영자 mfa 등록 완료를 전제한다.`
- [duplicate_paragraph] document: Duplicate paragraph appears 4 times (human review)
  - excerpt: `가용성 99.9% 목표, 주문·결제 api p95 500ms 이내, 결제·개인정보 aes-256 저장, 감사 로그 1년 보존, owasp top 10 대응, rbac·세션 타임아웃`
- [figure_table] paragraph[31]: Figure/table placeholder (figure_placeholder) (human review)
  - excerpt: `전체 시스템 개요는 그림 1과 같다. 고객은 JM-web(React SPA)에서 상품을 탐색·주문·결제하고, JM-api(Node.js)가 회원·상품·주문·결제·배송 API를 제공`
- [figure_table] paragraph[52]: Figure/table placeholder (figure_placeholder) (human review)
  - excerpt: `Figure 1. JM COLLECTION 시스템 구성도`
- [figure_table] paragraph[56]: Figure/table placeholder (figure_placeholder) (human review)
  - excerpt: `Figure 2. JM-web 주요 화면`
- [figure_table] paragraph[72]: Figure/table placeholder (figure_placeholder) (human review)
  - excerpt: `Figure 3. JM-api 서버 구조`
- [figure_table] paragraph[80]: Figure/table placeholder (figure_placeholder) (human review)
  - excerpt: `Figure 4. JM-admin 운영 화면`

### PASS
- Documents analyzed: 3

## Auto-fixable Items

- [mindrium] Residual reference text (mindrium_brand) @ paragraph[10]
- [mindrium] Residual reference text (mindrium_brand) @ paragraph[11]
- [mindrium] Residual reference text (mindrium_brand) @ paragraph[12]
- [mindrium] Residual reference text (mindrium_brand) @ paragraph[13]
- [mindrium] Residual reference text (mindrium_brand) @ paragraph[14]
- [mindrium] Residual reference text (mindrium_brand) @ paragraph[15]
- [mindrium] Residual reference text (mindrium_brand) @ paragraph[44]
- [mindrium] Residual reference text (mindrium_brand) @ paragraph[46]
- [mindrium] Residual reference text (mindrium_brand) @ paragraph[48]
- [mindrium] Residual reference text (mindrium_brand) @ paragraph[49]
- [mindrium] Residual reference text (mindrium_brand) @ paragraph[51]
- [mindrium] Residual reference text (mindrium_brand) @ paragraph[52]
- [mindrium] Residual reference text (mindrium_brand) @ paragraph[54]
- [mindrium] Residual reference text (mindrium_brand) @ paragraph[55]
- [mindrium] Residual reference text (mindrium_brand) @ paragraph[57]
- [mindrium] Residual reference text (mindrium_brand) @ paragraph[58]
- [mindrium] Residual reference text (mindrium_brand) @ paragraph[60]
- [mindrium] Residual reference text (mindrium_brand) @ paragraph[62]
- [mindrium] Residual reference text (mindrium_brand) @ paragraph[63]
- [mindrium] Residual reference text (mindrium_brand) @ paragraph[64]

## Human Review Required

- [figure_table] Figure/table placeholder (figure_placeholder) @ paragraph[65]
- [figure_table] Figure/table placeholder (table_placeholder) @ paragraph[181]
- [duplicate_paragraph] Duplicate paragraph appears 6 times @ document
- [duplicate_paragraph] Duplicate paragraph appears 6 times @ document
- [duplicate_paragraph] Duplicate paragraph appears 6 times @ document
- [duplicate_paragraph] Duplicate paragraph appears 3 times @ document
- [duplicate_paragraph] Duplicate paragraph appears 2 times @ document
- [duplicate_paragraph] Duplicate paragraph appears 2 times @ document
- [duplicate_paragraph] Duplicate paragraph appears 2 times @ document
- [duplicate_paragraph] Duplicate paragraph appears 4 times @ document
- [figure_table] Figure/table placeholder (figure_placeholder) @ paragraph[31]
- [figure_table] Figure/table placeholder (figure_placeholder) @ paragraph[52]
- [figure_table] Figure/table placeholder (figure_placeholder) @ paragraph[56]
- [figure_table] Figure/table placeholder (figure_placeholder) @ paragraph[72]
- [figure_table] Figure/table placeholder (figure_placeholder) @ paragraph[80]

## Human Review Checklist
- [ ] 표지·승인자 이름/직함/날짜
- [ ] 도메인 용어·비즈니스 시나리오 정확성
- [ ] Req. 설명·목적·기준 문장 품질
- [ ] 추적성 매트릭스 연결 정확성
- [ ] MDDR Figure/Table 캡션
