from __future__ import annotations

from typing import Any, Protocol

from document_ai.platform.document_harness import DocumentHarness
from document_ai.platform.operation.operation_harness import OperationHarness
from document_ai.platform.models import PlannerRequest, TaskSpec


class Harness(Protocol):
    harness_name: str

    def run(self, request: PlannerRequest, task: TaskSpec) -> dict[str, Any]:
        ...


class HarnessManager:
    def __init__(self) -> None:
        self._harnesses: dict[str, Harness] = {}
        self.register(DocumentHarness())
        self.register(OperationHarness())

    def register(self, harness: Harness) -> None:
        self._harnesses[harness.harness_name] = harness

    def get(self, name: str) -> Harness:
        try:
            return self._harnesses[name]
        except KeyError as exc:
            known = ", ".join(sorted(self._harnesses))
            raise KeyError(f"Unknown harness {name!r}. Known harnesses: {known}") from exc

    def run(self, name: str, request: PlannerRequest, task: TaskSpec) -> dict[str, Any]:
        return self.get(name).run(request, task)
