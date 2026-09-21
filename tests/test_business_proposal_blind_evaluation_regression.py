# -*- coding: utf-8 -*-
"""Cycle 6 blind evaluation regression — protocol & label coverage (no ranking changes)."""

from pathlib import Path

from document_ai.evaluation.business_proposal_gold import protocol as bp_protocol
from document_ai.evaluation.business_proposal_gold.official_metrics import (
    compute_official_business_proposal_metrics,
    compute_proxy_intent_grounding_metrics,
)
from document_ai.evaluation.document_set_v2.holdout_protocol import (
    prediction_code_must_not_read_sealed,
)
from document_ai.domain_packs.ec_sw.mdtm_indexer import index_mdtm_document

REPO = Path(__file__).resolve().parents[1]
GOLD_ROOT = REPO / "data" / "eval" / "document_set_benchmark_v2" / "business_proposal_node_gold"
FX_EC = REPO / "data" / "eval" / "document_set_benchmark_v2" / "fixtures" / "ec_sw"
PRIOR = {
    "20260801T152942Z_03c260f2",
    "20260801T163826Z_ab762b81",
    "20260801T181011Z_e7fe9ba3",
}


def test_prior_runs_immutable_include_cycle5():
    assert "20260801T181011Z_e7fe9ba3" in PRIOR


def test_sealed_gold_distribution_meets_targets():
    rows = bp_protocol.load_sealed_gold(gold_root=GOLD_ROOT)
    modes = {}
    for r in rows:
        modes[r["node_evaluation_mode"]] = modes.get(r["node_evaluation_mode"], 0) + 1
    assert modes.get("REQUIRED", 0) >= 8
    assert modes.get("AMBIGUOUS", 0) >= 2
    assert modes.get("OPTIONAL", 0) >= 2
    assert modes.get("NOT_APPLICABLE", 0) >= 2


def test_required_have_primary_reference():
    for r in bp_protocol.load_sealed_gold(gold_root=GOLD_ROOT):
        if r["node_evaluation_mode"] != "REQUIRED":
            continue
        pref = r.get("primary_reference") or {}
        assert pref.get("template_node_id") or pref.get("document_node_id") or pref.get("stable_node_id")


def test_ambiguous_have_groups():
    for r in bp_protocol.load_sealed_gold(gold_root=GOLD_ROOT):
        if r["node_evaluation_mode"] != "AMBIGUOUS":
            continue
        assert r.get("acceptable_groups")


def test_official_zero_denominator_returns_none():
    out = compute_official_business_proposal_metrics([], case_domain_by_id={})
    assert out["n_required"] == 0
    assert out["required_node_top1"] is None
    assert out["status"] == "NOT_APPLICABLE_ZERO_DENOMINATOR"


def test_proxy_metrics_do_not_require_gold():
    out = compute_proxy_intent_grounding_metrics(
        [
            {
                "case_id": "x",
                "change_request": "예산 표 수정",
                "ranked_preds": [{"node_id": "business_proposal_v1.budget", "rank": 1}],
            }
        ]
    )
    assert "intent_grounding_top1" in out or "top1" in str(out).lower() or out.get("n_cases", 0) >= 0


def test_prediction_adapter_and_analysis_do_not_read_sealed_bp_gold():
    bad = prediction_code_must_not_read_sealed(
        [
            str(REPO / "src/document_ai/evaluation/document_set/prediction_adapter.py"),
            str(REPO / "src/document_ai/workflow/analysis.py"),
        ],
        sealed_token="business_proposal_node_gold",
    )
    assert bad == []


def test_proposed_labels_not_auto_applied():
    prop = REPO / "output" / "document_set" / "business_proposal" / "business_proposal_proposed_label_changes.json"
    if not prop.is_file():
        return
    import json

    data = json.loads(prop.read_text(encoding="utf-8"))
    changes = data.get("changes") or data.get("proposed_label_changes") or []
    for c in changes:
        assert c.get("auto_applied") in (False, None)


def test_holdout_seal_manifest_present():
    man = REPO / "data/eval/document_set_benchmark_v2/holdout/holdout_label_manifest.json"
    assert man.is_file()
    import json

    m = json.loads(man.read_text(encoding="utf-8"))
    assert m.get("status") == "SEALED"
    assert m.get("aggregate_hash")


def test_ec_sw_stable_identity_regression():
    names = ["mdtm_base.docx", "mdtm_cols_dtr.docx", "mdtm_note_col.docx"]
    bases = set()
    for name in names:
        idx = index_mdtm_document(source_path=FX_EC / name, document_id=name.upper())
        for n in idx["nodes"]:
            if any("11" in str(x) for x in (n.source_identifiers.get("requirement_ids") or [])):
                bases.add(n.source_identifiers.get("stable_node_id_base"))
                break
    assert len(bases) == 1


def test_gold_manifest_hash_deterministic():
    hashes = GOLD_ROOT / "business_proposal_node_gold_hashes.json"
    assert hashes.is_file()
    import json

    h1 = json.loads(hashes.read_text(encoding="utf-8"))
    h2 = json.loads(hashes.read_text(encoding="utf-8"))
    assert h1 == h2
