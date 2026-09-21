# Research Readiness Report

> **Historical (lab_ec_sw / JM COLLECTION)** — **Not used in Trial 1**  
> 이 문서는 과거 스프린트·벤치마크·진단 기록이다.  
> Real-world Trial 1 확정 case는 **Mindrium XA** (`trial-001-mindrium-xa`)이다.  
> Trial 1 문서: `docs/trial1_case_decision_mindrium.md`, `docs/README.md` § Trial 1


**기준일:** 2026-07-10  
**저장소:** `document_AI` / `feature/ai-engineering-platform`  
**테스트:** 229 passed

본 문서는 Document AI 프로젝트가 **학술 연구·실험 플랫폼**으로 확장 가능한지, 현재 증거와 갭을 정리한다.

---

## 1. 연구 주제로서의 기여점

### 1.1 문제 정의

EC-SW(의료 소프트웨어) 및 규제 문서(MDSR/MDDR/XXCS)는 **표 중심·traceability 중심**이라 일반 LLM 문서 생성과 요구가 다르다. 본 프로젝트는:

- 완성본·빈 양식에서 **필드 스키마를 학습**하고,
- 새 케이스 facts + 유사 완성본 few-shot으로 **구조화 필드를 hallucination 없이** 채우며,
- 요구사항 변경 시 **영향 문서만 선별 패치**하는 Document Harness를 제공한다.

### 1.2 차별점 (기존 RAG·LLM 문서 생성 대비)

| 관점 | 기여 |
|------|------|
| **구조화 vs free text** | 구조화 필드는 facts/rules/similar only — LLM 금지 원칙 |
| **Traceability** | Req↔Design↔Test Knowledge Graph + 변경 영향 분석 |
| **평가 이중화** | Quality(휴리스틱) + Validation(gold DOCX 비교) 분리 |
| **Harness 일반화** | 단일 도메인(Mindrium) → inventory / hospital / real lab case |
| **Platform 통합** | Document Harness를 AI Engineering Platform의 첫 Harness로 배치 |

### 1.3 현재 증거 수준

- **정량:** 4-case harness benchmark overall **94.1**, 229 unit/integration tests.
- **정성:** 자연어 intake 데모, 실제 연구실 프로젝트(`lab_ec_sw`) E2E PASS.
- **한계:** MDDR validation 75.3, force-generate quality FAIL 사례, XXCS·실서버 미검증.

---

## 2. AI Engineering Platform 관점

### 2.1 아키텍처 포지션

```
Goal → Adaptive Planner → ExecutionPlan → Platform Runtime
                                              ↓
                                    Harness Manager
                                    ├── Document Harness  ← 본 연구 핵심
                                    ├── Operation Harness (GPU/Docker/로그)
                                    └── (예정) Research / Git Harness
                                              ↓
                                    Platform Memory (5종)
```

Document Harness는 **Change Impact 5-agent 파이프라인**으로 구현되며, `platform-run`으로 Operation Harness와 **Hybrid 워크플로** 연결이 가능하다.

### 2.2 연구 가설 후보

1. **Multi-Harness Orchestration** — 단일 Goal 하에 Document + Operation 태스크 순차 실행이 incident 대응 시간·문서 정합성을 동시에 개선하는가?
2. **Platform Memory 축적** — Knowledge/Event/Reasoning/Task/Evaluation 5종 memory가 후속 플랜 품질을 향상시키는가?
3. **Harness 추상화** — 동일 Runtime 위 Document·Operation·Research Harness의 공통 task graph 모델이 확장 비용을 줄이는가?

### 2.3 플랫폼 실험 인프라 (이미 존재)

| 컴포넌트 | 실험 활용 |
|----------|-----------|
| `platform-plan` | 플랜만 생성 — ablation 시 실행 비용 절감 |
| `platform-run` | E2E + memory 기록 |
| `correlation_id`, memory ID | 재현·추적 |
| Operation samples | `data/ops/samples` — Hybrid 시나리오 |

---

## 3. Document Harness 관점

### 3.1 파이프라인 단계 (연구 단위)

| 단계 | 모듈 | 측정 가능 출력 |
|------|------|----------------|
| Intake | `case-intake` | field coverage, confirm rate |
| Retrieval | `case-retrieval` | recall@k, few-shot 유무 |
| Form-fill | rules + similar + LLM(free_text) | field F1 (`golden_fields.jsonl`) |
| Render | MDSR/MDDR DOCX | structure pass rate |
| Quality | `document-quality` | 6-dimension scores |
| Validation | `document-validate` | section/req/traceability/design metrics |
| E2E | `project-validate` | PASS/FAIL vs manifest thresholds |

### 3.2 일반화 실험 결과 (도메인 확장)

