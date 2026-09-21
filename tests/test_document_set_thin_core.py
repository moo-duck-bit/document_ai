# -*- coding: utf-8 -*-
"""Tests for Thin Generic Document Set Core."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from document_ai.document_set.domain_pack import DomainPack, DomainPackRegistry
from document_ai.document_set.loader import load_document_set_registry
from document_ai.document_set.registry import build_default_pack_registry
from document_ai.document_set.schema import DocumentDescriptor, DocumentNode
from document_ai.document_set.validation import validate_descriptors, validate_nodes

REPO = Path(__file__).resolve().parents[1]
REGISTRY = REPO / "data" / "examples" / "ec_sw" / "document_set_registry.json"
DESKTOP_MDTM = Path.home() / "Desktop" / "EC-SW-MDTM(XA) 추적성 매트릭스.docx"


def test_registry_load_ok():
    loaded = load_document_set_registry(REGISTRY)
    assert loaded["validation"]["ok"] is True
    assert len(loaded["descriptors"]) == 8


def test_descriptor_deterministic_ordering():
    a = load_document_set_registry(REGISTRY)["descriptors"]
    b = load_document_set_registry(REGISTRY)["descriptors"]
    assert [d.short_id for d in a] == [d.short_id for d in b]
    priorities = [d.priority for d in a]
    assert priorities == sorted(priorities)


def test_missing_file_validation(tmp_path: Path):
    d = DocumentDescriptor(
        document_id="X",
        short_id="missing_doc",
        document_type="X",
        document_role="custom",
        source_path=str(tmp_path / "nope.docx"),
    )
    v = validate_descriptors([d])
    assert v["ok"] is False
    assert "missing_doc" in v["missing_files"]


def test_duplicate_short_id_validation():
    p = load_document_set_registry(REGISTRY)["descriptors"][0].source_path
    d1 = DocumentDescriptor("A", "dup", "A", "custom", p)
    d2 = DocumentDescriptor("B", "dup", "B", "custom", p)
    v = validate_descriptors([d1, d2])
    assert "duplicate_short_id" in v["issues"]


def test_domain_pack_selection():
    reg = build_default_pack_registry()
    assert "ec_sw_v1" in reg.list_pack_ids()
    loaded = load_document_set_registry(REGISTRY)
    mdtm = next(d for d in loaded["descriptors"] if d.short_id == "matrix_mdtm")
    pack = reg.select_for(mdtm)
    assert pack is not None
    assert pack.pack_id == "ec_sw_v1"
    assert pack.can_handle(mdtm)


def test_unsupported_document_graceful():
    class EmptyPack(DomainPack):
        pack_id = "empty"
        supported_document_types = frozenset()
        supported_short_ids = frozenset()

        def can_handle(self, descriptor: DocumentDescriptor) -> bool:
            return False

        def index_document(self, descriptor: DocumentDescriptor) -> list[DocumentNode]:
            return []

    reg = DomainPackRegistry()
    reg.register(EmptyPack())
    d = DocumentDescriptor("Z", "z", "Z", "custom", "x.docx")
    assert reg.select_for(d) is None


def test_document_node_unique_ids():
    nodes = [
        DocumentNode("n1", "MDTM", "MDTM", "traceability", "TABLE_ROW", "a"),
        DocumentNode("n2", "MDTM", "MDTM", "traceability", "TABLE_ROW", "b"),
    ]
    assert validate_nodes(nodes, document_id="MDTM")["ok"] is True


def test_duplicate_node_id_detected():
    nodes = [
        DocumentNode("n1", "MDTM", "MDTM", "traceability", "TABLE_ROW", "a"),
        DocumentNode("n1", "MDTM", "MDTM", "traceability", "TABLE_ROW", "b"),
    ]
    assert validate_nodes(nodes)["ok"] is False


def test_mdtm_path_exists_in_examples():
    loaded = load_document_set_registry(REGISTRY)
    mdtm = next(d for d in loaded["descriptors"] if d.short_id == "matrix_mdtm")
    assert Path(mdtm.source_path).is_file()
    assert "data/examples/ec_sw" in mdtm.source_path.replace("\\", "/")


def test_desktop_original_not_used_as_source_of_truth():
    loaded = load_document_set_registry(REGISTRY)
    mdtm = next(d for d in loaded["descriptors"] if d.short_id == "matrix_mdtm")
    assert "data/examples/ec_sw" in mdtm.source_path.replace("\\", "/")
    # Desktop may exist but must not be the registry path
    if DESKTOP_MDTM.exists():
        assert Path(mdtm.source_path).resolve() != DESKTOP_MDTM.resolve()


def test_registry_json_roundtrip_fields():
    raw = json.loads(REGISTRY.read_text(encoding="utf-8"))
    shorts = {d["short_id"] for d in raw["documents"]}
    assert "matrix_mdtm" in shorts
    assert "spec_mdsr" in shorts
