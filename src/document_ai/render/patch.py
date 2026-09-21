from __future__ import annotations

from pathlib import Path
from typing import Any

from docx.document import Document

from document_ai.learn.req_ids import normalize_requirement_id as normalize_req_id
from document_ai.learn.docx_io import load_document
from document_ai.render.requirements import _fill_req_table_full, _req_id_from_table
from document_ai.render.xxcs import apply_security_tests


def patch_mdsr_requirements(doc: Document, requirement_changes: list[dict[str, Any]]) -> list[str]:
    by_id: dict[str, dict[str, Any]] = {}
    for item in requirement_changes:
        req_id = normalize_req_id(item.get("req_id", ""))
        if req_id:
            by_id[req_id] = item

    patched: list[str] = []
    for table in doc.tables:
        req_id = _req_id_from_table(table)
        if not req_id or req_id not in by_id:
            continue
        if _fill_req_table_full(table, by_id[req_id], overwrite=True):
            patched.append(req_id)
    return patched


def patch_xxcs_security_tests(
    doc: Document,
    tests: list[dict[str, Any]],
    security_req_ids: list[str],
) -> dict[str, Any]:
    allowed = {
        normalize_req_id(rid) or rid
        for rid in security_req_ids
    }
    filtered = []
    for test in tests:
        rid = normalize_req_id(test.get("req_id", "")) or test.get("req_id")
        if rid in allowed:
            filtered.append({**test, "req_id": rid})
    stats = apply_security_tests(doc, filtered, overwrite=True)
    stats["security_req_ids_requested"] = list(security_req_ids)
    stats["security_req_ids_patched"] = sorted(
        {test["req_id"] for test in filtered if test.get("req_id") in allowed}
    )
    return stats


def patch_document_file(
    doc_path: Path,
    patch_fn,
    *args,
    **kwargs,
) -> Any:
    doc = load_document(doc_path)
    result = patch_fn(doc, *args, **kwargs)
    doc.save(str(doc_path))
    return result
