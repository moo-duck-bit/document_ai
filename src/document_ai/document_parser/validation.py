# -*- coding: utf-8 -*-
"""PR-20: Document structure validation (observational)."""

from __future__ import annotations

from collections import Counter
from typing import Any

from document_ai.document_parser.structure import DocumentModel, LocatorCandidate


def validate_document_structure(
    doc: DocumentModel,
    *,
    candidates: list[LocatorCandidate] | None = None,
) -> dict[str, Any]:
    """Validate hierarchy / headings / tree integrity. Does not mutate doc."""
    issues: list[str] = []
    warnings: list[str] = []

    by_id = {s.section_id: s for s in doc.sections}
    if len(by_id) != len(doc.sections):
        issues.append("duplicate_section_id")

    # Duplicate heading (same level + same text)
    heading_keys = [
        (s.heading_level, (s.heading or "").strip().lower())
        for s in doc.sections
        if (s.heading or "").strip() and s.heading_level > 0
    ]
    counts = Counter(heading_keys)
    for (level, text), n in sorted(counts.items()):
        if n > 1:
            issues.append(f"duplicate_heading:L{level}:{text}")

    # Empty heading
    for s in doc.sections:
        if s.heading_level > 0 and not (s.heading or "").strip():
            issues.append(f"empty_heading:{s.section_id}")

    # Invalid heading level
    for s in doc.sections:
        if s.heading_level < 0 or s.heading_level > 6:
            issues.append(f"invalid_heading_level:{s.section_id}:{s.heading_level}")

    # Parent references / broken tree
    for s in doc.sections:
        if s.parent is not None and s.parent not in by_id:
            issues.append(f"broken_tree:unknown_parent:{s.section_id}->{s.parent}")
        for cid in s.children:
            if cid not in by_id:
                issues.append(f"broken_tree:unknown_child:{s.section_id}->{cid}")
            elif by_id[cid].parent != s.section_id:
                issues.append(f"broken_tree:child_parent_mismatch:{cid}")

    # Parent cycle
    def _has_cycle(start: str) -> bool:
        seen: set[str] = set()
        cur: str | None = start
        while cur:
            if cur in seen:
                return True
            seen.add(cur)
            node = by_id.get(cur)
            if node is None:
                return False
            cur = node.parent
        return False

    for sid in by_id:
        if _has_cycle(sid):
            issues.append(f"parent_cycle:{sid}")
            break

    # Invalid hierarchy: child level must be > parent level (when both > 0)
    for s in doc.sections:
        if s.parent and s.parent in by_id:
            parent = by_id[s.parent]
            if parent.heading_level > 0 and s.heading_level > 0:
                if s.heading_level <= parent.heading_level:
                    issues.append(
                        f"invalid_hierarchy:{s.section_id}:level_{s.heading_level}"
                        f"_under_{parent.heading_level}"
                    )

    # Empty section (no content and no children) — warning unless root
    for s in doc.sections:
        if (
            s.heading_level > 0
            and not s.paragraphs
            and not s.tables
            and not s.lists
            and not s.children
        ):
            warnings.append(f"empty_section:{s.section_id}")

    if candidates is not None:
        for c in candidates:
            if c.section_id not in by_id:
                issues.append(f"candidate_unknown_section:{c.candidate_id}")
            if c.score < 0 or c.score > 1:
                issues.append(f"candidate_score_out_of_range:{c.candidate_id}")

    status = "INVALID" if issues else ("VALID_WITH_WARNINGS" if warnings else "VALID")
    return {
        "stage": "document_validation",
        "status": status,
        "issues": issues,
        "warnings": warnings,
        "invariants": {
            "no_duplicate_heading": not any(i.startswith("duplicate_heading") for i in issues),
            "valid_hierarchy": not any(i.startswith("invalid_hierarchy") for i in issues),
            "no_parent_cycle": not any(i.startswith("parent_cycle") for i in issues),
            "tree_intact": not any(i.startswith("broken_tree") for i in issues),
            "valid_heading_levels": not any(
                i.startswith("invalid_heading_level") for i in issues
            ),
            "no_empty_heading": not any(i.startswith("empty_heading") for i in issues),
            "observational_only": True,
            "no_semantic_matching": True,
            "no_llm": True,
            "no_docx_mutation": True,
        },
        "actual_docx_changed": False,
        "actual_generation_changed": False,
        "note": "PR-20 observational document structure validation.",
    }
