# Real-world Trial 1 Preparation Sprint 보고서

> **Trial 1 (Mindrium XA) — 현재 사용 문서**  
> case: `data/cases/mindrium_xa` · trial_id: `trial-001-mindrium-xa`  
> 과거 lab_ec_sw / JM COLLECTION 기준 문서와 혼동하지 말 것.  
> 인덱스: `docs/README.md` § Trial 1


> **이 Sprint에서는 Real-world Trial을 수행하지 않았다.**  
> 실제 Trial은 사용자가 실자료를 준비한 뒤 직접 실행한다.  
> 상태: **preparation complete / real trial pending**

기준 시스템: `v0.5-document-harness` (`d73fc18`)  
기준 case: **`mindrium_xa` (Mindrium XA / 옵션 B)** — 이전 후보 `lab_ec_sw`는 Trial 1에서 사용하지 않음.  
Case 결정 문서: `docs/trial1_case_decision_mindrium.md`

---

## 1. 현재 repository 분석

### 사용 가능 (레포 내)

| 자료 | 경로 | Trial에서의 역할 |
|------|------|------------------|
| Case facts | `data/cases/mindrium_xa/input.json` | 프로젝트 사실 입력 |
| 요구사항 payload | `.../requirements.json` | MDSR/추적성 근거 (다수 description 공란) |
| 설계 payload | `.../design_content.json` | MDDR 근거 |
| 보안시험 plan | examples XXCS / security JSON | XXCS plan 근거 |
| 생성 문서(case) | `output_mdsr/mddr.docx` | harness 출력 (원본과 구분) |
| **원본 완성본** | `data/examples/ec_sw/spec_*.docx`, `report_xxcs_*.docx` | **변경 전 기준 실자료** |
| 변경 패키지 후보 | `data/cases/mindrium_xa/changes/req6_*` | Req.6 로그인 잠금 to-be (준비된 CR) |
| 참고 (미사용) | `data/cases/lab_ec_sw/` | Trial 1 case 아님 |
| 템플릿 | `data/templates/ec_sw/template_*.docx` | 렌더 입력 |
| Trial 프레임 | `data/trials/` + trial-* CLI | 실행 인프라 (준비 완료) |
| Synthetic 검증 | `data/trials/trial-synthetic-001/` | 프레임만 검증됨 (실적 아님) |
| Baseline | `reports/baselines/v0.5-document-harness/` | 비교 기준선 |

### 사용 금지 / 격리

| 자료 | 이유 |
|------|------|
| `data/gold/**` | Independent gold — generation 입력 금지 |
| `hospital_reservation` holdout | 튜닝·입력 금지 |
| `human_revised` 최종본을 input에 배치 | leakage |
| synthetic security execution을 실적으로 보고 | 금지 |
| 평가용 최종 승인본을 input에 혼입 | 금지 |

### 파이프라인 재사용성

- **New Generation**: `harness-generate` / `trial-generate` 가능
- **Change Update**: `draft-change` → `impact` → `apply-change` 존재, Trial workdir에서만 적용 권장

---

## 2. Trial 1 추천 방식

### 추천: **Change Update** (`trial_type=change_update`)

| 이유 | 설명 |
|------|------|
| 실무 유사성 | EC-SW 문서는 완전 신규보다 **요구사항 변경 반영**이 잦음 |
| 레포 준비도 | `draft-change` / `impact` / `apply-change` / `eval-impact` 이미 존재 |
| 측정 가치 | “불필요 변경(unnecessary change)”·추적성 재검증이 Trial 핵심 지표 |
| 기준 문서 | Mindrium 원본 MDSR/MDDR/XXCS (`data/examples/ec_sw`) |
| 중간발표 | 변경 전후 Diff·오류 taxonomy가 Embedding/LLM 우선순위 논의에 직결 |

### New Generation을 쓰지 않는 이유 (이번 Trial 1)

- 이미 harness E2E·benchmark로 “신규 생성” 품질은 상당 부분 측정됨
- 실무 Pain은 변경 반영·기존 내용 보존에 더 가깝다
- New Generation은 Trial 2 이후 ablation/확장용으로 남겨도 충분

대안: JM/`lab_ec_sw`로 바꾸면 별도 trial_id(`trial-00x-lab-ec-sw`)를 쓴다.  
현재 Trial 1은 **`trial-001-mindrium-xa`** 로 고정.

---

## 3. 필요한 실제 입력

상세 체크리스트: `docs/trial1_required_inputs.md`  
실행 전 점검: `docs/trial1_preflight_checklist.md`

요약:

**기준 문서** — 변경 전 MDSR/MDDR/XXCS + 버전·기준일  
**변경 정보** — 변경요청, 회의록, 메신저/메일 요약, 개발자 확인, 적용/제외 범위  
**평가용 정답** — 최종본은 별도 격리 (input 금지)  
**시간** — 수작업 baseline, revision 분  
**리뷰어** — 역할·문서 담당·1/2인  
**민감정보** — 마스킹 완료본

