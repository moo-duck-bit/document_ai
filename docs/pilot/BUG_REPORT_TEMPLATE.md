# Pilot Bug Report Template

Copy this file or paste into an issue tracker.

---

## Summary

한 줄 요약:

## Environment

| Item | Value |
|------|-------|
| OS | Windows / macOS / Linux |
| Python | |
| Branch / commit | |
| Pilot UI URL | `http://127.0.0.1:8000/pilot-v2` |
| `CONTROLLED_WRITER_ENABLED` | true / false |
| CLI or UI | |

## Document

| Item | Value |
|------|-------|
| Domain | EC-SW / General Report / Business Proposal |
| Filename(s) | |
| Scenario id (if any) | |
| Session id | |

## Change Request

```
(붙여넣기)
```

## Expected Result

- Expected impacted documents:
- Expected nodes / sections:
- Expected user decision path:
- Expected writer behavior (blocked / copy):

## Actual Result

- Status:
- Review items (요약):
- Writer status / blocked reasons:
- Original changed? yes / no:

## Severity

- [ ] S0 — Safety (원본 변경, 승인 없는 쓰기, path escape)
- [ ] S1 — Workflow broken (업로드~결과 불가)
- [ ] S2 — Wrong candidate / confusing UX (워크어라운드 가능)
- [ ] S3 — Cosmetic / wording

## Screenshot / Artifacts

- Screenshot:
- Session path: `data/pilot/real_user_document_pilot/sessions/<session_id>/`
- Attach: `analysis_trace.json`, `writer_trace.json` (해당 시)

## 재현 방법

1.
2.
3.

## Notes

잘된 점 / 추가 맥락:
