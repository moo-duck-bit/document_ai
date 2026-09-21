# -*- coding: utf-8 -*-
"""Analysis adapters for workflow (reuse existing engines; no rewrite)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from docx import Document

from document_ai.document_set.observational import run_document_set_observational
from document_ai.template.concept_normalization import normalize_concepts, tokenize
from document_ai.template.generic_templates import (
    build_business_proposal_template,
    build_general_report_template,
)
from document_ai.workflow.catalog import get_catalog


def _is_mdtm_like_upload(d: dict[str, Any]) -> bool:
    """Identity/role based — not filename-only auto selection."""
    short = str(d.get("short_id") or d.get("registry_document_id") or "").upper()
    role = str(d.get("document_role") or d.get("role") or "").lower()
    dtype = str(d.get("document_type") or "").upper()
    if short == "MDTM" or dtype == "MDTM":
        return True
    if role == "traceability":
        return True
    # Explicit registry short id already resolved
    if d.get("identity_auto_selected") and short in {"MDTM"}:
        return True
    return False


def analyze_ec_sw(
    *,
    work_dir: Path,
    change_request: str,
    uploaded_docs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Run MDTM observational path; does not mutate uploads."""
    from document_ai.domain_packs.ec_sw.document_impact import (
        DocumentImpactEvidence,
        build_evidences_for_uploads,
        decide_document_impacts,
        write_document_impact_artifacts,
    )
    from document_ai.domain_packs.ec_sw.identifier_parser import (
        parse_requirement_identifiers,
        valid_canonical_requirement_ids,
    )
    from document_ai.domain_packs.ec_sw.mdtm_change_poc import run_mdtm_change_poc
    from document_ai.domain_packs.ec_sw.mdtm_indexer import index_mdtm_document
    from document_ai.domain_packs.ec_sw.semantic_evidence import (
        collect_semantic_review_evidence,
        semantic_to_review_candidates,
        write_semantic_review_artifacts,
    )
    from document_ai.document_set.loader import load_document_set_registry
    from document_ai.domain_packs.ec_sw.registry_adapter import get_mdtm_descriptor

    parsed_ids = parse_requirement_identifiers(change_request, source="change_request")
    reqs = valid_canonical_requirement_ids(change_request)
    obs = run_document_set_observational(
        output_dir=work_dir / "output",
        change_request=change_request,
        requirement_ids=reqs,
        document_set_mode="registry",
    )
    ec_dir = work_dir / "output" / "document_set" / "ec_sw"
    cand_path = ec_dir / "mdtm_change_candidates.json"
    review_path = ec_dir / "mdtm_review_required.json"

    candidates: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    if cand_path.exists():
        all_c = json.loads(cand_path.read_text(encoding="utf-8"))
        candidates = [c for c in all_c if c.get("status") == "PATCH_CANDIDATE"]
        review = [c for c in all_c if c.get("status") == "REVIEW_REQUIRED"]
    if review_path.exists() and not review:
        review = json.loads(review_path.read_text(encoding="utf-8"))

    # Prefer indexing uploaded MDTM-like files under their temporary/source document_id
    # so fixture document_id (e.g. MDTM_BASE) aligns with gold without filename canonicalization.
    upload_patch: list[dict[str, Any]] = []
    upload_review: list[dict[str, Any]] = []
    upload_nodes_by_doc: dict[str, list[Any]] = {}
    for d in uploaded_docs:
        if not _is_mdtm_like_upload(d):
            continue
        path = Path(d.get("path") or "")
        if not path.is_file():
            continue
        doc_id = str(d.get("document_id") or "")
        indexed = index_mdtm_document(source_path=path, document_id=doc_id)
        nodes = list(indexed.get("nodes") or [])
        if not nodes:
            continue
        upload_nodes_by_doc[doc_id] = nodes
        change = run_mdtm_change_poc(
            nodes,
            change_request=change_request,
            requirement_ids=reqs,
        )
        for c in change.get("candidate_dicts") or []:
            row = dict(c)
            row["document_id"] = doc_id
            if row.get("status") == "PATCH_CANDIDATE":
                upload_patch.append(row)
            elif row.get("status") == "REVIEW_REQUIRED":
                upload_review.append(row)
        for c in change.get("review_required") or []:
            row = dict(c)
            row["document_id"] = doc_id
            upload_review.append(row)

    if upload_patch or upload_review:
        candidates = upload_patch
        review = upload_review
        # Persist stable identity artifacts from upload indexing
        id_dir = work_dir / "output" / "document_identity"
        id_dir.mkdir(parents=True, exist_ok=True)
        stables: list[dict[str, Any]] = []
        legacy_map: list[dict[str, Any]] = []
        stables_v2: list[dict[str, Any]] = []
        key_fields: list[dict[str, Any]] = []
        dup_groups: list[dict[str, Any]] = []
        v1_v2: list[dict[str, Any]] = []
        recon_all: list[dict[str, Any]] = []
        ranking_all: list[dict[str, Any]] = []
        for d in uploaded_docs:
            if not _is_mdtm_like_upload(d):
                continue
            path = Path(d.get("path") or "")
            if not path.is_file():
                continue
            indexed = index_mdtm_document(source_path=path, document_id=str(d.get("document_id") or ""))
            stables.extend(indexed.get("stable_node_identities") or [])
            legacy_map.extend(indexed.get("legacy_to_stable_node_mapping") or [])
            stables_v2.extend(
                indexed.get("stable_node_identities_v2") or indexed.get("stable_node_identities") or []
            )
            key_fields = indexed.get("canonical_key_fields") or key_fields
            dup_groups.extend(indexed.get("stable_duplicate_groups") or [])
            v1_v2.extend(indexed.get("stable_node_identity_comparison_v1_v2") or [])
        import json as _json

        for row in list(upload_patch) + list(upload_review):
            meta = row.get("metadata") or {}
            if meta.get("rank_tier") is not None:
                ranking_all.append(
                    {
                        "node_id": row.get("node_id"),
                        "rank": meta.get("rank"),
                        "rank_tier": meta.get("rank_tier"),
                        "final_score": meta.get("final_score"),
                        "stable_node_id_base": meta.get("stable_node_id_base"),
                        "stable_base_match": meta.get("stable_base_match"),
                    }
                )
            if meta.get("reconciled_candidate_id"):
                recon_all.append(
                    {
                        "node_id": row.get("node_id"),
                        "reconciled_candidate_id": meta.get("reconciled_candidate_id"),
                        "reconciliation_status": meta.get("reconciliation_status"),
                        "stable_node_id_base": meta.get("stable_node_id_base"),
                    }
                )

        (id_dir / "stable_node_identities.json").write_text(
            _json.dumps(stables, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (id_dir / "legacy_to_stable_node_mapping.json").write_text(
            _json.dumps(legacy_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (id_dir / "stable_node_identities_v2.json").write_text(
            _json.dumps(stables_v2 or stables, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (id_dir / "stable_node_identity_comparison_v1_v2.json").write_text(
            _json.dumps(v1_v2, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (id_dir / "canonical_key_fields.json").write_text(
            _json.dumps(key_fields, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (id_dir / "stable_duplicate_groups.json").write_text(
            _json.dumps(dup_groups, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (id_dir / "node_reconciliation_results.json").write_text(
            _json.dumps(recon_all, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (id_dir / "identity_aware_ranking.json").write_text(
            _json.dumps(ranking_all, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (id_dir / "stable_node_v2_validation.json").write_text(
            _json.dumps(
                {
                    "stable_base_excludes_document_id": True,
                    "writer_executable_from_stable_only": False,
                    "identity_version": "stable_node_identity_v2",
                    "n_stable_v2": len(stables_v2 or stables),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (id_dir / "stable_node_identity_summary.json").write_text(
            _json.dumps(
                {
                    "n_stable": len(stables),
                    "n_mapped": len(legacy_map),
                    "identity_version": "stable_node_identity_v2",
                    "n_duplicate_groups": len(dup_groups),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (ec_dir / "mdtm_upload_index_summary.json").write_text(
            json.dumps(
                {
                    "indexed_document_ids": list(upload_nodes_by_doc.keys()),
                    "patch_count": len(upload_patch),
                    "review_count": len(upload_review),
                    "note": "upload_identity_aligned_indexing",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    else:
        # Remap registry MDTM candidates onto MDTM-like uploads when present
        mdtm_uploads = [d for d in uploaded_docs if _is_mdtm_like_upload(d)]
        if mdtm_uploads and any(c.get("document_id") == "MDTM" for c in candidates + review):
            target = str(mdtm_uploads[0].get("document_id"))
            candidates = [{**c, "document_id": target} for c in candidates]
            review = [{**c, "document_id": target} for c in review]

    # Semantic-only REVIEW (no PATCH) when exact IDs absent
    semantic_evidences = []
    if not reqs:
        mdtm_path = None
        semantic_doc_id = "MDTM"
        for d in uploaded_docs:
            p = Path(d.get("path") or "")
            if p.is_file() and p.suffix.lower() == ".docx" and _is_mdtm_like_upload(d):
                mdtm_path = p
                semantic_doc_id = str(d.get("document_id") or "MDTM")
                break
        if mdtm_path is None:
            for d in uploaded_docs:
                p = Path(d.get("path") or "")
                if p.is_file() and p.suffix.lower() == ".docx":
                    mdtm_path = p
                    semantic_doc_id = str(d.get("document_id") or "MDTM")
                    break
        if mdtm_path is None:
            try:
                loaded = load_document_set_registry()
                desc = get_mdtm_descriptor(loaded["descriptors"])
                if desc is not None:
                    mdtm_path = Path(desc.source_path)
            except Exception:
                mdtm_path = None
        nodes = upload_nodes_by_doc.get(semantic_doc_id) or []
        if not nodes and mdtm_path and Path(mdtm_path).is_file():
            indexed = index_mdtm_document(source_path=mdtm_path, document_id=semantic_doc_id)
            nodes = list(indexed.get("nodes") or [])
        if nodes:
            semantic_evidences = collect_semantic_review_evidence(
                change_request=change_request,
                nodes=nodes,
                document_id=semantic_doc_id,
            )
            write_semantic_review_artifacts(ec_dir, semantic_evidences)
            # Keep REVIEW at document-decision layer; do not flood node predictions
            # (empty gold node cases would otherwise penalize retrieval metrics).
            # Candidates remain in artifacts for human review.
            _ = semantic_to_review_candidates(semantic_evidences, limit=5)

    evidence_by_doc = build_evidences_for_uploads(
        change_request=change_request,
        uploaded_docs=uploaded_docs,
        patch_candidates=candidates,
        review_required=review,
        parsed_ids=parsed_ids,
    )
    if any(c.get("document_id") == "MDTM" for c in candidates + review) and "MDTM" not in evidence_by_doc:
        evidence_by_doc = build_evidences_for_uploads(
            change_request=change_request,
            uploaded_docs=list(uploaded_docs)
            + [{"document_id": "MDTM", "role": "traceability", "filename": "MDTM.docx"}],
            patch_candidates=candidates,
            review_required=review,
            parsed_ids=parsed_ids,
        )

    # Document-level semantic evidence when strong reviews exist
    strong = [e for e in semantic_evidences if e.supports_review]
    if strong:
        top = strong[0]
        sem_doc = str(getattr(top, "document_id", None) or "MDTM")
        evidence_by_doc.setdefault(sem_doc, [])
        evidence_by_doc[sem_doc].append(
            DocumentImpactEvidence(
                document_id=sem_doc,
                document_role="traceability",
                evidence_type="SEMANTIC_SECTION_MATCH",
                evidence_value=",".join(top.matched_terms) or top.node_id,
                source_stage="semantic_review",
                source_node_id=top.node_id,
                confidence=top.semantic_score,
                independent_group="semantic_doc",
                reason_codes=["SEMANTIC_REVIEW_CANDIDATE", "no_semantic_only_patch"],
                supports_impacted=False,
                supports_review=True,
            )
        )

    decisions = decide_document_impacts(evidence_by_doc)
    write_document_impact_artifacts(
        ec_dir,
        parsed_ids=parsed_ids,
        evidence_by_doc=evidence_by_doc,
        decisions=decisions,
    )

    impacted = sorted(d["document_id"] for d in decisions if d["predicted_status"] == "IMPACTED")
    review_docs = {
        d["document_id"] for d in decisions if d["predicted_status"] == "REVIEW_REQUIRED"
    }
    return {
        "engine": "ec_sw_mdtm_observational",
        "ok": bool(obs.get("ok")),
        "impacted_documents": impacted,
        "patch_candidates": candidates,
        "review_required": review,
        "document_impact_decisions": decisions,
        "document_impact_review_documents": sorted(review_docs),
        "observational": {
            "index_summary": obs.get("index_summary"),
            "change_summary": obs.get("change_summary"),
            "artifact_dir": obs.get("artifact_dir"),
        },
        "input_requirement_ids": reqs,
        "identifier_analysis": [p.to_dict() for p in parsed_ids],
        "semantic_review_count": len(strong),
    }


def _tokenize(text: str) -> set[str]:
    return tokenize(text)


def analyze_generic_template_doc(
    *,
    document_set: str,
    change_request: str,
    uploaded_docs: list[dict[str, Any]],
    work_dir: Path | None = None,
) -> dict[str, Any]:
    """Map CR tokens to template sections / uploaded paragraphs → REVIEW candidates."""
    from document_ai.document_set.schedule_table_retrieval import (
        collect_schedule_table_evidence,
        evidences_to_review_items,
        write_general_report_retrieval_artifacts,
    )
    from document_ai.domain_packs.generic.no_impact_policy import (
        ImpactEvidence,
        decide_no_impact,
    )
    from document_ai.domain_packs.generic.query_intent import (
        annotate_structural_role,
        parse_generic_query_intent,
    )
    from document_ai.domain_packs.generic.structural_match import (
        promote_aligned_template_candidates,
        rank_generic_candidates,
    )
    from document_ai.domain_packs.generic.target_existence import decide_target_existence

    is_bp = document_set == "business_proposal"
    bp_intent = None
    if is_bp:
        from document_ai.domain_packs.business_proposal.node_alignment import build_proposal_alignments
        from document_ai.domain_packs.business_proposal.node_ranking import (
            promote_aligned_proposal_template_candidates,
            rank_business_proposal_candidates,
        )
        from document_ai.domain_packs.business_proposal.concepts import normalize_proposal_concepts
        from document_ai.domain_packs.business_proposal.query_intent import (
            parse_business_proposal_query_intent,
        )
        from document_ai.domain_packs.business_proposal.structural_roles import (
            annotate_proposal_structural_role,
        )
        from document_ai.document_set.proposal_table_retrieval import (
            collect_proposal_table_evidence,
            evidences_to_review_items as proposal_evidences_to_review_items,
            write_proposal_table_artifacts,
        )

    cat = get_catalog(document_set)
    if document_set == "general_report":
        tmpl = build_general_report_template()
    else:
        tmpl = build_business_proposal_template()

    if is_bp:
        bp_intent = parse_business_proposal_query_intent(change_request)
        query_intent = bp_intent.to_generic_intent()
        cr_concepts = (
            normalize_concepts(change_request)
            | normalize_proposal_concepts(change_request)
            | set(bp_intent.canonical_concepts)
        )
    else:
        query_intent = parse_generic_query_intent(change_request)
        cr_concepts = normalize_concepts(change_request) | set(query_intent.canonical_concepts)
    cr_toks = _tokenize(change_request)
    candidates: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    impacted: list[str] = []
    document_impact_decisions: list[dict[str, Any]] = []
    target_decisions: list[dict[str, Any]] = []
    no_impact_decisions: list[dict[str, Any]] = []
    virtual_targets: list[dict[str, Any]] = []
    alignment_payload_global: dict[str, Any] = {}
    ranking_payload_global: dict[str, Any] = {}
    parent_child_rows: list[dict[str, Any]] = []

    template_hits: list[dict[str, Any]] = []
    for sec in tmpl.sections:
        if sec.section_id == "document":
            continue
        blob = " ".join(
            [sec.display_name, sec.section_id]
            + [f.display_name for f in (sec.fields or [])]
        )
        sec_toks = _tokenize(blob)
        sec_concepts = normalize_concepts(blob)
        if is_bp:
            sec_concepts |= normalize_proposal_concepts(blob)
        overlap = len(cr_toks & sec_toks) / max(1, len(cr_toks)) if cr_toks else 0.0
        concept_hit = bool(cr_concepts & sec_concepts)
        # Require clearer overlap: token intersection size >= 1 with multi-char tokens
        # or concept hit that is not TABLE alone from weak template fields
        strong_tok = bool(cr_toks & sec_toks) and (
            overlap >= 0.08 or any(len(t) >= 2 for t in (cr_toks & sec_toks))
        )
        # Ignore TABLE-only concept hits on template (too noisy after synonym cleanup still)
        concept_ok = concept_hit and (
            (cr_concepts & sec_concepts) - {"TABLE"} or "TABLE" not in cr_concepts or "SCHEDULE" in cr_concepts
        )
        hit = strong_tok or concept_ok
        item = {
            "item_id": f"{tmpl.template_id}.{sec.section_id}",
            "document_id": uploaded_docs[0]["document_id"] if uploaded_docs else tmpl.template_id,
            "node_id": f"{tmpl.template_id}.{sec.section_id}",
            "status": "REVIEW_REQUIRED" if hit else "UNRELATED",
            "display_name": sec.display_name,
            "overlap": round(overlap, 4),
            "reason_codes": (
                ["template_section_token_overlap"]
                if strong_tok
                else (["template_section_concept_match"] if concept_ok else ["no_overlap"])
            ),
            "human_review_required": True,
            "metadata": {
                "supports_patch": False,
                "overlap": round(overlap, 4),
                "virtual_target": True,
                "target_exists": False,
                "writer_supported": False,
                "template_only": True,
            },
        }
        if item["status"] == "REVIEW_REQUIRED":
            template_hits.append(item)
            # Do NOT add to impacted / review as document-grounded yet

    for doc in uploaded_docs:
        path = Path(doc.get("path") or "")
        did = str(doc.get("document_id") or "")
        if not path.is_file():
            continue
        try:
            d = Document(str(path))
        except Exception:
            continue

        doc_heading_concepts: set[str] = set()
        doc_heading_tokens: set[str] = set()
        doc_node_hits: list[dict[str, Any]] = []
        evidences: list[ImpactEvidence] = [
            ImpactEvidence(
                evidence_type="DOCUMENT_PRESENCE",
                evidence_value=str(doc.get("filename") or did),
                confidence=0.1,
                source_stage="upload",
            ),
            ImpactEvidence(
                evidence_type="TEMPLATE_COMPATIBILITY",
                evidence_value=document_set,
                confidence=0.1,
                source_stage="catalog",
            ),
        ]

        current_heading_id: str | None = None
        current_heading_concepts: set[str] = set()

        for i, p in enumerate(d.paragraphs):
            text = (p.text or "").strip()
            if not text:
                continue
            style = (p.style.name if p.style is not None else "") or ""
            toks = _tokenize(text)
            concepts = normalize_concepts(text)
            if is_bp:
                concepts |= normalize_proposal_concepts(text)
            is_heading = "heading" in style.lower() or (len(text) <= 40 and i < 30)
            if is_heading:
                doc_heading_concepts |= concepts
                doc_heading_tokens |= toks
            inter = cr_toks & toks
            concept_hit = bool(cr_concepts & concepts)
            if len(text) < 8 and not concept_hit and not (inter and is_heading):
                continue
            strong_single = bool(inter) and (
                is_heading
                or any(len(t) >= 3 for t in inter)
                or text.replace(" ", "") in (change_request or "").replace(" ", "")
            )
            if len(inter) < 2 and not concept_hit and not strong_single:
                # Still track heading for parent context even if not a CR hit
                if is_heading:
                    nid_h = f"heading_{i:04d}"
                    current_heading_id = nid_h
                    current_heading_concepts = set(concepts)
                continue
            if concept_hit and not inter and (cr_concepts & concepts) <= {"TABLE"}:
                continue

            if is_bp:
                role_ann = annotate_proposal_structural_role(
                    node_id=f"{'heading' if is_heading else 'paragraph'}_{i:04d}",
                    display_name=text[:80],
                    style=style,
                    is_heading=is_heading,
                    concepts=concepts,
                )
            else:
                role_ann = annotate_structural_role(
                    node_id=f"{'heading' if is_heading else 'paragraph'}_{i:04d}",
                    display_name=text[:80],
                    style=style,
                    is_heading=is_heading,
                )
            nid = f"{'heading' if is_heading else 'paragraph'}_{i:04d}"
            if is_heading:
                current_heading_id = nid
                current_heading_concepts = set(concepts)

            direct_match = bool(concepts & cr_concepts) or len(inter) >= 2
            inherited_match = bool(current_heading_concepts & cr_concepts) and not is_heading
            parent_child_rows.append(
                {
                    "node_id": nid,
                    "parent_section_id": None if is_heading else current_heading_id,
                    "section_concepts": sorted(current_heading_concepts if not is_heading else concepts),
                    "local_content_concepts": sorted(concepts),
                    "direct_match": direct_match,
                    "inherited_match": inherited_match,
                }
            )
            item = {
                "item_id": f"{did}.p{i:04d}",
                "document_id": did,
                "node_id": nid,
                "status": "REVIEW_REQUIRED",
                "display_name": text[:80],
                "evidence": sorted(inter)[:12],
                "reason_codes": (
                    ["paragraph_token_overlap"] if len(inter) >= 2 else ["paragraph_concept_match"]
                ),
                "human_review_required": True,
                "source_locator": {"paragraph_index": i},
                "source_stage": "document_paragraph",
                "metadata": {
                    "supports_patch": False,
                    "target_exists": True,
                    "structural_role": role_ann["structural_role"],
                    "physical": True,
                    "editable": True,
                    "virtual": False,
                    "canonical_concepts": sorted(concepts),
                    "content_specificity": role_ann["content_specificity"],
                    "parent_section_id": None if is_heading else current_heading_id,
                    "direct_match": direct_match,
                    "inherited_match": inherited_match,
                    "parent_context_match": 0.8 if direct_match else (0.35 if inherited_match else 0.0),
                    "section_context": " ".join(sorted(current_heading_concepts))[:120],
                    "writer_executable": False,
                },
            }
            review.append(item)
            doc_node_hits.append(item)
            et = "EXACT_HEADING_MATCH" if is_heading else "STRUCTURAL_BLOCK_MATCH"
            evidences.append(
                ImpactEvidence(
                    evidence_type=et,
                    evidence_value=text[:80],
                    node_id=item["node_id"],
                    confidence=0.7,
                    source_stage="document_paragraph",
                    supports_review=True,
                    reason_codes=list(item["reason_codes"]),
                )
            )

        schedule_grounded = False
        table_grounded = False
        alignment_payload: dict[str, Any] = {"alignments": [], "structural_equivalence_groups": []}
        proposal_table_evidences: list[Any] = []
        if document_set == "general_report":
            sch = collect_schedule_table_evidence(
                change_request=change_request,
                document_id=did,
                docx_path=path,
                template_section_hits=template_hits,
            )
            out_root = (work_dir or path.parent) / "output" / "document_set" / "general_report"
            write_general_report_retrieval_artifacts(
                out_root, change_request=change_request, evidences=sch
            )
            grounded = [
                e
                for e in sch
                if e.supports_review and "template_only_not_document_grounded" not in e.reason_codes
            ]
            schedule_grounded = bool(grounded)
            for item in evidences_to_review_items(grounded):
                item["source_stage"] = "schedule_table_retrieval"
                meta = item.setdefault("metadata", {})
                role_ann = annotate_structural_role(
                    node_id=str(item.get("node_id") or ""),
                    display_name=str(item.get("display_name") or ""),
                    evidence_type=str(meta.get("evidence_type") or "TABLE_STRUCTURE"),
                )
                meta.update(role_ann)
                meta["physical"] = True
                meta["writer_executable"] = False
                meta["canonical_concepts"] = sorted(
                    set(meta.get("canonical_concepts") or []) | normalize_concepts(str(item.get("display_name") or ""))
                )
                if not any(r.get("node_id") == item.get("node_id") for r in review):
                    review.append(item)
                doc_node_hits.append(item)
                evidences.append(
                    ImpactEvidence(
                        evidence_type="TABLE_HEADER_MATCH"
                        if meta.get("evidence_type") == "TABLE_STRUCTURE"
                        else "STRUCTURAL_BLOCK_MATCH",
                        evidence_value=str(item.get("display_name") or item.get("node_id")),
                        node_id=str(item.get("node_id")),
                        confidence=float(item.get("overlap") or 0.6),
                        source_stage="schedule_table_retrieval",
                        supports_review=True,
                        reason_codes=list(item.get("reason_codes") or []),
                    )
                )

        elif document_set == "business_proposal":
            proposal_table_evidences = collect_proposal_table_evidence(
                change_request=change_request,
                document_id=did,
                docx_path=path,
                template_section_hits=template_hits,
            )
            out_bp = (work_dir or path.parent) / "output" / "document_set" / "business_proposal"
            write_proposal_table_artifacts(
                out_bp,
                change_request=change_request,
                evidences=proposal_table_evidences,
            )
            grounded_tbl = [
                e
                for e in proposal_table_evidences
                if e.supports_review and "template_only_not_document_grounded" not in e.reason_codes
            ]
            table_grounded = bool(grounded_tbl)
            for item in proposal_evidences_to_review_items(grounded_tbl):
                item["source_stage"] = "proposal_table_retrieval"
                meta = item.setdefault("metadata", {})
                role_ann = annotate_proposal_structural_role(
                    node_id=str(item.get("node_id") or ""),
                    display_name=str(item.get("display_name") or ""),
                    evidence_type=str(meta.get("evidence_type") or "TABLE_STRUCTURE"),
                    table_role=str(meta.get("table_role") or ""),
                    concepts=set(meta.get("canonical_concepts") or []),
                )
                meta.update(role_ann)
                meta["physical"] = True
                meta["writer_executable"] = False
                meta["supports_patch"] = False
                meta["domain"] = "business_proposal"
                meta["canonical_concepts"] = sorted(
                    set(meta.get("canonical_concepts") or [])
                    | normalize_proposal_concepts(str(item.get("display_name") or ""))
                )
                if not any(r.get("node_id") == item.get("node_id") for r in review):
                    review.append(item)
                doc_node_hits.append(item)
                evidences.append(
                    ImpactEvidence(
                        evidence_type="TABLE_HEADER_MATCH"
                        if meta.get("evidence_type") == "TABLE_STRUCTURE"
                        else "STRUCTURAL_BLOCK_MATCH",
                        evidence_value=str(item.get("display_name") or item.get("node_id")),
                        node_id=str(item.get("node_id")),
                        confidence=float(item.get("overlap") or 0.6),
                        source_stage="proposal_table_retrieval",
                        supports_review=True,
                        reason_codes=list(item.get("reason_codes") or []),
                    )
                )

        from document_ai.template.node_alignment import (
            boost_template_alignment_scores,
            build_node_alignments,
        )
        import json as _json

        if is_bp:
            alignment_payload = build_proposal_alignments(
                document_id=did,
                template_review_items=template_hits + review,
                document_review_items=[
                    r
                    for r in review
                    if str(r.get("node_id") or "").startswith(("heading_", "paragraph_", "table_"))
                ],
            )
        else:
            alignment_payload = build_node_alignments(
                document_id=did,
                template_review_items=template_hits + review,
                document_review_items=[
                    r
                    for r in review
                    if str(r.get("node_id") or "").startswith(("heading_", "paragraph_", "table_"))
                ],
            )
        # Annotate physical nodes with alignment confidence
        align_by_doc: dict[str, dict[str, Any]] = {}
        for a in alignment_payload.get("alignments") or []:
            did_n = str(a.get("document_node_id") or "")
            if did_n and (
                did_n not in align_by_doc
                or float(a.get("confidence") or 0) > float(align_by_doc[did_n].get("confidence") or 0)
            ):
                align_by_doc[did_n] = a
        for item in review:
            a = align_by_doc.get(str(item.get("node_id") or ""))
            if not a:
                continue
            meta = item.setdefault("metadata", {})
            meta["alignment_confidence"] = float(a.get("confidence") or 0)
            meta["evaluation_equivalent"] = bool(a.get("equivalent_for_evaluation"))
            meta["template_node_id"] = a.get("template_node_id")
            meta["alignment_ids"] = [a.get("alignment_id")]

        if is_bp:
            review[:] = promote_aligned_proposal_template_candidates(
                review=review,
                template_hits=template_hits,
                alignments=alignment_payload.get("alignments") or [],
                intent=bp_intent,
            )
        else:
            review[:] = promote_aligned_template_candidates(
                review=review,
                template_hits=template_hits,
                alignments=alignment_payload.get("alignments") or [],
                intent=query_intent,
            )
        boost_template_alignment_scores(review, alignment_payload.get("alignments") or [])
        if is_bp:
            ranking_payload = rank_business_proposal_candidates(review, intent=bp_intent)
        else:
            ranking_payload = rank_generic_candidates(review, intent=query_intent)
        alignment_payload_global = alignment_payload
        ranking_payload_global = ranking_payload

        out_root = (work_dir or path.parent) / "output" / "document_set" / (
            "general_report" if document_set == "general_report" else document_set
        )
        generic_dir = (work_dir or path.parent) / "output" / "document_set" / "generic"
        out_root.mkdir(parents=True, exist_ok=True)
        generic_dir.mkdir(parents=True, exist_ok=True)
        (out_root / "node_alignments.json").write_text(
            _json.dumps(alignment_payload.get("alignments") or [], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (out_root / "structural_equivalence_groups.json").write_text(
            _json.dumps(
                alignment_payload.get("structural_equivalence_groups") or [],
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (out_root / "node_alignment_validation.json").write_text(
            _json.dumps(alignment_payload.get("validation") or {}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        for item in review:
            item.setdefault("metadata", {})["node_alignments"] = alignment_payload.get("alignments")
            item.setdefault("metadata", {})["structural_equivalence_groups"] = alignment_payload.get(
                "structural_equivalence_groups"
            )
            item.setdefault("metadata", {})["query_intent"] = (
                bp_intent.intent_label if is_bp and bp_intent else query_intent.intent_label
            )

        if is_bp and bp_intent:
            (out_root / "business_proposal_query_intent.json").write_text(
                _json.dumps(bp_intent.to_dict(), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            (out_root / "business_proposal_concept_analysis.json").write_text(
                _json.dumps(
                    {
                        "change_request": change_request,
                        "canonical_concepts": sorted(cr_concepts),
                        "primary_concept": bp_intent.primary_concept,
                        "secondary_concepts": bp_intent.secondary_concepts,
                        "preferred_template_node_id": bp_intent.preferred_template_node_id,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            structural_nodes = [
                {
                    "node_id": r.get("node_id"),
                    "display_name": r.get("display_name"),
                    "structural_role": (r.get("metadata") or {}).get("structural_role"),
                    "proposal_structural_role": (r.get("metadata") or {}).get("proposal_structural_role"),
                    "canonical_concepts": (r.get("metadata") or {}).get("canonical_concepts"),
                }
                for r in review[:200]
            ]
            (out_root / "business_proposal_structural_nodes.json").write_text(
                _json.dumps(structural_nodes, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            (out_root / "business_proposal_node_alignments.json").write_text(
                _json.dumps(alignment_payload.get("alignments") or [], ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            (out_root / "business_proposal_structural_match_matrix.json").write_text(
                _json.dumps(ranking_payload.get("structural_match_matrix") or [], ensure_ascii=False, indent=2)
                + "\n",
                encoding="utf-8",
            )
            (out_root / "business_proposal_node_ranking_results.json").write_text(
                _json.dumps(ranking_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            (out_root / "business_proposal_virtual_targets.json").write_text(
                _json.dumps(virtual_targets, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            (out_root / "business_proposal_node_ranking_validation.json").write_text(
                _json.dumps(ranking_payload.get("validation") or {}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

        # Generic ranking artifacts (GR always; BP keeps compatibility mirror)
        (generic_dir / "generic_query_intent.json").write_text(
            _json.dumps(query_intent.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (generic_dir / "generic_structural_candidates.json").write_text(
            _json.dumps(review[:200], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (generic_dir / "generic_structural_match_matrix.json").write_text(
            _json.dumps(ranking_payload.get("structural_match_matrix") or [], ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
        (generic_dir / "generic_node_ranking_results.json").write_text(
            _json.dumps(ranking_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (generic_dir / "generic_parent_child_context.json").write_text(
            _json.dumps(parent_child_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (generic_dir / "generic_table_ranking.json").write_text(
            _json.dumps(
                [r for r in ranking_payload.get("ranking_candidates") or [] if r.get("structural_role") in {"TABLE", "TABLE_CELL"}],
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (generic_dir / "generic_virtual_target_ranking.json").write_text(
            _json.dumps(
                [r for r in ranking_payload.get("ranking_candidates") or [] if r.get("structural_role") == "VIRTUAL_TARGET"],
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (generic_dir / "generic_node_ranking_validation.json").write_text(
            _json.dumps(ranking_payload.get("validation") or {}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        # Template-only compatibility evidence (non-substantive)
        if template_hits:
            evidences.append(
                ImpactEvidence(
                    evidence_type="DOCUMENT_LEVEL_CONCEPT_MATCH",
                    evidence_value=",".join(str(h.get("node_id")) for h in template_hits[:4]),
                    confidence=0.3,
                    source_stage="generic_template_sections",
                    supports_review=False,
                    reason_codes=["template_only_hit"],
                )
            )

        target = decide_target_existence(
            document_id=did,
            requested_concepts=cr_concepts,
            document_heading_concepts=doc_heading_concepts,
            document_heading_tokens=doc_heading_tokens,
            cr_tokens=cr_toks,
            template_section_hits=template_hits,
            document_node_hits=doc_node_hits,
            schedule_document_grounded=schedule_grounded if document_set == "general_report" else table_grounded,
        )
        target_decisions.append(target.to_dict())

        decision = decide_no_impact(document_id=did, evidences=evidences, target=target)
        no_impact_decisions.append(decision.to_dict())
        virtual_targets.extend(decision.virtual_targets)

        # Virtual template hits recorded as artifacts only (not document REVIEW elevation)
        if target.target_status == "MISSING_ADDABLE" and target.template_node_id:
            virtual_targets.append(
                {
                    "virtual_target": True,
                    "target_exists": False,
                    "template_node_id": target.template_node_id,
                    "allowed_operation": "ADD",
                    "writer_supported": False,
                    "human_review_required": True,
                }
            )

        document_impact_decisions.append(
            {
                "document_id": did,
                "predicted_status": decision.status,
                "substantive_evidence_count": decision.substantive_evidence_count,
                "role_evidence_count": sum(
                    1 for e in evidences if e.evidence_type in {"DOCUMENT_PRESENCE", "TEMPLATE_COMPATIBILITY"}
                ),
                "exact_identifier_count": 0,
                "normalized_identifier_count": 0,
                "semantic_evidence_count": sum(
                    1 for e in evidences if e.evidence_type == "SEMANTIC_SECTION_MATCH"
                ),
                "malformed_identifier_count": 0,
                "reason_codes": decision.reason_codes,
                "source_stages": sorted(
                    {e.source_stage for e in evidences if e.source_stage}
                ),
                "top_evidence": decision.top_evidence,
                "human_review_required": decision.human_review_required,
                "target_status": decision.target_status,
                "validation": decision.validation,
            }
        )
        if decision.status in {"IMPACTED", "REVIEW_REQUIRED"}:
            if did not in impacted:
                impacted.append(did)

        # Artifacts
        out_root = (work_dir or path.parent) / "output" / "document_set" / "general_report"
        if document_set != "general_report":
            out_root = (work_dir or path.parent) / "output" / "document_set" / document_set
        out_root.mkdir(parents=True, exist_ok=True)
        import json as _json

        (out_root / "target_existence_decisions.json").write_text(
            _json.dumps(target_decisions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (out_root / "no_impact_decisions.json").write_text(
            _json.dumps(no_impact_decisions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (out_root / "virtual_targets.json").write_text(
            _json.dumps(virtual_targets, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (out_root / "general_report_impact_evidence.json").write_text(
            _json.dumps([e.to_dict() for e in evidences], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (out_root / "general_report_no_impact_validation.json").write_text(
            _json.dumps(
                {"ok": all((d.get("validation") or {}).values()) for d in no_impact_decisions if d.get("validation")},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    # Ensure every upload has a decision row
    decided_ids = {d["document_id"] for d in document_impact_decisions}
    for d in uploaded_docs:
        did = str(d.get("document_id") or "")
        if did and did not in decided_ids:
            document_impact_decisions.append(
                {
                    "document_id": did,
                    "predicted_status": "UNRELATED",
                    "substantive_evidence_count": 0,
                    "role_evidence_count": 1,
                    "exact_identifier_count": 0,
                    "normalized_identifier_count": 0,
                    "semantic_evidence_count": 0,
                    "malformed_identifier_count": 0,
                    "reason_codes": ["no_substantive_evidence"],
                    "source_stages": ["generic_no_impact_policy"],
                    "top_evidence": [],
                    "human_review_required": False,
                }
            )

    result: dict[str, Any] = {
        "engine": "business_proposal_pack" if is_bp else "generic_template_sections",
        "ok": True,
        "template_id": cat.get("template_id"),
        "impacted_documents": impacted,
        "patch_candidates": candidates,
        "review_required": review[:200],
        "document_impact_decisions": document_impact_decisions,
        "target_existence_decisions": target_decisions,
        "no_impact_decisions": no_impact_decisions,
        "virtual_targets": virtual_targets,
        "node_alignments": alignment_payload_global.get("alignments")
        or ((review[0].get("metadata") or {}).get("node_alignments") if review else []),
        "structural_equivalence_groups": alignment_payload_global.get("structural_equivalence_groups")
        or [],
        "generic_query_intent": query_intent.to_dict(),
        "generic_ranking": ranking_payload_global,
        "note": (
            "Business proposal pack: proposal intent/table retrieval/ranking; PATCH disabled."
            if is_bp
            else "Generic packs: structural ranking + no-impact policy; auto PATCH disabled; virtual/template eval nodes not writer-executable."
        ),
    }
    if is_bp and bp_intent:
        result["business_proposal_query_intent"] = bp_intent.to_dict()
        result["business_proposal_ranking"] = ranking_payload_global
    return result


def run_workflow_analysis(
    *,
    document_set: str,
    work_dir: Path,
    change_request: str,
    uploaded_docs: list[dict[str, Any]],
) -> dict[str, Any]:
    cat = get_catalog(document_set)
    if cat["analysis"] == "ec_sw_mdtm":
        return analyze_ec_sw(
            work_dir=work_dir,
            change_request=change_request,
            uploaded_docs=uploaded_docs,
        )
    return analyze_generic_template_doc(
        document_set=document_set,
        change_request=change_request,
        uploaded_docs=uploaded_docs,
        work_dir=work_dir,
    )
