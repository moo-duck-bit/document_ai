# -*- coding: utf-8 -*-
"""PR-20 Document Structure Mapping Engine — package exports."""

from document_ai.document_parser.docx_parser import parse_docx_file
from document_ai.document_parser.locator_candidates import build_locator_candidates
from document_ai.document_parser.markdown_parser import parse_markdown_file, parse_markdown_text
from document_ai.document_parser.normalization import (
    build_section_tree,
    document_from_object,
    normalize_document,
)
from document_ai.document_parser.parser import (
    SAMPLE_MARKDOWN_PROPOSAL,
    SAMPLE_MARKDOWN_REPORT,
    map_document_structure,
    run_document_structure_mapping_engine,
)
from document_ai.document_parser.structure import (
    DocumentModel,
    ListModel,
    LocatorCandidate,
    ParagraphModel,
    SectionModel,
    TableModel,
)
from document_ai.document_parser.validation import validate_document_structure

__all__ = [
    "DocumentModel",
    "SectionModel",
    "ParagraphModel",
    "TableModel",
    "ListModel",
    "LocatorCandidate",
    "parse_markdown_text",
    "parse_markdown_file",
    "parse_docx_file",
    "document_from_object",
    "normalize_document",
    "build_section_tree",
    "build_locator_candidates",
    "validate_document_structure",
    "map_document_structure",
    "run_document_structure_mapping_engine",
    "SAMPLE_MARKDOWN_REPORT",
    "SAMPLE_MARKDOWN_PROPOSAL",
]
