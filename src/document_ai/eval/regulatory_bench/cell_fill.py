"""Rule-based cell fill for live mode (no gold after-text).

Parses the change-request for target frequency and rewrites cell *before*
strings into candidate *after* values. Honest non-gold filler so cell F1
measures rule/model fill quality, not oracle copy.
"""

from __future__ import annotations

import re
from typing import Any

_WEEKLY_RE = re.compile(
    r"(?:주\s*(\d+)\s*회|(\d+)\s*per\s*week|(\d+)_per_week)",
    re.IGNORECASE,
)
_DAILY_RE = re.compile(r"(매일|daily)", re.IGNORECASE)


def parse_target_frequency(change_text: str) -> dict[str, Any] | None:
    """Extract target frequency from CR. Returns {n_per_week, label_ko, label_en}."""
    text = change_text or ""
    matches = list(_WEEKLY_RE.finditer(text))
    n: int | None = None
    if matches:
        m = matches[-1]
        n = int(next(g for g in m.groups() if g))
    elif _DAILY_RE.search(text) and not matches:
        n = 7
    if n is None:
        return None
    return {
        "n_per_week": n,
        "label_ko": "매일" if n >= 7 else f"주 {n}회",
        "label_en": "daily" if n >= 7 else f"{n}_per_week",
        "label_en_alt": "daily" if n >= 7 else f"{n} per week",
    }


def fill_cell_after(before: str, freq: dict[str, Any], *, node_id: str = "") -> str:
    """Rewrite a before-cell string to match target frequency."""
    src = before or ""
    n = int(freq["n_per_week"])
    ko = freq["label_ko"]
    en = freq["label_en"]

    out = src
    out = re.sub(r"매일", ko if n < 7 else "매일", out)
    out = re.sub(r"주\s*\d+\s*회", ko if n < 7 else "매일", out)
    out = re.sub(r"daily", en, out, flags=re.I)
    out = re.sub(r"\d+_per_week", en, out, flags=re.I)
    out = re.sub(r"\d+\s*per\s*week", freq["label_en_alt"], out, flags=re.I)

    if out == src and node_id.endswith(("_DESC", "_NOTIFY", "_PARAM")):
        if "frequency=" in src.lower() or "diary_input_frequency" in src:
            out = re.sub(
                r"(diary_input_frequency\s*=\s*)\S+",
                rf"\1{en}",
                src,
                flags=re.I,
            )
        elif "알림" in src and ko not in out:
            out = re.sub(r"매일|주\s*\d+\s*회", ko, src)
            if out == src:
                out = f"{ko} {src}"
        elif "입력" in src and ko not in out:
            out = re.sub(r"매일|주\s*\d+\s*회", ko, src)
    return out


def build_filled_patches(
    *,
    change_text: str,
    predicted_nodes: list[str],
    node_texts: dict[str, str],
    document_by_node: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Create REPLACE_CELL patches for predicted nodes using CR-derived frequency."""
    freq = parse_target_frequency(change_text)
    if not freq:
        return []
    doc_map = document_by_node or {}
    patches: list[dict[str, Any]] = []
    for nid in predicted_nodes:
        before = node_texts.get(nid, "")
        after = fill_cell_after(before, freq, node_id=nid)
        if not after or after == before:
            if nid.endswith("_PARAM"):
                after = f"diary_input_frequency={freq['label_en']}"
            elif nid.endswith("_NOTIFY"):
                after = f"{freq['label_ko']} 입력 알림"
            elif nid.endswith("_DESC"):
                after = fill_cell_after(
                    before or f"사용자는 일기를 {freq['label_ko']} 입력할 수 있어야 한다.",
                    freq,
                    node_id=nid,
                )
            else:
                continue
        doc_id = doc_map.get(nid) or (
            "MDSR_v1" if nid.startswith("REQ_") or nid.startswith("TRACE_") else "MDDR_v1"
        )
        patches.append(
            {
                "node_id": nid,
                "document_id": doc_id,
                "operation": "REPLACE_CELL",
                "before": before,
                "after": after,
                "new_value": after,
                "value": after,
                "value_type": "rule_fill",
                "fill_source": "change_request_frequency_rules",
            }
        )
    return patches
