from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from document_ai.impact.graph import normalize_req_id
from document_ai.learn.req_ids import normalize_requirement_id, requirement_sort_key


def load_change(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "requirement_changes" not in data:
        raise ValueError("change file must include requirement_changes[]")
    return data


def save_change(data: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def changed_req_ids(change: dict[str, Any]) -> list[str]:
    req_ids: list[str] = []
    for item in change.get("requirement_changes", []):
        normalized = normalize_requirement_id(item.get("req_id", ""))
        if normalized and normalized not in req_ids:
            req_ids.append(normalized)
    return req_ids


def merge_requirement_changes(requirements_payload: dict[str, Any], change: dict[str, Any]) -> list[str]:
    by_id = {row["req_id"]: row for row in requirements_payload.get("requirements", [])}
    updated: list[str] = []

    for item in change.get("requirement_changes", []):
        req_id = normalize_requirement_id(item.get("req_id", ""))
        if not req_id:
            continue
        description = item.get("description")
        if req_id in by_id:
            if description is not None:
                by_id[req_id]["description"] = description
        else:
            by_id[req_id] = {"req_id": req_id, "description": description or ""}
        updated.append(req_id)

    requirements_payload["requirements"] = sorted(by_id.values(), key=lambda r: requirement_sort_key(r["req_id"]))
    return updated


def design_changes_for_patch(change: dict[str, Any], design_index: Any) -> list[dict[str, Any]]:
    sync = change.get("sync_design_from_requirement", True)
    changes: list[dict[str, Any]] = []

    for item in change.get("requirement_changes", []):
        req_id = normalize_requirement_id(item.get("req_id", ""))
        if not req_id or not design_index.has(req_id):
            continue

        design_description = item.get("design_description")
        if design_description is None and sync:
            design_description = item.get("description")

        fields = item.get("fields") or item.get("design_fields") or {}
        if design_description is None and not fields:
            continue

        changes.append(
            {
                "req_id": req_id,
                "design_description": design_description,
                "fields": fields,
            }
        )
    return changes


def merge_design_item_changes(design_payload: dict[str, Any], design_changes: list[dict[str, Any]]) -> list[str]:
    by_id = {item["req_id"]: item for item in design_payload.get("items", [])}
    updated: list[str] = []

    for change in design_changes:
        req_id = normalize_requirement_id(change.get("req_id", ""))
        if not req_id:
            continue
        item = by_id.get(req_id, {"req_id": req_id, "block_kind": "unknown", "fields": {}})
        if change.get("design_description") is not None:
            item["design_description"] = change["design_description"]
        if change.get("fields"):
            item["fields"] = {**item.get("fields", {}), **change["fields"]}
        by_id[req_id] = item
        updated.append(req_id)

    design_payload["items"] = sorted(by_id.values(), key=lambda item: requirement_sort_key(item["req_id"]))
    return updated
