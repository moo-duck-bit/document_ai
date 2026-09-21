# Document AI v2 — Demo Script (발표용)

발표자가 **그대로 읽을 수 있는** 스크립트입니다. 권장 시연 길이: 12–15분.

준비:

```powershell
pip install -e ".[dev]"
python -m document_ai.cli materialize-pilot-demo
$env:CONTROLLED_WRITER_ENABLED = "false"
uvicorn document_ai.pilot_ui.app:app --port 8000
```

브라우저: `http://127.0.0.1:8000/pilot-v2`

---

## 오프닝 (30초)

> “문서 AI의 목표는 완성본을 학습해, 빈 양식과 새 케이스만으로 문서를 고치는 것이 아닙니다.
> 오늘 Pilot은 **실제 문서를 올리고**, **변경 요청을 넣고**, **사람이 승인하기 전에는 원본에 손대지 않는** 제품 흐름을 보여 드립니다.”

---

## Demo A — EC-SW · Req.11 (4분)

### 1. 어떤 문서를 업로드하는지

> “EC-SW 추적성 행렬 샘플입니다. Req. 10·11·12 행이 있는 MDTM 스타일 표입니다.”

UI: 시나리오 `[ec_sw] EC-SW 단일 Req ID 변경` 선택 → **세션 만들고 업로드**.

### 2. 왜 수정하는지

> “요구사항 11번 기능이 바뀌어서, 추적성 행을 갱신해야 합니다.”

변경 요청 확인: `Req. 11 …`

### 3. AI가 무엇을 찾는지

> “문서 유형을 추천받고, Domain Pack이 EC-SW인지 확인합니다.”

**유형 분석 실행** → 필요 시 **추천대로 확정** → **분석 실행**.

> “영향 후보와 REVIEW 사유가 한국어로 나옵니다. 내부 코드명 대신 사람이 읽을 문구입니다.”

### 4. Review를 어떻게 보여주는지

항목 카드에서 문서·사유·근거를 가리킨다.

### 5. Approval

> “이 항목만 **승인**, 나머지는 **보류**로 두고 결정을 저장합니다.”

### 6. Writer

> “지금은 Writer를 꺼 두었습니다. 켜더라도 **승인 + 체크박스 + 환경 변수**가 모두 필요합니다.
> 결과는 원본이 아니라 세션 복사본입니다.”

(시간 있으면 `CONTROLLED_WRITER_ENABLED=true` 후 복사본 생성.)

### 7–8. Diff · Validation

결과 화면에서 Writer 상태, 원본 변경 여부(아니오), 다운로드 링크를 보여준다.

### 9. 결과

> “한 세션 안에서 업로드부터 검토·안전 게이트까지 끊기지 않습니다.”

---

## Demo B — 일반 보고서 · 방법론 (3분)

시나리오: `[general_report] 일반보고서 방법론 문단 수정`

> “연구 진행 보고서에서 방법론에 데이터 출처를 보강하라는 요청입니다.
> 표나 Req ID가 없어도 섹션을 찾아 후보를 올립니다.”

흐름: 업로드 → 유형 확인 → 분석 → 검토 → 결과.

강조:

> “잘못된 섹션을 건드리지 않도록 **사람이 승인**합니다.”

---

## Demo C — 사업 제안서 · 예산 (3분)

시나리오: `[business_proposal] 사업제안서 예산표 수정`

> “예산 표·인건비 항목 변경입니다. 금액·일정은 자동 승인하지 않습니다.”

흐름 동일. 인건비 고위험 케이스는 별도 시나리오(`demo_bp_labor_cell`)로 “자동 쓰기 없음”을 짧게 언급.

---

## Safety 클로징 (1분)

> “원본 변경 0, 승인 없는 Writer 0, 경로 탈출 차단.
> Benchmark는 이미 Holdout F1 0.956 / E2E 0.957 / False Patch 0으로 고정되어 있고,
> 오늘은 그 엔진을 **실제 사용자가 만질 수 있는 Pilot**으로 포장한 것입니다.”

체크리스트: `docs/pilot/PILOT_CHECKLIST.md`

---

## CLI 백업 (UI 장애 시)

```powershell
python -m document_ai.cli run-pilot-demo
# 결과: data/pilot/demo/results/<run_id>/DEMO_RUN_SUMMARY.json
```

---

## Q&A 대비

| 질문 | 답 |
|------|----|
| LLM 쓰나요? | Pilot 경로에서 원격 LLM/임베딩 없음 |
| 원본이 바뀌나요? | 아니요. 세션 복사본만 |
| 새 Domain Pack? | 이번 단계 없음. EC-SW / GR / BP |
| Gold를 Pilot으로 고치나요? | 금지 |
