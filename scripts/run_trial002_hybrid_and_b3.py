# -*- coding: utf-8 -*-
"""Trial 2: Hybrid retrieval comparison + B3 impact judgment.

- Does NOT overwrite lexical_baseline/
- Does NOT use expected_impact during retrieval/judgment
- Does NOT run B4/B5 patch
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from document_ai.impact.impact_judgment import judge_candidates
from document_ai.impact.semantic_hybrid_retrieve import (
    find_rank,
    rank_by_method,
    score_all_methods,
)
from document_ai.impact.semantic_index import load_index_jsonl

TRIAL = Path("data/trials/trial-002-lockout-multireq")
TOP_K = 15
FOCUS = (
    ("Req. 105", "MDSR"),
    ("Req. 105", "MDDR"),
    ("Req. 103", "MDSR"),
    ("Req. 103", "MDDR"),
    ("Req. 6", "MDSR"),
    ("Req. 6", "MDDR"),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def posthoc_focus(ranked: list, method: str) -> dict:
    out = {"method": method, "by_doc": {}, "best": {}}
    for rid, doc in FOCUS:
        info = find_rank(ranked, rid, doc)
        out["by_doc"][f"{rid}|{doc}"] = info
    for rid in ("Req. 6", "Req. 103", "Req. 105"):
        out["best"][rid] = find_rank(ranked, rid, None)
    return out


def posthoc_fp(ranked: list, expected_impacted: set[str]) -> list[dict]:
    fps = []
    for h in ranked:
        if h.rank <= 5 and h.candidate_id not in expected_impacted:
            fps.append(
                {
                    "rank": h.rank,
                    "id": h.candidate_id,
                    "document": h.document,
                    "lexical_score": h.lexical_score,
                    "semantic_score": h.semantic_score,
                    "hybrid_score": h.hybrid_score,
                }
            )
    return fps


def main() -> None:
    # Prefer frozen baseline index copy; fall back to parent retrieval index
    baseline_idx = TRIAL / "retrieval" / "lexical_baseline" / "index_all.jsonl"
    parent_idx = TRIAL / "retrieval" / "index_all.jsonl"
    idx_path = baseline_idx if baseline_idx.exists() else parent_idx
    if not idx_path.exists():
        raise SystemExit(f"Missing index: {idx_path}")

    cr_path = TRIAL / "input" / "change_request.txt"
    cr_text = cr_path.read_text(encoding="utf-8").strip()
    for banned in ("Req. 6", "Req. 103", "Req. 105", "Req.6", "Req.103", "Req.105"):
        if banned in cr_text:
            raise SystemExit(f"CR must not contain Exact-ID {banned!r}")

    blocks = load_index_jsonl(idx_path)
    scored = score_all_methods(cr_text, blocks)

    hybrid_dir = TRIAL / "retrieval" / "hybrid"
    hybrid_dir.mkdir(parents=True, exist_ok=True)

    methods = {}
    for method in ("lexical", "semantic", "hybrid"):
        ranked = rank_by_method(scored, method, top_k=TOP_K)  # type: ignore[arg-type]
        methods[method] = ranked

    # expected only for posthoc
    expected = json.loads((TRIAL / "expected" / "expected_impact.json").read_text(encoding="utf-8"))
    expected_impacted = {
        r["req_id"]
        for r in expected.get("requirements", [])
        if r.get("expected_judgment") == "impacted"
    }

    comparison = {
        "created_at": utc_now(),
        "trial_id": "trial-002-lockout-multireq",
        "stage": "hybrid_retrieval_compare",
        "index_path": str(idx_path).replace("\\", "/"),
        "change_request_path": str(cr_path).replace("\\", "/"),
        "expected_impact_used_in_retrieval": False,
        "top_k": TOP_K,
        "semantic_channel": "tfidf_cosine",
        "hybrid_weights": {"lexical": 0.4, "semantic": 0.6},
        "note": "lexical_baseline/ left untouched; this is a separate artifact",
        "methods": {},
    }

    for method, ranked in methods.items():
        comparison["methods"][method] = {
            "candidates": [h.to_dict() for h in ranked],
            "focus": posthoc_focus(ranked, method),
            "top5_false_positives_vs_expected_impacted": posthoc_fp(ranked, expected_impacted),
        }

    # Compact rank table for MDSR Req.105 etc.
    rank_table = []
    for rid, doc in FOCUS:
        row = {"req_id": rid, "document": doc}
        for method, ranked in methods.items():
            info = find_rank(ranked, rid, doc)
            row[f"{method}_rank"] = info.get("rank") if info.get("found") else None
            row[f"{method}_lex"] = info.get("lexical_score") if info.get("found") else None
            row[f"{method}_sem"] = info.get("semantic_score") if info.get("found") else None
            row[f"{method}_hybrid"] = info.get("hybrid_score") if info.get("found") else None
        rank_table.append(row)
    comparison["focus_rank_table"] = rank_table

    (hybrid_dir / "comparison.json").write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for method, ranked in methods.items():
        (hybrid_dir / f"candidates_{method}.json").write_text(
            json.dumps(
                {
                    "method": method,
                    "top_k": TOP_K,
                    "expected_impact_used_in_retrieval": False,
                    "candidates": [h.to_dict() for h in ranked],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    # Markdown compare
    lines = [
        "# Hybrid Retrieval Comparison",
        "",
        f"- created_at: `{utc_now()}`",
        "- lexical_baseline: preserved under `retrieval/lexical_baseline/`",
        "- expected_impact_used_in_retrieval: `false`",
        "- semantic channel: TF-IDF cosine (project embedding backend; no neural model dep)",
        "",
        "## Focus ranks by document (document-aware)",
        "",
        "| Req | Doc | lexical | semantic | hybrid |",
        "|-----|-----|--------:|---------:|-------:|",
    ]
    for row in rank_table:
        lines.append(
            f"| {row['req_id']} | {row['document']} | {row['lexical_rank']} | "
            f"{row['semantic_rank']} | {row['hybrid_rank']} |"
        )
    lines.extend(["", "## Top-5 FP vs expected impacted", ""])
    for method in ("lexical", "semantic", "hybrid"):
        fps = comparison["methods"][method]["top5_false_positives_vs_expected_impacted"]
        lines.append(f"### {method}")
        if not fps:
            lines.append("- (none)")
        for fp in fps:
            lines.append(f"- rank {fp['rank']}: {fp['id']} ({fp['document']})")
        lines.append("")
    (hybrid_dir / "COMPARISON.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # B3 on hybrid top-k (and ensure both MDSR/MDDR 105 if in scored pool with hybrid score)
    hybrid_ranked = methods["hybrid"]
    decisions = judge_candidates(cr_text, blocks, hybrid_ranked)

    # Also judge MDSR Req.105 / focus docs if missing from top-k but present in index
    judged_keys = {(d.candidate_id, d.document) for d in decisions}
    from document_ai.impact.impact_judgment import judge_block
    from document_ai.impact.semantic_hybrid_retrieve import ScoredHit

    scored_by_key = {(h.candidate_id, h.document): h for h in scored}
    for rid, doc in FOCUS:
        if (rid, doc) in judged_keys:
            continue
        hit = scored_by_key.get((rid, doc))
        block = next((b for b in blocks if b.req_id == rid and b.document_type == doc), None)
        if not hit or not block:
            continue
        # force-include for judgment completeness of focus set (still not using expected for scoring)
        decisions.append(
            judge_block(
                cr_text,
                block,
                lexical_score=hit.lexical_score,
                semantic_score=hit.semantic_score,
                retrieval_rank=None,
            )
        )

    judgment_dir = TRIAL / "validation" / "impact_judgment"
    judgment_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_at": utc_now(),
        "stage": "B3_impact_judgment",
        "source_retrieval": "hybrid top_k (+ focus complements if absent from top_k)",
        "expected_impact_used_in_judgment": False,
        "rule": "theme overlap + lex/sem scores; same Req ID alone is insufficient",
        "decisions": [d.to_dict() for d in decisions],
        "summary": {
            "IMPACTED": sum(1 for d in decisions if d.judgment == "IMPACTED"),
            "NOT_IMPACTED": sum(1 for d in decisions if d.judgment == "NOT_IMPACTED"),
            "UNCERTAIN": sum(1 for d in decisions if d.judgment == "UNCERTAIN"),
        },
    }
    (judgment_dir / "decisions.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    jlines = [
        "# B3 Impact Judgment",
        "",
        f"- created_at: `{utc_now()}`",
        "- patch: not executed",
        "- expected_impact_used_in_judgment: `false`",
        "",
        f"Summary: {payload['summary']}",
        "",
        "| ID | Doc | Judgment | Rank | Reason (short) |",
        "|----|-----|----------|-----:|----------------|",
    ]
    for d in decisions:
        reason_short = d.reason[:100].replace("|", "/")
        jlines.append(
            f"| {d.candidate_id} | {d.document} | **{d.judgment}** | "
            f"{d.retrieval_rank if d.retrieval_rank is not None else '-'} | {reason_short} |"
        )
    (judgment_dir / "DECISIONS.md").write_text("\n".join(jlines) + "\n", encoding="utf-8")

    # freeze note
    freeze = TRIAL / "retrieval" / "lexical_baseline" / "FREEZE.md"
    freeze.write_text(
        "\n".join(
            [
                "# Lexical baseline FREEZE",
                "",
                "These files are the B1–B2 lexical baseline evidence.",
                "Do not overwrite. Hybrid/B3 outputs live under `retrieval/hybrid/` and `validation/impact_judgment/`.",
                f"",
                f"frozen_at: `{utc_now()}`",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "hybrid_dir": str(hybrid_dir).replace("\\", "/"),
                "judgment_dir": str(judgment_dir).replace("\\", "/"),
                "focus_rank_table": rank_table,
                "b3_summary": payload["summary"],
                "b3_focus": [
                    {
                        "id": d.candidate_id,
                        "doc": d.document,
                        "judgment": d.judgment,
                    }
                    for d in decisions
                    if d.candidate_id in {"Req. 6", "Req. 103", "Req. 105", "Req. 101"}
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
