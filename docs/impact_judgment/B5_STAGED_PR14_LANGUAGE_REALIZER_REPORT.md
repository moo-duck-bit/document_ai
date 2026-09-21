# B5 Staged Architecture — PR-14 Language Realizer 보고서

**최종 판정:** `READY_FOR_STAGED_B5_PR15`  
**범위:** Requirement Language Realizer (shadow, rule-based) + **PR-14.1 regression fix**  
**일자:** 2026-07-26

---

## 1. Objective

Requirement Patch가 생성한 `patched_requirement`를  
사람이 읽을 수 있는 자연스러운 요구사항 문장으로 **표면 후처리**한다.

- Semantic Draft **미변경**
- Requirement Patch 모듈 의미 **미변경**
- Activation Policy / Preview 코드 **미변경**
- DOCX / Legacy generation **미연결·미변경**
- 의미 추론·신규 내용 추가 **금지**
- 정상 문장 단일 문체 강제 통일 **금지** (PR-14.1)

```text
Requirement Patch
  → Language Realizer (exact / allowlist only)
  → Activation Policy
  → Activation Preview
```

---

## 2. Architecture

모듈: `src/document_ai/impact/language_realizer.py`

| 컴포넌트 | 역할 |
|----------|------|
| `EXACT_REPLACEMENTS` | 완전 phrase 치환 |
| `SAFE_REGEX_RULES` | 좁은 범위 regex |
| `normalize_whitespace` | 공백·문장부호만 |
| `validate_realization` | unsafe → rollback |
| `realize_requirement_text` | 오케스트레이션 |
| `realize_requirement_patches` | runner payload |

적용 순서: exact → narrow regex → whitespace → safety validation → unsafe면 `before_text`.

---

## 3. LanguageRealization Schema

| Field | 의미 |
|-------|------|
| `before_text` / `after_text` | 정제 전·후 |
| `applied_rules` / `rule_count` | 적용 규칙 |
| `semantic_changed` | 수용 경로에서는 항상 `false` |
| `meaning_preserved` | 숫자·부정·조건·보안명사·token 보존 |
| `requirement_style` | broken ending만 검사 (혼용 허용) |
| `rejected` / `rejection_reasons` | optional rollback trace (PR-14.1) |
| `unsafe_pattern_detected` | optional |

---

## 4. Regression Cause (PR-14.1)

| 원인 규칙 | 증상 |
|-----------|------|
| `requirement_style`: `도록 설계한다` → `야 한다` | `제한하야 한다` / `있야 한다` / `않야 한다` |
| 광역 `particle_i_ga` | `비인가` → `비인이` |
| `시인 경우` → `시` 후 과도한 공백/토큰 처리 | `실패 시 시스템`이 `실패 시스템`으로 붕괴 가능 |
| 문체 혼용 시 강제 통일 | 정상 design-style 문장 훼손 |

---

## 5. Over-broad Rule Removal

**삭제/비활성화:**

- `_rule_requirement_style` (도록→야 강제 변환)
- `_rule_particle_eul_reul` / `_rule_particle_i_ga` / `_rule_particle_eun_neun` (광역 조사)
- 광역 duplicate word regex (`([가-힣]{2,})\s+\1`)
- phrase dictionary의 광역 `계정을 잠그` 등 불필요 항목

**축소:**

- 조사 수정 → allowlisted exact phrase만 (`이벤트을` → `이벤트를`, `은(는)` 등)
- 알림 중복 → `알림에 대한 알림` → `알림` (신규 주어 삽입 금지)

---

## 6. Exact-match / Allowlist Strategy

Exact 예:

| before | after |
|--------|-------|
| `시인 경우` | `시` |
| `잠그해야 한다` | `잠가야 한다` |
| `알림에 대한 알림` | `알림` |
| `대상을 해제` | `계정 잠금을 해제` |
| `계정, 기록 및 이벤트을` | `계정 잠금, 로그인 실패 및 관련 이벤트를` |
| `이벤트을` | `이벤트를` |

유지 (변환 금지):

- `~하도록 설계한다`
- `~할 수 있도록 설계한다`
- `~하지 않도록 설계한다`
- `~해야 한다` / `~되어야 한다` / `~할 수 있어야 한다`

---

## 7. Safety Rollback

`validate_realization(before, after)` 실패 시:

- `after_text = before_text`
- `rejected=true`, `rejection_reasons` 기록
- `validation_status=REVIEW_REQUIRED`
- silent accept 금지

금지 after 패턴: `하야 한다`, `있야 한다`, `않야 한다`, `비인이`, `실패 시스템은`, `잠그해야`, design-style 무단 변경 등.

의미 보존: 숫자, 부정·조건 마커, 보안 명사, 과도한 token 삭제 금지.

---

## 8. Idempotency

`realize(realize(text)) == realize(text)` — regression tests로 고정.

---

## 9. Before/After corrected examples

| before | after (PR-14.1) |
|--------|-----------------|
| `제한하도록 설계한다.` | **원문 유지** |
| `저장할 수 있도록 설계한다.` | **원문 유지** |
| `중단하지 않도록 설계한다.` | **원문 유지** |
| `…시인 경우 … 잠그해야 한다.` | `…시 … 잠가야 한다.` |
| `비인가 접근` | **원문 유지** |

Lockout fixture: design-style 문장 유지 + `시인 경우`/`잠그해야`만 수정.

---

## 10. Artifacts

Runner shadow (시나리오 실행 시):

| File | Content |
|------|---------|
| `language_realization.json` | realizations + validation |
| `language_summary.json` | rule/change/rejected counts |
| `language_vs_patch.json` | before/after pairs |

확인: `제한하야 한다` / `있야 한다` / `않야 한다` / `비인이 접근` / `연속 로그인 실패 시스템은` **0건**.  
`actual_docx_changed=false`, `actual_generation_changed=false`.

---

## 11. Tests

`tests/test_b5_staged_pr14_language_realizer.py` (**28**)

- PR-14 핵심 + PR-14.1 regression fixtures
- design-style 3종 원문 유지
- `시` 보존, `비인가` 보존, idempotency, unsafe rollback
- lockout / audit exact fixtures

---

## 12. Full pytest 결과

```text
python -m pytest -q
→ 577 passed in 155.16s (0 failed, 0 skipped)
```

PR-14 초기 563 → PR-14.1 테스트 보강 후 **577**. 회귀 없음.

---

## 13. Compatibility / Freeze

변경 금지 유지: Semantic Draft, Requirement Patch, Activation Policy/Preview, DOCX, Legacy, Scenario-001 freeze.  
Scenario-001 / Trials **미재실행·미수정**.

---

## 14. Known Limitations

- allowlist에 없는 어색한 표현은 수정하지 않음
- LLM 미사용
- Language Realizer ≠ DOCX 반영

---

## 15. Next PR 제안 (PR-15)

- Realized preview human-review artifact
- dual-write side-by-side
- DOCX cutover는 별도 승인

**Final judgment:** `READY_FOR_STAGED_B5_PR15`
