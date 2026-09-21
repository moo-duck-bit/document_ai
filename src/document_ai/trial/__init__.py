"""Real-world Trial evaluation foundation for Document Harness."""

from __future__ import annotations

from document_ai.trial.analyze import analyze_trial
from document_ai.trial.baseline import freeze_baseline
from document_ai.trial.check_input import check_trial_input
from document_ai.trial.generate import generate_trial
from document_ai.trial.init import init_trial
from document_ai.trial.review import prepare_trial_review
from document_ai.trial.summary import summarize_trial

__all__ = [
    "analyze_trial",
    "check_trial_input",
    "freeze_baseline",
    "generate_trial",
    "init_trial",
    "prepare_trial_review",
    "summarize_trial",
]
