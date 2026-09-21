# B4 Semantic Consistency Report

- created_at: `2026-07-22T22:03:21Z`
- IMPACTED ≠ automatic patch permission
- expected_impact_used_in_gate: `false`

Summary: {'CONSISTENT': 2, 'CONFLICT': 1, 'NEEDS_REVIEW': 0}

| Req | Status | Auto-patch | Reason (short) |
|-----|--------|------------|----------------|
| Req. 103 | **CONSISTENT** | True | CR audit-of-lockout events is a scope extension of an audit-primary requirement; no title/purpose role conflic |
| Req. 6 | **CONFLICT** | False | CR lockout-policy themes ['계정 잠금', '잠금', '자동 해제', '관리자 승인', '연속 로그인 실패'] conflict with existing UX-primary tit |
| Req. 105 | **CONSISTENT** | True | CR lockout policy themes align with existing abuse-prevention / login-limit responsibility; no UX-title vs pol |

## Focus evidence (Req.6 / 103 / 105)

### Req. 103 — CONSISTENT
- reason: CR audit-of-lockout events is a scope extension of an audit-primary requirement; no title/purpose role conflict detected.
- proposed_resolution: Extend criteria/description to include account-lock and unlock audit events; do not replace unrelated patient-registration audit clauses.
  - [title] Audit-primary requirement: `감사 기록 생성 및 관리`
  - [criteria] Existing audit coverage hits=['로그인 성공', '실패']; lock events missing=True: `로그인 성공 및 실패 이력은 감사 기록으로 생성되어야 한다.
의료진에 의한 환자 등록 이력은 감사기록으로 생성되어야 한다.
감사기록에는 발생 일시, 사용자 식별자, 이벤트 유형, 요청 출처, 처리 결과를 포함해야 한다.
감사기록은 파일 기반으로 저장하`
  - [change_request] CR extends audit event scope — aligns with audit role, not a title conflict: `로그인 실패·계정 잠금·잠금 해제 이벤트는 감사 기록으로 남겨야 한다`

### Req. 6 — CONFLICT
- reason: CR lockout-policy themes ['계정 잠금', '잠금', '자동 해제', '관리자 승인', '연속 로그인 실패'] conflict with existing UX-primary title/purpose for Req. 6. Applying CR text to description would reproduce Trial-1 internal semantic inconsistency (policy text under UX title).
- proposed_resolution: Do NOT auto-patch description with lockout policy. Keep Req as UX owner; map policy changes to Req.105; optional UX-only criteria refine under human review.
  - [title] Existing role is auth-error UX guidance: `서버와의 통신 중 인증 관련 에러 발생 시 사용자 안내`
  - [purpose] Purpose centers on user clarity / no sensitive leak — not lockout policy: `이 요구사항은 사용자가 인증 문제로 인해 혼란을 겪거나 애플리케이션 사용을 중단하지 않도록 하기 위함이다. 명확한 에러 메시지와 적절한 조치 안내를 통해 사용자 경험을 개선하고, 인증 정보 또는 내부 시스템 정보가 오류 메시지를 통해 노출되지 않도록 `
  - [change_request] CR introduces account-lockout *policy* (admin unlock / auto unlock): `연속 로그인 실패 시 계정을 잠그고… 관리자 승인 또는 … 자동 해제`
  - [criteria] Criteria already covers lock-state *guidance* (UX), not policy ownership: `로그인 실패가 설정된 횟수 이상 발생한 경우, 애플리케이션은 사용자에게 로그인 제한 상태 및 재시도 방법을 안내해야 한다.`

### Req. 105 — CONSISTENT
- reason: CR lockout policy themes align with existing abuse-prevention / login-limit responsibility; no UX-title vs policy-body conflict (title IP framing is compatible extension, not hard conflict).
- proposed_resolution: Patch description/criteria to incorporate consecutive-failure account lockout and unlock policy without dropping existing DoS/IP controls.
  - [title] Policy/limit-oriented title: `API 요청 과다 방지 및 IP 차단`
  - [description] Existing policy cues=['차단', '과다']: `서버는 과도한 API 요청 또는 비정상적인 접근 시도를 탐지하고, 설정된 정책에 따라 요청 제한 또는 접근 차단을 수행해야 한다.`
  - [change_request] CR strengthens login-failure lockout policy — same responsibility family: `연속 로그인 실패 시 계정 잠금 / 자동 해제 / 관리자 승인`
  - [title_vs_cr] Title emphasizes IP/rate-limit; CR uses account-lock wording — same family, extend carefully: `API 요청 과다 방지 및 IP 차단`

