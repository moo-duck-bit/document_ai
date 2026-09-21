from __future__ import annotations

from pathlib import Path
from typing import Any

from document_ai.agents.orchestrator import run_change_pipeline
from document_ai.platform.memory.graph_query import KnowledgeGraph
from document_ai.platform.models import PlannerRequest, TaskSpec


class DocumentHarness:
    """Thin wrapper around the existing Document AI change pipeline."""

    harness_name = "document"

    def run(self, request: PlannerRequest, task: TaskSpec) -> dict[str, Any]:
        knowledge_graph = request.metadata.get("knowledge_graph")
        change = request.change
        if isinstance(change, Path):
            return run_change_pipeline(
                request.case_dir,
                change,
                dry_run=request.dry_run,
                apply=request.apply,
                report_path=request.report_path,
                change_path=request.change_path or change,
                knowledge_graph=knowledge_graph,
            )
        return run_change_pipeline(
            request.case_dir,
            change,
            dry_run=request.dry_run,
            apply=request.apply,
            report_path=request.report_path,
            change_path=request.change_path,
            knowledge_graph=knowledge_graph,
        )

    @staticmethod
    def build_knowledge_context(
        knowledge_graph: KnowledgeGraph,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        impact = result.get("impact", {})
        changed_req_ids = impact.get("changed_req_ids", [])
        context: dict[str, Any] = {
            "engine": "knowledge_graph",
            "changed_req_ids": changed_req_ids,
            "queries": [],
        }

        for req_id in changed_req_ids:
            downstream = knowledge_graph.find_downstream(req_id, max_depth=1)
            query_entry: dict[str, Any] = {
                "req_id": req_id,
                "downstream": downstream,
                "impact_radius": knowledge_graph.find_impact_radius(req_id, max_depth=2),
                "related_design": knowledge_graph.find_related_design(req_id),
                "related_tests": knowledge_graph.find_related_tests(req_id),
                "related_documents": knowledge_graph.find_related_documents(req_id),
            }
            for linked_id in downstream[:3]:
                path = knowledge_graph.explain_path(req_id, linked_id)
                if path.get("found"):
                    query_entry.setdefault("paths", []).append(path)
            context["queries"].append(query_entry)

        return context
