from __future__ import annotations

from document_ai.platform.models import PlannerMode
from document_ai.platform.planning.goal_parser import ParsedGoal
from document_ai.platform.planning.intent_classifier import PlannerIntent


def resolve_legacy_mode(intent: PlannerIntent, parsed_goal: ParsedGoal) -> PlannerMode:
    if intent == "operation_analysis":
        return "operation_request"
    return "change_request"


def intent_action(intent: PlannerIntent) -> str:
    mapping = {
        "document_change": "run_change_pipeline",
        "operation_analysis": "analyze_incidents",
        "document_generation": "run_change_pipeline",
        "security_review": "run_change_pipeline",
        "knowledge_query": "run_change_pipeline",
    }
    return mapping[intent]
