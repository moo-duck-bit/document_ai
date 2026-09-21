"""Autonomous multi-agent collaboration before planning."""

from document_ai.platform.collaboration.collaboration_manager import CollaborationManager, CollaborationResult
from document_ai.platform.collaboration.consensus import ConsensusResult, build_consensus
from document_ai.platform.collaboration.discussion import Conflict, DiscussionResult, discuss_proposals
from document_ai.platform.collaboration.proposal import Proposal
from document_ai.platform.collaboration.review_cycle import ReviewFinding, ReviewResult, run_review_cycle
from document_ai.platform.collaboration.voting import select_winning_proposal, vote_summary

__all__ = [
    "CollaborationManager",
    "CollaborationResult",
    "ConsensusResult",
    "Conflict",
    "DiscussionResult",
    "Proposal",
    "ReviewFinding",
    "ReviewResult",
    "build_consensus",
    "discuss_proposals",
    "run_review_cycle",
    "select_winning_proposal",
    "vote_summary",
]
