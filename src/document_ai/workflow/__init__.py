# -*- coding: utf-8 -*-
"""Generic Document Set End-to-End Workflow (PR-27)."""

from document_ai.workflow.orchestrator import (
    approve_workflow,
    catalog_payload,
    create_workflow,
    get_workflow,
    list_workflows,
    run_analysis,
    run_result,
    run_writer,
)
from document_ai.workflow.schema import WORKFLOW_STATES, WorkflowRecord

__all__ = [
    "WORKFLOW_STATES",
    "WorkflowRecord",
    "create_workflow",
    "run_analysis",
    "approve_workflow",
    "run_writer",
    "run_result",
    "get_workflow",
    "list_workflows",
    "catalog_payload",
]
