"""Document Harness — service-level generate API (outside Platform Runtime)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from document_ai.harness.pipeline import GenerationPipeline, PipelineReport


class DocumentHarness:
    """End-to-end EC-SW document generation harness."""

    def __init__(self, **pipeline_kwargs: Any) -> None:
        self.pipeline = GenerationPipeline(**pipeline_kwargs)

    def generate(
        self,
        case_dir: str | Path,
        *,
        template_id: str | None = None,
        use_retrieval: bool | None = None,
        force_form_fill: bool | None = None,
    ) -> dict[str, Any]:
        if use_retrieval is not None:
            self.pipeline.use_retrieval = use_retrieval
        if force_form_fill is not None:
            self.pipeline.force_form_fill = force_form_fill

        report: PipelineReport = self.pipeline.run(Path(case_dir), template_id=template_id)
        return report.to_dict()
