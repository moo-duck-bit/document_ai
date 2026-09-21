"""Secondary Form Fill Field F1 for Small-A regulatory_bench.

Scores a few *structured* gold patch cells against predicted patch values.
This is intentionally narrow — not the North Star full form-fill stack.
Primary claim remains μ / Safety-first; Field F1 is a secondary usability signal.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .case_loader import load_case

# Structured / semi-structured only — pure free_text is optional LLM territory.
STRUCTURED_VALUE_TYPES = frozenset({"structured", "free_text_structured"})


def _norm(text: Any) -> str:
    s = "" if text is None else str(text)
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _patch_value(patch: dict[str, Any]) -> str:
    for key in ("after", "new_value", "value", "text"):
        if patch.get(key) is not None:
            return str(patch[key])
    return ""


def _index_patches(patches: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for p in patches or []:
        nid = str(p.get("node_id") or p.get("id") or "")
        if nid:
            out[nid] = p
    return out


def score_structured_field_f1(
    case_dir: Path | str,
    artifacts: dict[str, Any] | None = None,
    *,
    max_fields: int = 4,
) -> dict[str, Any]:
    """Field F1 over a small structured gold-patch subset (secondary metric)."""
    case = load_case(case_dir)
    gold_patches = (case.get("gold") or {}).get("expected_patch") or {}
    if isinstance(gold_patches, dict):
        gold_list = list(gold_patches.get("patches") or [])
    else:
        gold_list = []

    structured = [
        p
        for p in gold_list
        if str(p.get("value_type") or p.get("value_kind") or "") in STRUCTURED_VALUE_TYPES
        or bool(p.get("must_match_exactly") or p.get("must_match_exactly"))
    ]
    # Prefer PARAM / ID-like nodes first, then DESC.
    structured.sort(
        key=lambda p: (
            0 if "PARAM" in str(p.get("node_id") or "") else 1,
            str(p.get("node_id") or ""),
        )
    )
    structured = structured[: max(1, max_fields)]

    pred_list: list[dict[str, Any]] = []
    if artifacts:
        pred_list = list(artifacts.get("patch_diff") or artifacts.get("patches") or [])
    pred_by = _index_patches(pred_list)

    fields: list[dict[str, Any]] = []
    tp = fp = fn = 0
    for gp in structured:
        nid = str(gp.get("node_id") or "")
        expected = _norm(_patch_value(gp))
        pred = pred_by.get(nid)
        actual = _norm(_patch_value(pred)) if pred else ""
        matched = bool(expected) and expected == actual
        if matched:
            tp += 1
        elif pred is None or not actual:
            fn += 1
        else:
            fp += 1
            fn += 1  # wrong value counts as miss + false
        fields.append(
            {
                "node_id": nid,
                "value_type": gp.get("value_type") or gp.get("value_kind"),
                "expected": _patch_value(gp),
                "actual": _patch_value(pred) if pred else None,
                "matched": matched,
            }
        )

    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "role": "secondary_usability",
        "note": (
            "Small-A structured-cell Field F1 only. "
            "Not the primary Document-TNR / μ claim; not full North Star form-fill."
        ),
        "case_id": case.get("case_id"),
        "field_count": len(fields),
        "matched_count": tp,
        "field_precision": round(precision, 4),
        "field_recall": round(recall, 4),
        "field_f1": round(f1, 4),
        "fields": fields,
    }
