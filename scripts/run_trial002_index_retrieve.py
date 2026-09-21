# -*- coding: utf-8 -*-
"""Run Trial 2 B1–B2: index Mindrium MDSR/MDDR + lexical retrieve CR.

Does not load expected_impact during retrieval. Post-hoc evaluation only.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from document_ai.impact.semantic_index import (
    index_documents,
    load_traceability,
    save_index_jsonl,
)
from document_ai.impact.semantic_retrieve import retrieve_candidates, save_candidates

TRIAL = Path("data/trials/trial-002-lockout-multireq")
TRIAL1_REF = Path("data/trials/trial-001-mindrium-xa/reference")
CASE_REQ = Path("data/cases/mindrium_xa/requirements.json")
TOP_K = 15
FOCUS_IDS = ("Req. 6", "Req. 103", "Req. 105")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_reference() -> tuple[Path, Path]:
    ref_dir = TRIAL / "reference"
    ref_dir.mkdir(parents=True, exist_ok=True)
    mdsr_src = next(TRIAL1_REF.glob("spec_mdsr*.docx"))
    mddr_src = next(TRIAL1_REF.glob("spec_mddr*.docx"))
    mdsr_dst = ref_dir / mdsr_src.name
    mddr_dst = ref_dir / mddr_src.name
    if not mdsr_dst.exists() or mdsr_dst.stat().st_size != mdsr_src.stat().st_size:
        shutil.copy2(mdsr_src, mdsr_dst)
    if not mddr_dst.exists() or mddr_dst.stat().st_size != mddr_src.stat().st_size:
        shutil.copy2(mddr_src, mddr_dst)
    return mdsr_dst, mddr_dst


def posthoc_compare(candidates: list[dict], expected_path: Path) -> dict:
    """Evaluation-only: compare retrieval ranks to expected. Not used for ranking."""
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    must = [
        r["req_id"]
        for r in expected.get("requirements", [])
        if r.get("retrieval_must_include") or r.get("expected_judgment") == "impacted"
    ]
    # best rank per req_id across documents
    best: dict[str, dict] = {}
    for c in candidates:
        cid = c["candidate_id"]
        prev = best.get(cid)
        if prev is None or c["rank"] < prev["rank"]:
            best[cid] = c

    focus = {}
    for rid in FOCUS_IDS:
        hit = best.get(rid)
        focus[rid] = (
            {
                "found": True,
                "best_rank": hit["rank"],
                "best_score": hit["score"],
                "document": hit["document"],
                "evidence_snippet": hit.get("evidence_snippet"),
                "matched_evidence": hit.get("matched_evidence"),
            }
            if hit
            else {"found": False}
        )

    top_ids = [c["candidate_id"] for c in candidates]
    false_positives = [
        c
        for c in candidates
        if c["candidate_id"] not in must and c["candidate_id"] not in FOCUS_IDS
    ]
    # FP among top-5 relative to expected impacted set
    expected_impacted = {
        r["req_id"] for r in expected.get("requirements", []) if r.get("expected_judgment") == "impacted"
    }
    top5_fp = [
        c
        for c in candidates
        if c["rank"] <= 5 and c["candidate_id"] not in expected_impacted
    ]

    return {
        "stage": "posthoc_evaluation_only",
        "note": "expected_impact was NOT used during retrieval/ranking",
        "focus_ranks": focus,
        "must_include_hit": {rid: rid in best for rid in must},
        "top_k_candidate_ids": top_ids,
        "top5_false_positives_vs_expected_impacted": [
            {"rank": c["rank"], "id": c["candidate_id"], "document": c["document"], "score": c["score"]}
            for c in top5_fp
        ],
        "all_non_focus_in_topk": [
            {"rank": c["rank"], "id": c["candidate_id"], "document": c["document"], "score": c["score"]}
            for c in false_positives
        ],
    }


def main() -> None:
    mdsr, mddr = ensure_reference()
    cr_path = TRIAL / "input" / "change_request.txt"
    cr_text = cr_path.read_text(encoding="utf-8").strip()
    # Sanity: no Exact-ID leakage in CR
    for banned in ("Req. 6", "Req.6", "Req. 103", "Req.103", "Req. 105", "Req.105"):
        if banned in cr_text:
            raise SystemExit(f"CR must not contain Exact-ID {banned!r}")

    trace = load_traceability(CASE_REQ)
    blocks = index_documents(mdsr_path=mdsr, mddr_path=mddr, traceability=trace)

    out_dir = TRIAL / "retrieval"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Split indexes
    mdsr_blocks = [b for b in blocks if b.document_type == "MDSR"]
    mddr_blocks = [b for b in blocks if b.document_type == "MDDR"]
    save_index_jsonl(mdsr_blocks, out_dir / "index_mdsr.jsonl")
    save_index_jsonl(mddr_blocks, out_dir / "index_mddr.jsonl")
    save_index_jsonl(blocks, out_dir / "index_all.jsonl")

    index_meta = {
        "created_at": utc_now(),
        "mdsr_path": str(mdsr).replace("\\", "/"),
        "mddr_path": str(mddr).replace("\\", "/"),
        "mdsr_block_count": len(mdsr_blocks),
        "mddr_block_count": len(mddr_blocks),
        "total_blocks": len(blocks),
        "focus_present_in_index": {
            rid: any(b.req_id == rid for b in blocks) for rid in FOCUS_IDS
        },
        "traceability_source": str(CASE_REQ).replace("\\", "/"),
    }
    (out_dir / "index_meta.json").write_text(
        json.dumps(index_meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    candidates = retrieve_candidates(cr_text, blocks, top_k=TOP_K)
    cand_dicts = [c.to_dict() for c in candidates]

    retrieval_payload = {
        "created_at": utc_now(),
        "trial_id": "trial-002-lockout-multireq",
        "stage": "B1_B2",
        "method": "lexical_overlap",
        "top_k": TOP_K,
        "change_request_path": str(cr_path).replace("\\", "/"),
        "change_request_text": cr_text,
        "exact_id_in_cr": False,
        "expected_impact_used_in_retrieval": False,
        "candidates": cand_dicts,
    }
    save_candidates(out_dir / "candidates.json", retrieval_payload)

    # Post-hoc evaluation ONLY
    eval_payload = posthoc_compare(cand_dicts, TRIAL / "expected" / "expected_impact.json")
    eval_payload["created_at"] = utc_now()
    (out_dir / "posthoc_vs_expected.json").write_text(
        json.dumps(eval_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Human-readable smoke report
    lines = [
        "# B1–B2 Smoke Report",
        "",
        f"- created_at: `{utc_now()}`",
        f"- method: lexical_overlap",
        f"- top_k: `{TOP_K}`",
        f"- expected_impact_used_in_retrieval: `false`",
        f"- index blocks: MDSR={len(mdsr_blocks)}, MDDR={len(mddr_blocks)}",
        "",
        "## Focus ranks (post-hoc)",
        "",
    ]
    for rid, info in eval_payload["focus_ranks"].items():
        if info.get("found"):
            lines.append(
                f"- **{rid}**: rank={info['best_rank']}, score={info['best_score']}, "
                f"doc={info['document']}"
            )
            lines.append(f"  - evidence: {info.get('evidence_snippet', '')[:180]}")
        else:
            lines.append(f"- **{rid}**: NOT FOUND in top-{TOP_K}")
    lines.extend(["", "## Top-k list", ""])
    for c in cand_dicts:
        lines.append(
            f"{c['rank']}. `{c['candidate_id']}` ({c['document']}) score={c['score']} "
            f"— {', '.join(c.get('matched_evidence') or [])[:80]}"
        )
    lines.extend(["", "## Top-5 false positives vs expected impacted", ""])
    for fp in eval_payload["top5_false_positives_vs_expected_impacted"]:
        lines.append(f"- rank {fp['rank']}: {fp['id']} ({fp['document']})")
    if not eval_payload["top5_false_positives_vs_expected_impacted"]:
        lines.append("- (none)")
    lines.extend(
        [
            "",
            "## Limits (lexical baseline)",
            "",
            "- Exact string/token overlap only; no embeddings.",
            "- Korean tokenization is naive regex; compounds may mismatch.",
            "- Req.105-in-topk alone is NOT Trial success (B3+ required later).",
            "",
        ]
    )
    (out_dir / "B1_B2_SMOKE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"index_meta": index_meta, "focus": eval_payload["focus_ranks"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
