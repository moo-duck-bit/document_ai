# -*- coding: utf-8 -*-
"""Robustness / metamorphic transforms (metadata + CR variants; no case-id hardcode in engine)."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Callable


@dataclass
class MetamorphicPair:
    pair_id: str
    base_case_id: str
    variant_case_id: str
    transformation: str
    expected_relation: str
    notes: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def whitespace_variant(text: str) -> str:
    return re.sub(r"\s+", "  ", (text or "").strip()) + " "


def case_variant(text: str) -> str:
    # Toggle ASCII letters only
    out = []
    for ch in text or "":
        if "a" <= ch <= "z":
            out.append(ch.upper())
        elif "A" <= ch <= "Z":
            out.append(ch.lower())
        else:
            out.append(ch)
    return "".join(out)


def paren_variant(text: str) -> str:
    t = (text or "").strip()
    return f"({t})" if t else t


def req_format_variants(canonical_cr: str) -> dict[str, str]:
    """Produce identifier format variants when CR contains Req. N."""
    m = re.search(r"Req\.\s*(\d+)", canonical_cr or "", re.IGNORECASE)
    if not m:
        return {}
    n = m.group(1)
    base = re.sub(r"Req\.\s*\d+", "{ID}", canonical_cr, count=1, flags=re.IGNORECASE)
    return {
        "req_dot": base.replace("{ID}", f"Req. {n}"),
        "req_space": base.replace("{ID}", f"Req {n}"),
        "req_dash": base.replace("{ID}", f"REQ-{n}"),
    }


TRANSFORM_REGISTRY: dict[str, Callable[[str], str]] = {
    "whitespace": whitespace_variant,
    "case_toggle": case_variant,
    "paren": paren_variant,
}


def apply_text_transform(text: str, name: str) -> str:
    fn = TRANSFORM_REGISTRY.get(name)
    if not fn:
        raise KeyError(f"unknown_transform:{name}")
    return fn(text)


def compute_decision_consistency(
    pairs: list[dict[str, Any]],
    decisions_by_case: dict[str, str],
) -> dict[str, Any]:
    """pairs: [{base_case_id, variant_case_id, transformation, expected_relation}]"""
    ok = 0
    n = 0
    by_tf: dict[str, list[float]] = {}
    for p in pairs:
        base = decisions_by_case.get(p["base_case_id"])
        var = decisions_by_case.get(p["variant_case_id"])
        if base is None or var is None:
            continue
        n += 1
        same = base == var
        # REVIEW may downgrade from IMPACTED under ambiguity — still consistent if relation allows
        relation = p.get("expected_relation") or "same_document_decision"
        if relation == "same_document_decision":
            hit = same
        elif relation == "no_patch_upgrade":
            # variant must not become more aggressive toward PATCH/IMPACTED incorrectly
            order = {"UNRELATED": 0, "REVIEW_REQUIRED": 1, "IMPACTED": 2}
            hit = order.get(var, 0) <= order.get(base, 0) or same
        else:
            hit = same
        ok += int(hit)
        by_tf.setdefault(p.get("transformation") or "unknown", []).append(float(hit))
    def _avg(xs: list[float]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    return {
        "decision_consistency_rate": (ok / n) if n else 0.0,
        "n_pairs": n,
        "by_transformation": {k: _avg(v) for k, v in by_tf.items()},
        "metamorphic_pass_rate": (ok / n) if n else 0.0,
    }


def compute_node_consistency(
    pairs: list[dict[str, Any]],
    top1_by_case: dict[str, str | None],
    equivalence: dict[str, set[str]] | None = None,
) -> dict[str, Any]:
    eq = equivalence or {}
    ok = n = 0
    for p in pairs:
        a = top1_by_case.get(p["base_case_id"])
        b = top1_by_case.get(p["variant_case_id"])
        if a is None and b is None:
            ok += 1
            n += 1
            continue
        if a is None or b is None:
            n += 1
            continue
        n += 1
        if a == b:
            ok += 1
            continue
        group = eq.get(a) or eq.get(b) or set()
        if a in group and b in group:
            ok += 1
    return {
        "node_consistency_rate": (ok / n) if n else 0.0,
        "n_pairs": n,
    }
