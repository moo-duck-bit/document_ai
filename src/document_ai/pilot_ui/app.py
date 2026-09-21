# -*- coding: utf-8 -*-
"""FastAPI app for Document AI Pilot UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from document_ai.pilot_ui import service

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app() -> FastAPI:
    app = FastAPI(title="Document AI Pilot UI", version="0.1.0")

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        index_path = STATIC_DIR / "index.html"
        if not index_path.exists():
            raise HTTPException(500, "index.html missing")
        return HTMLResponse(index_path.read_text(encoding="utf-8"))

    @app.get("/api/pilot/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "service": "document-ai-pilot-ui"}

    @app.get("/api/pilot/runs")
    def api_list_runs() -> dict[str, Any]:
        return {"runs": service.list_runs()}

    @app.post("/api/pilot/runs")
    async def api_create_and_run(
        scenario_name: str = Form("pilot-run"),
        change_request: str = Form(...),
        top_k: int = Form(15),
        keep_output: bool = Form(False),
        execute: bool = Form(True),
        document_set_mode: str = Form("legacy_pair"),
        mdsr: UploadFile = File(...),
        mddr: UploadFile = File(...),
    ) -> dict[str, Any]:
        try:
            mdsr_bytes = await mdsr.read()
            mddr_bytes = await mddr.read()
            if not mdsr_bytes or not mddr_bytes:
                raise ValueError("MDSR/MDDR files are empty")
            meta = service.create_run(
                scenario_name=scenario_name,
                change_request=change_request,
                mdsr_bytes=mdsr_bytes,
                mdsr_filename=mdsr.filename or "MDSR.docx",
                mddr_bytes=mddr_bytes,
                mddr_filename=mddr.filename or "MDDR.docx",
                top_k=top_k,
                keep_output=keep_output,
                document_set_mode=document_set_mode,
            )
            if execute:
                return service.execute_run(
                    meta["run_id"],
                    top_k=top_k,
                    keep_output=keep_output,
                    document_set_mode=document_set_mode,
                )
            return {"run_id": meta["run_id"], "status": "created", "meta": meta}
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/pilot/runs/from-existing")
    def api_from_existing(
        source_scenario: str = Form(...),
        scenario_name: str = Form("from-existing"),
        top_k: int = Form(15),
        execute: bool = Form(True),
    ) -> dict[str, Any]:
        try:
            meta = service.create_run_from_existing_scenario(
                source_scenario=source_scenario,
                scenario_name=scenario_name,
                top_k=top_k,
            )
            if execute:
                return service.execute_run(meta["run_id"], top_k=top_k)
            return {"run_id": meta["run_id"], "status": "created", "meta": meta}
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/pilot/runs/{run_id}")
    def api_get_run(run_id: str) -> dict[str, Any]:
        try:
            return service.get_run(run_id)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/api/pilot/runs/{run_id}/execute")
    def api_execute(run_id: str, top_k: int = 15, keep_output: bool = False) -> dict[str, Any]:
        try:
            return service.execute_run(run_id, top_k=top_k, keep_output=keep_output)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(400, str(exc)) from exc

    @app.get("/api/pilot/runs/{run_id}/artifacts/{name}")
    def api_artifact(run_id: str, name: str) -> FileResponse:
        try:
            path = service.resolve_artifact(run_id, name)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        return FileResponse(path, filename=path.name)

    @app.post("/api/pilot/runs/{run_id}/approve")
    def api_approve(
        run_id: str,
        decision: str = Form("APPROVED"),
        approved_by: str = Form("pilot-user"),
        reason: str = Form(""),
    ) -> dict[str, Any]:
        try:
            approval = service.save_approval(
                run_id,
                decision=decision,
                approved_by=approved_by,
                reason=reason,
            )
            return {"ok": True, "approval": approval}
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/pilot/runs/{run_id}/writer")
    def api_writer(run_id: str) -> dict[str, Any]:
        try:
            result = service.run_writer(run_id, force_enable=True)
            return {"ok": True, "writer": result}
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(500, str(exc)) from exc

    # --- PR-27 Generic Document Set E2E Workflow ---
    from document_ai import workflow as wf

    @app.get("/workflow", response_class=HTMLResponse)
    def workflow_page() -> HTMLResponse:
        path = STATIC_DIR / "workflow.html"
        if not path.exists():
            raise HTTPException(500, "workflow.html missing")
        return HTMLResponse(path.read_text(encoding="utf-8"))

    @app.get("/api/workflow/catalog")
    def api_wf_catalog() -> dict[str, Any]:
        return wf.catalog_payload()

    @app.get("/api/workflow/list")
    def api_wf_list() -> dict[str, Any]:
        return {"workflows": wf.list_workflows()}

    @app.post("/api/workflow/create")
    async def api_wf_create(
        document_set: str = Form(...),
        change_request: str = Form(...),
        name: str = Form("workflow"),
        document_routing_mode: str = Form("assisted"),
        files: list[UploadFile] = File(default=[]),
    ) -> dict[str, Any]:
        try:
            uploaded: list[tuple[str, bytes, str | None]] = []
            for f in files or []:
                data = await f.read()
                if data:
                    uploaded.append((f.filename or "doc.docx", data, None))
            return wf.create_workflow(
                document_set=document_set,
                change_request=change_request,
                files=uploaded,
                name=name,
                document_routing_mode=document_routing_mode or "assisted",
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/workflow/{workflow_id}/analyze")
    def api_wf_analyze(workflow_id: str) -> dict[str, Any]:
        try:
            return wf.run_analysis(workflow_id)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/workflow/{workflow_id}/approve")
    def api_wf_approve(workflow_id: str) -> dict[str, Any]:
        try:
            return wf.approve_workflow(workflow_id, approve_all_pending=True)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/workflow/{workflow_id}/approve-json")
    def api_wf_approve_json(workflow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return wf.approve_workflow(
                workflow_id,
                decisions=payload.get("decisions"),
                document_decisions=payload.get("document_decisions"),
                approve_all_pending=bool(payload.get("approve_all_pending")),
                approved_by=str(payload.get("approved_by") or "pilot"),
            )
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/workflow/{workflow_id}/writer")
    def api_wf_writer(workflow_id: str, enable_write: bool = False) -> dict[str, Any]:
        try:
            return wf.run_writer(workflow_id, enable_write=enable_write)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(400, str(exc)) from exc

    @app.get("/api/workflow/{workflow_id}")
    def api_wf_get(workflow_id: str) -> dict[str, Any]:
        try:
            return wf.get_workflow(workflow_id)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/api/workflow/{workflow_id}/result")
    def api_wf_result(workflow_id: str) -> dict[str, Any]:
        try:
            return wf.run_result(workflow_id)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc

    # --- Real User Document Pilot v2 (Product Validation Cycle 1) ---
    from document_ai.pilot_v2 import cli_support as pilot_cli_support  # noqa: F401 (import smoke)
    from document_ai.pilot_v2 import orchestrator as pv2
    from document_ai.pilot_v2 import scenarios as pv2_scenarios
    from document_ai.pilot_v2.orchestrator import PilotOrchestratorError
    from document_ai.pilot_v2.scenarios import ScenarioError
    from document_ai.pilot_v2.security import PilotSecurityError

    def _pv2_error(exc: Exception) -> HTTPException:
        if isinstance(exc, FileNotFoundError):
            return HTTPException(404, str(exc))
        if isinstance(exc, (PilotOrchestratorError, ScenarioError, PilotSecurityError, ValueError)):
            return HTTPException(400, str(exc))
        return HTTPException(500, str(exc))

    @app.get("/pilot-v2", response_class=HTMLResponse)
    def pilot_v2_page() -> HTMLResponse:
        path = STATIC_DIR / "pilot_v2.html"
        if not path.exists():
            raise HTTPException(500, "pilot_v2.html missing")
        return HTMLResponse(path.read_text(encoding="utf-8"))

    @app.get("/api/pilot-v2/scenarios")
    def api_pv2_scenarios() -> dict[str, Any]:
        try:
            rows = [s.to_dict() for s in pv2_scenarios.load_scenarios()]
            return {"scenarios": rows, "count": len(rows)}
        except Exception as exc:  # noqa: BLE001
            raise _pv2_error(exc) from exc

    @app.get("/api/pilot-v2/sessions")
    def api_pv2_list_sessions() -> dict[str, Any]:
        return {"sessions": pv2.list_sessions()}

    @app.post("/api/pilot-v2/sessions")
    async def api_pv2_create_session(
        document_set: str = Form(...),
        change_request: str = Form(...),
        participant_id: str = Form(""),
        scenario_id: str = Form(""),
        routing_mode: str = Form("assisted"),
        files: list[UploadFile] = File(default=[]),
    ) -> dict[str, Any]:
        try:
            session = pv2.create_session(
                document_set=document_set,
                change_request=change_request,
                participant_id=participant_id or None,
                scenario_id=scenario_id or None,
            )
            session_id = session["session_id"]

            upload_files: list[tuple[str, bytes, str | None]] = []
            for f in files or []:
                data = await f.read()
                if data:
                    upload_files.append((f.filename or "doc.docx", data, None))
            if not upload_files and scenario_id:
                scenario = pv2_scenarios.get_scenario(scenario_id)
                fixture_path = pv2_scenarios.ensure_fixture(scenario)
                upload_files.append((fixture_path.name, fixture_path.read_bytes(), scenario.fixture_role))
            if upload_files:
                session = pv2.upload_documents(session_id, upload_files)
                session = pv2.resolve_identity(session_id, routing_mode=routing_mode or "assisted")
            return session
        except Exception as exc:  # noqa: BLE001
            raise _pv2_error(exc) from exc

    @app.post("/api/pilot-v2/sessions/{session_id}/resolve-identity")
    def api_pv2_resolve_identity(
        session_id: str,
        routing_mode: str = Form("assisted"),
        user_confirmed: bool = Form(False),
        document_set_override: str = Form(""),
    ) -> dict[str, Any]:
        try:
            return pv2.resolve_identity(
                session_id,
                routing_mode=routing_mode,
                user_confirmed=user_confirmed,
                document_set_override=document_set_override or None,
            )
        except Exception as exc:  # noqa: BLE001
            raise _pv2_error(exc) from exc

    @app.post("/api/pilot-v2/sessions/{session_id}/analyze")
    def api_pv2_analyze(session_id: str) -> dict[str, Any]:
        try:
            return pv2.analyze(session_id)
        except Exception as exc:  # noqa: BLE001
            raise _pv2_error(exc) from exc

    @app.get("/api/pilot-v2/sessions/{session_id}/review-items")
    def api_pv2_review_items(session_id: str) -> dict[str, Any]:
        try:
            return {"review_items": pv2.get_review_items(session_id)}
        except Exception as exc:  # noqa: BLE001
            raise _pv2_error(exc) from exc

    @app.post("/api/pilot-v2/sessions/{session_id}/decisions")
    def api_pv2_decisions(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return pv2.apply_decisions(
                session_id,
                decisions=list(payload.get("decisions") or []),
                decided_by=str(payload.get("decided_by") or "reviewer"),
            )
        except Exception as exc:  # noqa: BLE001
            raise _pv2_error(exc) from exc

    @app.post("/api/pilot-v2/sessions/{session_id}/writer")
    def api_pv2_writer(
        session_id: str,
        enable_write: bool = Form(False),
        decided_by: str = Form("reviewer"),
    ) -> dict[str, Any]:
        try:
            return pv2.run_writer_if_allowed(session_id, enable_write=enable_write, decided_by=decided_by)
        except Exception as exc:  # noqa: BLE001
            raise _pv2_error(exc) from exc

    @app.post("/api/pilot-v2/sessions/{session_id}/human-review")
    def api_pv2_human_review(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return pv2.save_human_review(
                session_id,
                scores=dict(payload.get("scores") or {}),
                comments=str(payload.get("comments") or ""),
                verdict=str(payload.get("verdict") or "PENDING"),
                participant_id=payload.get("participant_id"),
            )
        except Exception as exc:  # noqa: BLE001
            raise _pv2_error(exc) from exc

    @app.get("/api/pilot-v2/sessions/{session_id}")
    def api_pv2_get_result(session_id: str) -> dict[str, Any]:
        try:
            return pv2.get_result(session_id)
        except Exception as exc:  # noqa: BLE001
            raise _pv2_error(exc) from exc

    @app.get("/api/pilot-v2/sessions/{session_id}/artifacts/{relative_path:path}")
    def api_pv2_artifact(session_id: str, relative_path: str) -> FileResponse:
        try:
            path = pv2.download_artifact(session_id, relative_path)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise _pv2_error(exc) from exc
        return FileResponse(path, filename=path.name)

    # Plan aliases (singular / alternate names) — same handlers as /sessions/*
    @app.post("/api/pilot-v2/session")
    async def api_pv2_create_session_alias(
        document_set: str = Form(...),
        change_request: str = Form(...),
        participant_id: str = Form(""),
        scenario_id: str = Form(""),
        routing_mode: str = Form("assisted"),
        files: list[UploadFile] = File(default=[]),
    ) -> dict[str, Any]:
        return await api_pv2_create_session(
            document_set=document_set,
            change_request=change_request,
            participant_id=participant_id,
            scenario_id=scenario_id,
            routing_mode=routing_mode,
            files=files,
        )

    @app.post("/api/pilot-v2/{session_id}/upload")
    async def api_pv2_upload(
        session_id: str,
        files: list[UploadFile] = File(...),
    ) -> dict[str, Any]:
        try:
            upload_files: list[tuple[str, bytes, str | None]] = []
            for f in files or []:
                data = await f.read()
                if data:
                    upload_files.append((f.filename or "doc.docx", data, None))
            if not upload_files:
                raise ValueError("no files uploaded")
            return pv2.upload_documents(session_id, upload_files)
        except Exception as exc:  # noqa: BLE001
            raise _pv2_error(exc) from exc

    @app.get("/api/pilot-v2/{session_id}/review")
    def api_pv2_review_alias(session_id: str) -> dict[str, Any]:
        return api_pv2_review_items(session_id)

    @app.post("/api/pilot-v2/{session_id}/approve")
    def api_pv2_approve_alias(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return api_pv2_decisions(session_id, payload)

    @app.post("/api/pilot-v2/{session_id}/write")
    def api_pv2_write_alias(
        session_id: str,
        enable_write: bool = Form(False),
        decided_by: str = Form("reviewer"),
    ) -> dict[str, Any]:
        return api_pv2_writer(session_id, enable_write=enable_write, decided_by=decided_by)

    @app.get("/api/pilot-v2/{session_id}/result")
    def api_pv2_result_alias(session_id: str) -> dict[str, Any]:
        return api_pv2_get_result(session_id)

    @app.get("/api/pilot-v2/{session_id}/download/{artifact:path}")
    def api_pv2_download_alias(session_id: str, artifact: str) -> FileResponse:
        return api_pv2_artifact(session_id, artifact)

    return app


app = create_app()
