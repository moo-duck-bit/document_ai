from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from document_ai.learn.field_io import extract_schema_values
from document_ai.paths import FILLED_PATHS, SCHEMAS_EC_SW


def bootstrap_design_content_from_schema(schema: dict[str, Any]) -> dict[str, Any]:
    fields = {
        fld["field_id"]: fld["example_value"]
        for fld in schema.get("fields", [])
        if fld.get("example_value")
    }
    return {
        "source": "schema bootstrap",
        "template_id": schema.get("template_id", "spec_design"),
        "fields": fields,
    }


def extract_design_content(filled_path: Path, schema: dict[str, Any]) -> dict[str, Any]:
    fields = extract_schema_values(filled_path, schema)
    return {
        "source": str(filled_path),
        "template_id": schema.get("template_id", "spec_design"),
        "fields": fields,
    }


def save_case_design_content(data: dict[str, Any], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def load_case_design_content(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def default_design_schema() -> dict[str, Any]:
    schema_path = SCHEMAS_EC_SW / "spec_design.schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))


def default_filled_design_path() -> Path:
    return FILLED_PATHS["spec_design"]
