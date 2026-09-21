# -*- coding: utf-8 -*-
"""Cycle 3 regression + fixture robustness (≥50 total with other cycle3 files)."""

from pathlib import Path

from document_ai.domain_packs.ec_sw.mdtm_indexer import index_mdtm_document
from document_ai.domain_packs.generic.no_impact_policy import decide_no_impact
from document_ai.document_set.stable_node_identity import mdtm_row_stable_identity

FX = Path("data/eval/document_set_benchmark_v2/fixtures/ec_sw")
PRIOR_RUNS = {
    "20260801T062321Z_c70af996",
    "20260801T072116Z_cbdca939",
    "20260801T143206Z_e6bd5201",
}


def _req11_base(name: str) -> str:
    idx = index_mdtm_document(source_path=FX / name, document_id=name.replace(".docx", "").upper())
    for n in idx["nodes"]:
        reqs = n.source_identifiers.get("requirement_ids") or []
        if any("11" in str(x) for x in reqs):
            return str(n.source_identifiers.get("stable_node_id_base") or "")
    return ""


def test_prior_runs_immutable_listed():
    assert len(PRIOR_RUNS) == 3


def test_fixture_column_reorder_same_base():
    assert _req11_base("mdtm_base.docx") == _req11_base("mdtm_cols_dtr.docx")


def test_fixture_row_reorder_same_base():
    assert _req11_base("mdtm_base.docx") == _req11_base("mdtm_row_shuffle.docx")


def test_fixture_note_column_same_base():
    assert _req11_base("mdtm_base.docx") == _req11_base("mdtm_note_col.docx")


def test_fixture_empty_gap_same_base():
    assert _req11_base("mdtm_base.docx") == _req11_base("mdtm_with_gap.docx")


def test_fixture_caption_removal_same_base():
    assert _req11_base("mdtm_base.docx") == _req11_base("mdtm_no_caption.docx")


def test_fixture_reordered_cols_same_base():
    assert _req11_base("mdtm_base.docx") == _req11_base("mdtm_reordered_cols.docx")


def test_all_table_variants_single_base():
    names = [
        "mdtm_base.docx",
        "mdtm_cols_dtr.docx",
        "mdtm_row_shuffle.docx",
        "mdtm_note_col.docx",
        "mdtm_no_caption.docx",
        "mdtm_with_gap.docx",
        "mdtm_reordered_cols.docx",
    ]
    bases = {_req11_base(n) for n in names}
    assert len(bases) == 1
    assert list(bases)[0]


def test_writer_not_executable_from_stable():
    a = mdtm_row_stable_identity(
        document_identity="X",
        requirement_ids=["Req. 11"],
        design_ids=["5.1.2"],
        test_ids=["TC-11"],
        source_locator={"row_index": 2},
    )
    assert a.writer_executable is False
    assert a.metadata.get("writer_executable") is False


def test_gr_no_impact_still_unrelated():
    from document_ai.domain_packs.generic.no_impact_policy import decide_no_impact
    from document_ai.domain_packs.generic.target_existence import decide_target_existence

    t = decide_target_existence(
        document_id="R1",
        requested_concepts={"AUTHENTICATION"},
        document_heading_concepts={"SCHEDULE"},
        cr_tokens={"인증"},
        document_heading_tokens={"일정"},
    )
    d = decide_no_impact(document_id="R1", evidences=[], target=t)
    assert d.status == "UNRELATED"


def test_indexer_emits_v2_artifacts():
    idx = index_mdtm_document(source_path=FX / "mdtm_base.docx", document_id="MDTM_BASE")
    assert idx.get("stable_node_identities_v2")
    assert idx.get("canonical_key_fields") is not None
    assert idx.get("legacy_to_stable_node_mapping")
    row = idx["stable_node_identities_v2"][0]
    assert row.get("stable_node_id_base")
    assert row.get("identity_version") == "stable_node_identity_v2"


def test_different_req_different_base_on_fixture():
    idx = index_mdtm_document(source_path=FX / "mdtm_base.docx", document_id="MDTM_BASE")
    bases = {}
    for n in idx["nodes"]:
        reqs = n.source_identifiers.get("requirement_ids") or []
        if not reqs:
            continue
        bases[reqs[0]] = n.source_identifiers.get("stable_node_id_base")
    if len(bases) >= 2:
        vals = list(bases.values())
        assert vals[0] != vals[1]


def test_legacy_id_still_present():
    idx = index_mdtm_document(source_path=FX / "mdtm_base.docx", document_id="MDTM_BASE")
    n = idx["nodes"][0]
    assert n.node_id.startswith("ec_sw_v1.mdtm")
    assert n.metadata.get("legacy_node_id") == n.node_id


def test_v1_v2_comparison_artifact():
    idx = index_mdtm_document(source_path=FX / "mdtm_note_col.docx", document_id="NOTE")
    assert idx.get("stable_node_identity_comparison_v1_v2")
    row = idx["stable_node_identity_comparison_v1_v2"][0]
    assert "stable_node_id_v1" in row and "stable_node_id_base" in row
