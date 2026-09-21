# -*- coding: utf-8 -*-
"""Stable logical node identity v1 + v2 (legacy physical IDs preserved separately)."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any

IDENTITY_VERSION = "stable_node_identity_v1"
IDENTITY_VERSION_V2 = "stable_node_identity_v2"

_WS = re.compile(r"\s+")
_REQ_NUM = re.compile(
    r"(?i)(?:req(?:uirements?)?|요구(?:사항)?)[\s._\-]*(\d+)|(?:^|[^\w])r[\s._\-]*(\d+)(?!\d)"
)
_REQ_SIMPLE = re.compile(r"(?i)(?<![A-Za-z0-9])Req\.?\s*(\d+)(?![A-Za-z0-9])")
_REQ_DASH = re.compile(r"(?i)(?<![A-Za-z0-9])REQ[_.\-](\d+)(?![A-Za-z0-9])")
_IA = re.compile(r"(?i)\bIA[\s_\-]*(\d+)\b")
_TC = re.compile(r"(?i)\bTC[\s_\-]*(\d+)\b")
_UC = re.compile(r"(?i)\bUC[\s_\-]*(\d+)\b")
_SI = re.compile(r"(?i)\bSI[\s_\-]*(\d+)\b")
_SECTION = re.compile(r"\b\d+\.\d+(?:\.\d+)*\b")


def _hash_blob(blob: str) -> str:
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s or "")


def _canon_token(s: str) -> str:
    """v1-compatible token (uppercase, Req. spacing)."""
    t = _WS.sub(" ", _nfkc(s).strip().upper())
    t = t.replace("REQ ", "REQ.")
    return t


def canonicalize_requirement_id(raw: str) -> str | None:
    """Canonical REQ-N (zero-pad not applied; natural int). Malformed → None."""
    s = _nfkc(raw or "").strip()
    if not s:
        return None
    # reject glued REQ2 / Req2
    if re.match(r"(?i)^REQ\d+$", s) or re.match(r"(?i)^Req\d+$", s):
        return None
    for rx in (_REQ_SIMPLE, _REQ_DASH):
        m = rx.fullmatch(s) or rx.search(s)
        if m:
            return f"REQ-{int(m.group(1))}"
    return None


def canonicalize_design_id(raw: str) -> str | None:
    s = _nfkc(raw or "").strip()
    if not s:
        return None
    if re.match(r"(?i)^IA[\s_\-]*\d+$", s):
        m = _IA.search(s)
        if m:
            n = int(m.group(1))
            return f"IA-{n:02d}" if n < 100 else f"IA-{n}"
    if _SECTION.fullmatch(s) and not _REQ_SIMPLE.search(s):
        return s
    return None


def canonicalize_test_id(raw: str) -> str | None:
    s = _nfkc(raw or "").strip()
    if not s:
        return None
    for rx, prefix in ((_TC, "TC"), (_UC, "UC"), (_SI, "SI"), (_IA, "IA")):
        m = rx.fullmatch(s.strip())
        if m:
            n = int(m.group(1))
            if prefix == "IA":
                return f"IA-{n:02d}" if n < 100 else f"IA-{n}"
            return f"{prefix}-{n}"
    if _SECTION.fullmatch(s.strip()) and not _REQ_SIMPLE.search(s):
        return s.strip()
    # TC 12 / tc_12 loose
    m = re.match(r"(?i)^(TC|UC|SI)[\s_\-]*(\d+)$", s.strip())
    if m:
        return f"{m.group(1).upper()}-{int(m.group(2))}"
    return None


def canonicalize_id_list(kind: str, values: list[str] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for v in values or []:
        if kind == "requirement":
            # Prefer dedicated parser canonical Req. N → REQ-N
            from document_ai.domain_packs.ec_sw.identifier_parser import valid_canonical_requirement_ids

            parsed = valid_canonical_requirement_ids(v)
            cands = []
            for p in parsed:
                c = canonicalize_requirement_id(p)
                if not c:
                    mnum = re.search(r"(\d+)", p)
                    if mnum:
                        c = f"REQ-{int(mnum.group(1))}"
                if c:
                    cands.append(c)
            if not cands:
                c = canonicalize_requirement_id(v)
                if c:
                    cands.append(c)
            for c in cands:
                if c not in seen:
                    seen.add(c)
                    out.append(c)
        elif kind == "design":
            c = canonicalize_design_id(v)
            if c and c not in seen:
                # Avoid treating IA as design when already a bare section from req cell noise
                seen.add(c)
                out.append(c)
            elif v and _SECTION.fullmatch(v.strip()) and v.strip() not in seen:
                seen.add(v.strip())
                out.append(v.strip())
        elif kind == "test":
            c = canonicalize_test_id(v)
            if c and c not in seen:
                seen.add(c)
                out.append(c)
            elif v and _SECTION.fullmatch(v.strip()) and v.strip() not in seen:
                seen.add(v.strip())
                out.append(v.strip())
    return sorted(out)


def canonical_identifier_key(
    *,
    requirement_ids: list[str] | None = None,
    design_ids: list[str] | None = None,
    test_ids: list[str] | None = None,
    version: str = IDENTITY_VERSION,
) -> str:
    if version == IDENTITY_VERSION_V2:
        reqs = canonicalize_id_list("requirement", requirement_ids)
        dens = canonicalize_id_list("design", design_ids)
        tests = canonicalize_id_list("test", test_ids)
    else:
        reqs = sorted({_canon_token(x) for x in (requirement_ids or []) if x})
        dens = sorted({_canon_token(x) for x in (design_ids or []) if x})
        tests = sorted({_canon_token(x) for x in (test_ids or []) if x})
    parts = []
    if reqs:
        parts.append("REQ[" + ",".join(reqs) + "]")
    if dens:
        parts.append("DESIGN[" + ",".join(dens) + "]")
    if tests:
        parts.append("TEST[" + ",".join(tests) + "]")
    return "|".join(parts)


@dataclass
class StableNodeIdentity:
    stable_node_id: str
    document_identity: str
    node_type: str
    logical_key: str
    canonical_identifiers: dict[str, list[str]] = field(default_factory=dict)
    canonical_content_signature: str = ""
    structural_role: str = ""
    source_locator: dict[str, Any] = field(default_factory=dict)
    fingerprint: str = ""
    identity_version: str = IDENTITY_VERSION
    confidence: float = 1.0
    reason_codes: list[str] = field(default_factory=list)
    legacy_node_id: str | None = None
    duplicate_instance_key: str | None = None
    physical_location_resolved: bool = False
    writer_executable: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    # v2 fields
    stable_node_id_base: str = ""
    stable_node_id_v1: str = ""
    stable_node_id_v2: str = ""
    identity_core_signature: str = ""
    instance_signature: str = ""
    duplicate_group_id: str | None = None
    identity_status: str = "STABLE"
    identity_confidence: float = 1.0
    domain_pack_id: str = "ec_sw_v1"
    document_role: str = "traceability"
    canonical_key_fields: list[dict[str, Any]] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_stable_node_id(
    *,
    document_identity: str,
    node_type: str,
    logical_key: str,
    structural_role: str = "",
    content_signature: str = "",
) -> str:
    """v1 stable id (includes document_identity — kept for compatibility)."""
    payload = json.dumps(
        {
            "doc": document_identity or "",
            "type": node_type or "",
            "key": logical_key or "",
            "role": structural_role or "",
            "sig": content_signature or "",
            "v": IDENTITY_VERSION,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return f"stable.{node_type.lower()}.{_hash_blob(payload)}"


def build_stable_node_id_base(
    *,
    domain_pack_id: str,
    document_role: str,
    node_type: str,
    logical_key: str,
    structural_role: str = "",
) -> str:
    """v2 base id — excludes upload document_id, row/table index, filename, path."""
    payload = json.dumps(
        {
            "pack": domain_pack_id or "ec_sw_v1",
            "doc_role": document_role or "",
            "type": node_type or "",
            "key": logical_key or "",
            "role": structural_role or "",
            "v": IDENTITY_VERSION_V2,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return f"stablev2.{node_type.lower()}.{_hash_blob(payload)}"


def build_instance_signature(
    *,
    local_texts: list[str] | None = None,
    note_text: str = "",
    cell_values: list[str] | None = None,
    identifier_texts: set[str] | None = None,
) -> str:
    """Row-local substantive content for duplicate disambiguation (not base identity)."""
    id_text = {(_canon_token(x) if x else "") for x in (identifier_texts or set())}
    parts: list[str] = []
    for t in local_texts or []:
        n = _WS.sub(" ", _nfkc(t).strip().lower())
        n = re.sub(r"[^\w가-힣\s.\-_/]", "", n)
        if not n or _canon_token(n) in id_text:
            continue
        if len(n) < 2:
            continue
        parts.append(n)
    if note_text.strip():
        n = _WS.sub(" ", _nfkc(note_text).strip().lower())
        n = re.sub(r"[^\w가-힣\s.\-_/]", "", n)
        if n and n not in parts:
            parts.append(n)
    # Optional: non-identifier cells
    for c in cell_values or []:
        n = _WS.sub(" ", _nfkc(c).strip().lower())
        n = re.sub(r"[^\w가-힣\s.\-_/]", "", n)
        if not n or len(n) < 2:
            continue
        if any(x in n.upper() for x in id_text) or _canon_token(c) in id_text:
            continue
        # skip pure identifiers
        if canonicalize_requirement_id(c) or canonicalize_design_id(c) or canonicalize_test_id(c):
            continue
        if n not in parts:
            parts.append(n)
    if not parts:
        return ""
    blob = "|".join(sorted(set(parts)))
    return _hash_blob(blob)


def mdtm_row_stable_identity(
    *,
    document_identity: str,
    requirement_ids: list[str],
    design_ids: list[str],
    test_ids: list[str],
    legacy_node_id: str | None = None,
    source_locator: dict[str, Any] | None = None,
    note_text: str = "",
    duplicate_instance_index: int | None = None,
    domain_pack_id: str = "ec_sw_v1",
    document_role: str = "traceability",
    cell_values: list[str] | None = None,
    canonical_key_fields: list[dict[str, Any]] | None = None,
    local_texts: list[str] | None = None,
) -> StableNodeIdentity:
    logical_key_v1 = canonical_identifier_key(
        requirement_ids=requirement_ids,
        design_ids=design_ids,
        test_ids=test_ids,
        version=IDENTITY_VERSION,
    )
    logical_key_v2 = canonical_identifier_key(
        requirement_ids=requirement_ids,
        design_ids=design_ids,
        test_ids=test_ids,
        version=IDENTITY_VERSION_V2,
    )
    content_sig = _hash_blob(_canon_token(note_text)) if note_text.strip() else ""
    sid_v1 = build_stable_node_id(
        document_identity=document_identity or "EC_SW_MDTM",
        node_type="TABLE_ROW",
        logical_key=logical_key_v1 or "EMPTY_ROW",
        structural_role="traceability_row",
        content_signature="",
    )
    base_v2 = build_stable_node_id_base(
        domain_pack_id=domain_pack_id,
        document_role=document_role,
        node_type="TABLE_ROW",
        logical_key=logical_key_v2 or "EMPTY_ROW",
        structural_role="traceability_row",
    )
    id_texts = set(requirement_ids or []) | set(design_ids or []) | set(test_ids or [])
    inst_sig = build_instance_signature(
        local_texts=local_texts,
        note_text=note_text,
        cell_values=cell_values,
        identifier_texts=id_texts,
    )
    # Full v2 id = base (+ instance when present for uniqueness display; base stays shared)
    sid_v2 = base_v2 if not inst_sig else f"{base_v2}+{inst_sig[:8]}"
    # Primary stable_node_id for Cycle 3 = v2 base (shared across structure variants)
    sid = base_v2

    dup_key = None
    if duplicate_instance_index is not None:
        dup_key = f"{base_v2}#dup{duplicate_instance_index}"
    elif inst_sig:
        dup_key = f"{base_v2}#inst:{inst_sig[:10]}"

    status = "STABLE"
    conf = 1.0 if logical_key_v2 else 0.3
    if not logical_key_v2:
        status = "UNRESOLVED"
    reasons = [
        "mdtm_identifier_set_key_v2",
        "column_order_independent",
        "row_index_excluded",
        "document_id_excluded_from_base",
        "filename_excluded",
    ]

    return StableNodeIdentity(
        stable_node_id=sid,
        document_identity=document_identity or "EC_SW_MDTM",
        node_type="TABLE_ROW",
        logical_key=logical_key_v2 or logical_key_v1,
        canonical_identifiers={
            "requirement_ids": canonicalize_id_list("requirement", requirement_ids),
            "design_ids": canonicalize_id_list("design", design_ids),
            "test_ids": canonicalize_id_list("test", test_ids),
        },
        canonical_content_signature=content_sig or inst_sig,
        structural_role="traceability_row",
        source_locator=dict(source_locator or {}),
        fingerprint=sid,
        identity_version=IDENTITY_VERSION_V2,
        confidence=conf,
        reason_codes=reasons,
        legacy_node_id=legacy_node_id,
        duplicate_instance_key=dup_key,
        physical_location_resolved=bool(source_locator),
        writer_executable=False,
        metadata={
            "logical_identity_resolved": bool(logical_key_v2),
            "physical_location_resolved": bool(source_locator),
            "writer_executable": False,
        },
        stable_node_id_base=base_v2,
        stable_node_id_v1=sid_v1,
        stable_node_id_v2=sid_v2,
        identity_core_signature=_hash_blob(logical_key_v2 or "EMPTY"),
        instance_signature=inst_sig,
        duplicate_group_id=base_v2 if dup_key else None,
        identity_status=status,
        identity_confidence=conf,
        domain_pack_id=domain_pack_id,
        document_role=document_role,
        canonical_key_fields=list(canonical_key_fields or []),
        provenance={
            "legacy_node_id": legacy_node_id,
            "source_locator": dict(source_locator or {}),
            "note_excluded_from_base": True,
        },
    )


def section_stable_identity(
    *,
    document_identity: str,
    template_node_id: str | None = None,
    heading_path: str = "",
    concept: str = "",
    legacy_node_id: str | None = None,
    domain_pack_id: str = "generic_v1",
    document_role: str = "report",
) -> StableNodeIdentity:
    logical_key = template_node_id or _canon_token(heading_path) or _canon_token(concept)
    sid_v1 = build_stable_node_id(
        document_identity=document_identity,
        node_type="SECTION",
        logical_key=logical_key,
        structural_role="section",
    )
    base = build_stable_node_id_base(
        domain_pack_id=domain_pack_id,
        document_role=document_role,
        node_type="SECTION",
        logical_key=logical_key,
        structural_role="section",
    )
    return StableNodeIdentity(
        stable_node_id=base,
        document_identity=document_identity,
        node_type="SECTION",
        logical_key=logical_key,
        structural_role="section",
        fingerprint=base,
        legacy_node_id=legacy_node_id,
        reason_codes=["section_template_or_heading_key", "v2_base"],
        writer_executable=False,
        identity_version=IDENTITY_VERSION_V2,
        stable_node_id_base=base,
        stable_node_id_v1=sid_v1,
        stable_node_id_v2=base,
        domain_pack_id=domain_pack_id,
        document_role=document_role,
        identity_status="STABLE",
    )


def assign_duplicate_instance_keys(identities: list[StableNodeIdentity]) -> list[StableNodeIdentity]:
    """Group by stable_node_id_base; preserve all members; instance keys from content then index."""
    groups: dict[str, list[StableNodeIdentity]] = {}
    for ident in identities:
        base = ident.stable_node_id_base or ident.stable_node_id
        groups.setdefault(base, []).append(ident)
    out: list[StableNodeIdentity] = []
    for base, items in groups.items():
        if len(items) == 1:
            item = items[0]
            if not item.duplicate_instance_key and item.instance_signature:
                item.duplicate_instance_key = f"{base}#inst:{item.instance_signature[:10]}"
            out.append(item)
            continue
        # Prefer instance_signature for disambiguation; fallback index lowers confidence
        used_sigs: dict[str, int] = {}
        for i, item in enumerate(items):
            item.duplicate_group_id = base
            item.identity_status = "DUPLICATE_GROUP"
            item.reason_codes = list(item.reason_codes) + ["duplicate_identifier_set"]
            if item.instance_signature:
                sig = item.instance_signature
                used_sigs[sig] = used_sigs.get(sig, 0) + 1
                suffix = "" if used_sigs[sig] == 1 else f"#{used_sigs[sig]}"
                item.duplicate_instance_key = f"{base}#inst:{sig[:10]}{suffix}"
                item.reason_codes = list(item.reason_codes) + ["RESOLVED_BY_LOCAL_CONTENT"]
            else:
                item.duplicate_instance_key = f"{base}#dup{i}"
                item.identity_confidence = min(item.identity_confidence, 0.45)
                item.confidence = item.identity_confidence
                item.reason_codes = list(item.reason_codes) + [
                    "instance_fallback_index",
                    "UNRESOLVED_DUPLICATE" if len(items) > 1 else "ok",
                ]
            out.append(item)
    return out


def build_legacy_to_stable_mapping(identities: list[StableNodeIdentity]) -> list[dict[str, Any]]:
    rows = []
    for ident in identities:
        if not ident.legacy_node_id:
            continue
        rows.append(
            {
                "legacy_node_id": ident.legacy_node_id,
                "stable_node_id": ident.stable_node_id,
                "stable_node_id_base": ident.stable_node_id_base,
                "stable_node_id_v1": ident.stable_node_id_v1,
                "stable_node_id_v2": ident.stable_node_id_v2,
                "match_method": "identifier_set_v2",
                "confidence": ident.confidence,
                "conflicts": [],
                "duplicate_instance_key": ident.duplicate_instance_key,
                "identity_version": ident.identity_version,
                "instance_signature": ident.instance_signature,
            }
        )
    return rows


def build_duplicate_groups(identities: list[StableNodeIdentity]) -> list[dict[str, Any]]:
    groups: dict[str, list[StableNodeIdentity]] = {}
    for ident in identities:
        base = ident.stable_node_id_base or ident.stable_node_id
        groups.setdefault(base, []).append(ident)
    out = []
    for base, items in groups.items():
        if len(items) <= 1:
            continue
        unresolved = any(
            "UNRESOLVED_DUPLICATE" in (i.reason_codes or []) or not i.instance_signature for i in items
        )
        out.append(
            {
                "group_id": base,
                "stable_node_id_base": base,
                "member_node_ids": [i.legacy_node_id for i in items],
                "member_stable_ids": [i.stable_node_id for i in items],
                "member_instance_keys": [i.duplicate_instance_key for i in items],
                "shared_identifiers": items[0].canonical_identifiers,
                "disambiguation_features": [i.instance_signature for i in items],
                "ambiguity_status": (
                    "UNRESOLVED_DUPLICATE" if unresolved else "RESOLVED_BY_LOCAL_CONTENT"
                ),
                "human_review_required": unresolved,
            }
        )
    return out
