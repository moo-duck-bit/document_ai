# -*- coding: utf-8 -*-
"""User Scenario Runner — end-to-end CR → patch/review harness.

Reuses Trial 2 B1–B5 library modules. Does NOT read expected_impact or target Req IDs.
Never writes into data/trials/trial-001-* or trial-002-*.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from document_ai.impact.atomic_change import (
    acus_to_trace_payload,
    acus_to_trace_payload_v2,
    build_acu_scope_isolation,
    compare_acu_v1_vs_v2,
    decompose_change_request,
)
from document_ai.impact.consistency_gate import gate_impacted_decisions
from document_ai.impact.impact_judgment import judge_candidates
from document_ai.impact.new_requirement_proposal import (
    build_new_requirement_proposal,
    render_new_requirement_markdown,
)
from document_ai.impact.patch_plan import (
    build_shadow_patch_plans,
    compare_legacy_vs_shadow,
    patch_plans_to_trace_payload,
)
from document_ai.impact.patch_contract import (
    build_patch_contracts,
    compare_contracts_to_legacy,
    patch_contracts_to_trace_payload,
    validate_patch_contracts,
)
from document_ai.impact.preserve_patch import sha256_file
from document_ai.impact.propagation import (
    apply_b4_b5_patches,
    build_propagation_plan,
    proposed_mddr_design_description,
    proposed_mdsr_description,
)
from document_ai.impact.semantic_draft import (
    compare_legacy_vs_semantic_drafts,
    generate_semantic_drafts,
    semantic_drafts_to_trace_payload,
    semantic_generation_summary,
    validate_semantic_drafts,
)
from document_ai.impact.requirement_patch import (
    apply_requirement_patches,
    compare_legacy_vs_requirement_patches,
    requirement_patches_to_trace_payload,
    validate_requirement_patches,
)
from document_ai.impact.activation_policy import (
    activation_decisions_to_trace_payload,
    build_activation_summary,
    compare_legacy_vs_activation,
    decide_requirement_activations,
    validate_activation_decisions,
)
from document_ai.impact.activation_preview import build_activation_preview
from document_ai.impact.language_realizer import realize_requirement_patches
from document_ai.impact.preview_validation_gate import (
    preview_gate_to_trace_payload,
    run_preview_validation_gate,
)
from document_ai.impact.docx_activation_writer import run_docx_activation_writer
from document_ai.impact.change_review_package import run_change_review_package
from document_ai.template.inventory import run_template_abstraction_layer
from document_ai.template.generic_mapping import run_generic_document_template_pack
from document_ai.document_parser.parser import run_document_structure_mapping_engine
from document_ai.semantic_locator.locator import run_semantic_locator_engine
from document_ai.patch_targeting.orchestrator import run_patch_targeting_engine
from document_ai.physical_locator.orchestrator import run_physical_locator_engine
from document_ai.patch_contract.orchestrator import run_patch_contract_engine
from document_ai.controlled_writer.orchestrator import run_controlled_writer_engine
from document_ai.impact.semantic_hybrid_retrieve import rank_by_method, score_all_methods
from document_ai.impact.semantic_index import (
    dedupe_blocks,
    index_mddr_docx,
    index_mdsr_docx,
)
from document_ai.impact.staged_shadow_e2e import run_staged_shadow_e2e

FROZEN_TRIAL_MARKERS = (
    "data/trials/trial-001-mindrium-xa",
    "data/trials/trial-002-lockout-multireq",
)


@dataclass
class ScenarioPaths:
    root: Path
    cr: Path
    mdsr: Path
    mddr: Path
    output: Path

    @classmethod
    def from_scenario_dir(cls, scenario_dir: Path) -> "ScenarioPaths":
        root = scenario_dir.resolve()
        input_dir = root / "input"
        cr = input_dir / "change_request.txt"
        ref = input_dir / "reference"
        mdsr = _find_docx(ref, hints=("MDSR", "mdsr", "요구사항"))
        mddr = _find_docx(ref, hints=("MDDR", "mddr", "설계"))
        if not cr.exists():
            raise FileNotFoundError(f"Missing CR: {cr}")
        if mdsr is None:
            raise FileNotFoundError(f"Missing MDSR under {ref}")
        if mddr is None:
            raise FileNotFoundError(f"Missing MDDR under {ref}")
        return cls(root=root, cr=cr, mdsr=mdsr, mddr=mddr, output=root / "output")


def _find_docx(ref: Path, hints: tuple[str, ...]) -> Path | None:
    if not ref.is_dir():
        return None
    files = sorted(ref.glob("*.docx"))
    if not files:
        return None
    for hint in hints:
        for f in files:
            if hint.lower() in f.name.lower():
                return f
    # fallback: alphabetical first/second
    if len(hints) and "MDDR" in hints[0].upper() and len(files) >= 2:
        return files[1]
    return files[0]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _assert_not_frozen_trial_write(path: Path) -> None:
    norm = str(path.resolve()).replace("\\", "/")
    for marker in FROZEN_TRIAL_MARKERS:
        if marker in norm:
            raise RuntimeError(
                f"Refusing to write under frozen trial path: {path} (marker={marker})"
            )


def run_user_scenario(
    scenario_dir: Path,
    *,
    top_k: int = 15,
    clean_output: bool = True,
    document_set_mode: str = "legacy_pair",
) -> dict[str, Any]:
    """Execute full pipeline; write only under scenario_dir/output/.

    document_set_mode:
      - legacy_pair (default): MDSR/MDDR only; no document-set observational path
      - registry: also run MDTM Thin Core observational artifacts (does not alter actual path)
      - explicit_documents: reserved; currently same as registry
    """
    root = scenario_dir.resolve()
    _assert_not_frozen_trial_write(root)

    paths = ScenarioPaths.from_scenario_dir(scenario_dir)
    out = paths.output
    _assert_not_frozen_trial_write(out)

    # Preserve inputs: hash before
    cr_text = paths.cr.read_text(encoding="utf-8").strip()
    if not cr_text:
        raise ValueError("change_request.txt is empty")

    in_mdsr_sha = sha256_file(paths.mdsr)
    in_mddr_sha = sha256_file(paths.mddr)

    if clean_output and out.exists():
        shutil.rmtree(out)
    for sub in ("documents", "trace", "review"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "created_at": utc_now(),
        "scenario_id": paths.root.name,
        "stage": "user_scenario_runner",
        "expected_impact_used": False,
        "target_req_ids_injected": False,
        "inputs": {
            "change_request": str(paths.cr).replace("\\", "/"),
            "mdsr": str(paths.mdsr).replace("\\", "/"),
            "mddr": str(paths.mddr).replace("\\", "/"),
            "mdsr_sha256_before": in_mdsr_sha,
            "mddr_sha256_before": in_mddr_sha,
        },
        "status": "RUNNING",
        "errors": [],
        "warnings": [],
        "limitations": [
            "B3/B4 theme heuristics were validated primarily on auth/lockout-family CRs",
            "Semantic channel is TF-IDF cosine (not dense embedding)",
            "Auto-patch only when B4 CONSISTENT + allow_auto_patch",
            "PR-4 ACU decomposition is trace/shadow only; actual B3–B5 still use whole CR",
            "PR-5 B6 patch planning is shadow-only; actual whole-CR append unchanged",
            "PR-6 staged shadow E2E is analysis-only; actual owner/DOCX unchanged",
        ],
    }

    try:
        # --- B1 index ---
        blocks = dedupe_blocks(
            index_mdsr_docx(paths.mdsr) + index_mddr_docx(paths.mddr)
        )
        if not blocks:
            raise RuntimeError("Indexing produced zero requirement/design blocks")

        # --- B2 hybrid retrieve ---
        scored = score_all_methods(cr_text, blocks)
        ranked = rank_by_method(scored, "hybrid", top_k=top_k)
        retrieval_payload = {
            "method": "hybrid",
            "top_k": top_k,
            "expected_impact_used": False,
            "candidates": [h.to_dict() for h in ranked],
        }
        (out / "trace" / "retrieval_candidates.json").write_text(
            json.dumps(retrieval_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # --- ACU decomposition (PR-4/PR-7): trace / shadow only — actual B3 still uses whole CR ---
        acu_units = decompose_change_request(cr_text)
        acu_payload = acus_to_trace_payload(cr_text, acu_units)
        (out / "trace" / "atomic_change_units.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    "stage": "ACU",
                    **acu_payload,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "atomic_change_units_v2.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **acus_to_trace_payload_v2(cr_text, acu_units),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "acu_scope_isolation.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **build_acu_scope_isolation(cr_text, acu_units),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "acu_v1_vs_v2_shadow.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **compare_acu_v1_vs_v2(cr_text),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        # --- B3 ---
        decisions_b3 = judge_candidates(cr_text, blocks, ranked)
        impact_payload = {
            "expected_impact_used": False,
            "decisions": [d.to_dict() for d in decisions_b3],
            "summary": {
                "IMPACTED": sum(1 for d in decisions_b3 if d.judgment == "IMPACTED"),
                "NOT_IMPACTED": sum(1 for d in decisions_b3 if d.judgment == "NOT_IMPACTED"),
                "UNCERTAIN": sum(1 for d in decisions_b3 if d.judgment == "UNCERTAIN"),
            },
        }
        (out / "trace" / "impact_judgments.json").write_text(
            json.dumps(impact_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # --- Zero-IMPACTED fallback: structured NEW_REQUIREMENT proposal (no DOCX insert) ---
        new_req_proposal = build_new_requirement_proposal(cr_text, decisions_b3, ranked)
        if new_req_proposal is not None:
            (out / "trace" / "new_requirement_candidates.json").write_text(
                json.dumps(
                    {
                        "expected_impact_used": False,
                        "proposal": new_req_proposal.to_dict(),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (out / "review" / "NEW_REQUIREMENT_PROPOSAL.md").write_text(
                render_new_requirement_markdown(new_req_proposal), encoding="utf-8"
            )

        # --- B4 ---
        consistency = gate_impacted_decisions(
            cr_text,
            blocks,
            [d.to_dict() for d in decisions_b3],
            focus_ids=None,
        )
        cons_payload = {
            "expected_impact_used": False,
            "decisions": [d.to_dict() for d in consistency],
            "summary": {
                "CONSISTENT": sum(1 for d in consistency if d.status == "CONSISTENT"),
                "CONFLICT": sum(1 for d in consistency if d.status == "CONFLICT"),
                "NEEDS_REVIEW": sum(1 for d in consistency if d.status == "NEEDS_REVIEW"),
            },
        }
        (out / "trace" / "consistency_decisions.json").write_text(
            json.dumps(cons_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # --- B5 plan + apply (PR-8: ACU owner selection; generation/DOCX helpers unchanged) ---
        traces, staged = build_propagation_plan(
            cr_text,
            consistency,
            blocks,
            b3_decisions=[d.to_dict() for d in decisions_b3],
            return_stages=True,
            acus=acu_units,
            owner_selection_mode="auto",
        )
        out_mdsr = out / "documents" / "updated_MDSR.docx"
        out_mddr = out / "documents" / "updated_MDDR.docx"
        patch_report = apply_b4_b5_patches(
            ref_mdsr=paths.mdsr,
            ref_mddr=paths.mddr,
            out_mdsr=out_mdsr,
            out_mddr=out_mddr,
            consistency=consistency,
            traces=traces,
            cr_text=cr_text,
            blocks=blocks,
        )

        prop_payload = {
            "expected_impact_used": False,
            "traces": [t.to_dict() for t in traces],
            "summary": {
                "PATCHED": sum(1 for t in traces if t.outcome == "PATCHED"),
                "SKIPPED_WITH_REASON": sum(
                    1 for t in traces if t.outcome == "SKIPPED_WITH_REASON"
                ),
                "NEEDS_REVIEW": sum(1 for t in traces if t.outcome == "NEEDS_REVIEW"),
                "propagation_decisions": {
                    k: sum(1 for t in traces if t.propagation_decision == k)
                    for k in (
                        "PATCH_EXISTING",
                        "EXTEND_EXISTING",
                        "NEW_DESIGN_CANDIDATE",
                        "SKIP",
                        "NEEDS_REVIEW",
                    )
                },
            },
            "patch_report": {k: v for k, v in patch_report.items() if k != "diffs"},
            "diffs": patch_report.get("diffs"),
        }
        (out / "trace" / "propagation_trace.json").write_text(
            json.dumps(prop_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        # Staged architecture traces (PR-1): discovery / alignment / decision
        (out / "trace" / "design_candidates.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    "stage": "B5a",
                    "entries": staged.get("design_candidates") or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "responsibility_alignment.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    "stage": "B5b",
                    "entries": staged.get("responsibility_alignment") or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "propagation_decisions.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    "stage": "B5c",
                    "entries": staged.get("propagation_decisions") or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        # PR-8 owner activation (ACU v2 selection; generation/DOCX unchanged)
        (out / "trace" / "owner_activation_summary.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(staged.get("owner_activation_summary") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "owner_activation_diff.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(staged.get("owner_activation_diff") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "acu_owner_mapping.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(staged.get("acu_owner_mapping") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        # PR-2 shadow evaluation traces (observation only — does not select owner)
        (out / "trace" / "design_candidates_shadow.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    "stage": "B5a_shadow",
                    "note": "Shadow candidate comparison does not select a new owner.",
                    "entries": staged.get("design_candidates_shadow") or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "responsibility_alignment_shadow.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    "stage": "B5b_shadow",
                    "note": "Shadow candidate comparison does not select a new owner.",
                    "entries": staged.get("responsibility_alignment_shadow") or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "design_candidate_shadow_comparison.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    "stage": "B5a_shadow_comparison",
                    "note": "Shadow candidate comparison does not select a new owner.",
                    "entries": staged.get("design_candidate_shadow_comparison") or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        # PR-3 evidence provenance / lineage (observational; does not select owner)
        (out / "trace" / "evidence_provenance.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    "stage": "B5_evidence_provenance",
                    **(staged.get("evidence_provenance") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        # --- B6 semantic patch planning (PR-5): shadow only — does not mutate DOCX ---
        shadow_plans = build_shadow_patch_plans(
            cr_text=cr_text, acus=acu_units, traces=traces
        )
        (out / "trace" / "patch_plan_shadow.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **patch_plans_to_trace_payload(
                        cr_text=cr_text, acus=acu_units, plans=shadow_plans
                    ),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "legacy_vs_patch_plan_shadow.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    "stage": "B6_legacy_vs_shadow",
                    **compare_legacy_vs_shadow(
                        cr_text=cr_text, traces=traces, plans=shadow_plans
                    ),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        # --- PR-9 Patch Contract (shadow only — no prose / no DOCX) ---
        patch_contracts = build_patch_contracts(
            acus=acu_units, plans=shadow_plans, traces=traces
        )
        contract_validation = validate_patch_contracts(patch_contracts)
        (out / "trace" / "patch_contracts.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **patch_contracts_to_trace_payload(
                        contracts=patch_contracts, validation=contract_validation
                    ),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "patch_contract_validation.json").write_text(
            json.dumps(
                {"expected_impact_used": False, **contract_validation},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "patch_contract_diff.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **compare_contracts_to_legacy(
                        contracts=patch_contracts, traces=traces, plans=shadow_plans
                    ),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        # --- PR-10 shadow semantic generation (no DOCX / no legacy replacement) ---
        owner_target_texts: dict[str, str] = {}
        for b in blocks:
            key = b.req_id
            blob = f"{b.title}\n{b.body_text}"
            if key in owner_target_texts:
                owner_target_texts[key] = owner_target_texts[key] + "\n" + blob
            else:
                owner_target_texts[key] = blob
        semantic_drafts = generate_semantic_drafts(
            patch_contracts, owner_target_texts=owner_target_texts
        )
        draft_validation = validate_semantic_drafts(semantic_drafts)
        legacy_texts: list[str] = []
        for tr in traces:
            if not tr.allow_mdsr_patch:
                continue
            # Observational only — same helpers used by actual generation
            for d in consistency:
                if d.req_id == tr.source_mdsr_req_id and d.document == "MDSR":
                    t = proposed_mdsr_description(d, cr_text)
                    if t:
                        legacy_texts.append(t)
            mddr_b = next(
                (
                    b
                    for b in blocks
                    if b.req_id == tr.source_mdsr_req_id and b.document_type == "MDDR"
                ),
                None,
            )
            if mddr_b is not None:
                dt = proposed_mddr_design_description(mddr_b, cr_text)
                if dt:
                    legacy_texts.append(dt)
        (out / "trace" / "semantic_drafts_shadow.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **semantic_drafts_to_trace_payload(semantic_drafts),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "semantic_draft_validation.json").write_text(
            json.dumps(
                {"expected_impact_used": False, **draft_validation},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "legacy_vs_semantic_draft.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **compare_legacy_vs_semantic_drafts(
                        legacy_generation_texts=legacy_texts,
                        drafts=semantic_drafts,
                        whole_cr=cr_text,
                    ),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "semantic_generation_summary.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **semantic_generation_summary(
                        contracts=patch_contracts, drafts=semantic_drafts
                    ),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        # --- PR-11 shadow requirement patch application (no DOCX) ---
        requirement_texts: dict[str, str] = {}
        for b in blocks:
            # Prefer body as field text; also expose ::description / ::design_body keys
            requirement_texts[b.req_id] = (b.body_text or b.title or "").strip()
            if b.document_type == "MDSR":
                requirement_texts[f"{b.req_id}::description"] = requirement_texts[b.req_id]
                requirement_texts[f"{b.req_id}::criteria"] = requirement_texts[b.req_id]
            if b.document_type == "MDDR":
                requirement_texts[f"{b.req_id}::design_body"] = requirement_texts[b.req_id]
                requirement_texts[f"{b.req_id}::design_condition"] = requirement_texts[b.req_id]
        req_patches = apply_requirement_patches(
            drafts=semantic_drafts, requirement_texts=requirement_texts
        )
        req_patch_validation = validate_requirement_patches(req_patches)
        (out / "trace" / "requirement_patches_shadow.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **requirement_patches_to_trace_payload(req_patches),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "requirement_patch_validation.json").write_text(
            json.dumps(
                {"expected_impact_used": False, **req_patch_validation},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "legacy_vs_requirement_patch.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **compare_legacy_vs_requirement_patches(
                        patches=req_patches, legacy_generation_texts=legacy_texts
                    ),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        # --- PR-14 shadow language realizer (surface only; no DOCX) ---
        language_payload = realize_requirement_patches(req_patches)
        realized_patches = language_payload["realized_patches"]
        (out / "trace" / "language_realization.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(language_payload.get("trace") or {}),
                    "validation": language_payload.get("validation") or {},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "language_summary.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(language_payload.get("summary") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "language_vs_patch.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(language_payload.get("language_vs_patch") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        # --- PR-12 shadow activation policy (no DOCX apply) ---
        # Consume language-realized patch texts (orchestration only; policy code unchanged).
        activation_decisions = decide_requirement_activations(realized_patches)
        activation_summary = build_activation_summary(activation_decisions)
        activation_policy_validation = validate_activation_decisions(activation_decisions)
        (out / "trace" / "requirement_activation_decisions.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **activation_decisions_to_trace_payload(activation_decisions),
                    "policy_validation": activation_policy_validation,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "activation_summary.json").write_text(
            json.dumps(
                {"expected_impact_used": False, **activation_summary},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "legacy_vs_activation.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **compare_legacy_vs_activation(
                        decisions=activation_decisions,
                        legacy_generation_texts=legacy_texts,
                    ),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        # --- PR-13 shadow activation preview (no DOCX apply) ---
        preview_payload = build_activation_preview(
            patches=realized_patches,
            decisions=activation_decisions,
            legacy_generation_texts=legacy_texts,
        )
        (out / "trace" / "activation_preview.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    "stage": preview_payload.get("stage"),
                    "schema_version": preview_payload.get("schema_version"),
                    "entries": preview_payload.get("entries") or [],
                    "aggregated_requirement_previews": preview_payload.get(
                        "aggregated_requirement_previews"
                    )
                    or [],
                    "review_queue": preview_payload.get("review_queue") or [],
                    "blocked_queue": preview_payload.get("blocked_queue") or [],
                    "note": preview_payload.get("note"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "preview_validation.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(preview_payload.get("validation") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "preview_summary.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(preview_payload.get("summary") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "preview_vs_legacy.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(preview_payload.get("preview_vs_legacy") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        # --- PR-15 shadow preview validation gate (observational; no DOCX) ---
        gate_payload = run_preview_validation_gate(
            patches=realized_patches,
            languages=language_payload.get("realizations") or [],
            decisions=activation_decisions,
            preview_entries=preview_payload.get("entries") or [],
            aggregated=preview_payload.get("aggregated_requirement_previews") or [],
            preview_validation=preview_payload.get("validation") or {},
            actual_docx_changed=False,
            actual_generation_changed=False,
        )
        (out / "trace" / "preview_gate_results.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **preview_gate_to_trace_payload(gate_payload),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "preview_gate_summary.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(gate_payload.get("summary") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "preview_gate_vs_activation.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(gate_payload.get("gate_vs_activation") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        # --- PR-16 feature-flag DOCX activation writer (default OFF; never in-place) ---
        activation_out_dir = out / "activated"
        docx_activation = run_docx_activation_writer(
            gate_payload=gate_payload,
            preview_entries=preview_payload.get("entries") or [],
            patches=realized_patches,
            source_docx_by_document={
                "MDSR": paths.mdsr,
                "MDDR": paths.mddr,
            },
            output_dir=activation_out_dir,
            # Defaults: env DOCX_ACTIVATION_ENABLED=false, policy=strict_global
            feature_flag_enabled=None,
            execution_policy=None,
        )
        (out / "trace" / "docx_activation_plan.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(docx_activation.get("plan") or {}),
                    "plan_validation": docx_activation.get("plan_validation") or {},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "docx_activation_results.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(docx_activation.get("results") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "docx_activation_summary.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(docx_activation.get("summary") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "docx_activation_vs_preview.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(docx_activation.get("vs_preview") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "docx_activation_validation.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(docx_activation.get("validation") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        # --- PR-17 Change Review Package (observational; no DOCX mutation) ---
        try:
            review_pkg = run_change_review_package(
                gate_payload=gate_payload,
                preview_entries=preview_payload.get("entries") or [],
                patches=realized_patches,
                activation_payload=docx_activation,
                cr_text=cr_text,
                acus=[
                    {
                        **(a.to_dict() if hasattr(a, "to_dict") else {}),
                        "atomic_change_id": getattr(a, "change_id", None)
                        or getattr(a, "atomic_change_id", None),
                    }
                    for a in (acu_units or [])
                ],

                feature_flag_enabled=bool(
                    (docx_activation.get("results") or {}).get("feature_flag_enabled", False)
                ),
            )
        except Exception as exc:  # noqa: BLE001
            review_pkg = {
                "stage": "change_review_package",
                "schema_version": "change_review_package_v1",
                "items": [],
                "groups": [],
                "summary": {
                    "stage": "change_review_summary",
                    "total_count": 0,
                    "global_review_status": "BLOCKED",
                    "error": str(exc),
                },
                "before_after": {"pairs": []},
                "markdown": f"# Change Review\n\nReview package failed: {exc}\n",
                "validation": {
                    "stage": "change_review_validation",
                    "status": "INVALID",
                    "issues": [f"review_package_error:{exc}"],
                    "warnings": [],
                    "invariants": {},
                },
                "note": "Fail-loud review package error; prior artifacts preserved.",
            }
        review_dir = out / "review"
        review_dir.mkdir(parents=True, exist_ok=True)
        (review_dir / "change_review.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    "stage": review_pkg.get("stage"),
                    "schema_version": review_pkg.get("schema_version"),
                    "items": review_pkg.get("items") or [],
                    "note": review_pkg.get("note"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (review_dir / "change_review_summary.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(review_pkg.get("summary") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (review_dir / "change_review.md").write_text(
            str(review_pkg.get("markdown") or ""),
            encoding="utf-8",
        )
        (review_dir / "before_after.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(review_pkg.get("before_after") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (review_dir / "change_groups.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    "stage": "change_groups",
                    "groups": review_pkg.get("groups") or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "change_review_validation.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(review_pkg.get("validation") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        # --- PR-18 Template Abstraction Layer (observational; no DOCX / no mutate) ---
        try:
            template_pkg = run_template_abstraction_layer(
                review_items=review_pkg.get("items") or [],
                patches=realized_patches,
                preview_entries=preview_payload.get("entries") or [],
                gate_results=gate_payload.get("results") or [],
                activation_items=(docx_activation.get("results") or {}).get("items")
                or (docx_activation.get("plan") or {}).get("items")
                or [],
            )
        except Exception as exc:  # noqa: BLE001
            template_pkg = {
                "stage": "template_abstraction_layer",
                "schema_version": "template_schema_v1",
                "registry": {"templates": []},
                "inventory": {},
                "nodes": {"nodes": []},
                "mappings": {"mappings": []},
                "summary": {
                    "global_template_status": "INVALID",
                    "error": str(exc),
                },
                "validation": {
                    "status": "INVALID",
                    "issues": [f"template_layer_error:{exc}"],
                    "global_template_status": "INVALID",
                },
                "note": "Fail-loud template layer error; prior artifacts preserved.",
            }
        template_dir = out / "template"
        template_dir.mkdir(parents=True, exist_ok=True)
        (template_dir / "template_registry.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(template_pkg.get("registry") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (template_dir / "template_inventory.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(template_pkg.get("inventory") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (template_dir / "template_nodes.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(template_pkg.get("nodes") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (template_dir / "template_mappings.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(template_pkg.get("mappings") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (template_dir / "template_summary.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(template_pkg.get("summary") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "template_validation.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(template_pkg.get("validation") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        # --- PR-19 Generic Document Template Pack (observational; isolated artifacts) ---
        try:
            generic_pkg = run_generic_document_template_pack()
        except Exception as exc:  # noqa: BLE001
            # Fail-loud for generic pack only — never mutate prior PR-18 artifacts.
            generic_pkg = {
                "stage": "generic_document_template_pack",
                "schema_version": "template_schema_v1",
                "registry": {"templates": []},
                "nodes": {"nodes": []},
                "sample_documents": {"samples": []},
                "mappings": {"mappings": []},
                "summary": {
                    "global_generic_template_status": "INVALID",
                    "error": str(exc),
                },
                "validation": {
                    "status": "INVALID",
                    "issues": [f"generic_template_pack_error:{exc}"],
                    "global_generic_template_status": "INVALID",
                },
                "note": "Fail-loud generic pack error; PR-18 artifacts preserved.",
                "actual_docx_changed": False,
                "actual_generation_changed": False,
            }
        (template_dir / "generic_template_registry.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(generic_pkg.get("registry") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (template_dir / "generic_template_nodes.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(generic_pkg.get("nodes") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (template_dir / "generic_sample_documents.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(generic_pkg.get("sample_documents") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (template_dir / "generic_template_mappings.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(generic_pkg.get("mappings") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (template_dir / "generic_template_summary.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(generic_pkg.get("summary") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "generic_template_validation.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(generic_pkg.get("validation") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        # --- PR-20 Document Structure Mapping Engine (observational; no DOCX mutate) ---
        try:
            structure_pkg = run_document_structure_mapping_engine()
        except Exception as exc:  # noqa: BLE001
            structure_pkg = {
                "stage": "document_structure_mapping_engine",
                "schema_version": "document_structure_v1",
                "documents": [],
                "section_trees": [],
                "locator_candidates": {},
                "statistics": {},
                "validation": {
                    "status": "INVALID",
                    "issues": [f"document_structure_error:{exc}"],
                },
                "summary": {
                    "validation_status": "INVALID",
                    "error": str(exc),
                },
                "note": "Fail-loud structure mapping error; prior artifacts preserved.",
                "actual_docx_changed": False,
                "actual_generation_changed": False,
            }
        structure_dir = out / "document_structure"
        structure_dir.mkdir(parents=True, exist_ok=True)
        (structure_dir / "document_structure.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    "stage": "document_structure",
                    "documents": structure_pkg.get("documents") or [],
                    "note": structure_pkg.get("note"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (structure_dir / "section_tree.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    "stage": "section_tree",
                    "trees": structure_pkg.get("section_trees") or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (structure_dir / "locator_candidates.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    "stage": "locator_candidates",
                    "candidates": structure_pkg.get("locator_candidates") or {},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (structure_dir / "document_statistics.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(structure_pkg.get("statistics") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (structure_dir / "document_validation.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(structure_pkg.get("validation") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (structure_dir / "summary.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(structure_pkg.get("summary") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        # --- PR-21 Semantic Locator Engine (observational; no DOCX / no patch) ---
        try:
            semantic_pkg = run_semantic_locator_engine()
        except Exception as exc:  # noqa: BLE001
            semantic_pkg = {
                "stage": "semantic_locator_engine",
                "schema_version": "semantic_locator_v1",
                "inputs": [],
                "template_node_candidates": [],
                "match_results": [],
                "ranked_matches": [],
                "summary": {
                    "global_semantic_locator_status": "INVALID",
                    "error": str(exc),
                },
                "validation": {
                    "status": "INVALID",
                    "issues": [f"semantic_locator_error:{exc}"],
                },
                "note": "Fail-loud semantic locator error; prior artifacts preserved.",
                "actual_docx_changed": False,
                "actual_generation_changed": False,
            }
        semantic_dir = out / "semantic_locator"
        semantic_dir.mkdir(parents=True, exist_ok=True)
        (semantic_dir / "semantic_locator_inputs.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    "stage": "semantic_locator_inputs",
                    "inputs": semantic_pkg.get("inputs") or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (semantic_dir / "template_node_candidates.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    "stage": "template_node_candidates",
                    "candidates": semantic_pkg.get("template_node_candidates") or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (semantic_dir / "semantic_match_results.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    "stage": "semantic_match_results",
                    "results": semantic_pkg.get("match_results") or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (semantic_dir / "ranked_template_matches.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    "stage": "ranked_template_matches",
                    "matches": semantic_pkg.get("ranked_matches") or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (semantic_dir / "semantic_locator_summary.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(semantic_pkg.get("summary") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (semantic_dir / "semantic_locator_validation.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(semantic_pkg.get("validation") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        # --- PR-22 Patch Targeting / Patch Intent Bridge (observational; no write) ---
        try:
            targeting_pkg = run_patch_targeting_engine()
        except Exception as exc:  # noqa: BLE001
            targeting_pkg = {
                "stage": "patch_targeting_engine",
                "schema_version": "patch_targeting_v1",
                "inputs": [],
                "intents": [],
                "targets": [],
                "previews": [],
                "summary": {
                    "global_patch_targeting_status": "INVALID",
                    "error": str(exc),
                },
                "validation": {
                    "status": "INVALID",
                    "issues": [f"patch_targeting_error:{exc}"],
                },
                "note": "Fail-loud patch targeting error; prior artifacts preserved.",
                "actual_docx_changed": False,
                "actual_generation_changed": False,
                "actual_patch_created": False,
                "actual_writer_called": False,
            }
        targeting_dir = out / "patch_targeting"
        targeting_dir.mkdir(parents=True, exist_ok=True)
        (targeting_dir / "patch_targeting_inputs.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    "stage": "patch_targeting_inputs",
                    "inputs": targeting_pkg.get("inputs") or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (targeting_dir / "patch_intents.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    "stage": "patch_intents",
                    "intents": targeting_pkg.get("intents") or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (targeting_dir / "patch_target_candidates.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    "stage": "patch_target_candidates",
                    "targets": targeting_pkg.get("targets") or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (targeting_dir / "activation_previews.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    "stage": "activation_previews",
                    "previews": targeting_pkg.get("previews") or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (targeting_dir / "patch_targeting_summary.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(targeting_pkg.get("summary") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (targeting_dir / "patch_targeting_validation.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(targeting_pkg.get("validation") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        # --- PR-23 Physical Locator (observational; no DOCX / Writer) ---
        try:
            physical_pkg = run_physical_locator_engine()
        except Exception as exc:  # noqa: BLE001
            physical_pkg = {
                "stage": "physical_locator_engine",
                "schema_version": "physical_locator_v1",
                "inputs": [],
                "candidates": [],
                "primaries": [],
                "summary": {
                    "global_physical_locator_status": "INVALID",
                    "error": str(exc),
                },
                "validation": {
                    "status": "INVALID",
                    "issues": [f"physical_locator_error:{exc}"],
                },
                "note": "Fail-loud physical locator error; prior artifacts preserved.",
                "actual_docx_changed": False,
                "actual_writer_called": False,
                "actual_patch_created": False,
            }
        physical_dir = out / "physical_locator"
        physical_dir.mkdir(parents=True, exist_ok=True)
        (physical_dir / "physical_locator_inputs.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    "stage": "physical_locator_inputs",
                    "inputs": physical_pkg.get("inputs") or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        artifact_meta = physical_pkg.get("artifact_meta") or {
            "candidate_scope": "TOP_K_PER_TARGET",
            "top_k_limit": 8,
            "full_candidate_count": len(physical_pkg.get("full_candidates") or []),
            "artifact_candidate_count": len(physical_pkg.get("candidates") or []),
        }
        (physical_dir / "physical_location_candidates.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    "stage": "physical_location_candidates",
                    "candidate_scope": artifact_meta.get("candidate_scope"),
                    "top_k_limit": artifact_meta.get("top_k_limit"),
                    "full_candidate_count": artifact_meta.get("full_candidate_count"),
                    "artifact_candidate_count": artifact_meta.get(
                        "artifact_candidate_count"
                    ),
                    "candidates": physical_pkg.get("candidates") or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (physical_dir / "physical_location_candidates_topk.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    "stage": "physical_location_candidates_topk",
                    "candidate_scope": "TOP_K_PER_TARGET",
                    "top_k_limit": artifact_meta.get("top_k_limit", 8),
                    "full_candidate_count": artifact_meta.get("full_candidate_count"),
                    "artifact_candidate_count": artifact_meta.get(
                        "artifact_candidate_count"
                    ),
                    "candidates": physical_pkg.get("artifact_candidates")
                    or physical_pkg.get("candidates")
                    or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (physical_dir / "primary_physical_locations.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    "stage": "primary_physical_locations",
                    "primaries": physical_pkg.get("primaries") or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (physical_dir / "physical_locator_summary.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(physical_pkg.get("summary") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (physical_dir / "physical_locator_validation.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **(physical_pkg.get("validation") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        # --- PR-24 Patch Contract / Writer Plan Bridge (observational; no Writer/DOCX) ---
        try:
            patch_contract_pkg = run_patch_contract_engine()
        except Exception as exc:  # noqa: BLE001
            patch_contract_pkg = {
                "stage": "patch_contract_engine",
                "schema_version": "patch_contract_v1",
                "inputs": [],
                "contracts": [],
                "preconditions": [],
                "operation_plans": [],
                "writer_plan_previews": [],
                "summary": {
                    "global_patch_contract_status": "INVALID",
                    "error": str(exc),
                },
                "validation": {
                    "status": "INVALID",
                    "issues": [f"patch_contract_error:{exc}"],
                },
                "note": "Fail-loud patch contract error; prior artifacts preserved.",
                "actual_patch_created": False,
                "actual_document_changed": False,
                "actual_docx_changed": False,
                "actual_writer_called": False,
                "activation_allowed": False,
                "contract_executable": False,
            }
        pc_dir = out / "patch_contract"
        pc_dir.mkdir(parents=True, exist_ok=True)
        _pc_meta = {
            "expected_impact_used": False,
            "stage": "patch_contract",
            "schema_version": "patch_contract_v1",
            "observational_only": True,
            "generated_from_pr22": True,
            "generated_from_pr23": True,
            "external_activation_flag": bool(
                patch_contract_pkg.get("external_activation_flag", False)
            ),
            "observational_gate_forced_off": True,
            "actual_patch_created": False,
            "actual_document_changed": False,
            "actual_writer_called": False,
            "actual_docx_changed": False,
            "activation_allowed": False,
            "contract_executable": False,
        }
        (pc_dir / "patch_contract_inputs.json").write_text(
            json.dumps(
                {**_pc_meta, "stage": "patch_contract_inputs", "inputs": patch_contract_pkg.get("inputs") or []},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (pc_dir / "patch_contracts.json").write_text(
            json.dumps(
                {
                    **_pc_meta,
                    "stage": "patch_contracts",
                    "contracts": patch_contract_pkg.get("contracts") or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (pc_dir / "patch_preconditions.json").write_text(
            json.dumps(
                {
                    **_pc_meta,
                    "stage": "patch_preconditions",
                    "preconditions": patch_contract_pkg.get("preconditions") or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (pc_dir / "patch_operation_plans.json").write_text(
            json.dumps(
                {
                    **_pc_meta,
                    "stage": "patch_operation_plans",
                    "operation_plans": patch_contract_pkg.get("operation_plans") or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (pc_dir / "writer_plan_previews.json").write_text(
            json.dumps(
                {
                    **_pc_meta,
                    "stage": "writer_plan_previews",
                    "writer_plan_previews": patch_contract_pkg.get(
                        "writer_plan_previews"
                    )
                    or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (pc_dir / "patch_contract_summary.json").write_text(
            json.dumps(
                {**_pc_meta, **(patch_contract_pkg.get("summary") or {})},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (pc_dir / "patch_contract_validation.json").write_text(
            json.dumps(
                {**_pc_meta, **(patch_contract_pkg.get("validation") or {})},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        # --- PR-25 Controlled Writer Activation (copy-only; dual flags + approval) ---
        writer_dir = out / "writer"
        writer_dir.mkdir(parents=True, exist_ok=True)
        try:
            writer_pkg = run_controlled_writer_engine(
                work_dir=writer_dir / "_engine",
                env={
                    "DOCX_ACTIVATION_ENABLED": "true",
                    "CONTROLLED_WRITER_ENABLED": "true",
                },
            )
        except Exception as exc:  # noqa: BLE001
            writer_pkg = {
                "stage": "controlled_writer_engine",
                "schema_version": "controlled_writer_v1",
                "approvals": [],
                "writer_plans": [],
                "writer_results": [],
                "diffs": [],
                "rollbacks": [],
                "summary": {"error": str(exc), "original_changed_count": 0},
                "validation": {
                    "status": "INVALID",
                    "issues": [f"controlled_writer_error:{exc}"],
                },
                "note": "Fail-loud controlled writer error; prior artifacts preserved.",
            }
        _w_meta = {
            "expected_impact_used": False,
            "schema_version": "controlled_writer_v1",
            "original_changed_count": int(
                (writer_pkg.get("summary") or {}).get("original_changed_count", 0)
            ),
        }
        (writer_dir / "approval.json").write_text(
            json.dumps(
                {
                    **_w_meta,
                    "stage": "approval",
                    "approvals": writer_pkg.get("approvals") or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (writer_dir / "writer_plan.json").write_text(
            json.dumps(
                {
                    **_w_meta,
                    "stage": "writer_plan",
                    "writer_plans": writer_pkg.get("writer_plans") or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (writer_dir / "writer_result.json").write_text(
            json.dumps(
                {
                    **_w_meta,
                    "stage": "writer_result",
                    "writer_results": writer_pkg.get("writer_results") or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (writer_dir / "diff.json").write_text(
            json.dumps(
                {
                    **_w_meta,
                    "stage": "diff",
                    "diffs": writer_pkg.get("diffs") or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (writer_dir / "rollback.json").write_text(
            json.dumps(
                {
                    **_w_meta,
                    "stage": "rollback",
                    "rollbacks": writer_pkg.get("rollbacks") or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (writer_dir / "validation.json").write_text(
            json.dumps(
                {**_w_meta, **(writer_pkg.get("validation") or {})},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (writer_dir / "summary.json").write_text(
            json.dumps(
                {**_w_meta, **(writer_pkg.get("summary") or {})},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        # --- PR-6 staged shadow E2E (analysis only — does not mutate DOCX / actual B5c) ---
        staged_e2e = run_staged_shadow_e2e(
            cr_text=cr_text,
            acus=acu_units,
            blocks=blocks,
            consistency=consistency,
            b3_decisions=[d.to_dict() for d in decisions_b3],
            actual_traces=traces,
        )
        (out / "trace" / "staged_shadow_execution.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    **{
                        k: v
                        for k, v in staged_e2e.items()
                        if k
                        not in (
                            "acu_owner_candidates",
                            "acu_owner_recommendations",
                            "staged_patch_plans",
                            "legacy_vs_staged",
                        )
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "acu_owner_candidates_shadow.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    "stage": "staged_shadow_candidates",
                    "entries": staged_e2e.get("acu_owner_candidates") or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "acu_owner_recommendations_shadow.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    "stage": "staged_shadow_recommendations",
                    "note": "recommended_owner is NOT the actual patch owner.",
                    "entries": staged_e2e.get("acu_owner_recommendations") or [],
                    "summary": staged_e2e.get("summary") or {},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "staged_patch_plan_shadow.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    "stage": "staged_shadow_b6",
                    "patch_plans": staged_e2e.get("staged_patch_plans") or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (out / "trace" / "legacy_vs_staged_shadow.json").write_text(
            json.dumps(
                {
                    "expected_impact_used": False,
                    "stage": "legacy_vs_staged_shadow",
                    **(staged_e2e.get("legacy_vs_staged") or {}),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        # --- NEW_REQUIREMENT_CANDIDATE / review flags ---
        auto_patched = bool(patch_report.get("mdsr_patched_req_ids"))
        conflicts = [d for d in consistency if d.status == "CONFLICT"]
        needs_review = [d for d in consistency if d.status == "NEEDS_REVIEW"]
        uncertain_b3 = [d for d in decisions_b3 if d.judgment == "UNCERTAIN"]
        new_req = new_req_proposal is not None
        new_req_reason = (
            new_req_proposal.trigger
            if new_req_proposal is not None
            else ""
        )

        review_flags = {
            "NEW_REQUIREMENT_CANDIDATE": new_req,
            "new_requirement_reason": new_req_reason,
            "new_requirement_proposal_path": (
                str(out / "review" / "NEW_REQUIREMENT_PROPOSAL.md").replace("\\", "/")
                if new_req
                else None
            ),
            "conflicts": [d.req_id for d in conflicts],
            "needs_review_consistency": [d.req_id for d in needs_review],
            "uncertain_impact": [
                {
                    "id": d.candidate_id,
                    "doc": d.document,
                    "change_type": d.change_type,
                }
                for d in uncertain_b3
            ],
        }

        # Verify inputs unchanged
        if sha256_file(paths.mdsr) != in_mdsr_sha or sha256_file(paths.mddr) != in_mddr_sha:
            raise RuntimeError("Input DOCX hashes changed — aborting (inputs must be immutable)")

        _write_review_docs(
            out=out,
            cr_text=cr_text,
            ranked=ranked,
            decisions_b3=decisions_b3,
            consistency=consistency,
            traces=traces,
            patch_report=patch_report,
            review_flags=review_flags,
        )

        final_status = "COMPLETED"
        if conflicts and not auto_patched and not patch_report.get("mddr_patched_req_ids"):
            final_status = "COMPLETED_WITH_CONFLICTS"
        if needs_review or uncertain_b3 or new_req:
            if final_status == "COMPLETED":
                final_status = "COMPLETED_NEEDS_REVIEW"
            elif final_status == "COMPLETED_WITH_CONFLICTS":
                final_status = "COMPLETED_WITH_CONFLICTS_AND_REVIEW"

        # --- Thin Generic Core / MDTM observational (does not mutate actual MDSR/MDDR path) ---
        document_set_obs: dict[str, Any] | None = None
        mode = (document_set_mode or "legacy_pair").strip().lower()
        if mode in {"registry", "explicit_documents"}:
            try:
                from document_ai.document_set.observational import (
                    run_document_set_observational,
                )

                impact_for_mdtm = [
                    {
                        "requirement_id": d.candidate_id,
                        "judgment": d.judgment,
                        "document": d.document,
                    }
                    for d in decisions_b3
                    if d.judgment == "IMPACTED" and d.document == "MDSR"
                ]
                document_set_obs = run_document_set_observational(
                    output_dir=out,
                    change_request=cr_text,
                    impact_results=impact_for_mdtm,
                    document_set_mode=mode,
                )
            except Exception as ds_exc:  # noqa: BLE001
                document_set_obs = {
                    "ok": False,
                    "error": str(ds_exc),
                    "note": "document_set observational failed; actual path unchanged",
                }
                report["warnings"].append(f"document_set_observational:{ds_exc}")

        report.update(
            {
                "status": final_status,
                "document_set_mode": mode,
                "outputs": {
                    "updated_mdsr": str(out_mdsr).replace("\\", "/"),
                    "updated_mddr": str(out_mddr).replace("\\", "/"),
                    "trace_dir": str(out / "trace").replace("\\", "/"),
                    "review_dir": str(out / "review").replace("\\", "/"),
                },
                "summaries": {
                    "retrieval_top": [
                        {
                            "rank": h.rank,
                            "id": h.candidate_id,
                            "document": h.document,
                            "hybrid_score": h.hybrid_score,
                        }
                        for h in ranked[:8]
                    ],
                    "impact": impact_payload["summary"],
                    "consistency": cons_payload["summary"],
                    "propagation": prop_payload["summary"],
                    "mdsr_patched_req_ids": patch_report.get("mdsr_patched_req_ids"),
                    "mddr_patched_req_ids": patch_report.get("mddr_patched_req_ids"),
                    "document_set": (document_set_obs or {}).get("summary"),
                    "mdtm_change": (document_set_obs or {}).get("change_summary"),
                },
                "review_flags": review_flags,
                "document_set_observational": document_set_obs,
                "input_hashes_unchanged": True,
            }
        )
    except Exception as exc:  # noqa: BLE001 — surface in execution_report
        report["status"] = "FAILED"
        report["errors"].append(str(exc))
        # Ensure inputs still intact
        try:
            report["input_hashes_unchanged"] = (
                sha256_file(paths.mdsr) == in_mdsr_sha
                and sha256_file(paths.mddr) == in_mddr_sha
            )
        except Exception:
            report["input_hashes_unchanged"] = False
        # Still write report
        (out / "execution_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        raise

    (out / "execution_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def _write_review_docs(
    *,
    out: Path,
    cr_text: str,
    ranked,
    decisions_b3,
    consistency,
    traces,
    patch_report: dict[str, Any],
    review_flags: dict[str, Any],
) -> None:
    impacted = [d for d in decisions_b3 if d.judgment == "IMPACTED"]
    conflicts = [d for d in consistency if d.status == "CONFLICT"]
    needs = [d for d in consistency if d.status == "NEEDS_REVIEW"]
    skipped = [t for t in traces if t.outcome == "SKIPPED_WITH_REASON"]
    patched_t = [t for t in traces if t.outcome == "PATCHED"]

    summary = [
        "# Change Summary (Human Review)",
        "",
        "## Input CR",
        "",
        "```",
        cr_text,
        "```",
        "",
        "## Top retrieval candidates",
        "",
    ]
    for h in ranked[:10]:
        summary.append(
            f"- rank {h.rank}: {h.candidate_id} [{h.document}] hybrid={h.hybrid_score}"
        )
    summary.extend(
        [
            "",
            "## Impacted (B3)",
            "",
        ]
    )
    if not impacted:
        summary.append("- (none)")
    for d in impacted:
        summary.append(f"- {d.candidate_id} [{d.document}] — {d.judgment}")
    summary.extend(
        [
            "",
            "## MDSR actually patched",
            "",
            f"- {patch_report.get('mdsr_patched_req_ids') or '(none)'}",
            "",
            "## MDDR actually patched",
            "",
            f"- {patch_report.get('mddr_patched_req_ids') or '(none)'}",
            "",
            "## Related but not modified (skip / conflict)",
            "",
        ]
    )
    for t in skipped:
        summary.append(
            f"- {t.source_mdsr_req_id} → {t.outcome}: {t.propagation_reason[:160]}"
        )
    for d in conflicts:
        summary.append(f"- {d.req_id} CONFLICT (no auto-patch): {d.reason[:160]}")
    summary.extend(["", "## Conflicts", ""])
    if not conflicts:
        summary.append("- (none)")
    for d in conflicts:
        summary.append(f"- **{d.req_id}**: {d.reason}")
        summary.append(f"  - resolution: {d.proposed_resolution_direction}")
    summary.extend(["", "## NEEDS_REVIEW", ""])
    if not needs and not review_flags.get("uncertain_impact"):
        summary.append("- (none)")
    for d in needs:
        summary.append(f"- consistency {d.req_id}: {d.reason[:160]}")
    for u in review_flags.get("uncertain_impact") or []:
        summary.append(f"- impact UNCERTAIN: {u}")
    summary.extend(
        [
            "",
            "## NEW_REQUIREMENT_CANDIDATE",
            "",
            f"- flagged: `{review_flags.get('NEW_REQUIREMENT_CANDIDATE')}`",
            f"- reason: {review_flags.get('new_requirement_reason') or '(n/a)'}",
            f"- proposal: `{review_flags.get('new_requirement_proposal_path') or '(none)'}`",
            "",
            "## Final execution notes",
            "",
            "- Inputs were not overwritten; outputs are under `output/documents/`.",
            "- Auto-patch requires B4 CONSISTENT + allow_auto_patch.",
            "",
        ]
    )
    (out / "review" / "CHANGE_SUMMARY.md").write_text(
        "\n".join(summary) + "\n", encoding="utf-8"
    )

    review_req = [
        "# Review Required",
        "",
        "Items that must not be silently auto-merged:",
        "",
    ]
    if conflicts:
        review_req.append("## CONFLICT (patch blocked)")
        for d in conflicts:
            review_req.append(f"- {d.req_id}: {d.reason}")
            review_req.append(f"  - proposed: {d.proposed_resolution_direction}")
        review_req.append("")
    if needs:
        review_req.append("## Consistency NEEDS_REVIEW")
        for d in needs:
            review_req.append(f"- {d.req_id}: {d.reason}")
        review_req.append("")
    if review_flags.get("uncertain_impact"):
        review_req.append("## Impact UNCERTAIN")
        for u in review_flags["uncertain_impact"]:
            review_req.append(f"- {u}")
        review_req.append("")
    if review_flags.get("NEW_REQUIREMENT_CANDIDATE"):
        review_req.append("## NEW_REQUIREMENT_CANDIDATE")
        review_req.append(f"- {review_flags.get('new_requirement_reason')}")
        if review_flags.get("new_requirement_proposal_path"):
            review_req.append(f"- see `{review_flags['new_requirement_proposal_path']}`")
        review_req.append("")
    if len(review_req) == 4:
        review_req.append("- (no blocking review items — still spot-check CHANGE_SUMMARY)")
    (out / "review" / "REVIEW_REQUIRED.md").write_text(
        "\n".join(review_req) + "\n", encoding="utf-8"
    )

    diffs = patch_report.get("diffs") or {}
    diff_lines = ["# Patch Diff", ""]
    for rid, d in (diffs.get("mdsr") or {}).items():
        diff_lines.append(f"## MDSR {rid} changed={d.get('changed')} patched={d.get('patched')}")
        diff_lines.append("")
        diff_lines.append("### before")
        diff_lines.append("```")
        diff_lines.append((d.get("before") or "")[:1000] or "(empty)")
        diff_lines.append("```")
        diff_lines.append("### after")
        diff_lines.append("```")
        diff_lines.append((d.get("after") or "")[:1000] or "(empty)")
        diff_lines.append("```")
        diff_lines.append("")
    for rid, d in (diffs.get("mddr") or {}).items():
        diff_lines.append(
            f"## MDDR {rid} outcome={d.get('outcome')} changed={d.get('changed')}"
        )
        diff_lines.append(f"- before: {(d.get('before') or '')[:400]}")
        diff_lines.append(f"- after: {(d.get('after') or '')[:400]}")
        diff_lines.append("")
    (out / "review" / "PATCH_DIFF.md").write_text(
        "\n".join(diff_lines) + "\n", encoding="utf-8"
    )
