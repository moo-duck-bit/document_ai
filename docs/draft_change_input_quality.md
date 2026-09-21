# draft-change 입력 품질 가이드 (Trial 1 준비)

> **Trial 1 (Mindrium XA) — 현재 사용 문서**  
> case: `data/cases/mindrium_xa` · trial_id: `trial-001-mindrium-xa`  
> 과거 lab_ec_sw / JM COLLECTION 기준 문서와 혼동하지 말 것.  
> 인덱스: `docs/README.md` § Trial 1


> 이 문서는 **parser 입력 품질 검증**용이다.  
> Real-world Trial의 최종 입력·정답·Human Revised를 대체하지 않는다.  
> `impact` / `apply-change`는 이 단계에서 수행하지 않는다.

## 1. 기대하는 자연어 입력 수준

`draft-change`는 **자유 형식 텍스트**를 받는다 (고정 Markdown 스키마 없음).

**잘 되는 입력의 최소 조건**

1. **변경 대상 Req ID를 명시** — `Req. 6` 형식 (권장: 한 파일에 하나)
2. **변경 후 description 전문** — “바꿔줘”가 아니라 shall 문장 전체
3. 파서가 인식하는 구분 형식 사용 (아래 권장 패턴)

**mindrium_xa / Trial 1 기준 주의**

- 변경 대상 기본안은 **`Req. 6`** (`changes/request_req6.txt`).
- 원본 MDSR에서 Req. 6 description은 **비어 있음** → 이 변경은 “기존 문장 수정”보다 **빈 칸 기입(fill)**에 가깝다.
- `lab_ec_sw`의 Req. 105(로그인 5회/15분)는 Trial 1 case가 아님.

**잘못된 혼동 금지:** lab_ec_sw Req.6(검색 등)과 mindrium Req.6(로그인 잠금 to-be)을 섞지 말 것.

## 2. Parser가 추출하는 것 / 못 하는 것

| 추출 가능 | 추출 불가 (사람·후속 단계) |
|-----------|---------------------------|
| `Req. N` / `요구사항 N` / `FR-n` 등 Req ID | Platform vs App 별도 필드 구조화 |
| `IA/UC/SI/DC/RA-xx` (traceability로 Req 확장; 다수면 clarifying) | MDDR 설계·XXCS 시험행 직접 생성 |
| 따옴표 / `설명:` / `→` / `Req. N:` 뒤 description | 회의록·Q&A·공지 메타데이터 |
| keyword overlap Req 후보 (불안정, 오탐 가능) | as-is 수치의 구조화된 before/after |
| `summary` 자동 (짧고 일반적) | 문서 섹션 단위 적용/제외 범위 |
| `change_id`, `intake.*`, `sync_design_from_requirement` | Ground Truth / 최종 문서 |

**중요 한계**

- 찾은 **모든 Req ID에 동일한 description**이 붙는다 → **Req당 파일 1개**.
- keyword-only는 잘못된 Req에 `confirmed=true`가 될 수 있다 → **Req ID 필수**.
- `"을 다음과 같이 변경:"` 패턴은 description 앞에 **`변경:`이 남을 수 있음** → `Req. 6:` 또는 따옴표/`→` 권장.

## 3. 로그인 실패 정책 — Trial 1 (`mindrium_xa`) 입력 후보

파일: `data/cases/mindrium_xa/changes/request_req6.txt`

권장 형식 (dry-run 시 description 접두 오염 최소화):

```text
Req. 6:
연속 로그인 실패 시 계정 잠금 및 관리자 알림을 수행해야 한다.
잠금 해제는 관리자 승인 또는 일정 시간 경과 후 자동 해제 중 하나를 지원해야 한다.
```

```powershell
$env:PYTHONIOENCODING='utf-8'
python -m document_ai.cli draft-change `
  --case data/cases/mindrium_xa `
  --request-file data/cases/mindrium_xa/changes/request_req6.txt `
  --dry-run
```

성공 기준: `intake.confirmed=true`, `parsed_req_ids=["Req. 6"]`.

> 원본 MDSR as-is 추출이 아닌 **준비된 to-be**. Trial 채택 시 발표에 「실문서 + 준비된 Req.6 CR」로 명시.

## 4. 자동 생성 JSON 필드 (예시 결과 형태)

```json
{
  "change_id": "chg-YYYYMMDD-xxxxxx",
  "summary": "Req. 6 업데이트",
  "sync_design_from_requirement": true,
  "intake": {
    "channel": "natural_language",
    "raw_request": "<원문>",
    "parsed_req_ids": ["Req. 6"],
    "parsed_security_ids": [],
    "confidence": 0.9,
    "clarifying_questions": [],
    "confirmed": true
  },
  "requirement_changes": [
    {
      "req_id": "Req. 6",
      "description": "<변경 후 shall 문장>"
    }
  ]
}
```

| 필드 | 출처 |
|------|------|
| `change_id` | 날짜 + uuid 자동 |
| `summary` | Req ID 기반 기본값 (또는 `--summary`) |
| `sync_design_from_requirement` | 기본 `true` |
| `intake.*` | 파서 메타 |
| `requirement_changes[]` | 파서/명시 |

CLI로 덮어쓰기: `--req`, `--description`, `--summary`.

## 5. 사람 필수 vs 파서 추론

| 사람이 반드시 명시 | 파서가 추론·자동 |
|--------------------|------------------|
| 변경 대상 `Req. N` (권장 정확히 하나) | `change_id` |
| **변경 후** description 전문 | `summary` (부정확 가능 → `--summary` 권장) |
| Platform/App·횟수·시간·관리자·감사·UI를 description 문장에 직접 쓰기 | `sync_design_from_requirement=true` |
| 여러 Req이면 파일 분리 | security ID→Req 확장 (모호하면 clarifying) |
| Trial용 회의록 등은 **별도 input** (draft-change 범위 밖) | confidence / confirmed |

## 6. Trial 1 입력 작성 가이드라인

1. 첫 줄: `Req. 6:` (또는 따옴표 / `Req. 6 → …`)
2. 그 아래: **변경 후** shall 문장만
3. **한 파일 = 한 Req**
4. `draft-change --dry-run`으로 `confirmed`·`req_id`·description 확인 후 저장
5. keyword-only 금지
6. lab_ec_sw Req.105 예시를 mindrium Trial에 그대로 쓰지 말 것
7. 운영 공지 전체가 아니라 description으로 쓸 문장만

## 검증 시 하지 말 것

- `impact` / `apply-change` 실행
- 이 예시를 Ground Truth·Human Revised로 저장
- 파서 description을 “운영 확정 정책”으로 간주 (사람이 CR과 대조)
