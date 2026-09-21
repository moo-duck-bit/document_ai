# Trial 1 생성 보정 보고서 (동결)

- 갱신: `2026-07-18T06:00:00Z`
- trial_id: `trial-001-mindrium-xa`
- 유형: 구현 검증
- **종합 결과: 실패(FAILED)**
- **사유: 수용 기준 미충족(Acceptance Criteria Not Met)**
- status: `implementation_validation_failed`
- trial_1_freeze: `true`
- 파이프라인 증거: `generated_patch_preserving/` (인용만, 수정 금지)
- real_world_trial_complete: `false`

## 1. 이전 생성 실패 요약

1. **JM 검색 오염**: 1차 harness.generate가 `jm_collection`을 few-shot으로 사용 → JM COLLECTION 브랜딩 혼입.
2. **clean 재생성 실패(원본 보존 관점)**: `use_retrieval=False`로 JM 문자열은 제거됐으나, 희소 JSON 기반 **전체 재생성 골격**이 됨.
   - MDSR 약 1.97MB → 약 293KB, MDDR 약 2.63MB → 약 317KB
   - 다수 Req 공란, 설계/그림/표 유실, XXCS 시험결과 NOT_EXECUTED 전면 교체
3. 따라서 `generated/`, `generated_clean_mindrium/` 는 **인적검토 부적합(INVALID_FOR_HR)**.

## 2. 수정 전략 (patch-in-place)

1. `reference/` 원본 DOCX를 `generated_patch_preserving/`로 byte-copy
2. MDSR: Req. 6 **description 셀만** patch (`patch_mdsr_description_only`)
3. MDDR: **Option 1** — 원본 복사, automatic design patch 없음 (`design_ids` null 반영)
4. XXCS: canonical 패키지에서 **제외** (OUT_OF_SCOPE)
5. full `harness.generate` / retrieval / JM·lab template 미사용
6. sparse `requirements.json`으로 원본 본문 전체 덮어쓰기 안 함

## 3. 산출물

| 문서 | 경로 | size | sha256 |
|------|------|------|--------|
| MDSR ref | `data/trials/trial-001-mindrium-xa/reference/spec_mdsr_EC-SW-MDSR(XA)_소프트웨어_요구사항명세서.docx` | 1968688 | `cd70f942ab8534c22887782b61d2319fd026e61f97744bde8f985c6484a3652d` |
| MDSR out | `data/trials/trial-001-mindrium-xa/generated_patch_preserving/output_mdsr.docx` | 1968210 | `3a119abb79c82fe5fe67579b171cec6ddbfb4c18822012c9a7e40892fea22ebd` |
| MDDR ref | `data/trials/trial-001-mindrium-xa/reference/spec_mddr_EC-SW-MDDR(XA) 소프트웨어 설계 명세서.docx` | 2630162 | `dff76e279aeeef1f2f13dda70770edfedfdfa6908407924812d7c9bcf9ebe0bf` |
| MDDR out | `data/trials/trial-001-mindrium-xa/generated_patch_preserving/output_mddr.docx` | 2630162 | `dff76e279aeeef1f2f13dda70770edfedfdfa6908407924812d7c9bcf9ebe0bf` |
| XXCS | (생성하지 않음) | — | reference 유지 |

## 4. MDSR exact diff

- unexpected_diff_count: `0`
- all_diff_count: `2`
- patched_req_ids: `['Req. 6']`

### Allowed / observed diffs
```json
[
  {
    "location": "t:12/r:1/c:0",
    "before": "",
    "after": "설명"
  },
  {
    "location": "t:12/r:1/c:1",
    "before": "",
    "after": "연속 로그인 실패 시 계정 잠금 및 관리자 알림을 수행해야 한다.\n잠금 해제는 관리자 승인 또는 일정 시간 경과 후 자동 해제 중 하나를 지원해야 한다."
  }
]
```

### Unexpected diffs
```json
[]
```

### OOXML structure
| metric | before | after |
|--------|--------|-------|
| tbl | 46 | 46 |
| drawing_like | 2 | 2 |
| sectPr | 1 | 1 |
| styles | 58 | 58 |

## 5. MDDR

- strategy: `no_automatic_design_patch`
- sha256 matches reference: `True`
- Req.6 design location candidates (report-only, not patched): `0`
- impact.design_ids was null → 자동 설계 생성/성공 주장 없음

## 6. XXCS

- Trial 선언 document_types: MDSR/MDDR
- canonical HR output에 XXCS **미포함**
- reference XXCS 원본 미변경
- 기존 opportunistic XXCS는 INVALID / OUT_OF_SCOPE

