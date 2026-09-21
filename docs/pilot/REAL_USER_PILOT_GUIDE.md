# How to run the Real User Document Pilot

Goal: upload a real `.docx`, confirm domain routing, review change candidates, optionally write a **copy**, download artifacts, and score usability.

## Install

```powershell
cd <repo>
pip install -e ".[dev]"
```

## Start the Pilot UI

```powershell
# Safe default: writer disabled
$env:CONTROLLED_WRITER_ENABLED = "false"
uvicorn document_ai.pilot_ui.app:app --reload --port 8000
```

Open [http://127.0.0.1:8000/pilot-v2](http://127.0.0.1:8000/pilot-v2).

| URL | Use |
|-----|-----|
| `/pilot-v2` | Real-user Pilot wizard (this guide) |
| `/workflow` | Lower-level document-set workflow UI |
| `/` | Legacy EC-SW pilot |

## Upload

1. Pick a **demo scenario** (recommended) or choose **직접 업로드**.
2. Confirm **문서 유형** (EC-SW / 일반 보고서 / 사업 제안서).
3. Optionally set participant id (`P001`…).
4. Click **세션 만들고 업로드**.

The server stores a session-local copy only. Original paths outside the session are never written.

## Routing

1. Choose confirmation mode (default: **추천 후 사용자 확인**).
2. Click **유형 분석 실행**.
3. If “사용자 확인 필요” is yes, click **추천대로 확정**.

## Review

1. Enter/confirm the change request (step 3).
2. **분석 실행** (step 4).
3. Per item: **승인** / **거절** / **보류** → **결정 저장**.

## Approval → Writer

Writer runs only when **all** are true:

- at least one item is **승인**
- routing is confirmed
- UI checkbox **복사본 저장 허용**
- env `CONTROLLED_WRITER_ENABLED=true`

Otherwise status is `BLOCKED` (safe). Output is copy-only under the session workspace.

## Result · Download

Step 6 shows status, writer result, original-unchanged, and download links for traces / copies.

## Human review

Score 10 dimensions (1–5), pick PASS / PARTIAL / FAIL, save comments.

## CLI

```powershell
# Single scenario (safe dry-review)
python -m document_ai.cli run-pilot-session --scenario pilot_ec_req_single --dry-review

# Materialize demo dataset under data/pilot/demo/
python -m document_ai.cli materialize-pilot-demo

# Run 3 flagship demos (EC-SW / GR / BP)
python -m document_ai.cli run-pilot-demo

# Aggregate pilot sessions
python -m document_ai.cli evaluate-pilot --json
```

| Exit | Meaning |
|------|---------|
| 0 | OK / safe |
| 1 | Runtime error |
| 2 | Pending human input / blocked write when write requested |
| 3 | Validation / insufficient data |

## Sample dataset

See `data/pilot/demo/README.md` (12 demos, 3 flagship).

## FAQ

**Q: Did my original file change?**  
A: No. Check upload fingerprint in the session `input/` folder vs the path you uploaded from.

**Q: Writer says BLOCKED even after 승인.**  
A: Set `$env:CONTROLLED_WRITER_ENABLED = "true"` and check **복사본 저장 허용**.

**Q: Can I use production MDSR/MDDR files?**  
A: Yes — upload copies only. Prefer files already under a pilot workspace.

**Q: Does this tune the benchmark?**  
A: No. Pilot never writes under `data/eval/document_set_benchmark_v2/`.

**Q: Where are session files?**  
A: `data/pilot/real_user_document_pilot/sessions/<session_id>/`.

## Related docs

- [DEMO_SCRIPT.md](./DEMO_SCRIPT.md) — presentation script  
- [PILOT_CHECKLIST.md](./PILOT_CHECKLIST.md) — go-live checklist  
- [BUG_REPORT_TEMPLATE.md](./BUG_REPORT_TEMPLATE.md)  
- [RELEASE_v2.0.md](./RELEASE_v2.0.md)  
- [../presentation/Document_AI_v2_Pilot_Presentation.md](../presentation/Document_AI_v2_Pilot_Presentation.md)
