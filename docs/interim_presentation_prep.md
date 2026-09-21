# 중간발표 준비 문서 (Trial 1 후 / Trial 2·Embedding 전)

> **Trial 1 (Mindrium XA) — 현재 사용 문서**  
> case: `data/cases/mindrium_xa` · trial_id: `trial-001-mindrium-xa`  
> 과거 lab_ec_sw / JM COLLECTION 기준 문서와 혼동하지 말 것.  
> 인덱스: `docs/README.md` § Trial 1


## 발표 목표

1. v0.5 Document Harness가 **실무 문서(MDSR/MDDR/XXCS)** 작성에 어느 정도 쓸 수 있는지 공유한다.
2. Trial 1(실자료·사람 수정) 결과로 **자동 점수만으로 보이지 않는** 수정 부담·오류 유형을 보여준다.
3. Trial 2 전에 **Embedding Retrieval / LLM free-text / Rule** 중 무엇부터 손댈지 합의한다.

시점: Real-world Trial 1 완료 후, Trial 2·Embedding Sprint 시작 전.  
Synthetic Trial 수치를 “실무 성과”로 발표하지 않는다.

## 발표 흐름 (권장 12슬라이드)

| # | 슬라이드 | 근거 자료 |
|---|----------|-----------|
| 1 | 프로젝트 목표 (완성문서 학습 → 자동 작성 Harness) | AGENTS.md |
| 2 | v0.5 시스템 구조 (Rule / Retrieval light / LLM 범위) | architecture docs |
| 3 | 지원 문서·추적성 (Req→Design→Security Test) | mindrium_xa / examples/ec_sw |
| 4 | Evaluation Foundation·baseline freeze | `reports/baselines/v0.5-…` |
| 5 | Trial 1 목적·유형(Change Update)·누수 방지 | trial protocol |
| 6 | 입력·조건·cutoff | trial_manifest / input_manifest |
| 7 | 생성 결과 데모 (스크린/표) | generated/ |
| 8 | 자동 평가 (quality / validation / traceability) | metrics, tables |
| 9 | 사람 평가·시간 절감·readiness | human_revision_record |
| 10 | 오류 분포·잘된/실패 사례 | error_annotations, diff |
| 11 | 현재 한계 | trial_report |
| 12 | Trial 2 가설 = Embedding/LLM/Rule 우선순위 | analysis plan |

## 현재 시스템 구조 (발표용 한 줄)

```text
facts + templates
  → Document Harness (rule fill + light retrieval)
  → MDSR / MDDR / XXCS
  → quality / validation / human review
  → (Trial) generate → revise → diff → metrics → presentation
```

Security Runner는 synthetic MVP로 동결 — 중간발표 본론이 아님.

## 구현 완료 기능 (Evaluation Foundation까지)

- MDSR/MDDR/XXCS 생성·추적성
- quality / validation / harness benchmark
- gold / holdout / human review package
- security execution import·review (동결)
- Trial CLI·leakage·baseline freeze·presentation summary
- XXCS fill 결정론 수정 (flaky 제거), pytest 320×3 PASS

## Trial 1 목적 (한 문장)

v0.5를 **개선하지 않은 채** 실무 유사 Change Update에서 생성→수정 부담·오류 유형·시간 효과를 측정한다.

## Trial 결과에서 반드시 보여줄 지표

### 자동

- Quality overall, Validation overall (문서별)
- Traceability / linked coverage
- Diff: unchanged / modified / added / deleted paragraph·cell ratio
- Edit burden score
- Unnecessary change 관련 관찰 (change_update)

### 사람

- 6차원 5점 (정확성·완전성·형식·추적성·문장·실무활용)
- usable_without_change / internal_review_ready / external_delivery_ready
- Critical / Major / Minor 이슈 수

### 시간

- manual_baseline_minutes (없으면 N/A)
- generation + revision
- time_saving_rate

### 오류

- taxonomy 분포 (verified만 강조, auto는 참고)

데이터 위치: `presentation_summary.*`, `reports/tables/*`, `reports/figures/data/*`

## Trial 2에서 개선할 내용 (가설 — Trial 1 후 확정)

| Trial 1에서 보이면 | Trial 2 / 다음 Sprint |
|--------------------|------------------------|
| FACT / MISSING / 근거 없는 서술 | Embedding Retrieval |
| STYLE / 문장 품질 | LLM free-text |
| TRACEABILITY / ID | Rule·스키마 |
| FORMAT | Template/render |
| 과도한 무관 변경 | Change patch 정책 |

## 발표 전 체크

- [ ] Real Trial complete (synthetic 아님)
- [ ] leakage clean
- [ ] verified annotations
- [ ] baseline freeze 인용
- [ ] PPTX 수동 초안
