from __future__ import annotations

from document_ai.agents.base import AgentContext, AgentResult, BaseAgent
from document_ai.impact.change import changed_req_ids
from document_ai.impact.graph import TraceabilityGraph, xxcs_test_ids
from document_ai.learn.extract_design_items import DesignItemIndex


class TraceabilityAgent(BaseAgent):
    """Analyze downstream links from traceability matrix."""

    agent_id = "traceability"

    def run(self, ctx: AgentContext) -> AgentResult:
        req_ids = changed_req_ids(ctx.change)
        traceability = ctx.requirements_payload.get("traceability", [])
        graph = TraceabilityGraph(traceability)

        design_index = None
        if ctx.design_payload:
            design_index = DesignItemIndex(ctx.design_payload.get("items", []))

        impact = graph.impact(req_ids, design_index=design_index)
        security_ids = impact.get("linked_security_ids", [])
        test_ids = impact.get("linked_test_ids", [])
        xxcs_ids = xxcs_test_ids(security_ids)

        design_req_ids = impact.get("documents", {}).get("spec_design", {}).get("req_ids", [])

        return AgentResult(
            agent_id=self.agent_id,
            status="ok" if req_ids else "warning",
            data={
                "changed_req_ids": req_ids,
                "linked_security_ids": security_ids,
                "linked_test_ids": test_ids,
                "linked_design_req_ids": design_req_ids,
                "xxcs_security_req_ids": xxcs_ids,
                "document_set_hint": impact.get("document_set_hint"),
                "documents": impact.get("documents", {}),
                "impact": impact,
            },
            issues=[] if req_ids else ["no changed requirement IDs"],
        )
