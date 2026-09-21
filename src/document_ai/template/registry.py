# -*- coding: utf-8 -*-
"""PR-18: Template registry."""

from __future__ import annotations

from typing import Any

from document_ai.template.schema import TemplateDefinition, TemplateNode, VALID_OPERATIONS


class TemplateRegistry:
    def __init__(self) -> None:
        self._templates: dict[str, TemplateDefinition] = {}
        self._nodes: dict[str, TemplateNode] = {}

    def register_template(self, template: TemplateDefinition) -> None:
        if template.template_id in self._templates:
            raise ValueError(f"duplicate_template_id:{template.template_id}")
        for op in template.allowed_operations:
            if op not in VALID_OPERATIONS:
                raise ValueError(f"invalid_operation:{op}")
        for sec in template.sections:
            for fld in sec.fields:
                for op in fld.allowed_operations:
                    if op not in VALID_OPERATIONS:
                        raise ValueError(f"invalid_operation:{op}")
        self._templates[template.template_id] = template

    def register_node(self, node: TemplateNode) -> None:
        if node.template_node_id in self._nodes:
            raise ValueError(f"duplicate_template_node_id:{node.template_node_id}")
        if node.template_id not in self._templates:
            raise ValueError(f"unknown_template:{node.template_id}")
        self._nodes[node.template_node_id] = node

    def get_template(self, template_id: str) -> TemplateDefinition | None:
        return self._templates.get(template_id)

    def list_templates(self) -> list[TemplateDefinition]:
        return [self._templates[k] for k in sorted(self._templates.keys())]

    def get_templates_by_document_type(self, document_type: str) -> list[TemplateDefinition]:
        return [
            t
            for t in self.list_templates()
            if t.document_type == document_type
        ]

    def list_nodes(self) -> list[TemplateNode]:
        return [self._nodes[k] for k in sorted(self._nodes.keys())]

    def get_node(self, template_node_id: str) -> TemplateNode | None:
        return self._nodes.get(template_node_id)

    def to_registry_payload(self) -> dict[str, Any]:
        return {
            "stage": "template_registry",
            "schema_version": "template_schema_v1",
            "template_count": len(self._templates),
            "templates": [t.to_dict() for t in self.list_templates()],
            "note": "PR-18 observational template registry.",
        }

    def validate_registry(self) -> dict[str, Any]:
        issues: list[str] = []
        warnings: list[str] = []
        # unique ids already enforced on register; re-check
        tids = [t.template_id for t in self.list_templates()]
        if len(tids) != len(set(tids)):
            issues.append("duplicate_template_ids")
        nids = [n.template_node_id for n in self.list_nodes()]
        if len(nids) != len(set(nids)):
            issues.append("duplicate_template_node_ids")

        # parent refs among sections
        for t in self.list_templates():
            sec_ids = {s.section_id for s in t.sections}
            for s in t.sections:
                if s.parent_section_id and s.parent_section_id not in sec_ids:
                    issues.append(f"{t.template_id}:unknown_parent:{s.parent_section_id}")
            # cycle detection on sections
            children: dict[str, list[str]] = {s.section_id: [] for s in t.sections}
            for s in t.sections:
                if s.parent_section_id and s.parent_section_id in children:
                    children[s.parent_section_id].append(s.section_id)

            def _has_cycle(start: str, seen: set[str]) -> bool:
                if start in seen:
                    return True
                seen.add(start)
                for ch in children.get(start, []):
                    if _has_cycle(ch, set(seen)):
                        return True
                return False

            for sid in children:
                if _has_cycle(sid, set()):
                    issues.append(f"{t.template_id}:parent_cycle:{sid}")
                    break

            for s in t.sections:
                if s.required and not s.fields and s.section_type == "requirement":
                    warnings.append(f"{t.template_id}:{s.section_id}:required_no_fields")

        for n in self.list_nodes():
            if n.parent_node_id and n.parent_node_id not in self._nodes:
                # parent may be a section logical id not registered as node — warn only if looks like node id
                if n.parent_node_id.startswith(n.template_id + "."):
                    issues.append(f"{n.template_node_id}:unknown_parent_node")

        status = "INVALID" if issues else ("VALID_WITH_WARNINGS" if warnings else "VALID")
        return {
            "stage": "template_registry_validation",
            "status": status,
            "issues": issues,
            "warnings": warnings,
        }
