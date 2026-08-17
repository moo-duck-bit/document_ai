from __future__ import annotations

from document_ai.agents.base import AgentContext, AgentResult, BaseAgent
from document_ai.impact.graph import xxcs_test_ids


class TestAgent(BaseAgent):
    """Find affected security verification / RTM test items."""

    agent_id = "test"

    def run(self, ctx: AgentContext) -> AgentResult:
        trace = ctx.prior.get("traceability", {})
        security_ids = trace.get("linked_security_ids", [])
        test_ids = trace.get("linked_test_ids", [])
        xxcs_ids = trace.get("xxcs_security_req_ids") or xxcs_test_ids(security_ids)
        issues: list[str] = []

        tests = (ctx.security_payload or {}).get("tests", [])
        tests_by_req = {t.get("req_id"): t for t in tests if t.get("req_id")}

        xxcs_candidates = []
        for sid in xxcs_ids:
            entry = tests_by_req.get(sid, {"req_id": sid})
            xxcs_candidates.append(
                {
                    "req_id": sid,
                    "has_security_tests_json": sid in tests_by_req,
                    "review_only": sid not in tests_by_req,
                }
            )
            if sid not in tests_by_req and ctx.security_payload:
                issues.append(f"{sid}: no row in security_tests.json (XXCS patch may be partial)")

        rtm_candidates = [{"test_id": tid, "source": "traceability_rtm"} for tid in test_ids]

        xxcs_action = trace.get("documents", {}).get("report_security_verification", {}).get("action", "skip")
        test_case_action = trace.get("documents", {}).get("test_cases", {}).get("action", "skip")

        return AgentResult(
            agent_id=self.agent_id,
            status="warning" if issues else "ok",
            data={
                "linked_test_ids": test_ids,
                "xxcs_security_req_ids": xxcs_ids,
                "xxcs_patch_candidates": xxcs_candidates,
                "rtm_review_candidates": rtm_candidates,
                "xxcs_action": xxcs_action,
                "test_case_action": test_case_action,
                "output_path": str(ctx.case_dir / "output_xxcs.docx"),
            },
            issues=issues,
        )
