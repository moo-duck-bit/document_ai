"""LEDGER-style consistency stub for regulatory document sets.

Minimal programmatic checks inspired by LEDGER reference / terminology /
hierarchy validators — redefined for MDSR↔MDDR regulatory packs.

**Not** a full LEDGER port. No embedding similarity thresholds (θ).
Produces a comparison column for paper tables.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .case_loader import load_case
from .hidden_ids import read_node_map

_FREQUENCY_TERMS = (
    "매일",
    "daily",
    "주 2회",
    "주 3회",
    "주 4회",
    "주 5회",
    "2_per_week",
    "3_per_week",
    "4_per_week",
    "5_per_week",
)


def _extract_frequency_tokens(text: str) -> set[str]:
    t = text or ""
    found: set[str] = set()
    for term in _FREQUENCY_TERMS:
        if term.lower() in t.lower() or term in t:
            found.add(term.lower() if term.isascii() else term)
    for m in re.finditer(r"주\s*(\d+)\s*회", t):
        found.add(f"주{m.group(1)}회")
    for m in re.finditer(r"(\d+)_per_week", t, re.I):
        found.add(f"{m.group(1)}_per_week")
    return found


def _norm_freq(tokens: set[str]) -> set[str]:
    out: set[str] = set()
    for x in tokens:
        m = re.match(r"주\s*(\d+)\s*회", x) or re.match(r"주(\d+)회", x)
        if m:
            out.add(f"w{m.group(1)}")
            continue
        m = re.match(r"(\d+)_per_week", x)
        if m:
            out.add(f"w{m.group(1)}")
            continue
        if x in {"매일", "daily"}:
            out.add("daily")
            continue
        out.add(x)
    return out


def check_reference_integrity(case: dict[str, Any]) -> dict[str, Any]:
    """Cross-doc references: gold impact nodes with trace_from must point at known req."""
    gold = case["gold"]
    objects = gold.get("impact_node_objects") or []
    untouched = gold.get("untouched_node_objects") or []
    known_reqs = {
        str(o.get("req_id"))
        for o in objects + untouched
        if o.get("req_id")
    }
    for o in objects + untouched:
        nid = str(o.get("node_id") or "")
        m = re.match(r"REQ_(\d+)_DESC", nid)
        if m:
            known_reqs.add(f"Req. {int(m.group(1))}")

    violations: list[dict[str, str]] = []
    checked = 0
    for o in objects:
        trace_from = o.get("trace_from")
        if not trace_from:
            continue
        checked += 1
        if str(trace_from) not in known_reqs:
            violations.append(
                {
                    "node_id": str(o.get("node_id")),
                    "trace_from": str(trace_from),
                    "reason": "trace_from_req_not_in_known_set",
                }
            )
    ok = len(violations) == 0
    return {
        "check": "reference",
        "ok": ok,
        "checked": checked,
        "violations": violations,
        "score": 1.0 if ok else max(0.0, 1.0 - len(violations) / max(1, checked)),
    }


def check_terminology_consistency(case: dict[str, Any]) -> dict[str, Any]:
    """Frequency terms should align across linked MDSR req and MDDR design cells.

    Surface string tokens only — no embeddings.
    """
    root = Path(case["case_dir"])
    node_maps: dict[str, dict[str, dict[str, Any]]] = {}
    for rel, key in (("input/MDSR_v1.docx", "MDSR"), ("input/MDDR_v1.docx", "MDDR")):
        p = root / rel
        if p.exists():
            node_maps[key] = read_node_map(p)

    objects = case["gold"].get("impact_node_objects") or []
    by_id = {str(o["node_id"]): o for o in objects if o.get("node_id")}
    seed_reqs = {
        str(o.get("req_id"))
        for o in objects
        if o.get("link_type") == "explicit_seed" and o.get("req_id")
    }

    violations: list[dict[str, Any]] = []
    checked = 0
    all_text: dict[str, str] = {}
    for _doc, nmap in node_maps.items():
        for nid, info in nmap.items():
            all_text[nid] = str(info.get("text") or "")

    for seed in seed_reqs or {"Req. 7"}:
        req_nodes = [
            nid
            for nid, o in by_id.items()
            if o.get("req_id") == seed or o.get("link_type") == "explicit_seed"
        ]
        design_nodes = [
            nid
            for nid, o in by_id.items()
            if o.get("trace_from") == seed or o.get("design_id")
        ]
        req_tokens: set[str] = set()
        design_tokens: set[str] = set()
        for nid in req_nodes:
            req_tokens |= _extract_frequency_tokens(all_text.get(nid, ""))
            checked += 1
        for nid in design_nodes:
            design_tokens |= _extract_frequency_tokens(all_text.get(nid, ""))
            checked += 1
        if req_tokens and design_tokens and _norm_freq(req_tokens).isdisjoint(_norm_freq(design_tokens)):
            violations.append(
                {
                    "seed_req": seed,
                    "req_tokens": sorted(req_tokens),
                    "design_tokens": sorted(design_tokens),
                    "reason": "frequency_term_mismatch_across_docs",
                }
            )

    ok = len(violations) == 0
    return {
        "check": "terminology",
        "ok": ok,
        "checked": checked,
        "violations": violations,
        "score": 1.0 if ok else max(0.0, 1.0 - len(violations) / max(1, len(seed_reqs) or 1)),
        "note": "surface-token check only; no embedding θ",
    }


def check_hierarchy_structure(case: dict[str, Any]) -> dict[str, Any]:
    """Structural hierarchy: MDSR+MDDR pair present in meta and on disk."""
    root = Path(case["case_dir"])
    meta = case.get("meta") or {}
    docs = meta.get("documents") or []
    violations: list[dict[str, str]] = []
    checked = 0

    ids = {str(d.get("document_id") or d.get("doc_id") or "") for d in docs}
    roles = {str(d.get("role") or d.get("document_role") or "") for d in docs}
    checked += 1
    if not ({"MDSR_v1", "MDDR_v1"} <= ids or len(ids) >= 2 or ({"requirements", "design"} & roles)):
        if len(docs) < 2:
            violations.append({"reason": "meta_missing_mdsr_mddr_pair"})

    for rel in ("input/MDSR_v1.docx", "input/MDDR_v1.docx"):
        checked += 1
        if not (root / rel).exists():
            violations.append({"reason": f"missing_file:{rel}"})

    dimpacts = case["gold"].get("document_impacts") or []
    checked += 1
    doc_ids = {
        str(d.get("document_id") or d.get("doc_id") or "")
        for d in dimpacts
    }
    if dimpacts and not ({"MDSR_v1", "MDDR_v1"} & doc_ids):
        violations.append({"reason": "gold_document_impacts_missing_mdsr_mddr"})

    ok = len(violations) == 0
    return {
        "check": "hierarchy",
        "ok": ok,
        "checked": checked,
        "violations": violations,
        "score": 1.0 if ok else max(0.0, 1.0 - len(violations) / max(1, checked)),
    }


def run_consistency_stub(case_dir: Path | str) -> dict[str, Any]:
    """Run all three LEDGER-style stub checks; return aggregate for scorecard column."""
    case = load_case(case_dir)
    reference = check_reference_integrity(case)
    terminology = check_terminology_consistency(case)
    hierarchy = check_hierarchy_structure(case)
    checks = [reference, terminology, hierarchy]
    scores = [float(c["score"]) for c in checks]
    aggregate = sum(scores) / len(scores) if scores else 0.0
    all_ok = all(bool(c["ok"]) for c in checks)
    return {
        "case_id": case["case_id"],
        "suite": "regulatory_consistency_stub_v0",
        "ledger_analogue": "reference/terminology/hierarchy (redefined; not embedding θ)",
        "full_ledger_port": False,
        "checks": {
            "reference": reference,
            "terminology": terminology,
            "hierarchy": hierarchy,
        },
        "consistency_score": round(aggregate, 4),
        "consistency_ok": all_ok,
    }
