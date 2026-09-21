"""Bootstrap approved case outputs into the independent gold dataset."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from document_ai.eval.gold_dataset import (
    gold_fields_path,
    gold_mddr_path,
    gold_mdsr_path,
    gold_root,
    gold_xxcs_path,
    upsert_manifest_case,
)
from document_ai.eval.gold_fields import build_gold_fields, save_gold_fields


def bootstrap_gold_from_case(
    case_dir: Path,
    *,
    case_id: str | None = None,
    split: str = "train",
    approve: bool = False,
    root: str | Path | None = None,
    include_xxcs: bool | None = None,
) -> dict[str, Any]:
    """Copy case outputs into data/gold and write gold_fields.json.

    Does not modify generation pipeline outputs beyond reading them.
    Approval elevates status from provisional → human_approved.
    """
    case_dir = case_dir.resolve()
    resolved_id = case_id or case_dir.name
    input_path = case_dir / "input.json"
    payload = json.loads(input_path.read_text(encoding="utf-8")) if input_path.exists() else {}
    domain = payload.get("domain", "")
    product_name = payload.get("product_name") or (payload.get("facts") or {}).get("product_name", "")

    src_mdsr = case_dir / "output_mdsr.docx"
    src_mddr = case_dir / "output_mddr.docx"
    src_xxcs = case_dir / "output_xxcs.docx"

    if not src_mdsr.exists() and not src_mddr.exists():
        raise FileNotFoundError(f"No output_mdsr.docx / output_mddr.docx in {case_dir}")

    root_path = gold_root(root)
    for sub in ("mdsr", "mddr", "xxcs", "fields"):
        (root_path / sub).mkdir(parents=True, exist_ok=True)

    # Auto-include XXCS when present unless explicitly disabled
    if include_xxcs is None:
        include_xxcs = src_xxcs.exists()

    copied: dict[str, str] = {}
    dst_mdsr = gold_mdsr_path(resolved_id, root)
    dst_mddr = gold_mddr_path(resolved_id, root)
    if src_mdsr.exists():
        shutil.copy2(src_mdsr, dst_mdsr)
        copied["mdsr"] = str(dst_mdsr)
    if src_mddr.exists():
        shutil.copy2(src_mddr, dst_mddr)
        copied["mddr"] = str(dst_mddr)
    if include_xxcs and src_xxcs.exists():
        dst_xxcs = gold_xxcs_path(resolved_id, root)
        shutil.copy2(src_xxcs, dst_xxcs)
        copied["xxcs"] = str(dst_xxcs)

    status = "human_approved" if approve else "provisional"
    fields = build_gold_fields(
        case_id=resolved_id,
        mdsr_path=dst_mdsr if dst_mdsr.exists() else None,
        mddr_path=dst_mddr if dst_mddr.exists() else None,
        product_name=product_name,
        domain=domain,
        source="case_output_bootstrap",
        approval_status=status,
    )
    fields_path = gold_fields_path(resolved_id, root)
    save_gold_fields(fields, fields_path)
    copied["fields"] = str(fields_path)

    entry = upsert_manifest_case(
        resolved_id,
        split=split,
        domain=domain,
        product_name=product_name or fields.get("product_name", ""),
        status=status,
        case_dir=str(case_dir),
        notes="Bootstrapped from case outputs; treat provisional until human-approved.",
        root=root,
    )

    return {
        "case_id": resolved_id,
        "split": split,
        "status": status,
        "copied": copied,
        "manifest_entry": entry,
        "gold_fields_summary": {
            "requirement_count": len(fields.get("requirement_ids") or []),
            "design_count": len(fields.get("design_ids") or []),
            "traceability_count": len(fields.get("traceability_rows") or []),
            "product_name": fields.get("product_name"),
        },
    }
