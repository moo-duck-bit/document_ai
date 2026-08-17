from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from document_ai.agents.base import AgentContext, AgentResult
from document_ai.agents.design_agent import DesignAgent
from document_ai.agents.document_review_agent import DocumentReviewAgent
from document_ai.agents.requirement_agent import RequirementAgent
from document_ai.agents.test_agent import TestAgent
from document_ai.agents.traceability_agent import TraceabilityAgent
from document_ai.impact.change import load_change
from document_ai.impact.orchestrator import DEFAULT_OUTPUTS, apply_change, compute_impact
from document_ai.learn.extract_design_items import load_design_items
from document_ai.learn.extract_security_tests import load_security_tests

IMPACT_REPORT_NAME = "impact_report.json"

_PIPELINE = (
    RequirementAgent(),
    TraceabilityAgent(),
    DesignAgent(),
    TestAgent(),
    DocumentReviewAgent(),
)


def _load_case_payloads(case_dir: Path) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]:
    req_path = case_dir / "requirements.json"
    if not req_path.exists():
        raise FileNotFoundError(f"Missing {req_path}")

    requirements_payload = json.loads(req_path.read_text(encoding="utf-8"))
    design_payload = None
    security_payload = None

    design_path = case_dir / "design_items.json"
    if design_path.exists():
        design_payload = load_design_items(design_path)

    security_path = case_dir / "security_tests.json"
    if security_path.exists():
        security_payload = load_security_tests(security_path)

    return requirements_payload, design_payload, security_payload


def save_impact_report(report: dict[str, Any], case_dir: Path, path: Path | None = None) -> Path:
    out = path or (case_dir / IMPACT_REPORT_NAME)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def run_change_pipeline(
    case_dir: Path,
    change: dict[str, Any] | Path,
    *,
    dry_run: bool = True,
    apply: bool = False,
    report_path: Path | None = None,
    change_path: Path | None = None,
) -> dict[str, Any]:
    """Run multi-agent impact analysis; optionally apply patches."""
    case_dir = Path(case_dir)
    resolved_change_path = Path(change_path) if change_path else None
    if isinstance(change, Path):
        resolved_change_path = change
        change = load_change(change)

    requirements_payload, design_payload, security_payload = _load_case_payloads(case_dir)

    ctx = AgentContext(
        case_dir=case_dir,
        change=change,
        requirements_payload=requirements_payload,
        design_payload=design_payload,
        security_payload=security_payload,
        dry_run=dry_run,
        apply=apply,
    )

    pipeline: list[dict[str, Any]] = []
    for agent in _PIPELINE:
        result: AgentResult = agent.run(ctx)
        pipeline.append(result.to_dict())
        ctx.prior[result.agent_id] = result.data

    legacy = compute_impact(case_dir, change)

    report: dict[str, Any] = {
        "case_dir": str(case_dir),
        "change_id": change.get("change_id"),
        "summary": change.get("summary"),
        "mode": "apply" if apply and not dry_run else "dry-run",
        "dry_run": dry_run or not apply,
        "pipeline": pipeline,
        "agents": {step["agent_id"]: step for step in pipeline},
        "impact": legacy.get("impact"),
        "outputs": legacy.get("outputs")
        or {k: str(case_dir / v) for k, v in DEFAULT_OUTPUTS.items()},
        "design_patch_candidates": ctx.prior.get("design", {}).get("patch_candidates", []),
        "test_patch_candidates": ctx.prior.get("test", {}).get("xxcs_patch_candidates", []),
        "review": {
            "status": pipeline[-1]["status"] if pipeline else "ok",
            "issues": pipeline[-1]["issues"] if pipeline else [],
        },
    }

    if apply and not dry_run:
        apply_path = resolved_change_path
        if apply_path is None or not apply_path.exists():
            apply_path = case_dir / "changes" / f"{change.get('change_id', 'change')}.json"
        if not apply_path.exists():
            apply_path = case_dir / "_pipeline_change.json"
            apply_path.write_text(json.dumps(change, ensure_ascii=False, indent=2), encoding="utf-8")
        apply_result = apply_change(case_dir, apply_path, dry_run=False)
        report["patches"] = apply_result.get("patches", {})
        report["dry_run"] = False
        report["mode"] = "apply"
    else:
        report["patches"] = {}

    saved = save_impact_report(report, case_dir, report_path)
    report["impact_report"] = str(saved)
    return report
