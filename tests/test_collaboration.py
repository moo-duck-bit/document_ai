from pathlib import Path

import pytest

from document_ai.platform.collaboration.collaboration_manager import CollaborationManager
from document_ai.platform.collaboration.consensus import build_consensus
from document_ai.platform.collaboration.discussion import discuss_proposals
from document_ai.platform.collaboration.proposal import Proposal
from document_ai.platform.collaboration.review_cycle import run_review_cycle
from document_ai.platform.planning.goal_parser import parse_goal
from document_ai.platform.planning.planner import AdaptivePlanner, MemoryQueryContext
from document_ai.platform.planner import RuleBasedPlanner

MINDRIUM = Path("data/cases/mindrium_xa")
CHANGE = MINDRIUM / "changes" / "req6_update.json"
HYBRID_GOAL = "Req 변경 후 GPU 서버 장애 로그 분석"


def test_proposal_generation():
    manager = CollaborationManager()
    parsed = parse_goal(
        case_dir=MINDRIUM,
        change=CHANGE,
        goal=HYBRID_GOAL,
    )
    proposals = manager.collect_proposals(parsed, memory_snapshot={})

    agent_ids = {proposal.agent_id for proposal in proposals}
    assert "planning_agent" in agent_ids
    assert "requirement_agent" in agent_ids
    assert "operation_agent" in agent_ids
    assert all(proposal.recommendation for proposal in proposals)
    assert all(proposal.rationale for proposal in proposals)
    assert all(isinstance(proposal.evidence, dict) for proposal in proposals)


def test_conflict_detection():
    proposals = [
        Proposal(
            agent_id="planning_agent",
            topic="intent",
            recommendation="document_change",
            confidence=0.9,
            rationale="planning",
            evidence={"source": "planning"},
        ),
        Proposal(
            agent_id="operation_agent",
            topic="intent",
            recommendation="operation_analysis",
            confidence=0.85,
            rationale="operation",
            evidence={"source": "operation"},
        ),
    ]
    discussion = discuss_proposals(proposals)

    assert discussion.conflicts
    assert discussion.conflicts[0].topic == "intent"
    assert set(discussion.conflicts[0].agents) == {"planning_agent", "operation_agent"}


def test_consensus_building():
    manager = CollaborationManager()
    parsed = parse_goal(case_dir=MINDRIUM, change=CHANGE)
    result = manager.run_full_cycle(
        parsed_goal=parsed,
        memory_snapshot={},
        case_dir=MINDRIUM,
    )

    consensus = result.consensus
    assert consensus.consensus_id.startswith("cons-")
    assert consensus.intent == "document_change"
    assert consensus.hybrid is False
    assert consensus.workflow_template == "document_workflow"
    assert consensus.selected_proposals


def test_hybrid_consensus():
    manager = CollaborationManager()
    parsed = parse_goal(
        case_dir=MINDRIUM,
        change=CHANGE,
        goal=HYBRID_GOAL,
    )
    consensus = manager.collaborate(
        parsed_goal=parsed,
        memory_snapshot={},
        case_dir=MINDRIUM,
    )

    assert consensus.hybrid is True
    assert consensus.workflow_template == "hybrid_workflow"
    assert consensus.intent == "document_change"


def test_review_cycle_flags_conflict():
    manager = CollaborationManager()
    parsed = parse_goal(
        case_dir=MINDRIUM,
        change="GPU 서버 Docker 로그 장애 분석",
    )
    result = manager.run_full_cycle(
        parsed_goal=parsed,
        memory_snapshot={},
        case_dir="data/ops",
    )

    review = run_review_cycle(result.consensus, result.discussion)
    assert any(finding.category == "conflict" for finding in review.findings) or result.discussion.conflicts


def test_planner_integration_uses_consensus(tmp_path):
    source_case = MINDRIUM
    case_copy = tmp_path / "case"
    case_copy.mkdir()
    (case_copy / "requirements.json").write_text(
        (source_case / "requirements.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    change_path = source_case / "changes" / "req6_update.json"

    planner = RuleBasedPlanner()
    planning_result = planner.plan_workflow(
        case_dir=case_copy,
        change=change_path,
        request_id="collab-plan",
    )

    assert planning_result.collaboration_consensus is not None
    assert planning_result.collaboration_consensus["workflow_template"] == "document_workflow"
    assert planning_result.execution_plan is not None
    assert planning_result.request.metadata.get("collaboration_consensus")
    assert planning_result.execution_plan.goal_context.metadata.get("collaboration_consensus")


def test_adaptive_planner_collaboration_full_cycle():
    planner = AdaptivePlanner()
    parsed = parse_goal(
        case_dir=MINDRIUM,
        change=CHANGE,
        goal=HYBRID_GOAL,
    )
    result = planner.collaboration_manager.run_full_cycle(
        parsed_goal=parsed,
        memory_snapshot={},
        case_dir=MINDRIUM,
    )

    assert result.review_approved
    assert result.consensus.workflow_template == "hybrid_workflow"
