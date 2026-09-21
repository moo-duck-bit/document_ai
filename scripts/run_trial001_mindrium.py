# -*- coding: utf-8 -*-
"""Orchestrate Trial 1 (mindrium_xa / Req.6) without mutating source case or examples."""
from __future__ import annotations

import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from document_ai.harness.document_harness import DocumentHarness
from document_ai.impact.orchestrator import apply_change, compute_impact
from document_ai.intake.change_intake import draft_change_from_request, load_requirements_payload
from document_ai.impact.change import save_change
from document_ai.paths import PROJECT_ROOT
from document_ai.quality.runner import run_document_quality
from document_ai.trial.check_input import check_trial_input
from document_ai.trial.init import init_trial
from document_ai.trial.paths import rel_to_project, sha256_file, write_json, write_text
from document_ai.trial.review import prepare_trial_review

TRIAL_ID = "trial-001-mindrium-xa"
CASE = PROJECT_ROOT / "data" / "cases" / "mindrium_xa"
EXAMPLES = PROJECT_ROOT / "data" / "examples" / "ec_sw"
TRIAL = PROJECT_ROOT / "data" / "trials" / TRIAL_ID
WORKDIR_CASE = TRIAL / "workdir" / "case"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def file_hash(path: Path) -> str | None:
    return sha256_file(path) if path.exists() else None


def snapshot_sources() -> dict:
    docs = {
        "case/output_mdsr.docx": CASE / "output_mdsr.docx",
        "case/output_mddr.docx": CASE / "output_mddr.docx",
        "case/requirements.json": CASE / "requirements.json",
        "case/input.json": CASE / "input.json",
        "case/changes/request_req6.txt": CASE / "changes" / "request_req6.txt",
    }
    for p in EXAMPLES.glob("*.docx"):
        docs[f"examples/{p.name}"] = p
    return {k: {"path": str(v), "sha256": file_hash(v), "size": v.stat().st_size if v.exists() else None} for k, v in docs.items()}


def copy_reference() -> list[dict]:
    ref = TRIAL / "reference"
    ref.mkdir(parents=True, exist_ok=True)
    mapping = [
        ("spec_mdsr*.docx", "MDSR"),
        ("spec_mddr*.docx", "MDDR"),
        ("report_xxcs*.docx", "XXCS"),
    ]
    copied = []
    for pattern, kind in mapping:
        matches = sorted(EXAMPLES.glob(pattern))
        if not matches:
            raise FileNotFoundError(f"missing reference pattern {pattern} under {EXAMPLES}")
        src = matches[0]
        dst = ref / src.name
        shutil.copy2(src, dst)
        copied.append(
            {
                "kind": kind,
                "source": rel_to_project(src),
                "dest": rel_to_project(dst),
                "sha256": sha256_file(dst),
                "size": dst.stat().st_size,
            }
        )
    return copied


def write_versions(copied: list[dict]) -> Path:
    input_json = json.loads((CASE / "input.json").read_text(encoding="utf-8"))
    facts = input_json.get("facts") or {}
    lines = [
        "# VERSIONS — trial-001-mindrium-xa reference freeze",
        "",
        f"- frozen_at_utc: `{utc_now()}`",
        f"- trial_id: `{TRIAL_ID}`",
        f"- case: `data/cases/mindrium_xa`",
        f"- system_version: `v0.5-document-harness`",
        f"- system_commit: `d73fc18`",
        f"- product: `{facts.get('product_name', 'Mindrium')}` / `{facts.get('product_code', 'XA')}`",
        f"- document_version (input.json): `{facts.get('document_version', '')}`",
        f"- approval_date (input.json): `{facts.get('approval_date', '')}`",
        "",
        "## Reference documents (copied from data/examples/ec_sw; originals not modified)",
        "",
        "| kind | file | sha256 | bytes |",
        "|------|------|--------|-------|",
    ]
    for row in copied:
        lines.append(
            f"| {row['kind']} | `{Path(row['dest']).name}` | `{row['sha256']}` | {row['size']} |"
        )
    lines.extend(
        [
            "",
            "## Change scenario note",
            "",
            "- change input: prepared Req. 6 CR (`request_req6.txt`)",
            "- change nature: update/fill of empty MDSR table description for Req. 6 (not as-is numeric policy edit)",
            "- original body-text Req. 6 title is auth-error UX guidance; table description was empty",
            "- XXCS is reference-only for this trial (case has no output_xxcs.docx / security_tests.json)",
            "",
        ]
    )
    path = TRIAL / "reference" / "VERSIONS.md"
    write_text(path, "\n".join(lines))
    return path