## 7. 오염 검사 (reference 대비 신규 토큰만)

- MDSR: `[]`
- MDDR: `[]`

## 8. Visual QA

```json
{
  "output": {
    "mdsr": {
      "ok": true,
      "engine": "win32com.Word",
      "pages": 29,
      "png_paths": [],
      "skipped_reason": null,
      "pdf_path": "data/trials/trial-001-mindrium-xa/logs/visual_qa/mdsr/output_mdsr.pdf",
      "notes": "PDF render saved for visual QA. Per-page PNG export skipped (Word COM page bitmap export not configured)."
    },
    "mddr": {
      "ok": true,
      "engine": "win32com.Word",
      "pages": 18,
      "png_paths": [],
      "skipped_reason": null,
      "pdf_path": "data/trials/trial-001-mindrium-xa/logs/visual_qa/mddr/output_mddr.pdf",
      "notes": "PDF render saved for visual QA. Per-page PNG export skipped (Word COM page bitmap export not configured)."
    }
  },
  "reference": {
    "mdsr": {
      "ok": true,
      "engine": "win32com.Word",
      "pages": 29,
      "png_paths": [],
      "skipped_reason": null,
      "pdf_path": "data/trials/trial-001-mindrium-xa/logs/visual_qa/reference_mdsr/spec_mdsr_EC-SW-MDSR(XA)_소프트웨어_요구사항명세서.pdf",
      "notes": "PDF render saved for visual QA. Per-page PNG export skipped (Word COM page bitmap export not configured)."
    },
    "mddr": {
      "ok": true,
      "engine": "win32com.Word",
      "pages": 18,
      "png_paths": [],
      "skipped_reason": null,
      "pdf_path": "data/trials/trial-001-mindrium-xa/logs/visual_qa/reference_mddr/spec_mddr_EC-SW-MDDR(XA) 소프트웨어 설계 명세서.pdf",
      "notes": "PDF render saved for visual QA. Per-page PNG export skipped (Word COM page bitmap export not configured)."
    }
  }
}
```

## 9. Trial 1 판정 (동결)

### 종합 결과

**실패(FAILED)**

### 사유

**수용 기준 미충족(Acceptance Criteria Not Met)**

### 통과(PASS) + 근거

1. 요구사항 매핑 — 자연어 CR → Req.6  
2. 패치 보존 — 원본 재생성 없이 패치  
3. 원본 보존 — 원본 DOCX 보존 · 원본 유지형 패치  
4. 문서 구조 보존 — 구조·서식 유지  

### 실패(FAIL)

- 의미적 일관성 · 요구사항 영향 식별 · 설계 전파  

### 근본 원인

- Exact-ID 의존 · 의미 검색 부재 · 그래프 확장 부재  

### Trial 1 동결

`true` — 코드/DOCX/재실행 추가 금지. 증거 경로: `generated_patch_preserving/`

### Trial 2 목표

검색 보강 의미 검색 · 영향 후보 발견 · 요구사항 간 영향 · 설계/검증 문서 전파 · 재검증  

### Trial 2 수용 기준

Req.105 영향 후보 포함 · 의미적 일관성 통과 · 필드 모순 없음 · MDDR 패치 또는 문서화 생략 · 문서 간 전파 추적 생성  

## 10. INVALID 표시

- `generated/INVALID_FOR_HR.txt`
- `generated_clean_mindrium/INVALID_FOR_HR.txt`


---

## 프레이밍 갱신 (동결)

종합 **실패(FAILED)** / 사유 **수용 기준 미충족**.  
정식 서술: `PRE_HUMAN_REVIEW_REPORT.md`

---

## 라벨 diff 보정 (2026-07-18T02:38:28Z)

이전 실행은 빈 라벨 셀(r1c0='')에 '설명' 문자열을 새로 기입했고, 값 셀(r1c1)에 CR 설명을 기입했다. 즉 OOXML run 허상 diff가 아니라 실제 라벨 텍스트 변경이었다.

라벨 셀은 원본대로 공란 유지, 설명(값) 셀만 수정하도록 preserve_patch 보정 후 재생성했다.

- 원본 r1c0: ''
- 보정 후 출력 r1c0: ''
- 비예상 diff 수: 0
- 텍스트 diff: [{"location": "t:12/r:1/c:1", "before": "", "after": "연속 로그인 실패 시 계정 잠금 및 관리자 알림을 수행해야 한다.\n잠금 해제는 관리자 승인 또는 일정 시간 경과 후 자동 해제 중 하나를 지원해야 한다."}]
- 패치 성공: True
