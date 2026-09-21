# Reviewer Instructions — `hospital_reservation` (Holdout)

## 검토 목적

이 패키지는 **frozen holdout** 케이스 `hospital_reservation`의 생성 문서가
Independent Gold로 승격 가능한지 **사람 검토**하기 위한 것이다.

- 시스템 규칙을 바꿔 점수를 올리지 않는다.
- Holdout 점수를 맞추기 위해 generation / form-fill을 튜닝하지 않는다.
- 승인은 **문서 품질·도메인 적합성**에만 근거한다.

## 제공 파일

| 파일 | 설명 |
|------|------|
| `generated_mdsr.docx` | 시스템이 생성한 MDSR |
| `generated_mddr.docx` | 시스템이 생성한 MDDR |
| `human_review_checklist.md` | 자동 생성 체크리스트 |
| `gold_fields_review.json` | 구조화 라벨 (Req/Design/Traceability) |
| `review_result.template.json` | 결과 기입용 템플릿 → `review_result.json`으로 저장 |
| `reviewer_instructions.md` | 본 문서 |

## 문서별 검토 방법

### MDSR (`generated_mdsr.docx`)

1. 표지·제품명·도메인이 병원 예약 시스템에 맞는지 확인
2. Req. 표: 설명/목적/기준이 비어 있지 않은지
3. Traceability (IA/UC/SI) linked_reqs가 Req ID와 연결되는지
4. 잔여 placeholder (`XX-XX-XXXX`)·이커머스 용어 혼입 여부

### MDDR (`generated_mddr.docx`)

1. 각 Req. 설계 블록 본문이 요구사항과 대응하는지
2. 그림/표 캡션이 placeholder로만 남아 있어도 되는지(의도적 vs 차단)
3. 컴포넌트·API 서술이 병원 예약 맥락인지

### `gold_fields_review.json`

1. `requirement_ids` / `design_ids` 누락·중복
2. `requirement_text` / `design_text`가 DOCX와 대략 일치하는지
3. `traceability_rows` linked_reqs 형식

## 수정 가능 항목

Reviewer가 **직접 고쳐도 되는 것** (승인 전):

- 오탈자, 명백한 도메인 오용 용어 (병원 맥락으로 교정한 사본)
- `gold_fields_review.json` 라벨 오류
- checklist 코멘트 / `review_result.json` 기록

**금지 (이 holdout sprint에서):**

- form-fill / replacement rule / Platform 코드 변경으로 점수 올리기
- holdout case를 train으로 재분류
- gold를 생성 결과에 맞춰 자의적으로 축소해 coverage만 높이기

교정 DOCX를 gold로 쓰려면 검토 완료 후 별도 폴더에 저장하고,
승인 시 해당 파일을 case `output_*.docx`로 반영한 뒤 bootstrap한다
(또는 bootstrap 전에 case output을 교정본으로 교체).

## 승인 기준 (Approve)

다음을 **모두** 만족하면 `approval_decision: approve`:

1. MDSR/MDDR 모두 `mdsr_status` / `mddr_status` = `accept` 또는 `accept_with_nits`
2. 5개 Likert(1–5) 점수의 **평균 ≥ 4.0**
3. `required_changes`가 비어 있거나, nits만 있고 문서 사용에 치명적이지 않음
4. 도메인(병원 예약) 서술과 규제 언급이 case facts와 모순되지 않음
5. Traceability가 주요 Req과 연결됨

## Reject 기준

하나라도 해당하면 `reject` 또는 `revise`:

- 제품/도메인이 병원 예약과 무관하거나 명백한 타 도메인 잔재가 다수
- 핵심 Req/Design 블록 다수 공란 또는 잘림
- Traceability가 실질적으로 비어 있거나 오연결
- 규제/표준 언급이 case와 심각하게 불일치
- Reviewer 판단상 gold로 쓰기에 위험

`revise`: 수정 후 재검토 가능. `reject`: 이번 라운드 gold 승격 불가.

## provisional vs human_approved

| 상태 | 의미 |
|------|------|
| **provisional** | 시스템 output을 복사한 임시 gold. 논문 claim용 독립 gold가 **아님** |
| **human_approved** | 본 절차로 reviewer가 승인한 gold. holdout 보고에 사용 가능 |

## Holdout freeze 원칙

1. `hospital_reservation`는 **holdout**으로 고정한다.
2. 승인 전후로 generation 규칙을 holdout 점수 때문에 바꾸지 않는다.
3. 승인 후 gold를 freeze하고, 이후 시스템 변경의 효과는 **별도 실험**으로 기록한다.
4. Self-gold(생성물=gold 복사) provisional 점수는 tooling smoke용으로만 인용한다.

## 검토 후 할 일

1. `review_result.template.json`을 복사 → `review_result.json` 작성
2. (선택) 교정 DOCX를 case output에 반영
3. 요약: `python -m document_ai.cli document-review-summary --case hospital_reservation`
4. 승인 시에만:
   ```powershell
   python -m document_ai.cli document-bootstrap-gold --case data/cases/hospital_reservation --split holdout --approve
   ```
