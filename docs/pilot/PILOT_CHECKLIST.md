# Pilot Go-Live Checklist

Use before a live participant session or a presentation.

## Workflow

- [ ] Upload (scenario or own `.docx`)
- [ ] Routing (identity / Domain Pack confirmed)
- [ ] Review items visible with Korean reasons
- [ ] Approval / Reject / Hold decisions save
- [ ] Writer stays blocked without approval
- [ ] Writer (optional) copy-only with `CONTROLLED_WRITER_ENABLED=true`
- [ ] Diff / validation traces present under session
- [ ] Download links work for session artifacts
- [ ] Human Review (10 scores + verdict) saves

## Safety

- [ ] Original unchanged (fingerprint match on `input/`)
- [ ] Unauthorized writer = 0
- [ ] Writer without approval = 0
- [ ] Path traversal / wrong-session download blocked
- [ ] Rollback path documented if write attempted and failed
- [ ] No writes under `data/eval/document_set_benchmark_v2/`
- [ ] No edits to Desktop / `data/examples` / Freeze trees

## Demo package

- [ ] `python -m document_ai.cli materialize-pilot-demo`
- [ ] `data/pilot/demo/{ec_sw,general_report,business_proposal}/` populated
- [ ] `python -m document_ai.cli run-pilot-demo` exit 0
- [ ] Flagship demos: EC-SW Req.11 / GR methodology / BP budget

## Docs

- [ ] `REAL_USER_PILOT_GUIDE.md`
- [ ] `DEMO_SCRIPT.md`
- [ ] `RELEASE_v2.0.md`
- [ ] `BUG_REPORT_TEMPLATE.md`
- [ ] Presentation deck under `docs/presentation/`

## Environment

- [ ] `pip install -e ".[dev]"`
- [ ] Server: `uvicorn document_ai.pilot_ui.app:app --port 8000`
- [ ] UI: `http://127.0.0.1:8000/pilot-v2`
- [ ] Writer kill-switch default off for public demos

## Sign-off

| Role | Name | Date | OK |
|------|------|------|----|
| Presenter | | | ☐ |
| Safety reviewer | | | ☐ |
