# Presentation Summary — trial-synthetic-001

## 1. 프로젝트 목표

완성 문서와 입력 자료로 MDSR/MDDR/XXCS를 생성하고, 추적성·품질·human review를
포함한 Document Harness를 구축한다.

## 2. v0.5 시스템 구조

- system_version: `v0.5-document-harness`
- system_commit: `d73fc18`
- Rule-based + Retrieval(light) + (LLM free-text는 이번 Trial 범위 밖)

## 3. 현재 지원 문서

MDSR, MDDR, XXCS

## 4. Trial 목적

v0.5 기준선에서 실제 업무 유사 환경의 문서 작성 수준을 측정한다.
이번 실행 completion_label: **synthetic_framework_validation**

## 5. Trial 입력과 조건

- case_id: `lab_ec_sw`
- trial_type: `change_update`
- synthetic: `True`
- data_leakage_checked: `True`

## 6. 생성 결과

- outputs: `{"MDSR": "data/trials/trial-synthetic-001/generated/output_mdsr.docx", "MDDR": "data/trials/trial-synthetic-001/generated/output_mddr.docx", "XXCS": "data/trials/trial-synthetic-001/generated/output_xxcs.docx"}`
- duration_seconds: `9.694`

## 7. 자동 평가 결과

- quality overall: `96.8`
- validation overall: `90.5`

## 8. 사람 평가 결과

- human record present: `False`
- ratings overall: `None`

## 9. 수정 시간

- time_saving_rate: `None`
- status: `N/A`
- reason: `manual_baseline_minutes missing`

## 10. 오류 유형 분포

```json
{}
```

## 11. 잘된 사례 / 12. 실패 사례

실무 Trial 완료 후 reviewer notes와 verified annotations를 채워 발표에 사용한다.
synthetic 실행에서는 사례를 실적으로 보고하지 않는다.

## 13. 현재 한계

- Embedding retrieval / LLM free-text 미적용
- Real-world 입력·human revision이 없으면 Trial 1 미완료
- Security runner는 synthetic MVP로 동결

## 14. Trial 2 개선 계획

Trial 1 오류 분석 후 Embedding Retrieval → Hybrid + LLM free-text 우선순위를 결정한다.
