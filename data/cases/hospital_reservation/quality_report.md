# Document Quality Report — data\cases\hospital_reservation

**Overall:** PASS (95.3/100)

**Product:** Hospital Reservation System | **Domain:** hospital_reservation

## Scores

| Dimension | Score | Status |
|-----------|------:|--------|
| Structure | 100.0 | PASS |
| Terminology | 90.0 | PASS |
| Completeness | 100.0 | PASS |
| Consistency | 100.0 | PASS |
| Traceability | 100.0 | PASS |
| Residual Text | 84.0 | WARNING |
| Overall | 95.3 | PASS |

## Findings

### FAIL
- [placeholder] paragraph[41]: Placeholder detected (placeholder_xxxx) (auto-fix)
  - excerpt: `소프트웨어 개발 계획서 (XX-XX-XXXX)`
- [placeholder] paragraph[42]: Placeholder detected (placeholder_xxxx) (auto-fix)
  - excerpt: `소프트웨어 요구사항명세서 (XX-XX-XXXX)`

### WARNING
- [figure_table] paragraph[65]: Figure/table placeholder (figure_placeholder) (human review)
  - excerpt: `그림 1. Hospital Reservation System 소프트웨어 상호 관계도`
- [figure_table] paragraph[181]: Figure/table placeholder (table_placeholder) (human review)
  - excerpt: `개인정보보호법 v4.0 및 OWASP ASVS v4.0 기본 원칙과 [표3. 사이버 보안 요구사항]을 충족하여야 하며, 민감 의료·수납 데이터 보호·접근 통제·취약점 관리·침해 대`
- [domain_mismatch] table[12] r2c1: Domain mismatch — foreign term (shopping_flow) (auto-fix)
  - excerpt: `빠른 검색·자동완성·오타 허용으로 진료과 발견률과 구매 전환을 높이기 위함이다.`
- [domain_mismatch] table[14] r2c1: Domain mismatch — foreign term (shopping_flow) (auto-fix)
  - excerpt: `예약 신청·선택 수납로 구매 전환을 유도하기 위함이다.`
- [figure_table] paragraph[31]: Figure/table placeholder (figure_placeholder) (human review)
  - excerpt: `전체 시스템 개요는 그림 1과 같다. 고객은 HRS-web(React SPA)에서 진료과을 탐색·예약·수납하고, HRS-api(Node.js)가 회원·진료과·예약·수납·진료일정 A`
- [figure_table] paragraph[52]: Figure/table placeholder (figure_placeholder) (human review)
  - excerpt: `Figure 1. Hospital Reservation System 시스템 구성도`
- [figure_table] paragraph[56]: Figure/table placeholder (figure_placeholder) (human review)
  - excerpt: `Figure 2. HRS-web 주요 화면`
- [figure_table] paragraph[72]: Figure/table placeholder (figure_placeholder) (human review)
  - excerpt: `Figure 3. HRS-api 서버 구조`
- [figure_table] paragraph[80]: Figure/table placeholder (figure_placeholder) (human review)
  - excerpt: `Figure 4. HRS-admin 운영 화면`

### PASS
- Documents analyzed: 2

## Auto-fixable Items

- [domain_mismatch] Domain mismatch — foreign term (shopping_flow) @ table[12] r2c1
- [domain_mismatch] Domain mismatch — foreign term (shopping_flow) @ table[14] r2c1
- [placeholder] Placeholder detected (placeholder_xxxx) @ paragraph[41]
- [placeholder] Placeholder detected (placeholder_xxxx) @ paragraph[42]

## Human Review Required

- [figure_table] Figure/table placeholder (figure_placeholder) @ paragraph[65]
- [figure_table] Figure/table placeholder (table_placeholder) @ paragraph[181]
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
