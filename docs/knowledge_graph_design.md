# Knowledge Graph Design

> **역할:** Knowledge Graph의 **HOW** — 스키마, builder, query, adapter, 구현 단계  
> **상위 문서:** [AI Engineering Concept](ai_engineering_concept.md) → [Platform Architecture](platform_architecture.md)  
> **상태:** Design (구현 전)  
> **기준선:** 55 tests passed, `TraceabilityGraph` in `impact/graph.py`

---

## 1. Overview

Knowledge Graph는 AI Engineering Platform의 **Knowledge Memory** 구현체이다. Platform 전체가 아니라 [Platform Memory](platform_architecture.md#4-platform-memory)의 structural layer이다.

### 1.1 기존 TraceabilityGraph와의 차이

| 차원 | TraceabilityGraph (현재) | KnowledgeGraph (목표) |
|------|-------------------------|------------------------|
| 범위 | `traceability[]` 행만 | Req, Design, Test, Security, Document, (+ Ops, Research) |
| 구조 | `dict[str, set[str]]` | typed nodes + edges + provenance |
| 탐색 | 1-hop | multi-hop, edge filter, explain_path |
| 저장 | 매 요청 인메모리 | case-scoped JSON/GraphML + NetworkX |
| 출처 | 없음 | `source_file`, `evidence`, `confidence` |

### 1.2 호환 계약 (불변)

다음 API 출력 스키마는 KG 도입 후에도 **동일**해야 한다.

- `compute_impact()` → `{ change_id, summary, impact, outputs }`
- `impact` 내부: `changed_req_ids`, `linked_downstream_ids`, `linked_security_ids`, `linked_test_ids`, `document_set_hint`, `documents`
- `apply_change()`, `run_change_pipeline()`, `eval-impact` prediction 필드

---

## 2. Module Structure

```
src/document_ai/knowledge/
├── __init__.py      # 공개 API re-export
├── models.py        # Node, Edge, NodeType, EdgeType
├── graph.py         # KnowledgeGraph (NetworkX wrapper)
├── builder.py       # build_graph_from_case()
├── query.py         # traversal, impact, explain_path
├── export.py        # JSON + GraphML
└── adapter.py       # TraceabilityGraph-compatible facade
```

| 모듈 | 책임 |
|------|------|
| `models.py` | 스키마 계약, ID 규칙 (`{case_id}:{type_slug}:{normalized_id}`), validation |
| `graph.py` | NetworkX DiGraph CRUD, load/save, orphan 탐지 |
| `builder.py` | case 아티팩트 → typed graph (read-only, Phase 1) |
| `query.py` | 공개 쿼리 API, `compute_change_impact()` → legacy impact dict |
| `export.py` | JSON/GraphML 영속화, roundtrip |
| `adapter.py` | `TraceabilityGraph` API 미러, legacy fallback |

---

## 3. Node Schema

### 3.1 공통 필드 (모든 노드)

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | `{case_id}:{type_slug}:{normalized_id}` |
| `type` | NodeType | 아래 enum |
| `label` | string | UI/CLI 표시용 |
| `source_file` | string | 프로젝트 루트 기준 상대 경로 |
| `document_type` | string \| null | `spec_requirements`, `ieee_srs`, `operations`, … |
| `case_id` | string | `data/cases/{case_id}` |
| `metadata` | object | 타입별 확장 |
| `raw_text` | string \| null | 원문 스니펫 |
| `normalized_id` | string | `learn.req_ids.normalize_requirement_id` 결과 |

### 3.2 NodeType

#### Phase 1–3 (문서 도메인)

| type | 용도 | 데이터 소스 |
|------|------|-------------|
| `Requirement` | EC-SW `Req. N` | `requirements.json` |
| `FunctionalRequirement` | IEEE `FR-xx` | `requirements.json` |
| `NonFunctionalRequirement` | IEEE `NFR-xx` | `requirements.json` |
| `DesignItem` | MDDR 설계 블록 | `design_items.json` |
| `TestCase` | SRS `TC-xx` | traceability |
| `SecurityControl` | IA/UC/SI/DC/RA | traceability upstream |
| `SecurityTest` | XXCS 시험 행 | `security_tests.json` |
| `Document` | MDSR/MDDR/XXCS 논리 단위 | output DOCX, template |
| `Section` | 문서 섹션 | DOCX 추출 (Phase 2+) |
| `Table` | 표 블록 | DOCX 추출 (Phase 2+) |
| `ChangeRequest` | 변경 요청 | `changes/*.json` |

#### Phase 4+ (Platform 확장)

| type | 용도 |
|------|------|
| `OperationResource` | 추상 운영 자원 |
| `Server` | 호스트/VM |
| `DockerContainer` | 컨테이너 |
| `GPU` | GPU 자원 |
| `LogEvent` | 로그 이벤트 |
| `Incident` | 장애 티켓 |
| `GitCommit` | 코드 변경 |
| `SourceCode` | 구현체 참조 |
| `Prompt` | agent/LLM prompt 버전 |
| `ModelVersion` | 모델 버전 |
| `ResearchNote` | 연구 메모 |
| `Meeting` | 회의록 |
| `Email` | 이메일 |
| `Task` | Planner Task Graph 노드 |

**타입 선택:** `Req. N` → Requirement; `FR-*` → FunctionalRequirement; `NFR-*` → NonFunctionalRequirement.

---

## 4. Edge Schema

### 4.1 공통 필드

| 필드 | 타입 | 설명 |
|------|------|------|
| `source` | string | source node `id` |
| `target` | string | target node `id` |
| `type` | EdgeType | 아래 enum |
| `confidence` | float | 0.0–1.0 |
| `evidence` | string | 사람이 읽을 수 있는 근거 |
| `source_file` | string | 근거 파일 |
| `metadata` | object | 방향, row_index 등 |

### 4.2 EdgeType

| type | 의미 | Phase 1 예시 |
|------|------|-------------|
| `TRACES_TO` | traceability 연결 | SecurityControl → Requirement |
| `IMPLEMENTS` | 설계가 요구사항 구현 | DesignItem → Requirement |
| `VERIFIES` | 시험이 검증 | SecurityTest → SecurityControl |
| `TESTS` | TC가 FR/NFR 시험 | TestCase → FunctionalRequirement |
| `BELONGS_TO` | 하위→상위 소속 | Table → Section → Document |
| `DERIVED_FROM` | 문서/필드 파생 | requirements.json → Document |
| `IMPACTS` | 변경 영향 | ChangeRequest → Requirement |
| `DEPENDS_ON` | 의존 | DockerContainer → GPU |
| `GENERATED_FROM` | 생성 출처 | output DOCX → ChangeRequest |
| `OBSERVED_IN` | 로그 관측 | LogEvent → Server |
| `CAUSED_BY` | 인과 | Incident → LogEvent |
| `MITIGATED_BY` | 완화 | Incident → ChangeRequest |
| `MODIFIED_BY` | 수정 주체 | Requirement → GitCommit |
| `RELATED_TO` | 약한 연관 (orphan fallback) | — |

### 4.3 Traceability 변환 규칙

**EC-SW** (`requirement: "IA-04", linked_reqs: "Req.6, ..."`):

```
SecurityControl(IA-04) --TRACES_TO--> Requirement(Req. 6)
Requirement(Req. 6)    --TRACES_TO--> SecurityControl(IA-04)   [bidirectional query support]
```

**IEEE SRS** (`requirement: "FR-02", linked_reqs: "TC-02"`):

```
FunctionalRequirement(FR-02) --TRACES_TO--> TestCase(TC-02)
TestCase(TC-02) --TESTS--> FunctionalRequirement(FR-02)
```

`TraceabilityGraph.downstream_for_req("Req. 6")`와 **동치**가 되도록 Req → Control 방향을 primary downstream으로 유지한다.

---

## 5. Storage Format

### 5.1 MVP: NetworkX + JSON + GraphML

| 파일 | 경로 |
|------|------|
| `knowledge_graph.json` | `data/cases/{case_id}/knowledge_graph.json` |
| `knowledge_graph.graphml` | `data/cases/{case_id}/knowledge_graph.graphml` |

**런타임:** `networkx.DiGraph`

### 5.2 JSON Envelope

| 필드 | 설명 |
|------|------|
| `schema_version` | `"1.0"` |
| `case_id` | case 식별자 |
| `document_set_hint` | `ec_sw` \| `ieee_srs` |
| `built_at` | ISO timestamp |
| `builder_version` | builder 버전 |
| `source_files` | 입력 파일 목록 |
| `stats` | `node_count`, `edge_count`, `orphan_count` |
| `nodes` | Node[] |
| `edges` | Edge[] |

### 5.3 향후 확장

| 단계 | 저장소 |
|------|--------|
| MVP | NetworkX + case JSON |
| v2 | SQLite per case |
| v3 | Neo4j (MERGE on `id`) |
| v4 | Vector DB (node text embedding) + Neo4j |

**원칙:** `models.py` Node/Edge가 SSOT. DB adapter는 동일 인터페이스.

---

## 6. Builder

### 6.1 `build_graph_from_case(case_path)`

**입력 파일 (존재 시):**

| 파일 | 생성 노드/엣지 |
|------|----------------|
| `requirements.json` | Requirement/FR/NFR, SecurityControl, TestCase, TRACES_TO |
| `design_items.json` | DesignItem, IMPLEMENTS |
| `security_tests.json` | SecurityTest, VERIFIES |
| `changes/*.json` | ChangeRequest, IMPACTS |
| output DOCX | Document (메타, Phase 2) |

**출력:** in-memory `KnowledgeGraph`

### 6.2 Builder 파이프라인

```
case artifacts
  → parse & normalize IDs
  → create nodes
  → create edges (with evidence)
  → detect orphans
  → return KnowledgeGraph
```

---

## 7. Query API

### 7.1 함수 목록

| 함수 | 역할 |
|------|------|
| `build_graph_from_case(case_path)` | case → KnowledgeGraph |
| `find_node(node_id)` | normalized_id 또는 full id 조회 |
| `find_downstream(node_id, edge_types?, max_depth=2)` | 하류 노드 |
| `find_upstream(node_id, edge_types?, max_depth=2)` | 상류 노드 |
| `find_related_requirements(node_id)` | 연결된 요구사항 |
| `find_related_design_items(node_id)` | 연결된 설계 블록 |
| `find_related_tests(node_id)` | 연결된 TC |
| `find_related_security_items(node_id)` | control + xxcs filter |
| `find_related_documents(node_id)` | 영향 문서 action |
| `find_impact_radius(node_id, max_depth=3)` | multi-hop 영향 집합 |
| `explain_path(source_id, target_id)` | 경로 + evidence |
| `compute_change_impact(req_ids)` | **legacy impact dict 반환** |

### 7.2 입출력 예시

**`find_downstream("Req. 6", edge_types=["TRACES_TO"], max_depth=1)`** (mindrium_xa):

| 필드 | 값 |
|------|-----|
| `origin` | `Req. 6` |
| `nodes` | IA-04, IA-06, IA-07, SI-06, DC-01, SI-07, … |
| `edges` | Req.6 → IA-04 (TRACES_TO) |

**`explain_path("Req. 6", "IA-04")`:**

| 필드 | 값 |
|------|-----|
| `found` | true |
| `path` | Req.6 → [TRACES_TO] → IA-04 |
| `evidence` | traceability row IA-04 links Req.6 |

**`compute_change_impact(["Req. 6"])`** → `TraceabilityGraph.impact()` dict와 동일 (섹션 1.2).

**`find_related_tests("FR-02")`** (stt_srs) → `["TC-02"]`

### 7.3 XXCS 필터

| 함수 | 필터 |
|------|------|
| `linked_security_ids` (legacy) | 모든 downstream ID (DC-01, SI-07 포함) |
| `find_related_security_items(xxcs=True)` | IA-/UC-/SI- prefix만 |

Phase 1은 legacy **byte 동치** 유지. eval 라벨 정비는 별도 티켓.

---

## 8. Adapter & Compatibility

### 8.1 TraceabilityGraphAdapter

`impact/graph.py`의 `TraceabilityGraph`를 **즉시 제거하지 않는다**.

```
compute_impact(case_dir, change)
    │
    ├─ [DOCUMENT_AI_USE_KG=1 & knowledge_graph.json exists]
    │       KnowledgeGraph.load → TraceabilityGraphAdapter.impact()
    │
    └─ [else] legacy TraceabilityGraph(traceability).impact()
```

### 8.2 Adapter API (미러)

| 메서드 | legacy 동작 |
|--------|-------------|
| `downstream_for_req(req_id)` | sorted downstream IDs |
| `downstream_for_reqs(req_ids)` | combined sorted |
| `impact(req_ids, design_index?)` | full impact dict |

### 8.3 Legacy Fallback

| 조건 | 동작 |
|------|------|
| `DOCUMENT_AI_USE_KG` unset / `0` | legacy only |
| `USE_KG=1`, JSON missing | on-the-fly build 또는 legacy + warning |
| KG build 실패 | legacy fallback |

---

## 9. Export

| 함수 | 출력 |
|------|------|
| `export_json(graph, path)` | `knowledge_graph.json` |
| `export_graphml(graph, path)` | `knowledge_graph.graphml` |
| `import_json(path)` | KnowledgeGraph |

GraphML: `type`, `label`, `normalized_id` attribute. `raw_text`는 JSON only (truncate in GraphML).

---

## 10. CLI Design (신규, 기존 CLI 불변)

기존 `impact`, `apply-change`, `eval-impact` CLI는 **변경하지 않는다**.

### `build-knowledge`

```powershell
python -m document_ai.cli build-knowledge --case data/cases/mindrium_xa
```

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--case` | required | case 디렉터리 |
| `--output` | case dir | JSON 경로 |
| `--graphml` | true | GraphML 동시 생성 |
| `--force` | false | 덮어쓰기 |

### `query-knowledge`

```powershell
python -m document_ai.cli query-knowledge `
  --case data/cases/mindrium_xa `
  --node "Req. 6" `
  --downstream
```

| 옵션 | 설명 |
|------|------|
| `--node` | normalized_id 또는 full id |
| `--downstream` / `--upstream` | 탐색 방향 |
| `--edge-types` | 콤마 구분 |
| `--max-depth` | 기본 2 |

### `explain-impact`

```powershell
python -m document_ai.cli explain-impact `
  --case data/cases/mindrium_xa `
  --source "Req. 6" `
  --target "IA-04"
```

---

## 11. Test Strategy

### 11.1 신규 테스트 파일

| 파일 | 범위 |
|------|------|
| `tests/test_knowledge_graph.py` | builder, models, query, export |
| `tests/test_knowledge_adapter.py` | legacy vs KG 동치, fallback |
| `tests/test_knowledge_cli.py` | build/query/explain smoke |

### 11.2 필수 테스트

| # | 테스트 | 검증 |
|---|--------|------|
| 1 | `test_req6_traces_to_ia04` | Req.6 → IA-04 |
| 2 | `test_fr02_traces_to_tc02` | FR-02 → TC-02 |
| 3 | `test_adapter_impact_equiv_mindrium` | legacy == adapter impact |
| 4 | `test_adapter_impact_equiv_stt_srs` | FR-02 동치 |
| 5 | `test_orphan_nodes_reported` | orphan count |
| 6 | `test_export_json_roundtrip` | build → export → import |
| 7 | `test_export_graphml_exists` | GraphML 생성 |
| 8 | `test_legacy_fallback_when_kg_missing` | no exception |
| 9 | `test_cli_build_knowledge_smoke` | exit 0 |
| 10 | `test_cli_explain_impact_smoke` | path found |

### 11.3 Regression Gate

- **모든 PR:** `python -m pytest -q` → 55 passed + 신규 KG tests
- `test_knowledge_adapter.py` → 동치성 fast gate
- `eval-impact` golden 변경 없이 통과

---

## 12. Implementation Phases

### Phase 1 — Read-only Builder

| 작업 | 산출물 |
|------|--------|
| `knowledge/models.py`, `graph.py`, `builder.py`, `export.py` | 모듈 골격 |
| `build_graph_from_case` | mindrium_xa, stt_srs |
| `build-knowledge` CLI | JSON + GraphML |
| `tests/test_knowledge_graph.py` | Req.6, FR-02, export |

**완료 기준:** 55 tests pass. `compute_impact` 미변경.

### Phase 2 — Adapter + compute_impact 위임

| 작업 | 산출물 |
|------|--------|
| `adapter.py`, `query.compute_change_impact` | legacy API 미러 |
| `impact/orchestrator.compute_impact` | adapter (flag off = legacy) |
| `tests/test_knowledge_adapter.py` | 4 eval cases 동치 |
| `DOCUMENT_AI_USE_KG` | 기본 `0` |

### Phase 3 — Harness Provenance

| 작업 | 산출물 |
|------|--------|
| `traceability_agent` | `paths`, `provenance` (additive) |
| `impact_report.json` | optional `provenance[]` |
| eval | prediction 스키마 불변 |

### Phase 4 — Operation Nodes

| 작업 | 산출물 |
|------|--------|
| builder 확장 | docker, log, incident ingest |
| Operation Harness 연동 | cross-domain impact PoC |

---

## 13. Risks & Decisions

| 리스크 | 완화 |
|--------|------|
| `networkx` 신규 의존 | `pyproject.toml` core vs `[knowledge]` extra 결정 |
| `impact/graph.py` vs `knowledge/graph.py` 이름 충돌 | import 경로 분리 |
| eval FPR (DC-01 과예측) | Phase 1 동치 유지, 라벨 별도 |
| `knowledge_graph.json` git track | eval reproducibility 위해 초기 track 권장 |

---

## 관련 문서

| 문서 | 역할 |
|------|------|
| [AI Engineering Concept](ai_engineering_concept.md) | WHY — KG가 Platform에서 어떤 역할 |
| [Platform Architecture](platform_architecture.md) | WHAT — Memory Plane, Roadmap |
| `src/document_ai/impact/graph.py` | 현재 TraceabilityGraph 구현 |

---

*Version 0.1 — Design phase, no implementation*
