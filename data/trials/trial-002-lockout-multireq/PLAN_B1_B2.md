# Trial 2 — B1–B2 구현 계획 (Semantic Retrieval MVP 진입 전)

> trial: `trial-002-lockout-multireq`  
> 범위: **B1 Requirement-level indexing** + **B2 Semantic candidate retrieval**만  
> B3–B6는 본 계획 승인·B1–B2 동작 확인 후 착수  
> Trial 1 코드 경로를 “성공으로 고치기” 위해 수정하지 않음. 신규 모듈 우선.

---

## 1. 목표

| ID | 목표 | 완료 정의 |
|----|------|-----------|
| B1 | MDSR/MDDR를 Req·의미 블록 단위로 인덱싱 | Mindrium reference에서 Req.6/103/105 블록이 ID·제목·본문·키워드·문서종류와 함께 조회됨 |
| B2 | CR → top-k 후보 | `change_request.txt` 입력 시 후보 목록에 **Req.105** 포함 + score·snippet·rank·document 기록 |

첫 검증 포인트: **Req.105가 적절한 순위의 후보에 있는가?**

---

## 2. 설계 요지

### B1 Index unit (`RequirementBlock`)

최소 필드:

```text
req_id
title
body_text          # 설명·목적·기준 등 결합 또는 분리 필드
keywords           # 잠금/감사/인증 등 (규칙+추출)
document_type      # MDSR | MDDR
source_path
trace_security_ids # 가능 시 requirements.json traceability
locator            # paragraph/table hint (optional)
```

추출 전략 (권장):

1. **1차:** 기존 `extract_design_items_docx` / OOXML·paragraph deep text 패턴 재사용 (MDDR)
2. **MDSR:** Trial 1에서 확인된 것처럼 python-docx 표 셀이 비는 경우가 있음 → **document.xml plain 또는 paragraph_deep_text**로 Req.N 블록 슬라이스
3. **Traceability:** `data/cases/mindrium_xa/requirements.json`의 IA-07 등 링크를 블록 메타에 부착 (검색 힌트; Exact-ID 대체가 아님)

인덱스 산출물 (Trial 전용):

- `retrieval/index_mdsr.jsonl`
- `retrieval/index_mddr.jsonl`
- (선택) `retrieval/index_meta.json`

### B2 Retrieval

입력: CR 문자열 (Exact-ID 없음 가정)

방법 (MVP, 단계적):

| Step | 방법 | 이유 |
|------|------|------|
| 1 | 한국어 토큰 overlap / TF 유사도 | 의존성 적음, 재현 가능 |
| 2 | (선택) 기존 embedder 있으면 벡터 top-k | Trial 2 후반 강화 |

출력 레코드 필수:

```text
candidate_id (req_id)
document (MDSR|MDDR)
score
rank
retrieval_reason | evidence_snippet
```

산출물:

- `retrieval/candidates.json` (CR 1회 실행 결과)
- CLI 또는 `python -m document_ai...` / `scripts/run_trial002_index_retrieve.py`

**금지:** `expected_impact.json`의 Req 목록을 retrieval 점수에 가산·주입.

---

## 3. 변경 예정 파일 목록

### 신규 (권장)

| 경로 | 역할 |
|------|------|
| `src/document_ai/impact/semantic_index.py` | B1: DOCX → RequirementBlock 리스트 / JSONL 저장 |
| `src/document_ai/impact/semantic_retrieve.py` | B2: CR → scored candidates |
| `scripts/run_trial002_index_retrieve.py` | Trial 2 reference 대상 인덱스+검색 실행 |
| `tests/test_semantic_index_retrieve.py` | Mindrium fixture 또는 trial reference로 Req.105 포함 assert |
| `data/trials/trial-002-lockout-multireq/retrieval/` | 실행 산출 |

### 기존 (읽기·얇은 연동만)

| 경로 | 사용 |
|------|------|
| `src/document_ai/learn/extract_design_items.py` | MDDR 블록·normalize 재사용 |
| `src/document_ai/learn/docx_io.py` / `iter_blocks` | 문서 순회 |
| `src/document_ai/learn/req_ids.py` | ID normalize |
| `data/cases/mindrium_xa/requirements.json` | traceability 메타 (읽기) |
| `data/trials/trial-001-mindrium-xa/reference/*.docx` | **읽기 전용** 소스 (복사해 trial-002/reference에 두는 것 권장) |

### 건드리지 않음 (이번 B1–B2)

| 경로 | 이유 |
|------|------|
| `data/trials/trial-001-mindrium-xa/**` | Freeze |
| `src/document_ai/impact/preserve_patch.py` | B5 이전 |
| Exact-ID만으로 단정하는 intake 강제 경로 | B2 검증 후 연동 |
| XXCS / form_fill / collaboration | 범위 외 |

---

## 4. 구현 순서 (B1–B2만)

1. Trial 2 `reference/`에 Mindrium MDSR/MDDR **복사** (Trial 1 reference와 동일 바이트, 독립 경로)
2. `semantic_index.py`: MDSR·MDDR 인덱싱 → JSONL
3. 스모크: 인덱스에 Req.6 / 103 / 105 존재 assert
4. `semantic_retrieve.py`: `input/change_request.txt` → top-k
5. `retrieval/candidates.json` 저장
6. 수동/테스트: **Req.105 rank 확인**
7. 보고서 초안: `retrieval/B1_B2_SMOKE.md` (PASS/FAIL만, 전체 Trial 성공으로 확대 해석 금지)

---

## 5. 완료 게이트 → B3 진입 조건

- [ ] B1 인덱스에 Req.105 body에 잠금·임계치 관련 텍스트 존재
- [ ] B2가 Exact-ID 없는 CR로 Req.105를 후보에 포함
- [ ] candidates.json에 score·snippet·rank·document 완비
- [ ] expected_impact를 retrieval에 주입하지 않음

이후: B3 impact judgment → B4 consistency → B5 MDDR → B6 trace.

---

## 6. 리스크

| 리스크 | 완화 |
|--------|------|
| MDSR 표 셀 공란 | OOXML/deep text 블록 슬라이스 |
| 키워드만으로 과다 후보 | top-k + B3 judgment 분리 (이번엔 검색만) |
| embedder 환경 편차 | MVP는 lexical 먼저 |
