# Trial 1 Case 결정: Mindrium XA (옵션 B)

> **Trial 1 (Mindrium XA) — 현재 사용 문서**  
> case: `data/cases/mindrium_xa` · trial_id: `trial-001-mindrium-xa`  
> 과거 lab_ec_sw / JM COLLECTION 기준 문서와 혼동하지 말 것.  
> 인덱스: `docs/README.md` § Trial 1


> **확정:** Real-world Trial 1 case = `mindrium_xa`  
> trial_id = `trial-001-mindrium-xa`  
> trial_type = `change_update`  
> 이전 권장안 `lab_ec_sw` / `trial-001-lab-ec-sw` 는 Trial 1에서 사용하지 않는다.

## 왜 B인가

사용자가 제공한 Mindrium 요구사항·설계·보안검증 완성본이 **실제 EC-SW 문서 코퍼스**이므로, Trial 1 기준 제품·제품 문맥을 여기에 둔다.

| 자산 | 경로 | Trial 역할 |
|------|------|------------|
| 원본 MDSR | `data/examples/ec_sw/spec_mdsr_EC-SW-MDSR(XA)_*.docx` | 변경 **전** 기준 문서 (실자료) |
| 원본 MDDR | `data/examples/ec_sw/spec_mddr_EC-SW-MDDR(XA)*.docx` | 변경 **전** 기준 문서 (실자료) |
| 원본 XXCS | `data/examples/ec_sw/report_xxcs_EC-SW-XXCS(XA)*.docx` | 변경 **전** 기준 / 참고 (실자료) |
| Case facts | `data/cases/mindrium_xa/input.json` | 제품·버전 메타 |
| Case 산출 | `data/cases/mindrium_xa/output_mdsr.docx`, `output_mddr.docx` | harness 생성본 (원본과 구분) |
| 변경 패키지 후보 | `data/cases/mindrium_xa/changes/request_req6.txt`, `req6_update.json` | Change Update 입력 후보 |

## 반드시 알아둘 제약

1. **원본 MDSR의 Req. 6 description은 비어 있다** (표 셀 기준).  
   `request_req6.txt` / `req6_update.json`의 로그인 잠금 문구는 **기존 완성본에서 추출한 as-is가 아니라**, 파이프라인 검증용으로 준비한 **to-be 변경 패키지**다.
2. `requirements.json`도 다수 Req description이 비어 있다 → Trial 전 **workdir에서** Req. 6 변경을 적용·생성할 때, “빈 칸 채우기(신규 기입)”에 가깝다.  
   lab_ec_sw의 Req. 105(기존 5회/15분 수정)와 **변경 유형이 다르다.**
3. case에 `output_xxcs.docx`가 없다 → XXCS는 원본 예시를 `reference/`에 두고, 생성 범위는 MDSR/MDDR 우선 또는 XXCS skeleton 전략을 명시해야 한다.
4. `changes/req6_*`를 실적으로 쓰려면 발표/리포트에  
   **「실문서 기준 + 준비된 Req.6 변경 요청」** 이라고 밝힌다.  
   운영 CR·회의록이 추가로 있으면 그때 “완전 실무 CR”로 격상한다.

## Trial 1 확정 시나리오 (실행 기준)

| 항목 | 값 |
|------|-----|
| trial_id | `trial-001-mindrium-xa` |
| case | `data/cases/mindrium_xa` |
| change | prepared `Req. 6` CR (`request_req6.txt`) |
| 성격 | 빈 표 description **update/fill** (기존 수치 정책 수정 아님) |
| 상태 | patch-preserving 검증 통과 (`pre_human_review_ready`; 이전 clean은 INVALID_FOR_HR) |

산출물:
- `PRE_HUMAN_REVIEW_REPORT.md` / `GENERATION_CORRECTION_REPORT.md`
- **HR용:** `generated_patch_preserving/` (원본 patch-in-place)
- **INVALID_FOR_HR:** `generated/`, `generated_clean_mindrium/`

## 다음 스텝 (현재)

Human Review: `generated_clean_mindrium/` 문서 검토·수정, `review/human_revision_record.template.json` 기입.  
원본 `data/cases/mindrium_xa` 및 `data/examples/ec_sw`는 계속 미수정.

관련: `data/trials/trial-001-mindrium-xa/PRE_HUMAN_REVIEW_REPORT.md` · 인덱스 `docs/README.md`
