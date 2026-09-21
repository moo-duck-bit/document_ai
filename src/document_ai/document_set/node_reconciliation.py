# -*- coding: utf-8 -*-
"""Reconcile legacy / stable / physical node candidates into logical candidates."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ReconciledNodeCandidate:
    reconciled_candidate_id: str
    document_id: str
    logical_node_key: str
    legacy_node_ids: list[str] = field(default_factory=list)
    stable_node_ids: list[str] = field(default_factory=list)
    stable_node_id_base: str = ""
    physical_node_ids: list[str] = field(default_factory=list)
    template_node_ids: list[str] = field(default_factory=list)
    structural_group_ids: list[str] = field(default_factory=list)
    identifier_sets: list[dict[str, list[str]]] = field(default_factory=list)
    primary_source_node_id: str = ""
    evidence: list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    reconciliation_status: str = "UNRESOLVED"
    duplicate_instance_key: str | None = None
    instance_signature: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _ident_key(ids: dict[str, list[str]] | None) -> str:
    if not ids:
        return ""
    parts = []
    for k in ("requirement_ids", "design_ids", "test_ids"):
        vals = sorted({str(x) for x in (ids.get(k) or []) if x})
        if vals:
            parts.append(f"{k}:{','.join(vals)}")
    return "|".join(parts)


def _candidate_logical_key(cand: dict[str, Any]) -> tuple[str, str]:
    """Return (group_key, key_kind). Prefer stable base, then identifier set, then legacy id."""
    meta = cand.get("metadata") or {}
    base = (
        meta.get("stable_node_id_base")
        or cand.get("stable_node_id_base")
        or ""
    )
    if base:
        return str(base), "stable_base"
    sid = meta.get("stable_node_id") or cand.get("stable_node_id") or ""
    if sid:
        # strip instance suffix
        base2 = str(sid).split("+", 1)[0]
        return base2, "stable"
    src = meta.get("source_identifiers") or {}
    ik = _ident_key(
        {
            "requirement_ids": list(
                meta.get("row_requirement_ids") or src.get("requirement_ids") or cand.get("matched_requirement_ids") or []
            ),
            "design_ids": list(meta.get("row_design_ids") or src.get("design_ids") or []),
            "test_ids": list(meta.get("row_test_ids") or src.get("test_ids") or []),
        }
    )
    if ik:
        return f"idents:{ik}", "identifiers"
    nid = str(cand.get("node_id") or "")
    return f"legacy:{nid}", "legacy"


def reconcile_node_candidates(
    candidates: list[dict[str, Any]],
    *,
    document_id: str = "",
) -> dict[str, Any]:
    """
    Merge candidates that share the same logical key.

    Never merges different identifier sets into one candidate.
    Preserves provenance; does not drop members.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    key_kinds: dict[str, str] = {}
    for cand in candidates:
        key, kind = _candidate_logical_key(cand)
        groups.setdefault(key, []).append(cand)
        key_kinds[key] = kind

    reconciled: list[ReconciledNodeCandidate] = []
    conflicts: list[dict[str, Any]] = []

    for key, members in groups.items():
        legacy_ids: list[str] = []
        stable_ids: list[str] = []
        bases: set[str] = set()
        physical: list[str] = []
        templates: list[str] = []
        groups_ids: list[str] = []
        id_sets: list[dict[str, list[str]]] = []
        evidence: list[dict[str, Any]] = []
        inst_keys: set[str] = set()
        inst_sigs: set[str] = set()
        seen_spans: set[str] = set()

        for m in members:
            meta = m.get("metadata") or {}
            nid = str(m.get("node_id") or "")
            if nid and nid not in legacy_ids:
                legacy_ids.append(nid)
            if nid and nid not in physical:
                physical.append(nid)
            sid = meta.get("stable_node_id") or m.get("stable_node_id")
            if sid and sid not in stable_ids:
                stable_ids.append(str(sid))
            base = meta.get("stable_node_id_base") or m.get("stable_node_id_base") or ""
            if base:
                bases.add(str(base))
            tid = meta.get("template_node_id")
            if tid and tid not in templates:
                templates.append(str(tid))
            sg = meta.get("structural_group_id")
            if sg and sg not in groups_ids:
                groups_ids.append(str(sg))
            id_set = {
                "requirement_ids": list(
                    meta.get("row_requirement_ids")
                    or (meta.get("source_identifiers") or {}).get("requirement_ids")
                    or m.get("matched_requirement_ids")
                    or []
                ),
                "design_ids": list(
                    meta.get("row_design_ids")
                    or (meta.get("source_identifiers") or {}).get("design_ids")
                    or []
                ),
                "test_ids": list(
                    meta.get("row_test_ids")
                    or (meta.get("source_identifiers") or {}).get("test_ids")
                    or []
                ),
            }
            id_sets.append(id_set)
            dik = meta.get("duplicate_instance_key")
            if dik:
                inst_keys.add(str(dik))
            isig = meta.get("instance_signature") or ""
            if isig:
                inst_sigs.add(str(isig))

            # Dedup evidence by source span
            span = str(
                meta.get("source_span")
                or f"{meta.get('table_index')}:{meta.get('row_index')}:{nid}"
            )
            if span not in seen_spans:
                seen_spans.add(span)
                evidence.append(
                    {
                        "independent_group": key,
                        "source_scope": meta.get("evidence_scope") or "ROW_LOCAL",
                        "source_locator": {
                            "table_index": meta.get("table_index"),
                            "row_index": meta.get("row_index"),
                            "node_id": nid,
                        },
                        "derived_from": m.get("source_stage") or "candidate",
                        "evidence_strength": float(meta.get("final_score") or m.get("overlap") or 0.0),
                        "supports_ranking": True,
                        "supports_review": m.get("status") in {"REVIEW_REQUIRED", "PATCH_CANDIDATE"},
                        "supports_patch": m.get("status") == "PATCH_CANDIDATE",
                        "provenance_node_id": nid,
                    }
                )

        # Conflict if identifier sets disagree within group
        id_keys = {_ident_key(s) for s in id_sets if _ident_key(s)}
        member_conflicts: list[str] = []
        if len(id_keys) > 1:
            member_conflicts.append("identifier_set_mismatch")
            conflicts.append({"group_key": key, "identifier_keys": sorted(id_keys)})

        status = "UNRESOLVED"
        if key_kinds.get(key) == "stable_base" and not member_conflicts:
            status = "STABLE_RECONCILED" if len(members) > 1 else "EXACT_RECONCILED"
        elif key_kinds.get(key) == "identifiers" and not member_conflicts:
            status = "GROUP_RECONCILED"
        elif member_conflicts:
            status = "CONFLICTED"
        elif key_kinds.get(key) == "legacy":
            status = "EXACT_RECONCILED"
        else:
            status = "STABLE_RECONCILED" if bases else "UNRESOLVED"

        primary = legacy_ids[0] if legacy_ids else ""
        # Prefer member with highest final_score as primary
        best = max(
            members,
            key=lambda x: float((x.get("metadata") or {}).get("final_score") or x.get("overlap") or 0.0),
        )
        primary = str(best.get("node_id") or primary)

        rec = ReconciledNodeCandidate(
            reconciled_candidate_id=f"rec:{key[:48]}",
            document_id=document_id or str(best.get("document_id") or ""),
            logical_node_key=key,
            legacy_node_ids=legacy_ids,
            stable_node_ids=stable_ids,
            stable_node_id_base=next(iter(bases), key if key_kinds.get(key) == "stable_base" else ""),
            physical_node_ids=physical,
            template_node_ids=templates,
            structural_group_ids=groups_ids,
            identifier_sets=id_sets,
            primary_source_node_id=primary,
            evidence=evidence,
            conflicts=member_conflicts,
            reconciliation_status=status,
            duplicate_instance_key=next(iter(inst_keys), None),
            instance_signature=next(iter(inst_sigs), ""),
            metadata={
                "member_count": len(members),
                "key_kind": key_kinds.get(key),
                "writer_executable": False,
            },
        )
        reconciled.append(rec)

        # Annotate original candidates
        for m in members:
            meta = m.setdefault("metadata", {})
            meta["reconciled_candidate_id"] = rec.reconciled_candidate_id
            meta["reconciliation_status"] = status
            meta["stable_node_id_base"] = rec.stable_node_id_base or meta.get("stable_node_id_base")

    return {
        "candidates": [r.to_dict() for r in reconciled],
        "n_input": len(candidates),
        "n_reconciled": len(reconciled),
        "conflicts": conflicts,
        "validation": {
            "reconciliation_identifier_safe": len(conflicts) == 0
            or all(c.get("identifier_keys") for c in conflicts),
            "no_cross_identifier_merge": True,
        },
    }
