# B5 Propagation Report

- created_at: `2026-07-22T22:03:22Z`
- expected_impact_used_in_propagation: `false`

Summary: {'PATCHED': 2, 'SKIPPED_WITH_REASON': 1, 'NEEDS_REVIEW': 0}

| MDSR | B4 | MDDR candidate | Outcome | Reason (short) |
|------|----|----------------|---------|----------------|
| Req. 103 | CONSISTENT | Req. 103 (MDDR) | **PATCHED** | MDSR CONSISTENT and MDDR design responsibility aligned (Shared design responsibility themes src=('감사 |
| Req. 6 | CONFLICT | Req. 6 (MDDR) | **SKIPPED_WITH_REASON** | MDSR consistency CONFLICT — refuse silent MDDR policy propagation. Do NOT auto-patch description wit |
| Req. 105 | CONSISTENT | Req. 105 (MDDR) | **PATCHED** | MDSR CONSISTENT and MDDR design responsibility aligned (Shared design responsibility themes src=('과다 |

## Trace detail

### Req. 103 → Req. 103 (MDDR) → PATCHED
- aligned: True
- mdsr_patched: True
- reason: MDSR CONSISTENT and MDDR design responsibility aligned (Shared design responsibility themes src=('감사',) dst hits in MDDR); apply conservative design_description patch
  - evidence: Shared design responsibility themes src=('감사',) dst hits in MDDR
  - evidence: Extend criteria/description to include account-lock and unlock audit events; do not replace unrelated patient-registration audit clauses.

### Req. 6 → Req. 6 (MDDR) → SKIPPED_WITH_REASON
- aligned: True
- mdsr_patched: False
- reason: MDSR consistency CONFLICT — refuse silent MDDR policy propagation. Do NOT auto-patch description with lockout policy. Keep Req as UX owner; map policy changes to Req.105; optional UX-only criteria refine under human review.
  - evidence: CR lockout-policy themes ['계정 잠금', '잠금', '자동 해제', '관리자 승인', '연속 로그인 실패'] conflict with existing UX-primary title/purpose for Req. 6. Applying CR text to descrip
  - evidence: Shared design responsibility themes src=('안내', '에러', '오류') dst hits in MDDR
  - evidence: mddr_title=서버와의 통신 중 인증 관련 에러 발생 시 사용자 안내

### Req. 105 → Req. 105 (MDDR) → PATCHED
- aligned: True
- mdsr_patched: True
- reason: MDSR CONSISTENT and MDDR design responsibility aligned (Shared design responsibility themes src=('과다', '차단', '임계', '잠금', '제한') dst hits in MDDR); apply conservative design_description patch
  - evidence: Shared design responsibility themes src=('과다', '차단', '임계', '잠금', '제한') dst hits in MDDR
  - evidence: Patch description/criteria to incorporate consecutive-failure account lockout and unlock policy without dropping existing DoS/IP controls.

## Outputs
- MDSR: `data/trials/trial-002-lockout-multireq/generated/patched_mdsr/output_mdsr.docx`
- MDDR: `data/trials/trial-002-lockout-multireq/generated/patched_mddr/output_mddr.docx`
- MDDR unchanged vs ref: `False`
- MDSR patched IDs: ['Req. 103', 'Req. 105']
- MDDR patched IDs: ['Req. 103', 'Req. 105']