| Case | Domain | Quality | 비고 |
|------|--------|--------:|------|
| inventory_mgmt | 재고/EC | 96.8 | baseline dummy |
| hospital_reservation | 의료 예약 | 95.3 | terminology 90, domain mismatch WARNING |
| lab_ec_sw | B2C ecommerce (real) | 96.8 | real project facts |
| jm_collection | B2C reference | 96.8 | authoring baseline |

**시사점:** 동일 파이프라인으로 도메인 전환 가능. hospital이 가장 낮은 overall(95.3) — **도메인 치환 규칙·용어 사전**이 ablation 대상.

---

## 4. 실제 프로젝트 Validation 결과 (lab_ec_sw)

### 4.1 설정

- **Case:** `data/cases/lab_ec_sw`
- **Product:** JM COLLECTION (`ecommerce_b2c`)
- **Intake:** `intake_channel: real_project`, facts from lab + jm_collection 참고
- **Gold:** `jm_collection/output_mdsr.docx`, `output_mddr.docx` (fallback)
- **Manifest thresholds:** quality ≥ 85, validation ≥ 70

### 4.2 결과 (skip-generate, PASS)

| Metric | Score |
|--------|------:|
| Quality overall | 96.8 |
| Validation overall | 87.5 |
| MDSR validation | 99.8 |
| MDDR validation | 75.3 |
| Req count match | 100% (37/37) |
| Req text similarity | 100% |
| Traceability coverage | 100% |
| Design block coverage | **5.3%** |
| E2E status | **PASS** |

### 4.3 force-generate 관측 (한계 증거)

- 동일 케이스 `--force-generate` 시 quality **70.0 FAIL** (consistency 0), validation **87.5 PASS**.
- **생성은 gold 대비 구조적으로 양호**하나, **quality 휴리스틱이 brand/component naming에서 false positive** 발생.
- 연구 보고 시 "이중 평가 체계의 불일치"를 explicit limitation으로 기술할 것.

---

## 5. Benchmark 결과

### 5.1 Document Harness E2E Benchmark

**실행:** `python -m document_ai.cli harness-benchmark`  
**설정:** `data/eval/document_harness_benchmark.json`

| Case | Quality | Validation | Benchmark Score | Status |
|------|--------:|-----------:|----------------:|:------:|
| lab_ec_sw | 96.8 | 87.5 | 92.2 | PASS |
| inventory_mgmt | 96.8 | — | 96.8 | PASS |
| hospital_reservation | 95.3 | — | 95.3 | PASS |
| jm_collection | 96.8 | 87.7 | 92.2 | PASS |

**Aggregate:** 4 passed / 0 failed, **overall 94.1**

(Benchmark score = validation 있을 때 quality·validation 평균, 없으면 quality만.)

### 5.2 수정 전후 비교 (내부 회귀)

| 시점 | Passed | Failed | Overall |
|------|-------:|-------:|--------:|
| analyzer 수정 전 | 2 | 2 | 89.3 |
| analyzer 수정 후 | 4 | 0 | 94.1 |

→ Quality analyzer의 도메인 규칙이 **벤치마크 통과율에 직접 영향** — 논문에서 configuration sensitivity로 다룰 수 있음.

### 5.3 Platform benchmark 병합 (선택)

```powershell
python -m document_ai.cli harness-benchmark `
  --merge-platform-report data/platform/benchmark/benchmark_report.json
