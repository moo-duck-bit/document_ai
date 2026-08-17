from __future__ import annotations

from typing import Any

from document_ai.agents.base import AgentContext, AgentResult, BaseAgent
from document_ai.impact.change import changed_req_ids
from document_ai.intake.change_intake import draft_change_from_request
from document_ai.learn.req_ids import normalize_requirement_id


class RequirementAgent(BaseAgent):
    """Validate change payload or draft from natural-language intake."""

    agent_id = "requirement"

    def run(self, ctx: AgentContext) -> AgentResult:
        change = ctx.change
        issues: list[str] = []
        req_changes: list[dict[str, Any]] = []

        for item in change.get("requirement_changes", []):
            req_id = normalize_requirement_id(item.get("req_id", ""))
            description = (item.get("description") or "").strip()
            if not req_id:
                issues.append("requirement_changes entry missing valid req_id")
                continue
            if not description:
                issues.append(f"{req_id}: empty description")
            req_changes.append(
                {
                    "req_id": req_id,
                    "description": description,
                    "purpose": item.get("purpose"),
                    "criteria": item.get("criteria"),
                }
            )

        intake = change.get("intake") or {}
        confidence = intake.get("confidence")
        clarifying = intake.get("clarifying_questions") or []
        confirmed = intake.get("confirmed", bool(req_changes and not clarifying and not issues))

        if not req_changes:
            issues.append("no valid requirement_changes")

        status = "error" if not req_changes else ("warning" if issues else "ok")
        return AgentResult(
            agent_id=self.agent_id,
            status=status,
            data={
                "change_id": change.get("change_id"),
                "summary": change.get("summary"),
                "req_ids": changed_req_ids(change),
                "requirement_changes": req_changes,
                "confidence": confidence,
                "clarifying_questions": clarifying,
                "confirmed": confirmed,
            },
            issues=issues,
        )

    @staticmethod
    def draft_from_request(
        request_text: str,
        *,
        requirements_payload: dict[str, Any] | None = None,
        explicit_req_id: str | None = None,
        explicit_description: str | None = None,
        summary: str | None = None,
        sync_design_from_requirement: bool = True,
    ) -> dict[str, Any]:
        return draft_change_from_request(
            request_text,
            requirements_payload=requirements_payload,
            explicit_req_id=explicit_req_id,
            explicit_description=explicit_description,
            summary=summary,
            sync_design_from_requirement=sync_design_from_requirement,
        )
