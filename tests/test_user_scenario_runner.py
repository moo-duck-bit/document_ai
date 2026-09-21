# -*- coding: utf-8 -*-
"""Regression + smoke tests for User Scenario Runner.

Must not mutate Trial 1/2 frozen artifacts.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from document_ai.impact.consistency_gate import check_consistency
from document_ai.impact.propagation import proposed_mdsr_description
from document_ai.impact.semantic_index import load_index_jsonl
from document_ai.scenario.runner import run_user_scenario

ROOT = Path(__file__).resolve().parents[1]
TRIAL2 = ROOT / "data" / "trials" / "trial-002-lockout-multireq"
TRIAL2_HASH_FILE = TRIAL2 / "execution_report.json"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@pytest.fixture(scope="module")
def frozen_hashes():
    if not TRIAL2_HASH_FILE.exists():
        pytest.skip("Trial 2 freeze missing")
    report = json.loads(TRIAL2_HASH_FILE.read_text(encoding="utf-8"))
    return report.get("canonical_evidence") or {}


def test_trial2_frozen_artifacts_unchanged(frozen_hashes):
    assert frozen_hashes, "expected canonical_evidence in Trial 2 execution_report"
    for rel, meta in frozen_hashes.items():
        path = TRIAL2 / rel
        assert path.exists(), rel
        assert _sha256(path) == meta["sha256"], f"hash drift: {rel}"


def test_refuse_frozen_trial_as_scenario():
    with pytest.raises(RuntimeError, match="frozen trial"):
        run_user_scenario(TRIAL2)


def test_proposed_patch_text_not_req_id_hardcoded():
    """Patch text must come from CR, not only Req.105/103 canned strings."""
    from document_ai.impact.consistency_gate import ConsistencyDecision

    cr = "연속 로그인 실패 시 계정을 잠그고 자동 해제한다."
    d = ConsistencyDecision(
        req_id="Req. 999",
        document="MDSR",
        status="CONSISTENT",
        reason="test",
        allow_auto_patch=True,
        fields={"description": "기존 설명입니다."},
    )
    text = proposed_mdsr_description(d, cr)
    assert text is not None
    assert "변경 요청 반영" in text
    assert "계정" in text or "잠금" in text or "로그인" in text


def test_conflict_disallows_auto_patch_text(frozen_hashes):
    idx = TRIAL2 / "retrieval" / "lexical_baseline" / "index_all.jsonl"
    if not idx.exists():
        pytest.skip("index missing")
    blocks = load_index_jsonl(idx)
    cr = (TRIAL2 / "input" / "change_request.txt").read_text(encoding="utf-8")
    b6 = next(b for b in blocks if b.req_id == "Req. 6" and b.document_type == "MDSR")
    d = check_consistency(cr, b6, b3_judgment="IMPACTED")
    assert d.status == "CONFLICT"
    assert proposed_mdsr_description(d, cr) is None


def test_runner_smoke_tmp_scenario(tmp_path: Path, frozen_hashes):
    """Copy Mindrium refs + Trial2 CR into tmp scenario; run without expected_impact."""
    ref_mdsr = next((TRIAL2 / "reference").glob("*MDSR*.docx"))
    ref_mddr = next((TRIAL2 / "reference").glob("*MDDR*.docx"))
    cr_src = TRIAL2 / "input" / "change_request.txt"
    assert ref_mdsr.exists() and ref_mddr.exists()

    scenario = tmp_path / "scenario-smoke"
    (scenario / "input" / "reference").mkdir(parents=True)
    shutil.copy2(ref_mdsr, scenario / "input" / "reference" / "MDSR.docx")
    shutil.copy2(ref_mddr, scenario / "input" / "reference" / "MDDR.docx")
    shutil.copy2(cr_src, scenario / "input" / "change_request.txt")

    before_mdsr = _sha256(scenario / "input" / "reference" / "MDSR.docx")
    before_mddr = _sha256(scenario / "input" / "reference" / "MDDR.docx")

    report = run_user_scenario(scenario, top_k=10)

    assert str(report["status"]).startswith("COMPLETED")
    assert report["expected_impact_used"] is False
    assert report["target_req_ids_injected"] is False
    assert report["input_hashes_unchanged"] is True
    assert _sha256(scenario / "input" / "reference" / "MDSR.docx") == before_mdsr
    assert _sha256(scenario / "input" / "reference" / "MDDR.docx") == before_mddr

    out = scenario / "output"
    assert (out / "documents" / "updated_MDSR.docx").exists()
    assert (out / "documents" / "updated_MDDR.docx").exists()
    assert (out / "trace" / "retrieval_candidates.json").exists()
    assert (out / "trace" / "impact_judgments.json").exists()
    assert (out / "trace" / "consistency_decisions.json").exists()
    assert (out / "trace" / "propagation_trace.json").exists()
    assert (out / "review" / "CHANGE_SUMMARY.md").exists()
    assert (out / "review" / "REVIEW_REQUIRED.md").exists()
    assert (out / "review" / "PATCH_DIFF.md").exists()
    assert (out / "execution_report.json").exists()

    # Conflict on Req.6 should appear in consistency; that Req must not be in mdsr patched
    cons = json.loads((out / "trace" / "consistency_decisions.json").read_text(encoding="utf-8"))
    d6 = next((d for d in cons["decisions"] if d["req_id"] == "Req. 6"), None)
    assert d6 is not None
    assert d6["status"] == "CONFLICT"
    patched = report["summaries"]["mdsr_patched_req_ids"] or []
    assert "Req. 6" not in patched

    # Trial 2 freeze still intact after smoke
    for rel, meta in frozen_hashes.items():
        assert _sha256(TRIAL2 / rel) == meta["sha256"]
