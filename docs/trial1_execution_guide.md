# Trial 1 실행 가이드

> **Trial 1 (Mindrium XA) — 현재 사용 문서**  
> case: `data/cases/mindrium_xa` · trial_id: `trial-001-mindrium-xa`  
> 과거 lab_ec_sw / JM COLLECTION 기준 문서와 혼동하지 말 것.  
> 인덱스: `docs/README.md` § Trial 1


> Real-world Trial은 **사용자가 실자료 준비 후 직접** 수행한다.  
> Preparation Sprint는 준비만 완료했으며, Trial 완료로 보고하지 않는다.

## 관련 문서

| 문서 | 용도 |
|------|------|
| `docs/trial1_case_decision_mindrium.md` | **Case 확정 (Mindrium XA / 옵션 B)** |
| `docs/trial1_preparation_sprint_report.md` | Preparation Sprint 종합 |
| `docs/trial1_required_inputs.md` | 필요·부족 입력 |
| `docs/trial1_preflight_checklist.md` | 실행 직전 점검 |
| `docs/trial1_execution_checklist.md` | 실무 순서 체크리스트 |
| `docs/trial1_execution_commands.md` | PowerShell 명령 |
| `docs/trial1_artifacts_artifacts.md` | 디렉터리·산출물 |
| `docs/interim_presentation_prep.md` | 중간발표 |
| `docs/trial1_result_analysis_plan.md` | 오류→Embedding 연결 |

## Framework 검증 (synthetic) — 이미 완료된 것

`trial-synthetic-001`은 프레임 검증용이다. 실적으로 사용하지 않는다.

## Real-world Trial 1 (입력 준비 후 · 사용자 실행)

1. `docs/trial1_required_inputs.md` 완료  
2. `docs/trial1_preflight_checklist.md` 통과  
3. `docs/trial1_execution_checklist.md` + `docs/trial1_execution_commands.md` 따라 실행  
4. Human revision·annotation·summary  
5. `docs/interim_presentation_prep.md`로 중간발표  
6. `docs/trial1_result_analysis_plan.md`로 Embedding Sprint 우선순위 확정  

## 금지

- 원본 `data/cases/*/output_*.docx` 덮어쓰기  
- `v0.5-document-harness` 태그 수정  
- synthetic 결과를 실적으로 발표  
- 실입력 없이 real trial complete 보고  
