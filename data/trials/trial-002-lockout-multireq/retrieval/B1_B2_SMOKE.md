# B1–B2 Smoke Report

- created_at: `2026-07-22T21:40:36Z`
- method: lexical_overlap
- top_k: `15`
- expected_impact_used_in_retrieval: `false`
- index blocks: MDSR=38, MDDR=38

## Focus ranks (post-hoc)

- **Req. 6**: rank=3, score=0.316128, doc=MDSR
  - evidence: …애플리케이션 사용을 위한 구체적인 안내를 제공해야 한다. 이러한 에러는 로그인 실패, 세션 만료, 권한 부족 등 다양한 인증 문제를 포함할 수 있다. 에러 메시지는 사용자가 문제를 이해하고 적절한 조치를 취할 수 있도록 명확하고 이해하기 쉬운 언어로 제공되어야 한다.  목적 이 요구사항은 사용자가 인증 문제로 인해 혼란
- **Req. 103**: rank=2, score=0.32697, doc=MDSR
  - evidence: 감사 기록 생성 및 관리 설명 서버는 주요 보안 이벤트에 대한 감사기록을 생성하고 관리해야 한다. 목적 로그인 등 보안 관련 이벤트를 추적하여 비인가 접근 및 이상 행위 발생 시 원인 분석 및 대응이 가능록 하기 위함이다. 기준 로그인 성공 및 실패 이력은 감사 기록으로 생성되어야 한다…
- **Req. 105**: rank=1, score=0.49, doc=MDDR
  - evidence: …로그인 시도를 제한하도록 설계한다. 로그인 실패 및 계정 잠금 이벤트는 감사 기록으로 저장할 수 있도록 설계한다.

## Top-k list

1. `Req. 105` (MDDR) score=0.49 — 감사, 계정, 기록으로, 로그인, 시간, 실패, 이벤트는, 일정, 잠금
2. `Req. 103` (MDSR) score=0.32697 — 감사, 기록으로, 로그인, 실패
3. `Req. 6` (MDSR) score=0.316128 — 로그인, 실패, 안내해야, 알림을, 재시도
4. `Req. 103` (MDDR) score=0.305478 — 감사, 로그인, 실패
5. `Req. 101` (MDSR) score=0.292399 — 감사, 기록으로, 로그인, 실패, 이벤트는, 하며
6. `Req. 110` (MDSR) score=0.269822 — 감사, 계정, 관리자, 기록으로, 남겨야
7. `Req. 102` (MDDR) score=0.253598 — 감사, 기록으로, 로그인, 실패
8. `Req. 2` (MDDR) score=0.220613 — 감사, 계정, 계정을
9. `Req. 102` (MDSR) score=0.220206 — 계정, 관리자, 로그인
10. `Req. 100` (MDSR) score=0.219453 — 감사, 관리자, 기록으로, 남겨야, 하며
11. `Req. 2` (MDSR) score=0.216335 — 감사, 계정, 안내해야, 지원해야, 하며
12. `Req. 101` (MDDR) score=0.199134 — 감사, 기록으로, 실패, 이벤트는
13. `Req. 105` (MDSR) score=0.19748 — 계정, 로그인, 시간, 일정
14. `Req. 109` (MDDR) score=0.175965 — 계정, 시간, 알림을
15. `Req. 7` (MDSR) score=0.170953 — 실패, 안내해야, 재시도

## Top-5 false positives vs expected impacted

- rank 5: Req. 101 (MDSR)

## Limits (lexical baseline)

- Exact string/token overlap only; no embeddings.
- Korean tokenization is naive regex; compounds may mismatch.
- Req.105-in-topk alone is NOT Trial success (B3+ required later).

