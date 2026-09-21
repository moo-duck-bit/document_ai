# MDSR Reviewer Package (Implementation Validation)

> Trial 1 **Result: FAILED** — PASS에 mapping/patch preservation, FAIL에 semantic consistency 포함.  
> status: `implementation_validation_failed`

- reference: `data/trials/trial-001-mindrium-xa/reference/spec_mdsr_EC-SW-MDSR(XA)_소프트웨어_요구사항명세서.docx`
- generated: `data/trials/trial-001-mindrium-xa/generated_patch_preserving/output_mdsr.docx`
- change target: **Req. 6** description value cell only

## 변경 위치 (정확한 표/행/셀)

| 항목 | 값 |
|------|-----|
| table_index (0-based) | `12` |
| 변경 대상 Req ID | `Req. 6` |
| 라벨 셀 | row=1, col=0 |
| description 값 셀 | row=1, col=1 |

### 원본 → 변경 후

| 셀 | 원본 | 변경 후 |
|----|------|---------|
| r1c0 (라벨) | `''` | `''` |
| r1c1 (값) | `''` | (CR description, 아래) |

변경 후 description:

```
연속 로그인 실패 시 계정 잠금 및 관리자 알림을 수행해야 한다.
잠금 해제는 관리자 승인 또는 일정 시간 경과 후 자동 해제 중 하나를 지원해야 한다.
```

## “허용 2건: 설명 라벨 + description 기입” 의미 정정

이전 patch 실행에서는:

1. **실제 라벨 텍스트 변경**: 원본 r1c0이 빈 문자열(`''`)인데 `'설명'`을 새로 기입함  
   → OOXML run 허상이 아니라 **의도치 않은 텍스트 변경**이었음.
2. description 값 셀(r1c1)에 CR 문구 기입.

**보정 후 (현재 canonical):**

- 라벨 셀(r1c0)은 원본과 동일하게 **공란 유지**
- **값 셀(r1c1)만** CR description으로 수정
- 허용 변경 = description 값 1건 (라벨 변경 0건)

현재 unexpected_text_diff_count: `0`  
현재 text_diffs: `1`건

```json
[
  {
    "location": "t:12/r:1/c:1",
    "before": "",
    "after": "연속 로그인 실패 시 계정 잠금 및 관리자 알림을 수행해야 한다.\n잠금 해제는 관리자 승인 또는 일정 시간 경과 후 자동 해제 중 하나를 지원해야 한다."
  }
]
```

## 구조 비교

| metric | reference | generated |
|--------|-----------|-----------|
| tbl | 46 | 46 |
| drawing_like | 2 | 2 |
| sectPr | 1 | 1 |
| styles | 58 | 58 |
| size | 1968688 | 1968231 |
| pages | 29 | 29 |

## 리뷰어 확인 포인트

1. Req.6 표 description 값만 CR과 일치하는가
2. 라벨 셀이 원본처럼 비어 있는가 (임의 '설명' 삽입 없음)
3. 본문 문단의 기존 Req.6 제목/설명(인증 에러 안내)이 그대로인가
4. 다른 Req·표·그림·머리글/바닥글 불변인가
