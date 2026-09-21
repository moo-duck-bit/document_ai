# -*- coding: utf-8 -*-
"""Adapt document_set_registry.json into descriptors for EC-SW pack."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from document_ai.document_set.loader import load_document_set_registry
from document_ai.document_set.schema import DocumentDescriptor


def load_ec_sw_descriptors(
    registry_path: Path | None = None,
    *,
    enabled_only: bool = False,
) -> dict[str, Any]:
    return load_document_set_registry(registry_path, enabled_only=enabled_only)


def get_mdtm_descriptor(descriptors: list[DocumentDescriptor]) -> DocumentDescriptor | None:
    for d in descriptors:
        if d.short_id == "matrix_mdtm" or d.document_type == "MDTM":
            return d
    return None