```

Document Harness 점수를 Platform-level benchmark 리포트에 통합 가능 (Hybrid 실험 확장용).

---

## 6. 논문 실험으로 확장하려면 필요한 것

### 6.1 데이터

| 항목 | 현재 | 필요 |
|------|------|------|
| Gold DOCX | jm_collection proxy 1세트 | 케이스별 human-reviewed gold ≥ 3 |
| 필드 정답 | `golden_fields.jsonl` 부분 | 도메인별 확장 + blind holdout |
| XXCS | 미포함 | IA/UC/SI 시험결과 gold + CSV bulk |
| Negative cases | 없음 | 의도적 누락·오입력 robustness set |

### 6.2 메트릭

| 메트릭 | 용도 |
|--------|------|
| Field F1 (structured) | form-fill 정확도 |
| Validation overall / per-doc | gold 정합 |
| Quality 6-dim | 자동 QA proxy |
| Traceability coverage | 규제 문서 핵심 KPI |
| Design block coverage | MDDR 약점 정량화 |
| Latency / cost | LLM free_text 비율별 |
| Human review time | 실용성 (minutes to approve) |

### 6.3 실험 설계

- **Train:** 완성본 corpus (Mindrium XA + lab cases)
- **Test:** holdout cases (hospital, new product)
- **Baselines:** (1) pure LLM end-to-end, (2) template only no retrieval, (3) no change impact
- **통계:** case-level PASS rate, paired score diff, inter-annotator on sample docs

### 6.4 재현성

- `project-validate`, `harness-benchmark` CLI + 고정 `input.json` + commit hash
- `skip-generate` vs `force-generate` 모드 명시
- 229 tests CI gate

---

## 7. Ablation 후보

| ID | 제거/변경 대상 | 가설 | 측정 |
|----|----------------|------|------|
| A1 | case-retrieval (few-shot) | free_text 품질·terminology 하락 | quality terminology, human score |
| A2 | domain replacement rules | hospital/inventory residual 증가 | consistency, domain_mismatch count |
| A3 | structured field LLM ban → allow | structured F1 vs hallucination rate | field F1, false fact count |
| A4 | change impact KG | apply-change precision/recall | affected doc count, wrong patch rate |
| A5 | quality analyzer brand rules | force-generate PASS rate | consistency score |
| A6 | gold proxy → independent gold | validation score 변화 | validation overall, MDDR coverage |
| A7 | Operation Harness in Hybrid | incident + doc update latency | end-to-end workflow time |

---

## 8. Real Server Operation Validation 후보

Document Harness와 **Operation Harness**를 실제 인프라에서 검증하는 시나리오.

### 8.1 후보 시나리오

| 시나리오 | Document 측 | Operation 측 | 성공 기준 |
|----------|-------------|--------------|-----------|
| **Req 변경 + GPU OOM** | Req.6 변경 → MDSR/MDDR patch | `nvidia_smi` OOM 로그 분석 | Hybrid `platform-run` 완료, memory 기록 |
| **배포 후 장애** | 설계 문서 traceability 확인 | docker restart loop | incident severity ≥ threshold 시 설계 항목 링크 |
| **규제 감사 대비** | validation ≥ threshold DOCX 출력 | — | audit checklist PASS |
| **Staging E2E** | lab_ec_sw generate on CI agent | sample ops logs from staging | benchmark overall ≥ 90 |

### 8.2 인프라 요구

- GPU 서버 또는 Docker 호스트 (샘플: `data/ops/samples` → live 수집)
- FastAPI Platform REST (로드맵) — 원격 trigger
- Secret·PII 격리 — 의료/결제 도메인 주의

### 8.3 현재 가능한 최소 실증

```powershell
python -m document_ai.cli platform-run `
  --case data/cases/mindrium_xa `
  --change data/cases/mindrium_xa/changes/req6_update.json `
  --goal "Req 변경 후 GPU 서버 장애 로그 분석" `
  --sample-dir data/ops/samples `
  --out data/platform/results/hybrid_runtime.json
```

→ **샘플 로그 기반** Hybrid는 재현 가능. **Live server** 검증은 미실시 — 논문에서는 "simulated ops environment"로 명시.

---

## 9. 연구 성숙도 요약

| 영역 | 성숙도 | 근거 |
|------|:------:|------|
| Document generation E2E | ●●●○ | 4-case benchmark 94.1, 229 tests |
| Gold-based validation | ●●○○ | MDSR 강함, MDDR 약함 (75.3) |
| Domain generalization | ●●●○ | 3 domains, hospital 95.3 |
| Real project case | ●●●○ | lab_ec_sw PASS, proxy gold |
| Platform Hybrid | ●●○○ | 샘플 기반 demo, live ops 미검증 |
| 논문급 dataset | ●○○○ | gold·annotator·holdout 부족 |
| Human study | ○○○○ | 미실시 |

**결론:** **시스템 논문·데모 논문(short paper, workshop)** 에 적합한 구현 성숙도. **대규모 정량 벤치마크 논문** 은 gold 확장·human eval·ablation 실행이 선행되어야 한다.

---

## 10. 권장 논문 스토리라인 (초안)

**제목 방향:** *Traceability-Aware Document Harness for Regulated Software Documentation within an AI Engineering Platform*

**기여 bullet:**

1. EC-SW 표 중심 문서용 **form-fill 파이프라인** (facts > rules > similar > LLM-free_text)
2. **이중 평가** — heuristic quality vs gold validation, 불일치 사례 분석
3. **Multi-domain harness benchmark** — dummy + real lab, 94.1 overall
4. **Platform embedding** — Document + Operation Hybrid workflow prototype

**Limitation bullet:**

- MDDR design block coverage 5.3%
- force-generate quality false negative
- XXCS·live ops 미포함
- proxy gold (jm_collection)

---

## 11. 관련 산출물

| 문서/경로 | 내용 |
|-----------|------|
| [demo_document_harness_report.md](demo_document_harness_report.md) | 데모 시나리오·케이스 비교·한계 |
| [ai_engineering_concept.md](ai_engineering_concept.md) | Platform 비전 |
| [platform_architecture.md](platform_architecture.md) | 컴포넌트 설계 |
| `data/eval/document_harness_benchmark.json` | 벤치마크 설정 |
| `data/cases/lab_ec_sw/e2e_validation_report.json` | 실제 프로젝트 E2E |
