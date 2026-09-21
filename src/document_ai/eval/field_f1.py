"""Flat golden_fields.jsonl evaluation — Field-level precision/recall/F1."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

DEFAULT_GOLDEN_PATH = Path("data/eval/golden_fields.jsonl")


def load_golden_fields_jsonl(path: Path | None = None) -> list[dict[str, Any]]:
    p = Path(path) if path else DEFAULT_GOLDEN_PATH
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rows.append(json.loads(line))
    return rows


def _normalize(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _get_nested(data: dict[str, Any], dotted: str) -> Any:
    cur: Any = data
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _load_case_json(case_dir: Path, filename: str) -> dict[str, Any] | None:
    path = case_dir / filename
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def extract_field_value(case_dir: Path, field_id: str) -> str | None:
    """Resolve field_id to a string from case artifacts.

    Supported prefixes:
      input.facts.*          — input.json facts
      input.*                — top-level input.json keys
      mdsr.*                 — mdsr_content.json
      requirements.{Req.N}.* — requirements.json requirement row
    """
    case_dir = case_dir.resolve()
    if field_id.startswith("input.facts."):
        payload = _load_case_json(case_dir, "input.json") or {}
        val = _get_nested(payload, field_id.replace("input.", "", 1))
        return _normalize(val) if val is not None else None

    if field_id.startswith("input."):
        payload = _load_case_json(case_dir, "input.json") or {}
        val = _get_nested(payload, field_id.replace("input.", "", 1))
        return _normalize(val) if val is not None else None

    if field_id.startswith("mdsr."):
        payload = _load_case_json(case_dir, "mdsr_content.json") or {}
        val = _get_nested(payload, field_id.replace("mdsr.", "", 1))
        if val is not None:
            return _normalize(val)
        return None

    if field_id.startswith("requirements."):
        # requirements.Req. 11.description
        payload = _load_case_json(case_dir, "requirements.json") or {}
        parts = field_id.split(".")
        if len(parts) < 3:
            return None
        req_key = ".".join(parts[1:-1])  # Req. 11
        attr = parts[-1]
        for row in payload.get("requirements", []):
            if _normalize(row.get("req_id")) == _normalize(req_key):
                val = row.get(attr)
                return _normalize(val) if val is not None else None
        return None

    return None


def _values_match(expected: str, actual: str, *, exact: bool = False) -> bool:
    exp = _normalize(expected)
    act = _normalize(actual)
    if not exp and not act:
        return True
    if exact:
        return exp == act
    if exp == act:
        return True
    return exp.lower() in act.lower() or act.lower() in exp.lower()


def score_field_row(
    case_dir: Path,
    row: dict[str, Any],
) -> dict[str, Any]:
    field_id = row["field_id"]
    expected = _normalize(row.get("expected_value", ""))
    actual_raw = extract_field_value(case_dir, field_id)
    actual = _normalize(actual_raw) if actual_raw is not None else ""
    exact = bool(row.get("exact_match", False))
    matched = _values_match(expected, actual, exact=exact) if expected else bool(actual)
    return {
        "case_id": row.get("case_id"),
        "field_id": field_id,
        "expected_value": expected,
        "actual_value": actual,
        "matched": matched,
        "missing_actual": actual_raw is None,
    }


def compute_field_f1(
    *,
    case_dir: Path | None = None,
    case_id: str | None = None,
    golden_path: Path | None = None,
    rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Macro Field F1 over golden rows (optionally filtered by case)."""
    all_rows = rows if rows is not None else load_golden_fields_jsonl(golden_path)
    if case_id:
        all_rows = [r for r in all_rows if r.get("case_id") == case_id]
    if not all_rows:
        return {
            "case_id": case_id,
            "field_count": 0,
            "matched_count": 0,
            "field_f1": 0.0,
            "field_precision": 0.0,
            "field_recall": 0.0,
            "fields": [],
            "warning": "no golden rows",
        }

    scored: list[dict[str, Any]] = []
    for row in all_rows:
        cid = row.get("case_id")
        if not case_dir and cid:
            from document_ai.paths import CASES

            cdir = CASES / cid
        else:
            cdir = case_dir
        if cdir is None:
            raise ValueError("case_dir required when rows lack resolvable case_id")
        scored.append(score_field_row(Path(cdir), row))

    tp = sum(1 for s in scored if s["matched"])
    fn = sum(1 for s in scored if not s["matched"])
    fp = sum(1 for s in scored if s["actual_value"] and not s["matched"])
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    return {
        "case_id": case_id or (scored[0]["case_id"] if scored else None),
        "field_count": len(scored),
        "matched_count": tp,
        "field_precision": round(precision, 4),
        "field_recall": round(recall, 4),
        "field_f1": round(f1, 4),
        "fields": scored,
    }


def bootstrap_golden_fields_jsonl_from_case(
    case_dir: Path,
    *,
    out_path: Path | None = None,
    include_requirements: bool = False,
    append: bool = False,
) -> list[dict[str, Any]]:
    """Build flat golden rows from input.json facts (+ optional Req.1)."""
    case_dir = case_dir.resolve()
    case_id = case_dir.name
    payload = json.loads((case_dir / "input.json").read_text(encoding="utf-8"))
    facts = payload.get("facts") or {}
    rows: list[dict[str, Any]] = []

    for key, value in facts.items():
        if value is None or str(value).strip() == "":
            continue
        rows.append(
            {
                "case_id": case_id,
                "field_id": f"input.facts.{key}",
                "expected_value": str(value),
                "exact_match": key in {"product_code", "model_name", "approval_date"},
                "source": "input.json",
            }
        )

    org = facts.get("author_org")
    mdsr_path = case_dir / "mdsr_content.json"
    if org and mdsr_path.exists():
        rows.append(
            {
                "case_id": case_id,
                "field_id": "mdsr.cover_product_line",
                "expected_value": str(org),
                "exact_match": False,
                "source": "mdsr_content.json",
            }
        )

    product = facts.get("product_name")
    if product and mdsr_path.exists():
        rows.append(
            {
                "case_id": case_id,
                "field_id": "mdsr.document_title",
                "expected_value": str(product),
                "exact_match": False,
                "source": "mdsr_content.json",
            }
        )

    if include_requirements:
        req_path = case_dir / "requirements.json"
        if req_path.exists():
            req_payload = json.loads(req_path.read_text(encoding="utf-8"))
            first = (req_payload.get("requirements") or [{}])[0]
            if first.get("req_id") and first.get("description"):
                rows.append(
                    {
                        "case_id": case_id,
                        "field_id": f"requirements.{first['req_id']}.description",
                        "expected_value": first["description"][:120],
                        "exact_match": False,
                        "source": "requirements.json",
                    }
                )

    out = out_path or DEFAULT_GOLDEN_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    if append and out.exists():
        existing = load_golden_fields_jsonl(out)
        # Drop prior rows for this case_id so re-bootstrap is idempotent
        existing = [r for r in existing if r.get("case_id") != case_id]
        merged = existing + rows
        write_golden_fields_jsonl(merged, out)
        return rows

    write_golden_fields_jsonl(rows, out)
    return rows


def write_golden_fields_jsonl(rows: list[dict[str, Any]], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path
