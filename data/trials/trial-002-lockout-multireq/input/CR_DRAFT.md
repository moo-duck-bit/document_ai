# Trial 2 Change Request (초안) — A1 Multi-Req Lockout

> trial_id: `trial-002-lockout-multireq`  
> intent: Trial 1과 **동일 정책 의도**, 형식은 **자연어·비 Exact-ID 우선**  
> Trial 1 CR (`Req. 6:` 명시)과 달리, 이번 Trial은 ID를 주지 않고도 후보를 찾는지 검증한다.

---

## change_request.txt (본문)

아래 텍스트를 `input/change_request.txt`에 둔다.

```text
연속 로그인 실패 시 계정을 잠그고 관리자에게 알림을 보내도록 정책을 강화한다.
잠금 해제는 관리자 승인 또는 일정 시간 경과 후 자동 해제 중 하나를 지원해야 한다.
사용자에게는 잠금 상태와 재시도 가능 시점을 안내해야 하며,
로그인 실패·계정 잠금·잠금 해제 이벤트는 감사 기록으로 남겨야 한다.
```

---

## 설계 의도

| 항목 | 내용 |
|------|------|
| Exact-ID | CR에 `Req. 6` / `Req. 105` 등을 **넣지 않음** (가설 검증용) |
| 정책 의미 | Trial 1과 동일: 실패→잠금·관리자 알림·승인/자동 해제 |
| UX | 사용자 안내(잠금 상태·재시도) — expected: Req.6 쪽 |
| 정책·서버 | 실패 횟수·잠금 — expected: Req.105 쪽 |
| 감사 | 실패·잠금·해제 이벤트 — expected: Req.103 쪽 |
| 관리자 **모드 UI 신규** | **이번 CR 범위 밖** (별도 Trial). 알림·승인 **정책 문장만** 포함 |

---

## Intake 시 기대 동작 (참고)

- `confirmed`는 사람/게이트가 multi-req 후보를 본 뒤에 올릴 수 있음.  
- Exact-ID가 없어도 retrieval이 Req.105 등을 후보에 올려야 함.  
- Trial 1처럼 `Req. 6:`만 파싱해 단일 패치로 단정하면 **가설 실패**.

---

## 버전

- v0.1 — 초안 (구현 전 고정 후보)  
- 실행 시작 전 문구 freeze. 실행 중 완화·개서 금지.
