from __future__ import annotations

from document_ai.agents.base import AgentContext, AgentResult, BaseAgent
from document_ai.learn.req_ids import normalize_requirement_id


class DocumentReviewAgent(BaseAgent):
    """Consistency checks across requirement, traceability, design, and test artifacts."""

    agent_id = "document_review"

    def run(self, ctx: AgentContext) -> AgentResult:
        issues: list[str] = []
        req_data = ctx.prior.get("requirement", {})
        trace_data = ctx.prior.get("traceability", {})
        design_data = ctx.prior.get("design", {})
        test_data = ctx.prior.get("test", {})

        known_req_ids = {
            normalize_requirement_id(r.get("req_id", ""))
            for r in ctx.requirements_payload.get("requirements", [])
            if normalize_requirement_id(r.get("req_id", ""))
        }

        for item in req_data.get("requirement_changes", []):
            req_id = item.get("req_id")
            if not item.get("description"):
                issues.append(f"{req_id}: change description is empty")
            if req_id and req_id not in known_req_ids:
                issues.append(f"{req_id}: not found in requirements.json (will be added on apply)")

        changed = trace_data.get("changed_req_ids") or []
        if changed and not trace_data.get("linked_security_ids") and not trace_data.get("linked_test_ids"):
            doc_hint = trace_data.get("document_set_hint")
            if doc_hint == "ec_sw":
                issues.append("no downstream security IDs linked for changed requirements")

        if trace_data.get("documents", {}).get("spec_design", {}).get("action") == "patch":
            if not design_data.get("patch_candidates") and design_data.get("linked_design_req_ids"):
                issues.append("MDDR patch expected but no design patch candidates generated")

        if trace_data.get("documents", {}).get("report_security_verification", {}).get("action") == "patch":
            if not (ctx.case_dir / "security_tests.json").exists():
                issues.append("XXCS patch planned but security_tests.json is missing")

        if test_data.get("test_case_action") == "review" and not test_data.get("linked_test_ids"):
            issues.append("SRS test review flagged but no linked test IDs")

        status = "error" if any("empty" in i for i in issues) else ("warning" if issues else "ok")
        return AgentResult(
            agent_id=self.agent_id,
            status=status,
            data={
                "issue_count": len(issues),
                "checks_run": [
                    "requirement_descriptions",
                    "requirements_json_membership",
                    "traceability_downstream",
                    "design_patch_readiness",
                    "security_tests_readiness",
                ],
            },
            issues=issues,
        )
