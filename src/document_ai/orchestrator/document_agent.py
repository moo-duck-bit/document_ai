"""Dual-mode document agent orchestrator (Form Fill + Change Impact)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from document_ai.agents.orchestrator import run_change_pipeline
from document_ai.harness.document_harness import DocumentHarness
from document_ai.impact.change import load_change
from document_ai.safety.document_tnr import DocumentTNRSpec, assess_severity, baseline_from_session

Mode = Literal["new", "change"]


class DocumentAgent:
    """Unified entry: same TNR contract, two modes."""

    def __init__(
        self,
        *,
        tnr: DocumentTNRSpec | None = None,
        use_retrieval: bool = True,
        force_form_fill: bool = False,
    ) -> None:
        self.tnr = tnr or DocumentTNRSpec()
        self.harness = DocumentHarness(
            use_retrieval=use_retrieval,
            materialize=True,
            force_form_fill=force_form_fill,
        )

    def run(
        self,
        case_dir: Path | str,
        *,
        mode: Mode = "new",
        change: dict[str, Any] | Path | None = None,
        dry_run: bool = True,
        apply: bool = False,
        template_id: str | None = None,
    ) -> dict[str, Any]:
        case_dir = Path(case_dir).resolve()
        if mode == "new":
            result = self.harness.generate(
                case_dir,
                template_id=template_id,
                force_form_fill=self.harness.pipeline.force_form_fill,
            )
            return {
                "mode": "new",
                "case_dir": str(case_dir),
                "tnr_spec": self.tnr.to_dict(),
                "result": result,
            }

        if change is None:
            changes_dir = case_dir / "changes"
            default = changes_dir / "req_change.json"
            if default.exists():
                change = default
            else:
                json_files = sorted(changes_dir.glob("*.json")) if changes_dir.exists() else []
                if not json_files:
                    raise FileNotFoundError(f"No change JSON under {changes_dir}")
                change = json_files[0]

        if isinstance(change, Path):
            change_payload = load_change(change)
        else:
            change_payload = change

        report = run_change_pipeline(
            case_dir,
            change_payload,
            dry_run=dry_run if not apply else False,
            apply=apply,
            change_path=change if isinstance(change, Path) else None,
        )
        return {
            "mode": "change",
            "case_dir": str(case_dir),
            "tnr_spec": self.tnr.to_dict(),
            "result": report,
        }


def run_document_agent(
    case_dir: Path | str,
    *,
    mode: Mode = "new",
    change: dict[str, Any] | Path | None = None,
    dry_run: bool = True,
    apply: bool = False,
    ablation_variant: str | None = None,
) -> dict[str, Any]:
    from document_ai.safety.document_tnr import ablation_flags

    tnr = ablation_flags(ablation_variant) if ablation_variant else DocumentTNRSpec()
    agent = DocumentAgent(tnr=tnr)
    return agent.run(
        case_dir,
        mode=mode,
        change=change,
        dry_run=dry_run,
        apply=apply,
    )


def checkpoint_summary(session: dict[str, Any]) -> dict[str, Any]:
    """R1 checkpoint metadata for reporting."""
    fp = baseline_from_session(session)
    mu = assess_severity(
        {
            "false_patch": 0,
            "unsafe_write": 0,
            "original_broken": 0,
            "unapproved_write": 0,
        },
        baseline_ok=bool(fp),
    )
    return {"baseline_fingerprint": fp, "tnr": mu}