---

## 4. 부족한 입력

레포만으로는 Real-world Trial 1을 **완료할 수 없다.**

| 부족 항목 | 상태 |
|-----------|------|
| 실제 업무 변경 요청 원문 | ❌ 없음 (`req6`는 예시일 뿐) |
| 실제 회의록 | ❌ |
| 카카오/이메일 결정 근거 | ❌ |
| 담당자 확인 답변 | ❌ |
| 문서 버전·기준일 공식 메타 | ⚠️ output에 암묵적, 사용자 확정 필요 |
| 수작업 baseline 시간 | ❌ |
| Human revision 실측 | ❌ |
| 리뷰어 지정 | ❌ |
| 최종 정답본 격리 위치 | ❌ 사용자 지정 |

`mindrium_xa`의 `req6_*`는 **완성본에서 뽑은 as-is가 아니라 준비된 to-be 변경 패키지**다.  
Trial 입력으로 채택 시 리포트에 「실문서 기준 + 준비된 Req.6 CR」로 표기한다. 운영 회의록이 있으면 실무 CR로 격상.

---

## 5. Trial 실행 순서

실무 체크리스트: `docs/trial1_execution_checklist.md`  
명령 예시: `docs/trial1_execution_commands.md`

요약 순서:

1. 입력자료 준비 → 2. Preflight → 3. trial-init → 4. trial-check-input  
5. (선택) draft-change/impact in workdir → 6. trial-generate  
7. trial-prepare-review → 8. human revision → 9. trial-analyze → 10. trial-summary  
11. 중간발표 데이터 확인 → 12. Embedding Sprint 우선순위 결정

---

## 6. 중간발표 준비 상태

문서: `docs/interim_presentation_prep.md` (+ 기존 `interim_presentation_plan.md`)

| 항목 | 상태 |
|------|------|
| 발표 목표·흐름 | ✅ 문서화 |
| 시스템 구조·완료 기능 | ✅ |
| Trial 1 목적 | ✅ |
| 보여줄 지표 목록 | ✅ |
| Trial 2 개선 가설 | ✅ 초안 (Trial 1 후 확정) |
| 실제 Trial 수치 | ❌ pending (실 Trial 후) |
| PPTX | ❌ 수동 (자동 생성 범위 밖) |

---

## 7. Trial 종료 후 생성될 결과물

| 산출물 | 위치 |
|--------|------|
| `trial_manifest.json` | trial root |
| `input_manifest.json` | trial root |
| `generation_manifest.json` | trial root |
| `generated/output_*.docx` | generated/ |
| `human_revision_record.json` | trial root 또는 review/ |
| `error_annotations.json` | trial root |
| `diff/docx_diff.json` | diff/ |
| `metrics.json` | trial root |
| `trial_report.md` | trial root / reports/ |
| `presentation_summary.md` / `.json` | trial root / presentation/ |
| `reports/tables/*.csv` | tables |
| `reports/figures/data/*.json` | figures |

상세: `docs/trial1_artifacts_artifacts.md` (본 Sprint에서 정리).

---

## 8. Trial 결과 분석 계획

문서: `docs/trial1_result_analysis_plan.md`

요약 매핑:

| 오류 | 다음 Sprint 방향 |
|------|------------------|
| FACT_ERROR / MISSING_CONTENT / UNSUPPORTED_ASSUMPTION | Embedding Retrieval |
| STYLE_EDIT / TERMINOLOGY / REDUNDANT | LLM free-text |
| TRACEABILITY / 잘못된 ID | Rule-based 강화 |
| FORMAT / WRONG_SECTION | Template·render |
| 불필요 변경 과다 | Change pipeline·patch 정책 |

---

## 9. Embedding Sprint로 넘어가기 위한 준비 상태

| 준비 | 상태 |
|------|------|
| v0.5 기준선 동결 | ✅ |
| Trial 프레임·지표·발표 스키마 | ✅ |
| 오류 taxonomy | ✅ |
| Real Trial 수치 | ❌ 사용자 Trial 1 후 |
| Retrieval 구현 | ❌ (다음 Sprint) |

**게이트:** Trial 1 `real_world_trial_complete=true` + verified annotations + 중간발표 공유 후 Embedding Sprint 착수.

---

## 10. 사용자가 다음으로 해야 하는 작업

1. `docs/trial1_required_inputs.md` 체크리스트로 실자료 수집·마스킹  
2. `docs/trial1_preflight_checklist.md` 통과  
3. `docs/trial1_execution_commands.md`로 **직접** Trial 1 실행  
4. Human revision·시간·rating·verified annotation 기입  
5. `trial-summary` 후 `presentation_summary`로 중간발표  
6. `docs/trial1_result_analysis_plan.md`로 Embedding/LLM/Rule 우선순위 확정  

이번 Preparation Sprint는 여기서 종료한다.  
**Real-world Trial 1 완료로 보고하지 않는다.**