def isolate_workdir() -> None:
    if WORKDIR_CASE.exists():
        shutil.rmtree(WORKDIR_CASE)
    ignore = shutil.ignore_patterns(
        "executions",
        "execution_reviews",
        "__pycache__",
        ".git",
        "platform",
        "memory",
        "output_mdsr_new.docx",
        "output_mdsr_v2.docx",
    )
    shutil.copytree(CASE, WORKDIR_CASE, ignore=ignore)


def main() -> int:
    log: dict = {
        "trial_id": TRIAL_ID,
        "started_at": utc_now(),
        "phase": "pre_human_review",
        "real_world_trial_complete": False,
        "human_review_complete": False,
        "notes": [
            "Mindrium real corpus + prepared Req. 6 CR",
            "update/fill of empty table description",
            "No Ground Truth / Human Revised generated in this run",
        ],
    }
    t0 = time.perf_counter()
    source_before = snapshot_sources()
    log["source_hashes_before"] = source_before

    # 7) trial-init (creates layout). reference/input filled after.
    init_result = init_trial(
        trial_id=TRIAL_ID,
        case=CASE,
        trial_type="change_update",
        system_version="v0.5-document-harness",
        system_commit="d73fc18",
        synthetic=False,
        force=True,
    )
    log["trial_init"] = {
        "ok": init_result.get("ok"),
        "trial_dir": init_result.get("trial_dir"),
        "document_types": init_result.get("manifest", {}).get("document_types"),
        "version_warnings": init_result.get("version_warnings"),
    }

    # 1-3) reference + VERSIONS
    copied_ref = copy_reference()
    versions_path = write_versions(copied_ref)
    log["reference"] = {"files": copied_ref, "versions_md": rel_to_project(versions_path)}

    # 4) input placement
    input_dir = TRIAL / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CASE / "input.json", input_dir / "input.json")
    shutil.copy2(CASE / "requirements.json", input_dir / "requirements.json")
    if (CASE / "design_content.json").exists():
        shutil.copy2(CASE / "design_content.json", input_dir / "design_content.json")
    shutil.copy2(CASE / "changes" / "request_req6.txt", input_dir / "change_request.txt")
    # optional structured change later from draft
    write_text(
        input_dir / "README_INPUTS.md",
        "# Trial 1 inputs (mindrium_xa)\n\n"
        "- `change_request.txt`: prepared Req. 6 CR (copied from case changes/request_req6.txt)\n"
        "- `input.json` / `requirements.json`: case facts snapshot for check-input\n"
        "- Do not place gold / human_revised finals here\n",
    )
    log["input_files"] = [rel_to_project(p) for p in sorted(input_dir.glob("*")) if p.is_file()]

    # 5-6) dry-run draft-change against SOURCE case (read-only parse)
    req_text = (CASE / "changes" / "request_req6.txt").read_text(encoding="utf-8")
    payload = load_requirements_payload(CASE)
    dry = draft_change_from_request(req_text, requirements_payload=payload)
    dry_ok = (
        dry["intake"]["confirmed"] is True
        and dry["intake"]["parsed_req_ids"] == ["Req. 6"]
        and bool(dry["requirement_changes"])
        and "계정 잠금" in dry["requirement_changes"][0]["description"]
    )
    log["draft_change_dry_run"] = {
        "ok": dry_ok,
        "parsed_req_ids": dry["intake"]["parsed_req_ids"],
        "confirmed": dry["intake"]["confirmed"],
        "confidence": dry["intake"]["confidence"],
        "clarifying_questions": dry["intake"]["clarifying_questions"],
        "description": dry["requirement_changes"][0]["description"] if dry["requirement_changes"] else None,
        "summary": dry.get("summary"),
    }
    write_json(TRIAL / "logs" / "draft_change_dry_run.json", {"change": dry})
    if not dry_ok:
        log["status"] = "aborted_dry_run_failed"
        write_json(TRIAL / "execution_report.json", log)
        print(json.dumps(log, ensure_ascii=False, indent=2))
        return 2

    # 8) trial-check-input
    check = check_trial_input(TRIAL)
    log["trial_check_input"] = {
        "ok": check.get("ok"),
        "findings": check.get("findings"),
        "warnings": check.get("warnings"),
        "data_leakage_clean": check.get("data_leakage_clean"),
    }
    if not check.get("ok"):
        log["status"] = "aborted_input_check_failed"
        write_json(TRIAL / "execution_report.json", log)
        print(json.dumps(log, ensure_ascii=False, indent=2))
        return 2

    # 9) isolate workdir + write change JSON only under workdir
    isolate_workdir()
    change = draft_change_from_request(
        (TRIAL / "input" / "change_request.txt").read_text(encoding="utf-8"),
        requirements_payload=load_requirements_payload(WORKDIR_CASE),
        summary="Req. 6 로그인 시도 제한 정책 기입(update/fill)",
    )
    change_path = WORKDIR_CASE / "changes" / f"{change['change_id']}.json"
    change_path.parent.mkdir(parents=True, exist_ok=True)
    save_change(change, change_path)
    # also keep a copy under trial input for audit (not applied to source)
    shutil.copy2(change_path, TRIAL / "input" / "change_request.json")
    log["change_json"] = {
        "workdir_path": rel_to_project(change_path),
        "input_copy": rel_to_project(TRIAL / "input" / "change_request.json"),
        "change_id": change["change_id"],
        "requirement_changes": change.get("requirement_changes"),
    }

    # 10) impact (workdir only)
    impact = compute_impact(WORKDIR_CASE, change)
    write_json(TRIAL / "logs" / "impact.json", impact)
    impact_docs = impact.get("impact", {}).get("documents", {})
    log["impact"] = {
        "change_id": impact.get("change_id"),
        "req_ids": impact.get("impact", {}).get("req_ids"),
        "security_ids": impact.get("impact", {}).get("security_ids"),
        "design_ids": impact.get("impact", {}).get("design_ids"),
        "documents": {
            k: {
                "req_ids": v.get("req_ids"),
                "security_req_ids": v.get("security_req_ids"),
                "design_ids": v.get("design_ids"),
            }
            for k, v in impact_docs.items()
        },
    }

    # 11) apply-change (workdir only)
    apply_started = time.perf_counter()
    apply_result = apply_change(WORKDIR_CASE, change_path, dry_run=False)
    apply_elapsed = round(time.perf_counter() - apply_started, 3)
    write_json(TRIAL / "logs" / "apply_change.json", apply_result)
    log["apply_change"] = {
        "elapsed_seconds": apply_elapsed,
        "patches": apply_result.get("patches"),
        "impact_req_ids": apply_result.get("impact", {}).get("req_ids"),
    }

    # 12) generate MDSR/MDDR inside workdir via harness (do NOT use trial-generate copy wipe)
    gen_started = time.perf_counter()
    harness = DocumentHarness(use_retrieval=True, materialize=True, force_form_fill=False)
    harness_report = harness.generate(WORKDIR_CASE, force_form_fill=False)
    gen_elapsed = round(time.perf_counter() - gen_started, 3)
    write_json(TRIAL / "logs" / "harness_generate.json", harness_report)

    quality_report = run_document_quality(
        WORKDIR_CASE,
        report_path=WORKDIR_CASE / "quality_report.md",
    )
    write_json(TRIAL / "logs" / "quality.json", quality_report)

    generated = TRIAL / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    outputs = {}
    for name, label in (("output_mdsr.docx", "MDSR"), ("output_mddr.docx", "MDDR"), ("output_xxcs.docx", "XXCS")):
        src = WORKDIR_CASE / name
        if src.exists():
            dst = generated / name
            shutil.copy2(src, dst)
            shutil.copy2(src, generated / f"generated_{label.lower()}.docx")
            outputs[label] = {
                "path": rel_to_project(dst),
                "sha256": sha256_file(dst),
                "size": dst.stat().st_size,
            }
    for report_name in ("quality_report.md", "validation_report.md", "validation_report.json", "e2e_validation_report.json"):
        src = WORKDIR_CASE / report_name
        if src.exists():
            shutil.copy2(src, generated / report_name)

    xxcs_in_scope = "XXCS" in (init_result.get("manifest", {}).get("document_types") or [])
    log["generation"] = {
        "elapsed_seconds": gen_elapsed,
        "harness_ok": harness_report.get("ok"),
        "harness_summary": {
            k: harness_report.get(k)
            for k in ("ok", "case_id", "outputs", "error", "errors")
            if k in harness_report
        },
        "quality": {
            "status": quality_report.get("status"),
            "scores": quality_report.get("scores"),
        },
        "outputs": outputs,
        "xxcs_in_generation_scope": xxcs_in_scope,
        "xxcs_note": (
            "XXCS not in trial document_types / case has no output_xxcs.docx or security_tests.json; "
            "reference XXCS copied for baseline only; not generated in this run"
            if not xxcs_in_scope or "XXCS" not in outputs
            else "XXCS generated"
        ),
    }

    source_after = snapshot_sources()
    source_preserved = True
    drift = []
    for key, before in source_before.items():
        after = source_after.get(key) or {}
        if before.get("sha256") != after.get("sha256"):
            source_preserved = False
            drift.append({"key": key, "before": before.get("sha256"), "after": after.get("sha256")})
    log["source_hashes_after"] = source_after
    log["source_preserved"] = source_preserved
    log["source_hash_drift"] = drift

    # generation_manifest compatible fields
    generation_manifest = {
        "trial_id": TRIAL_ID,
        "generated_at": utc_now(),
        "duration_seconds": gen_elapsed,
        "apply_seconds": apply_elapsed,
        "synthetic": False,
        "source_case_dir": rel_to_project(CASE),
        "work_case_dir": rel_to_project(WORKDIR_CASE),
        "change_path": rel_to_project(change_path),
        "source_case_output_hashes": {
            k: v.get("sha256") for k, v in source_after.items() if k.startswith("case/output_")
        },
        "outputs": {k: v["path"] for k, v in outputs.items()},
        "output_hashes": {k: v["sha256"] for k, v in outputs.items()},
        "harness": {"ok": harness_report.get("ok"), "skipped": False},
        "quality": log["generation"]["quality"],
        "xxcs_in_generation_scope": xxcs_in_scope,
        "overwrite_source_case": False,
        "commands": [
            "draft-change (workdir output only)",
            "impact --case workdir/case",
            "apply-change --case workdir/case",
            "DocumentHarness.generate(workdir/case)",
        ],
        "note": "trial-generate was not used after apply because it recopies source case and would wipe workdir patches",
    }
    write_json(TRIAL / "generation_manifest.json", generation_manifest)
    write_json(TRIAL / "metrics" / "generation_metrics.json", {
        "quality": generation_manifest["quality"],
        "duration_seconds": gen_elapsed,
        "apply_seconds": apply_elapsed,
        "outputs": generation_manifest["outputs"],
    })

    # Update trial manifest status
    manifest_path = TRIAL / "trial_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = "generated_pre_human_review"
    manifest["generated_at"] = generation_manifest["generated_at"]
    manifest["input_cutoff"] = utc_now()
    manifest["change_scenario"] = {
        "req_id": "Req. 6",
        "nature": "update_fill_empty_table_description",
        "prepared_cr": True,
        "change_request": "input/change_request.txt",
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # Prepare review package (templates only; no human_revised content)
    try:
        review = prepare_trial_review(TRIAL)
        log["prepare_review"] = {"ok": review.get("ok"), "review_dir": review.get("review_dir")}
    except Exception as exc:  # noqa: BLE001
        log["prepare_review"] = {"ok": False, "error": str(exc)}

    elapsed_total = round(time.perf_counter() - t0, 3)
    log["finished_at"] = utc_now()
    log["elapsed_seconds_total"] = elapsed_total
    log["status"] = "pre_human_review_ready" if source_preserved and harness_report.get("ok") else "pre_human_review_partial"
    log["next_human_review_paths"] = {
        "generated_mdsr": outputs.get("MDSR", {}).get("path"),
        "generated_mddr": outputs.get("MDDR", {}).get("path"),
        "review_dir": rel_to_project(TRIAL / "review"),
        "human_revision_template": rel_to_project(TRIAL / "review" / "human_revision_record.template.json"),
        "error_annotations_template": rel_to_project(TRIAL / "review" / "error_annotations.template.json")
        if (TRIAL / "review" / "error_annotations.template.json").exists()
        else rel_to_project(TRIAL / "review"),
        "change_request": rel_to_project(TRIAL / "input" / "change_request.txt"),
        "impact_log": rel_to_project(TRIAL / "logs" / "impact.json"),
        "apply_log": rel_to_project(TRIAL / "logs" / "apply_change.json"),
        "execution_report": rel_to_project(TRIAL / "execution_report.json"),
    }

    # Markdown report
    md = [
        "# Trial 1 Execution Report (Pre–Human Review)",
        "",
        f"- trial_id: `{TRIAL_ID}`",
        f"- case: `data/cases/mindrium_xa`",
        f"- system: `v0.5-document-harness` @ `d73fc18`",
        f"- status: `{log['status']}`",
        f"- real_world_trial_complete: `false` (Human Review not done)",
        f"- elapsed_seconds_total: `{elapsed_total}`",
        "",
        "## Presentation notes",
        "",
        "- Case documents are real Mindrium EC-SW corpus.",
        "- Change request is a **prepared Req. 6 CR**.",
        "- Original body-text Req. 6 is auth-error guidance; MDSR **table description was empty**.",
        "- This trial is an **update/fill** of the empty table description (not editing an existing numeric lock policy).",
        "- Purpose: baseline validation of harness change propagation.",
        "",
        "## Reference placement",
        "",
    ]
    for row in copied_ref:
        md.append(f"- {row['kind']}: `{row['dest']}` (`{row['sha256'][:12]}…`)")
    md.extend(["", f"See `{rel_to_project(versions_path)}`.", "", "## Dry-run", ""])
    md.append(f"- parsed_req_ids: `{log['draft_change_dry_run']['parsed_req_ids']}`")
    md.append(f"- confirmed: `{log['draft_change_dry_run']['confirmed']}`")
    md.append(f"- confidence: `{log['draft_change_dry_run']['confidence']}`")
    md.append(f"- ok: `{log['draft_change_dry_run']['ok']}`")
    md.extend(["", "## Input check / leakage", ""])
    md.append(f"- ok: `{log['trial_check_input']['ok']}`")
    md.append(f"- data_leakage_clean: `{log['trial_check_input']['data_leakage_clean']}`")
    md.append(f"- findings: `{log['trial_check_input']['findings']}`")
    md.append(f"- warnings: `{log['trial_check_input']['warnings']}`")
    md.extend(["", "## Impact", ""])
    md.append(f"- req_ids: `{log['impact'].get('req_ids')}`")
    md.append(f"- security_ids: `{log['impact'].get('security_ids')}`")
    md.append(f"- design_ids: `{log['impact'].get('design_ids')}`")
    md.append(f"- documents: `{json.dumps(log['impact'].get('documents'), ensure_ascii=False)}`")
    md.extend(["", "## Apply patches", ""])
    md.append(f"```json\n{json.dumps(log['apply_change'].get('patches'), ensure_ascii=False, indent=2)}\n```")
    md.extend(["", "## Generated documents", ""])
    for label, meta in outputs.items():
        md.append(f"- {label}: `{meta['path']}` sha256=`{meta['sha256']}`")
    if "XXCS" not in outputs:
        md.append(f"- XXCS: **not generated** — {log['generation']['xxcs_note']}")
    md.extend(["", "## Source preservation", ""])
    md.append(f"- source_preserved: `{source_preserved}`")
    if drift:
        md.append(f"- drift: `{drift}`")
    md.extend(["", "## Next Human Review paths", ""])
    for k, v in log["next_human_review_paths"].items():
        md.append(f"- {k}: `{v}`")
    write_text(TRIAL / "PRE_HUMAN_REVIEW_REPORT.md", "\n".join(md) + "\n")
    write_json(TRIAL / "execution_report.json", log)

    print(json.dumps({
        "status": log["status"],
        "source_preserved": source_preserved,
        "dry_run_ok": dry_ok,
        "check_ok": check.get("ok"),
        "harness_ok": harness_report.get("ok"),
        "outputs": list(outputs),
        "xxcs_generated": "XXCS" in outputs,
        "report": rel_to_project(TRIAL / "PRE_HUMAN_REVIEW_REPORT.md"),
        "elapsed_seconds_total": elapsed_total,
    }, ensure_ascii=False, indent=2))
    return 0 if source_preserved and dry_ok and check.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
