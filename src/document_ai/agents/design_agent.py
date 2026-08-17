from __future__ import annotations

from document_ai.agents.base import AgentContext, AgentResult, BaseAgent
from document_ai.impact.change import design_changes_for_patch
from document_ai.learn.extract_design_items import DesignItemIndex


class DesignAgent(BaseAgent):
    """Find affected design items and build MDDR patch candidates."""

    agent_id = "design"

    def run(self, ctx: AgentContext) -> AgentResult:
        trace = ctx.prior.get("traceability", {})
        linked_design_ids = trace.get("linked_design_req_ids", [])
        issues: list[str] = []

        if not ctx.design_payload:
            if linked_design_ids:
                issues.append(
                    f"design_items.json missing but {len(linked_design_ids)} design req(s) linked"
                )
            return AgentResult(
                agent_id=self.agent_id,
                status="warning" if issues else "ok",
                data={
                    "linked_design_req_ids": linked_design_ids,
                    "indexed_req_ids": [],
                    "patch_candidates": [],
                    "mddr_action": trace.get("documents", {}).get("spec_design", {}).get("action", "skip"),
                },
                issues=issues,
            )

        design_index = DesignItemIndex(ctx.design_payload.get("items", []))
        patch_candidates = design_changes_for_patch(ctx.change, design_index)
        indexed = design_index.req_ids_for(linked_design_ids or [c["req_id"] for c in patch_candidates])

        missing = [rid for rid in linked_design_ids if not design_index.has(rid)]
        for rid in missing:
            issues.append(f"{rid}: listed in traceability impact but not in design_items.json")

        return AgentResult(
            agent_id=self.agent_id,
            status="warning" if issues else "ok",
            data={
                "linked_design_req_ids": linked_design_ids,
                "indexed_req_ids": indexed,
                "patch_candidates": patch_candidates,
                "mddr_action": trace.get("documents", {}).get("spec_design", {}).get("action", "skip"),
                "output_path": str(ctx.case_dir / "output_mddr.docx"),
            },
            issues=issues,
        )
