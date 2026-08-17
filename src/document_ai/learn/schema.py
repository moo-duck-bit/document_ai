from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from document_ai.learn.diff import diff_documents, extract_req_tables


def _rel(path: Path) -> str:
    from document_ai.paths import PROJECT_ROOT

    try:
        return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def export_schema_from_pair(
    template_id: str,
    blank_path: Path,
    filled_path: Path,
    out_path: Path | None = None,
) -> dict[str, Any]:
    diff = diff_documents(blank_path, filled_path)
    schema: dict[str, Any] = {
        "template_id": template_id,
        "format": "docx",
        "blank_path": _rel(blank_path),
        "filled_example_path": _rel(filled_path),
        "stats": {
            "field_count": len(diff["fields"]),
            "repeating_entity_count": len(diff["repeating_entities"]),
            "blank_blocks": diff["blank_blocks"],
            "filled_blocks": diff["filled_blocks"],
        },
        "fields": diff["fields"],
        "repeating_entities": diff["repeating_entities"],
    }

    if template_id == "spec_requirements":
        schema["requirements"] = extract_req_tables(filled_path)

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")

    return schema


def export_all_ec_sw_schemas(schemas_dir: Path) -> dict[str, Path]:
    from document_ai.paths import FILLED_PATHS, SCHEMAS_EC_SW, TEMPLATE_PATHS

    outputs: dict[str, Path] = {}
    pairs = [
        ("spec_requirements", TEMPLATE_PATHS["spec_requirements"], FILLED_PATHS["spec_requirements"]),
        ("spec_design", TEMPLATE_PATHS["spec_design"], FILLED_PATHS["spec_design"]),
    ]
    for template_id, blank, filled in pairs:
        if not blank.exists() or not filled.exists():
            raise FileNotFoundError(f"Missing pair for {template_id}: {blank} / {filled}")
        out = schemas_dir / f"{template_id}.schema.json"
        export_schema_from_pair(template_id, blank, filled, out)
        outputs[template_id] = out
    return outputs
