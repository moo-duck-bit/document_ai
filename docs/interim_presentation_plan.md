# 중간발표 계획 (Trial 1 후 / Trial 2 전)

## 목적

v0.5 Document Harness의 실무 문서 작성 수준을 공유하고,
Embedding Retrieval / LLM free-text의 개발 우선순위를 합의한다.

## 시점

- **이후**: Trial 1 완료 (`real_world_trial_complete=true`)
- **이전**: Trial 2 시작 전
- synthetic framework 검증만으로는 중간발표 “결과”로 쓰지 않는다.

## 발표 구성

1. 프로젝트 목표
2. v0.5 시스템 구조
3. 지원 문서 (MDSR/MDDR/XXCS)
4. Trial 목적·입력·누수 방지
5. 생성 결과
6. 자동 평가
7. 사람 평가
8. 시간 절감
9. 오류 유형
10. 성공/실패 사례
11. 한계
12. Trial 2 가설·개선 계획

## 필요 표/Figure

Trial `reports/tables/`:

- system_baseline.csv
- document_quality.csv
- human_review.csv
- time_savings.csv
- error_taxonomy.csv
- edit_burden.csv

Trial `reports/figures/data/`:

- score_comparison.json
- error_distribution.json
- edit_ratio.json
- time_comparison.json
- traceability.json

## 발표 전 체크리스트

- [ ] Trial 1 non-synthetic 완료
- [ ] leakage check 통과
- [ ] human ratings 기입
- [ ] verified error annotations
- [ ] baseline freeze 존재
- [ ] PPTX는 수동 작성 (자동 생성 불필요)

## Trial 2 가설 (초안, Trial 1 후 확정)

- Embedding retrieval이 free_text/유사 요구사항 품질을 개선한다
- Hybrid + LLM이 STYLE/MISSING_CONTENT를 줄인다
- Rule-based ID/traceability는 유지한다
