# Trial 1 결과 분석 계획 → Embedding Sprint 연결

> **Trial 1 (Mindrium XA) — 현재 사용 문서**  
> case: `data/cases/mindrium_xa` · trial_id: `trial-001-mindrium-xa`  
> 과거 lab_ec_sw / JM COLLECTION 기준 문서와 혼동하지 말 것.  
> 인덱스: `docs/README.md` § Trial 1


> Trial 1 **완료 후**에만 수행. 지금은 계획만 확정한다.  
> Synthetic annotations를 실무 오류로 취급하지 않는다.

## 분석 원칙

1. `verified=true` annotation만 우선순위 결정에 사용
2. auto_candidate는 참고, 발표·로드맵에 단독 사용 금지
3. 문서별(MDSR/MDDR/XXCS)·심각도별 집계
4. Change Update면 “변경 요청 미반영” vs “무관 구간 과다 수정”을 분리
5. v0.5 결과를 고친 뒤 **같은 trial_id를 덮어쓰지 않음** → Trial 2는 새 trial_id

## 오류 → 개선 매핑

```text
FACT_ERROR
  → 사실·제품 정보 오기재
  → Embedding Retrieval (유사 완성본·요구사항 few-shot) + facts 우선 규칙

MISSING_CONTENT
  → 필수 서술·표 셀 누락
  → Retrieval로 유사 섹션 보강 / 스키마 required 점검

UNSUPPORTED_ASSUMPTION
  → 입력에 없는 내용 생성
  → Retrieval grounding + LLM 사용 시 evidence 강제 (Trial 2+)

TRACEABILITY_ERROR
  → Req/Design/Test ID 단절·오연결
  → Rule-based ID·linked_reqs 검증 강화 (Retrieval보다 우선)

FORMAT_ERROR / WRONG_SECTION
  → 양식·섹션 위치
  → template-learn / render / XXCS fill 규칙

TERMINOLOGY_ERROR / STYLE_EDIT
  → 용어·문장 다듬기
  → LLM free-text (Retrieval few-shot과 결합)

REDUNDANT_CONTENT / INCONSISTENT_CONTENT
  → 중복·모순
  → Change patch 범위 제한 + (선택) LLM 정리

NO_CHANGE_REQUIRED
  → 수정 불필요 — 성공 사례로 집계
```

## Trial 1 직후 작업 순서

1. `error_annotations.json`에서 verified만 필터
2. `reports/tables/error_taxonomy.csv`와 교차 확인
3. Diff burden이 큰 문서·섹션 목록화
4. 상위 2개 오류 유형 → Sprint 백로그 확정
5. Embedding Sprint 착수 조건: FACT/MISSING/UNSUPPORTED가 상위이거나 free_text 품질이 병목일 때

## Embedding Sprint 진입 체크

- [ ] Trial 1 real complete
- [ ] 중간발표에서 오류 분포 공유
- [ ] Retrieval 가설 문장 1개 이상 합의
- [ ] holdout 오염 없이 개발 세트만 사용
- [ ] Security/Operation 범위 확대하지 않음
