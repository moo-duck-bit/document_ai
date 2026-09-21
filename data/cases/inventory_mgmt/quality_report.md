# Document Quality Report — data\cases\inventory_mgmt

**Overall:** PASS (96.8/100)

**Product:** Inventory Management System | **Domain:** inventory_b2b

## Scores

| Dimension | Score | Status |
|-----------|------:|--------|
| Structure | 100.0 | PASS |
| Terminology | 100.0 | PASS |
| Completeness | 100.0 | PASS |
| Consistency | 100.0 | PASS |
| Traceability | 100.0 | PASS |
| Residual Text | 84.0 | WARNING |
| Overall | 96.8 | PASS |

## Findings

### FAIL
- [placeholder] paragraph[41]: Placeholder detected (placeholder_xxxx) (auto-fix)
  - excerpt: `소프트웨어 개발 계획서 (XX-XX-XXXX)`
- [placeholder] paragraph[42]: Placeholder detected (placeholder_xxxx) (auto-fix)
  - excerpt: `소프트웨어 요구사항명세서 (XX-XX-XXXX)`

### WARNING
- [figure_table] paragraph[65]: Figure/table placeholder (figure_placeholder) (human review)
  - excerpt: `그림 1. Inventory Management System 소프트웨어 상호 관계도`
- [figure_table] paragraph[181]: Figure/table placeholder (table_placeholder) (human review)
  - excerpt: `ISO 27001 v4.0 및 OWASP ASVS v4.0 기본 원칙과 [표3. 사이버 보안 요구사항]을 충족하여야 하며, 민감 데이터 보호·접근 통제·취약점 관리·침해 대응 요구`
- [figure_table] paragraph[31]: Figure/table placeholder (figure_placeholder) (human review)
  - excerpt: `전체 시스템 개요는 그림 1과 같다. 고객은 IMS-web(React SPA)에서 품목을 탐색·입출고·ERP정산하고, IMS-api(Node.js)가 회원·품목·입출고·ERP정산·`
- [figure_table] paragraph[52]: Figure/table placeholder (figure_placeholder) (human review)
  - excerpt: `Figure 1. Inventory Management System 시스템 구성도`
- [figure_table] paragraph[56]: Figure/table placeholder (figure_placeholder) (human review)
  - excerpt: `Figure 2. IMS-web 주요 화면`
- [figure_table] paragraph[72]: Figure/table placeholder (figure_placeholder) (human review)
  - excerpt: `Figure 3. IMS-api 서버 구조`
- [figure_table] paragraph[80]: Figure/table placeholder (figure_placeholder) (human review)
  - excerpt: `Figure 4. IMS-admin 운영 화면`

### PASS
- Documents analyzed: 3

## Auto-fixable Items

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
