# Surviving claim (민주 합의 · 논문 한 줄)

> **다문서 Change Impact → writable scope → μ=(false_patch, unsafe_write, original_broken, unapproved_write) 를 하나의 프로그래밍 벤치로 측정한다.**

## 쓰지 않는 주장

- “첫 pre-write contract” / “첫 unintended-edit metric” — **금지** (LEDGER 등이 선행)
- full LEDGER port 완료 — **아님** (stub 비교 열만)

## 우리 vs LEDGER (한 줄)

- LEDGER: find → edit → **사후** consistency (reference / terminology / hierarchy)
- 우리: **쓰기 전** gate · C1 closure · copy-only · approval 계약을 μ로 벤치

## 용어 고정

| 용어 | 의미 | 아님 |
|------|------|------|
| B4 consistency gate | 규칙 기반 impact consistency | C2 human approval 아님 |
| C1 dependency closure | 의존 확장 | 사람 승인 아님 |
| C2 human approval | 승인 게이트 | closure 아님 |
| Ablation | **sandbox counterfactual** | live에서 안전장치 제거 아님 |
| consistency stub | LEDGER-style 비교 열 (임베딩 θ 금지) | full LEDGER port 아님 |

## Live honesty (PR8)

- Live node closure: **document-native** TRACE + row co-location (not gold topology).
- Gold remains the **scoring** oracle only.
