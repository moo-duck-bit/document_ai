# MDDR Validation Diagnosis

> **Historical (lab_ec_sw / JM COLLECTION)** — **Not used in Trial 1**  
> 이 문서는 과거 스프린트·벤치마크·진단 기록이다.  
> Real-world Trial 1 확정 case는 **Mindrium XA** (`trial-001-mindrium-xa`)이다.  
> Trial 1 문서: `docs/trial1_case_decision_mindrium.md`, `docs/README.md` § Trial 1


**Date:** 2026-07-14  
**Case:** `data/cases/lab_ec_sw`  
**Gold:** `data/cases/jm_collection/output_mddr.docx`  
**Baseline:** MDDR validation **75.3**, design block coverage **5.3%**

---

## Symptom

| Metric | Value |
|--------|------:|
| gold_design_block_count | 38 |
| generated_design_block_count | 38 |
| design_block_count_match | 1.0 |
| design_block_text_similarity | 1.0 |
| design_block_coverage | **0.053** |
| MDDR score | **75.3** |

Req ID 집합은 gold/generated가 동일하다. 점수 하락의 주원인은 **coverage 정의와 추출 필드 불일치**이다.

---

## Root cause (extraction)

MDDR 설계 블록은 Mindrium 스타일로 **한 paragraph**에 저장된다.

```
Req. 1
<design body text...>
```

`extract_design_items.REQ_PARAGRAPH` 패턴:

```text
^Req\.\s*(\d+)\.?\s*(.*)$
```

여기서 `\s*`가 **개행(\n)을 소비**하고, `(.*)`가 본문 전체를 `title_suffix`로 캡처한다.
추출기는 `continue`로 본문을 `design_description`에 넣지 않는다.

Coverage 계산 (`validation/runner.py`):

```python
filled = sum(1 for item in gen_items if item.get("design_description", "").strip())
```

`title_suffix`는 무시 → 38개 중 후속 paragraph 본문이 있는 **2개만 filled** → **2/38 ≈ 5.3%**.

검증:

| Stage | Finding |
|-------|---------|
| DOCX paragraph | 38개 모두 `Req. N\n<body>` (단일 paragraph, newline) |
| Extractor | 38 items, `block_kind=paragraph`, 대부분 `design_description=""`, 본문은 `title_suffix` |
| Matcher | Req ID match 완벽 (missing/extra 없음) |
| Render | 내용 존재; extractor가 본문을 잘못된 필드에 둠 |

**Mismatch 위치:** `extract_design_items` + coverage 집계 (render/mddr 생성물 자체는 본문 보유).

---

## Secondary gaps

1. **Section-prefixed headings** (`4.2.1 Req. 1`, `5.2.3 Req. 102`) — 현재 regex 미지원.
2. **표 내부 Req 블록** — `_item_from_req_table` 존재하나 jm/lab MDDR는 paragraph 중심.
3. **Run 분할** — 현재 샘플은 run=1; deep text / first-line split으로 방어 필요.
4. **Coverage 의미** — “동일 Req ID 존재 여부”가 아니라 “non-empty design_description”에 종속되어 gold≈gen이어도 점수 붕괴.
5. **force-generate quality FAIL (과거)** — `JM-web` 등 product_code 토큰을 `mindrium_brand` residual로 오탐 (analyzer allow_brand로 완화됨). 재생성 시 중복 블록 여부도 확인 대상.

---

## Fix plan

1. Extractor: first-line / body split; section prefix; table + paragraph; `title_suffix`를 설계 본문으로 승격.
2. Matcher: Req ID 우선 coverage; 본문 유사도는 보조 지표 (`design_text` = suffix + description + fields).
3. Render: consolidate 유지, 중복 Req patch 방지, extractor가 읽는 형식 보장.
4. force-generate: brand allow + deterministic regenerate 후 quality PASS 확인.

---

## Success criteria

- design block coverage ≥ 50% (목표: ~100% on lab_ec_sw self-aligned gold)
- MDDR validation ≥ 85
- `project-validate --force-generate` quality PASS
- Existing tests remain green
