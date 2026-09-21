# -*- coding: utf-8 -*-
from document_ai.document_set.node_reconciliation import reconcile_node_candidates


def _cand(nid, *, base="", reqs=None, status="PATCH_CANDIDATE", score=10.0):
    return {
        "node_id": nid,
        "status": status,
        "document_id": "MDTM",
        "metadata": {
            "stable_node_id_base": base,
            "stable_node_id": base or nid,
            "row_requirement_ids": reqs or [],
            "row_design_ids": [],
            "row_test_ids": [],
            "final_score": score,
            "table_index": 0,
            "row_index": int(nid[-1]) if nid[-1].isdigit() else 0,
        },
    }


def test_legacy_stable_merge():
    out = reconcile_node_candidates(
        [
            _cand("L1", base="stablev2.table_row.aaa", reqs=["Req. 11"], score=20),
            _cand("L2", base="stablev2.table_row.aaa", reqs=["Req. 11"], score=15),
        ]
    )
    assert out["n_reconciled"] == 1
    assert out["candidates"][0]["reconciliation_status"] in {
        "STABLE_RECONCILED",
        "EXACT_RECONCILED",
    }
    assert set(out["candidates"][0]["legacy_node_ids"]) == {"L1", "L2"}


def test_stable_physical_merge():
    out = reconcile_node_candidates(
        [
            _cand("P1", base="B1", reqs=["Req. 10"]),
            _cand("P2", base="B1", reqs=["Req. 10"]),
        ]
    )
    assert out["n_reconciled"] == 1
    assert len(out["candidates"][0]["physical_node_ids"]) == 2


def test_different_identifier_sets_not_merged():
    out = reconcile_node_candidates(
        [
            _cand("A", base="B_A", reqs=["Req. 11"]),
            _cand("B", base="B_B", reqs=["Req. 10"]),
        ]
    )
    assert out["n_reconciled"] == 2


def test_provenance_retained():
    out = reconcile_node_candidates(
        [_cand("L1", base="BX", reqs=["Req. 11"]), _cand("L2", base="BX", reqs=["Req. 11"])]
    )
    ev = out["candidates"][0]["evidence"]
    assert len(ev) == 2
    assert all(e.get("provenance_node_id") for e in ev)


def test_conflict_status_on_identifier_mismatch_same_base_key():
    # Forced same base but different reqs — still one group by base; conflict flagged
    a = _cand("L1", base="SAME", reqs=["Req. 11"])
    b = _cand("L2", base="SAME", reqs=["Req. 99"])
    out = reconcile_node_candidates([a, b])
    assert out["n_reconciled"] == 1
    assert out["candidates"][0]["reconciliation_status"] == "CONFLICTED"
    assert out["conflicts"]


def test_template_alignment_merge():
    c1 = _cand("N1", base="T1", reqs=["Req. 1"])
    c1["metadata"]["template_node_id"] = "tpl.section.a"
    c2 = _cand("N2", base="T1", reqs=["Req. 1"])
    c2["metadata"]["template_node_id"] = "tpl.section.a"
    out = reconcile_node_candidates([c1, c2])
    assert "tpl.section.a" in out["candidates"][0]["template_node_ids"]


def test_writer_not_executable_on_reconciled():
    out = reconcile_node_candidates([_cand("L1", base="B", reqs=["Req. 1"])])
    assert out["candidates"][0]["metadata"]["writer_executable"] is False


def test_annotates_candidates():
    c = _cand("L1", base="B9", reqs=["Req. 1"])
    reconcile_node_candidates([c])
    assert c["metadata"].get("reconciled_candidate_id")
    assert c["metadata"].get("reconciliation_status")
