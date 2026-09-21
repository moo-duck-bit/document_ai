"""Platform Runtime MVP for AI Engineering Platform."""

__all__ = [
    "DocumentHarness",
    "HarnessManager",
    "MemoryManager",
    "PlatformRuntime",
    "RuleBasedPlanner",
    "TaskGraph",
    "Workflow",
    "build_task_graph",
]


def __getattr__(name: str):
    if name == "DocumentHarness":
        from document_ai.platform.document_harness import DocumentHarness

        return DocumentHarness
    if name == "HarnessManager":
        from document_ai.platform.harness_manager import HarnessManager

        return HarnessManager
    if name == "MemoryManager":
        from document_ai.platform.memory_manager import MemoryManager

        return MemoryManager
    if name == "PlatformRuntime":
        from document_ai.platform.runtime import PlatformRuntime

        return PlatformRuntime
    if name == "RuleBasedPlanner":
        from document_ai.platform.planner import RuleBasedPlanner

        return RuleBasedPlanner
    if name == "TaskGraph":
        from document_ai.platform.task_graph import TaskGraph

        return TaskGraph
    if name == "Workflow":
        from document_ai.platform.workflow import Workflow

        return Workflow
    if name == "build_task_graph":
        from document_ai.platform.task_graph import build_task_graph

        return build_task_graph
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
