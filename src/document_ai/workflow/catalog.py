# -*- coding: utf-8 -*-
"""Document set catalogs for E2E workflow (uses DocumentDescriptor)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from document_ai.document_set.loader import load_document_set_registry
from document_ai.document_set.schema import DocumentDescriptor
from document_ai.template.generic_templates import (
    build_business_proposal_template,
    build_general_report_template,
)

REPO = Path(__file__).resolve().parents[3]

CATALOG: dict[str, dict[str, Any]] = {
    "ec_sw": {
        "document_set_id": "ec_sw",
        "display_name": "EC-SW (Mindrium)",
        "domain_pack_id": "ec_sw_v1",
        "description": "MDSR/MDDR + MDTM observational; registry-backed",
        "supports_upload_roles": ["requirements", "design", "traceability", "custom"],
        "analysis": "ec_sw_mdtm",
    },
    "general_report": {
        "document_set_id": "general_report",
        "display_name": "General Report",
        "domain_pack_id": "generic_report_v1",
        "template_id": "general_report_v1",
        "description": "Generic report template sections",
        "supports_upload_roles": ["general_report", "custom"],
        "analysis": "generic_template_sections",
    },
    "business_proposal": {
        "document_set_id": "business_proposal",
        "display_name": "Business Proposal",
        "domain_pack_id": "generic_proposal_v1",
        "template_id": "business_proposal_v1",
        "description": "Generic business proposal template sections",
        "supports_upload_roles": ["custom"],
        "analysis": "generic_template_sections",
    },
}


def list_document_sets() -> list[dict[str, Any]]:
    return [
        {
            "document_set_id": k,
            "display_name": v["display_name"],
            "description": v["description"],
            "domain_pack_id": v["domain_pack_id"],
        }
        for k, v in CATALOG.items()
    ]


def get_catalog(document_set: str) -> dict[str, Any]:
    if document_set not in CATALOG:
        raise KeyError(f"unknown_document_set:{document_set}")
    return CATALOG[document_set]


def descriptors_for_ec_sw() -> list[DocumentDescriptor]:
    loaded = load_document_set_registry()
    return list(loaded["descriptors"])


def template_section_descriptors(document_set: str) -> list[DocumentDescriptor]:
    """Logical descriptors from generic template (no file until upload)."""
    cat = get_catalog(document_set)
    if document_set == "general_report":
        tmpl = build_general_report_template()
    elif document_set == "business_proposal":
        tmpl = build_business_proposal_template()
    else:
        return descriptors_for_ec_sw()

    out: list[DocumentDescriptor] = []
    for i, sec in enumerate(tmpl.sections):
        out.append(
            DocumentDescriptor(
                document_id=f"{tmpl.template_id}.{sec.section_id}",
                short_id=sec.section_id,
                document_type=document_set.upper(),
                document_role="general_report" if document_set == "general_report" else "custom",
                source_path="",
                template_id=tmpl.template_id,
                domain_pack_id=str(cat["domain_pack_id"]),
                priority=i,
                enabled=True,
                metadata={
                    "section_id": sec.section_id,
                    "display_name": sec.display_name,
                    "logical": True,
                },
            )
        )
    return out
