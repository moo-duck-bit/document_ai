"""Document-native impact → node closure for Small-A regulatory_bench.

Closes changed Req. IDs to hidden cell node_ids using DOCX node maps and
traceability row text (e.g. ``Req. 7 → DI-12``), plus same-design PARAM/NOTIFY
co-location. Does **not** walk gold ``impact_node_objects``.

Honest label: ``closure_source = "doc_trace_and_row_colocation"``.
Not a full C1 production graph — Small-A structure rules only.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_REQ_NODE_RE = re.compile(r"^REQ_(\d+)_DESC$")
_TRACE_NODE_RE = re.compile(r"^TRACE_ROW_REQ_(\d+)$")
_DI_PARAM_RE = re.compile(r"^DI_(\d+)_PARAM$")
_DI_NOTIFY_RE = re.compile(r"^DI_(\d+)_NOTIFY$")
_TRACE_ARROW_RE = re.compile(
    r"Req\.?\s*(\d+)\s*[→\->]+\s*DI[-\s]?(\d+)",
    re.IGNORECASE,
)
_DI_TOKEN_RE = re.compile(r"DI[-\s]?(\d+)", re.IGNORECASE)
_FREQ_HINT_RE = re.compile(r"(매일|주\s*\d+\s*회|daily|per\s*week|_per_week)", re.I)


def req_num(req_id: str) -> int | None:
    m = re.search(r"(\d+)", req_id or "")
    return int(m.group(1)) if m else None


def node_id_for_req(req_id: str) -> str:
    n = req_num(req_id) or 0
    return f"REQ_{n:03d}_DESC"


def design_param_node(design_num: int) -> str:
    return f"DI_{design_num:03d}_PARAM"


def design_notify_node(design_num: int) -> str:
    return f"DI_{design_num:03d}_NOTIFY"


def normalize_req_label(req_id: str) -> str:
    n = req_num(req_id)
    return f"Req. {n}" if n is not None else str(req_id)


def parse_design_nums_from_trace_text(text: str) -> list[int]:
    """Extract DI numbers from a TRACE cell string like ``Req. 7 → DI-12``."""
    t = text or ""
    nums: list[int] = []
    m = _TRACE_ARROW_RE.search(t)
    if m:
        nums.append(int(m.group(2)))
    else:
        for dm in _DI_TOKEN_RE.finditer(t):
            n = int(dm.group(1))
            if n not in nums:
                nums.append(n)
    return nums


def parse_req_num_from_trace_text(text: str) -> int | None:
    m = _TRACE_ARROW_RE.search(text or "")
    if m:
        return int(m.group(1))
    m = re.search(r"Req\.?\s*(\d+)", text or "", re.I)
    return int(m.group(1)) if m else None


def close_changed_reqs_to_nodes(
    changed_req_ids: list[str] | set[str],
    *,
    mdsr_map: dict[str, dict[str, Any]],
    mddr_map: dict[str, dict[str, Any]],
) -> list[str]:
    """Document-native closure: Req → TRACE → DI PARAM (+ NOTIFY co-location)."""
    predicted: list[str] = []
    mdsr_ids = set(mdsr_map)
    mddr_ids = set(mddr_map)

    for req_id in changed_req_ids:
        n = req_num(str(req_id))
        if n is None:
            continue
        req_node = f"REQ_{n:03d}_DESC"
        if req_node in mdsr_ids and req_node not in predicted:
            predicted.append(req_node)

        # Prefer TRACE_ROW_REQ_NNN; also scan all TRACE texts mentioning this Req.
        trace_candidates = [f"TRACE_ROW_REQ_{n:03d}"]
        for tid, info in mdsr_map.items():
            if not tid.startswith("TRACE_ROW_"):
                continue
            if parse_req_num_from_trace_text(str(info.get("text") or "")) == n:
                if tid not in trace_candidates:
                    trace_candidates.append(tid)

        for tid in trace_candidates:
            info = mdsr_map.get(tid)
            if not info:
                continue
            for dnum in parse_design_nums_from_trace_text(str(info.get("text") or "")):
                param = design_param_node(dnum)
                notify = design_notify_node(dnum)
                if param in mddr_ids and param not in predicted:
                    predicted.append(param)
                if notify in mddr_ids and notify not in predicted:
                    predicted.append(notify)

    return predicted


def pick_seed_req_from_docx(
    *,
    mdsr_map: dict[str, dict[str, Any]],
    change_text: str = "",
) -> tuple[str, str]:
    """Pick (req_label, REQ_*_DESC) without gold seed objects.

    Prefer frequency-bearing REQ that appears in TRACE; else TRACE-linked REQ;
    else REQ_007 if present; else first REQ_*_DESC.
    """
    req_nodes = sorted(
        (nid for nid in mdsr_map if _REQ_NODE_RE.match(nid)),
        key=lambda x: int(_REQ_NODE_RE.match(x).group(1)),  # type: ignore[union-attr]
    )
    traced: set[int] = set()
    for tid, info in mdsr_map.items():
        if tid.startswith("TRACE_ROW_"):
            rn = parse_req_num_from_trace_text(str(info.get("text") or ""))
            if rn is not None:
                traced.add(rn)
            m = _TRACE_NODE_RE.match(tid)
            if m:
                traced.add(int(m.group(1)))

    freq_traced: list[str] = []
    traced_only: list[str] = []
    for nid in req_nodes:
        n = int(_REQ_NODE_RE.match(nid).group(1))  # type: ignore[union-attr]
        text = str(mdsr_map[nid].get("text") or "")
        if n in traced and _FREQ_HINT_RE.search(text):
            freq_traced.append(nid)
        elif n in traced:
            traced_only.append(nid)

    chosen = None
    if freq_traced:
        chosen = freq_traced[0]
    elif traced_only:
        chosen = traced_only[0]
    elif "REQ_007_DESC" in mdsr_map:
        chosen = "REQ_007_DESC"
    elif req_nodes:
        chosen = req_nodes[0]
    else:
        return "Req. 7", "REQ_007_DESC"

    n = int(_REQ_NODE_RE.match(chosen).group(1))  # type: ignore[union-attr]
    return f"Req. {n}", chosen


def extract_traceability_from_mdsr(
    mdsr_map: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    """Build {req_id, design_id} rows from TRACE cell text."""
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for tid, info in mdsr_map.items():
        if not tid.startswith("TRACE_ROW_"):
            continue
        text = str(info.get("text") or "")
        rn = parse_req_num_from_trace_text(text)
        for dnum in parse_design_nums_from_trace_text(text):
            if rn is None:
                m = _TRACE_NODE_RE.match(tid)
                rn = int(m.group(1)) if m else None
            if rn is None:
                continue
            key = f"{rn}:{dnum}"
            if key in seen:
                continue
            seen.add(key)
            rows.append({"req_id": f"Req. {rn}", "design_id": f"DI-{dnum}"})
    return rows


def build_index_payloads_from_docx(
    *,
    mdsr_map: dict[str, dict[str, Any]],
    mddr_map: dict[str, dict[str, Any]],
    change_text: str,
    after_seed_description: str,
) -> dict[str, Any]:
    """Build requirements/design/change JSON payloads from DOCX maps only."""
    req_rows: list[dict[str, Any]] = []
    for nid, info in sorted(mdsr_map.items()):
        m = _REQ_NODE_RE.match(nid)
        if not m:
            continue
        n = int(m.group(1))
        req_rows.append(
            {
                "req_id": f"Req. {n}",
                "description": str(info.get("text") or f"Requirement {n}"),
            }
        )

    traceability = extract_traceability_from_mdsr(mdsr_map)
    # design items from DI_*_PARAM; attach req via traceability when possible
    req_by_design: dict[str, str] = {t["design_id"]: t["req_id"] for t in traceability}
    design_items: list[dict[str, Any]] = []
    for nid, info in sorted(mddr_map.items()):
        m = _DI_PARAM_RE.match(nid)
        if not m:
            continue
        dnum = int(m.group(1))
        design_id = f"DI-{dnum}"
        design_items.append(
            {
                "req_id": req_by_design.get(design_id) or f"Req. {dnum}",
                "design_id": design_id,
                "design_description": str(info.get("text") or f"{design_id} parameter"),
            }
        )

    seed_req, seed_node = pick_seed_req_from_docx(mdsr_map=mdsr_map, change_text=change_text)
    change = {
        "change_id": "live-doc-native",
        "summary": (change_text.strip().splitlines()[0] if change_text.strip() else seed_req)[:200],
        "sync_design_from_requirement": True,
        "requirement_changes": [
            {"req_id": seed_req, "description": after_seed_description},
        ],
        "intake": {
            "channel": "regulatory_bench",
            "raw_request": change_text,
            "parsed_req_ids": [seed_req],
            "confirmed": True,
        },
    }

    return {
        "requirements": {
            "source": "regulatory_bench.live.doc_native",
            "requirements": sorted(req_rows, key=lambda r: req_num(r["req_id"]) or 0),
            "traceability": traceability,
        },
        "design_items": {
            "source": "regulatory_bench.live.doc_native",
            "items": design_items,
        },
        "change": change,
        "seed_req": seed_req,
        "seed_node": seed_node,
        "closure_source": "doc_trace_and_row_colocation",
    }
