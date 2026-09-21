# VERSIONS — trial-001-mindrium-xa 기준 문서 동결

- 동결 시각(UTC): `2026-07-17T22:11:04Z`
- trial_id: `trial-001-mindrium-xa`
- case: `data/cases/mindrium_xa`
- system_version: `v0.5-document-harness`
- system_commit: `d73fc18`
- 제품: `Mindrium` / `XA`
- 문서 버전 (input.json): `1.0`
- 승인일 (input.json): `2025.02.07`

## 기준 문서 (data/examples/ec_sw에서 복사 · 원본 미수정)

| 종류 | 파일 | sha256 | 바이트 |
|------|------|--------|-------|
| MDSR | `spec_mdsr_EC-SW-MDSR(XA)_소프트웨어_요구사항명세서.docx` | `cd70f942ab8534c22887782b61d2319fd026e61f97744bde8f985c6484a3652d` | 1968688 |
| MDDR | `spec_mddr_EC-SW-MDDR(XA) 소프트웨어 설계 명세서.docx` | `dff76e279aeeef1f2f13dda70770edfedfdfa6908407924812d7c9bcf9ebe0bf` | 2630162 |
| XXCS | `report_xxcs_EC-SW-XXCS(XA) 소프트웨어 보안 검증 보고서.docx` | `c2b2a7621a8a8205a73f5401fc3fb538be4ea28197330ab244af68d54bff4b63` | 25255815 |

## 변경 시나리오 메모

- 변경 입력: 준비된 Req. 6 CR (`request_req6.txt`)
- 변경 성격: MDSR 표의 빈 Req. 6 description에 대한 **update/fill** (기존 as-is 수치 정책 수정 아님)
- 원본 본문 Req. 6 제목은 인증 에러 안내이며, 표 description은 비어 있었음
- 본 Trial에서 XXCS는 기본적으로 **reference 전용** (case에 `output_xxcs.docx` / `security_tests.json` 없음)
