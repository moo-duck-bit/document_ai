# -*- coding: utf-8 -*-
"""Template Abstraction Layer + Generic Document Template Pack — package exports."""

from document_ai.template.adapters import (
    build_mdsr_template,
    build_mddr_template,
    map_artifacts_to_template_nodes,
)
from document_ai.template.generic_mapping import (
    map_generic_sample_changes,
    run_generic_document_template_pack,
)
from document_ai.template.generic_templates import (
    build_business_proposal_template,
    build_general_report_template,
    build_static_nodes_for_template,
    make_generic_node_id,
)
from document_ai.template.inventory import (
    build_template_inventory,
    build_template_summary,
    run_template_abstraction_layer,
)
from document_ai.template.registry import TemplateRegistry
from document_ai.template.sample_documents import list_sample_documents
from document_ai.template.schema import (
    FieldDefinition,
    LocatorHints,
    OperationPolicy,
    SectionDefinition,
    TemplateDefinition,
    TemplateNode,
)
from document_ai.template.validation import validate_template_layer

__all__ = [
    "FieldDefinition",
    "LocatorHints",
    "OperationPolicy",
    "SectionDefinition",
    "TemplateDefinition",
    "TemplateNode",
    "TemplateRegistry",
    "build_mdsr_template",
    "build_mddr_template",
    "map_artifacts_to_template_nodes",
    "build_template_inventory",
    "build_template_summary",
    "run_template_abstraction_layer",
    "validate_template_layer",
    "build_general_report_template",
    "build_business_proposal_template",
    "build_static_nodes_for_template",
    "make_generic_node_id",
    "list_sample_documents",
    "map_generic_sample_changes",
    "run_generic_document_template_pack",
]
