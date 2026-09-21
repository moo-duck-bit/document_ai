"""Platform Memory implementations."""

from document_ai.platform.memory.event_memory import EventMemory, EVENT_FIELDS, PlatformEvent
from document_ai.platform.memory.graph_builder import build_from_case
from document_ai.platform.memory.graph_export import export_graphml, export_json, import_json
from document_ai.platform.memory.graph_query import KnowledgeGraph, TraceabilityGraphAdapter, compute_change_impact
from document_ai.platform.memory.impact_engine import resolve_impact_engine, use_legacy_graph
from document_ai.platform.memory.knowledge_memory import KnowledgeMemory
from document_ai.platform.memory.legacy_adapter import LegacyTraceabilityAdapter

__all__ = [
    "EVENT_FIELDS",
    "EventMemory",
    "KnowledgeGraph",
    "KnowledgeMemory",
    "LegacyTraceabilityAdapter",
    "PlatformEvent",
    "TraceabilityGraphAdapter",
    "build_from_case",
    "compute_change_impact",
    "export_graphml",
    "export_json",
    "import_json",
    "resolve_impact_engine",
    "use_legacy_graph",
]
