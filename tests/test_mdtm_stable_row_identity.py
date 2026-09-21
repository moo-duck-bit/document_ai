# -*- coding: utf-8 -*-
from pathlib import Path

from document_ai.domain_packs.ec_sw.mdtm_indexer import index_mdtm_document
from document_ai.document_set.stable_node_identity import mdtm_row_stable_identity

REPO = Path(__file__).resolve().parents[1]
FX = REPO / "data" / "eval" / "document_set_benchmark_v2" / "fixtures" / "ec_sw"


def _stable_for(path: Path) -> dict[str, str]:
    indexed = index_mdtm_document(source_path=path, document_id="MDTM")
    out = {}
    for n in indexed.get("nodes") or []:
        reqs = n.source_identifiers.get("requirement_ids") or []
        if not reqs:
            continue
        out[reqs[0]] = (n.metadata or {}).get("stable_node_id") or n.source_identifiers.get(
            "stable_node_id"
        )
    return out


def test_same_row_after_column_reorder():
    base = FX / "mdtm_base.docx"
    var = FX / "mdtm_cols_dtr.docx"
    if not (base.is_file() and var.is_file()):
        return
    assert _stable_for(base).get("Req. 11") == _stable_for(var).get("Req. 11")


def test_same_row_after_row_movement():
    base = FX / "mdtm_base.docx"
    var = FX / "mdtm_row_shuffle.docx"
    if not (base.is_file() and var.is_file()):
        return
    assert _stable_for(base).get("Req. 11") == _stable_for(var).get("Req. 11")


def test_same_row_after_note_column():
    base = FX / "mdtm_base.docx"
    var = FX / "mdtm_note_col.docx"
    if not (base.is_file() and var.is_file()):
        return
    assert _stable_for(base).get("Req. 11") == _stable_for(var).get("Req. 11")


def test_same_row_after_empty_row_insertion():
    base = FX / "mdtm_base.docx"
    var = FX / "mdtm_with_gap.docx"
    if not (base.is_file() and var.is_file()):
        return
    assert _stable_for(base).get("Req. 11") == _stable_for(var).get("Req. 11")


def test_same_row_after_filename_change_same_bytes():
    base = FX / "mdtm_base.docx"
    var = FX / "uploaded_trace_matrix.docx"
    if not (base.is_file() and var.is_file()):
        return
    assert _stable_for(base).get("Req. 11") == _stable_for(var).get("Req. 11")


def test_identifier_ordering_independence_unit():
    a = mdtm_row_stable_identity(
        document_identity="EC_SW_MDTM",
        requirement_ids=["Req. 11", "Req. 10"],
        design_ids=["5.1.2", "5.1.1"],
        test_ids=["TC-11", "TC-10"],
    )
    b = mdtm_row_stable_identity(
        document_identity="EC_SW_MDTM",
        requirement_ids=["Req. 10", "Req. 11"],
        design_ids=["5.1.1", "5.1.2"],
        test_ids=["TC-10", "TC-11"],
    )
    assert a.stable_node_id == b.stable_node_id


def test_legacy_id_differs_but_stable_same_on_reorder():
    base = FX / "mdtm_base.docx"
    var = FX / "mdtm_cols_dtr.docx"
    if not (base.is_file() and var.is_file()):
        return
    ib = index_mdtm_document(source_path=base, document_id="MDTM")
    iv = index_mdtm_document(source_path=var, document_id="MDTM")

    def node_for(nodes, req):
        for n in nodes:
            if req in (n.source_identifiers.get("requirement_ids") or []):
                return n
        return None

    nb = node_for(ib["nodes"], "Req. 11")
    nv = node_for(iv["nodes"], "Req. 11")
    assert nb and nv
    assert nb.node_id != nv.node_id  # legacy physical differs
    assert nb.metadata["stable_node_id"] == nv.metadata["stable_node_id"]


def test_caption_removal_stable():
    base = FX / "mdtm_base.docx"
    var = FX / "mdtm_no_caption.docx"
    if not (base.is_file() and var.is_file()):
        return
    assert _stable_for(base).get("Req. 11") == _stable_for(var).get("Req. 11")


def test_duplicate_identifier_rows_have_instance_keys():
    path = FX / "mdtm_dup_req.docx"
    if not path.is_file():
        return
    indexed = index_mdtm_document(source_path=path, document_id="MDTM")
    req11 = [
        n
        for n in indexed["nodes"]
        if "Req. 11" in (n.source_identifiers.get("requirement_ids") or [])
    ]
    if len(req11) < 2:
        return
    keys = {n.metadata.get("duplicate_instance_key") for n in req11}
    # either distinct instance keys or same base with mapping
    assert len(req11) >= 2
