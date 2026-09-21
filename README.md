# Document AI Platform

규제 산업의 기술 문서를 **Agent 오케스트레이션**으로 자동 작성·갱신하는 플랫폼.

요구사항이 하나 바뀌면 연관 문서 수십 페이지를 사람이 추적해 고쳐야 합니다. 이 프로젝트는 문서 간 traceability를 Knowledge Graph로 모델링해, **변경의 영향 범위만 자동 산출하고 해당 항목만 패치**합니다. 의료기기 SW 문서(EC-SW / IEC 62304)로 검증했으며, 금융 컴플라이언스 문서처럼 **양식·감사 추적·근거 요구가 있는 도메인에 동일한 구조로 적용**됩니다.

## 핵심 설계 결정

**1. LLM을 자유서술로 격리 — 환각을 아키텍처로 차단**

규제 문서에서 금액·날짜·요구사항 ID를 LLM이 생성하면 감사에서 무너집니다. 그래서 생성 경로를 둘로 분리했습니다.

| 셀 종류 | 생성 주체 |
|---|---|
| 구조적 사실 (ID, 날짜, 수치, 빈도) | 규칙 + Knowledge Graph — **LLM 접근 차단** |
| 자유서술 (개요, 설명) | LLM (선택적), 실패 시 규칙 기반 폴백 |

`field_kind`가 `structured`/`rule`/`fact`면 LLM 호출 자체를 우회합니다. LLM은 교체 가능한 인터페이스 뒤에 있어, 미설정 환경에서도 파이프라인이 완주합니다.

**2. Goal → Plan → Execute 런타임**

자연어 Goal을 받아 Intent를 분류하고, 실행 계획(Task Graph)을 만들어 여러 Harness에 분배합니다. Harness는 교체·추가 가능한 실행 단위입니다.

**3. 실행 이력을 Memory로 축적**

Knowledge / Event / Reasoning / Task / Evaluation 5종을 실행마다 기록합니다. 재현·디버깅과 향후 자기개선(Self-Improvement)의 입력입니다.

## 아키텍처

```
Goal ─→ Adaptive Planner ─→ Goal Orchestrator ─→ ExecutionPlan
                                                      │
                                    ┌─────────────────┴─────────────────┐
                                    ↓                                   ↓
                            Platform Runtime ──→ Harness Manager        │
                                    │              ├─ Document Harness  │
                                    │              └─ Operation Harness │
                                    ↓                                   │
                            Platform Memory ←───────────────────────────┘
                     (Knowledge · Event · Reasoning · Task · Evaluation)
```

- **Document Harness** — 5-agent 파이프라인 (요구사항 / 설계 / 테스트 / traceability / 문서리뷰)
- **Operation Harness** — GPU·컨테이너·로그 샘플에서 장애 이벤트 탐지 및 severity 산출
- **Change Impact** — `requirements.json` traceability → Knowledge Graph → 영향 문서·항목 산출 (dry-run / apply 분리)
- **Hybrid Retrieval** — lexical + TF-IDF cosine, `EmbeddingBackend` 교체 가능

## 기술 스택

| 영역 | 사용 기술 |
|---|---|
| 코어 | Python 3.11, python-docx, networkx |
| 검색 | TF-IDF 하이브리드 (의존성 없는 순수 구현), 교체 가능 백엔드 |
| LLM | OpenAI 호환 (선택적, 자유서술 전용) |
| API / UI | FastAPI |
| 배포 | Docker, docker-compose |
| 테스트 | pytest — 테스트 파일 160개 |

## 빠른 시작

```bash
pip install -e ".[dev]"
python -m pytest -q
```

실행 계획 미리보기 — 실제 실행 전 어떤 Harness가 어떤 순서로 도는지 확인합니다.

```bash
python -m document_ai.cli platform-plan \
  --goal "요구사항 변경 후 GPU 서버 장애 로그 분석" \
  --case data/cases/<case> \
  --change data/cases/<case>/changes/<change>.json
```

Goal 실행 — Document → Operation 순차 실행 후 Memory에 기록합니다.

```bash
python -m document_ai.cli platform-run \
  --case data/cases/<case> \
  --change data/cases/<case>/changes/<change>.json \
  --goal "요구사항 변경 후 GPU 서버 장애 로그 분석" \
  --out runtime_result.json
```

## 품질 검증 체계

생성 품질을 주관 평가에 맡기지 않기 위해 평가 파이프라인을 별도로 설계했습니다.

| 항목 | 내용 |
|---|---|
| Gold Dataset | 독립 정답셋 설계, `provisional` → `human_approved` 승인 단계 분리 |
| Holdout | 홀드아웃 케이스 동결 — 점수를 위한 규칙 수정 차단 |
| Human Evaluation | 리뷰 패키지 자동 생성 → 사람 검토 → 승인 워크플로 |
| Data Leakage | 학습·평가 분리 정책 문서화 |

설계 문서는 [`docs/`](docs/)에 있습니다 — 플랫폼 아키텍처, Knowledge Graph 스키마, 평가 프로토콜, 연구 확장 방향.

## 로드맵

| 상태 | 항목 |
|:---:|---|
| ✅ | Document Harness, Change Impact, Knowledge Graph |
| ✅ | Platform Memory 5종, Operation Harness |
| ✅ | Adaptive Planner, Goal Orchestrator, Multi-Task Runtime |
| 🔲 | LLM Planner — Goal 분해·플랜 생성 |
| 🔲 | Platform REST API, Workflow 시각화 대시보드 |
| 🔲 | Research / Git Harness |

## 참고

생성 DOCX 산출물과 실제 프로젝트 문서는 저장소에 포함되지 않습니다. 빈 양식과 합성 테스트 픽스처만 커밋되어 있으며, 산출물은 위 CLI로 재생성됩니다.

SKKU Document AI 프로젝트. 이슈·PR은 저장소 정책에 따릅니다.
