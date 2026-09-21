from __future__ import annotations



import argparse

import json

import sys

from pathlib import Path

from typing import Any



from document_ai.learn.extract_design import (
    bootstrap_design_content_from_schema,
    default_design_schema,
    default_filled_design_path,
    extract_design_content,
    save_case_design_content,
)
from document_ai.learn.extract_design_items import extract_design_items_docx, save_design_items
from document_ai.learn.import_srs import import_srs_markdown, save_srs_payload

from document_ai.learn.extract_requirements import extract_requirements_docx, save_case_requirements

from document_ai.learn.extract_security_tests import extract_security_tests_docx, save_security_tests

from document_ai.learn.schema import export_all_ec_sw_schemas

from document_ai.paths import CASES, FILLED_PATHS, PROJECT_ROOT, SCHEMAS_EC_SW, TEMPLATES_EC_SW

from document_ai.render.fill import create_xxcs_skeleton, fill_from_facts

from document_ai.render.xxcs import fill_xxcs_report

from document_ai.harness.document_harness import DocumentHarness
from document_ai.agents.orchestrator import run_change_pipeline
from document_ai.quality.runner import run_document_quality
from document_ai.validation.runner import run_document_validation
from document_ai.harness.intake_chat import parse_intake_text, save_intake_draft
from document_ai.eval.harness_benchmark import merge_into_platform_benchmark, run_harness_benchmark
from document_ai.eval.real_project_runner import run_project_e2e_validation
from document_ai.eval.ablation_runner import run_ablation_suite, tnr_from_scorecard_file
from document_ai.eval.bootstrap_gold import bootstrap_gold_from_case
from document_ai.eval.field_f1 import bootstrap_golden_fields_jsonl_from_case, compute_field_f1
from document_ai.eval.rq3_experiment import run_rq3_experiment
from document_ai.orchestrator.document_agent import run_document_agent
from document_ai.eval.human_review_package import prepare_review_package, summarize_human_evaluation
from document_ai.eval.runner import run_evaluation
from document_ai.evaluation.document_set.dataset_loader import DatasetValidationError
from document_ai.evaluation.document_set.evaluator import run_benchmark
from document_ai.impact.orchestrator import apply_change, compute_impact

from document_ai.intake.change_intake import (
    append_intake_log,
    draft_change_from_request,
    load_requirements_payload,
)
from document_ai.impact.change import save_change
from document_ai.platform.cli import (
    cmd_platform_benchmark,
    cmd_platform_improve,
    cmd_platform_ops_analyze,
    cmd_platform_plan,
    cmd_platform_run,
)
from document_ai.trial import (
    analyze_trial,
    check_trial_input,
    freeze_baseline,
    generate_trial,
    init_trial,
    prepare_trial_review,
    summarize_trial,
)
from document_ai.trial.dataset import ensure_dataset_manifest, load_dataset_manifest, validate_dataset_manifest
from document_ai.trial.models import BASELINE_COMMIT, BASELINE_SYSTEM_VERSION



TEMPLATE_FILES = {

    "spec_requirements": "template_mdsr.docx",

    "spec_design": "template_mddr.docx",

    "report_security_verification": "template_xxcs_skeleton.docx",

}



DEFAULT_OUTPUTS = {

    "spec_requirements": "output_mdsr.docx",

    "spec_design": "output_mddr.docx",

    "report_security_verification": "output_xxcs.docx",

}



CASE_PAYLOAD_FILES = {

    "spec_requirements": "requirements.json",

    "spec_design": "design_content.json",

    "report_security_verification": "security_tests.json",

}





def _case_facts(payload: dict) -> dict:

    facts = dict(payload.get("facts", {}))

    if payload.get("standards"):

        facts["standards"] = payload["standards"]

    if payload.get("free_text_hints"):

        facts["free_text_hints"] = payload["free_text_hints"]

    return facts





def cmd_export_schema(_: argparse.Namespace) -> int:

    paths = export_all_ec_sw_schemas(SCHEMAS_EC_SW)

    for tid, p in paths.items():

        print(f"exported {tid} -> {p.relative_to(PROJECT_ROOT)}")

    return 0





def cmd_xxcs_skeleton(args: argparse.Namespace) -> int:

    filled = Path(args.filled) if args.filled else FILLED_PATHS["report_security_verification"]

    out = Path(args.output) if args.output else TEMPLATES_EC_SW / "template_xxcs_skeleton.docx"

    result = create_xxcs_skeleton(filled, out)

    print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0





def cmd_extract_requirements(args: argparse.Namespace) -> int:

    filled = Path(args.from_doc) if args.from_doc else FILLED_PATHS["spec_requirements"]

    out = Path(args.output) if args.output else Path(args.case) / "requirements.json"

    data = extract_requirements_docx(filled)

    save_case_requirements(data, out)

    print(

        json.dumps(

            {

                "output": str(out),

                "requirements": len(data["requirements"]),

                "with_description": sum(1 for r in data["requirements"] if r["description"]),

                "traceability_rows": len(data["traceability"]),

            },

            ensure_ascii=False,

            indent=2,

        )

    )

    return 0





def cmd_extract_design(args: argparse.Namespace) -> int:
    schema = default_design_schema()
    out = Path(args.output) if args.output else Path(args.case) / "design_content.json"
    if args.from_schema:
        data = bootstrap_design_content_from_schema(schema)
    else:
        filled = Path(args.from_doc) if args.from_doc else default_filled_design_path()
        data = extract_design_content(filled, schema)
    save_case_design_content(data, out)

    print(

        json.dumps(

            {

                "output": str(out),

                "fields": len(data["fields"]),

            },

            ensure_ascii=False,

            indent=2,

        )

    )

    return 0


def cmd_extract_design_items(args: argparse.Namespace) -> int:
    filled = Path(args.from_doc) if args.from_doc else FILLED_PATHS["spec_design"]
    out = Path(args.output) if args.output else Path(args.case) / "design_items.json"
    data = extract_design_items_docx(filled)
    save_design_items(data, out)
    with_description = sum(1 for item in data["items"] if item.get("design_description"))
    print(
        json.dumps(
            {
                "output": str(out),
                "items": len(data["items"]),
                "with_design_description": with_description,
                "sample_req_ids": [item["req_id"] for item in data["items"][:5]],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_import_srs(args: argparse.Namespace) -> int:
    case_dir = Path(args.case)
    source = Path(args.from_md) if args.from_md else case_dir / "source_srs.md"
    if not source.exists():
        print(f"Missing {source}", file=sys.stderr)
        return 1
    out = Path(args.output) if args.output else case_dir / "requirements.json"
    data = import_srs_markdown(source, case_id=case_dir.name)
    save_srs_payload(data, out)
    print(
        json.dumps(
            {
                "output": str(out),
                "requirements": len(data["requirements"]),
                "traceability": len(data["traceability"]),
                "document_set": data.get("document_set"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_extract_security_tests(args: argparse.Namespace) -> int:

    filled = Path(args.from_doc) if args.from_doc else FILLED_PATHS["report_security_verification"]

    out = Path(args.output) if args.output else Path(args.case) / "security_tests.json"

    data = extract_security_tests_docx(filled)

    save_security_tests(data, out)

    print(

        json.dumps(

            {

                "output": str(out),

                "tests": len(data["tests"]),

                "with_results": sum(1 for t in data["tests"] if t.get("test_result") or t.get("applied")),

            },

            ensure_ascii=False,

            indent=2,

        )

    )

    return 0


def cmd_import_security_results(args: argparse.Namespace) -> int:
    from document_ai.form_fill.security_execution import (
        SecurityExecutionImportError,
        import_security_results,
    )

    case_dir = Path(args.case)
    results_path = Path(args.results)
    try:
        summary = import_security_results(case_dir, results_path, accept=not args.no_accept)
    except SecurityExecutionImportError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def cmd_run_security_tests(args: argparse.Namespace) -> int:
    from document_ai.security_runner.executor import run_security_tests
    from document_ai.security_runner.policy import SecurityRunnerConfigError

    case_dir = Path(args.case)
    config_path = Path(args.config)
    output_path = Path(args.output)
    try:
        summary = run_security_tests(
            case_dir,
            config_path,
            output_path=output_path,
            selected_check=args.check,
            timeout=args.timeout,
            execution_id=args.execution_id,
            synthetic=bool(args.synthetic),
            no_network=bool(args.no_network),
            dry_run=bool(args.dry_run),
        )
    except (SecurityRunnerConfigError, FileNotFoundError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=True, indent=2))
        return 1
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    return 0


def cmd_prepare_security_review(args: argparse.Namespace) -> int:
    from document_ai.form_fill.security_execution_review import (
        SecurityReviewError,
        ensure_plan_gold_layout,
        prepare_security_review_package,
    )

    case_dir = Path(args.case)
    out_dir = Path(args.out) if args.out else None
    try:
        ensure_plan_gold_layout(case_dir.name)
        summary = prepare_security_review_package(
            case_dir,
            args.execution_id,
            out_dir=out_dir,
        )
    except SecurityReviewError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def cmd_import_security_review(args: argparse.Namespace) -> int:
    from document_ai.form_fill.security_execution_review import (
        SecurityReviewError,
        import_security_review,
    )

    case_dir = Path(args.case)
    review_path = Path(args.review)
    try:
        summary = import_security_review(
            case_dir,
            review_path,
            allow_synthetic_demo_selection=bool(args.allow_synthetic_demo),
        )
    except SecurityReviewError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    return 0


def cmd_security_review_summary(args: argparse.Namespace) -> int:
    from document_ai.form_fill.security_execution_review import (
        SecurityReviewError,
        security_review_summary,
    )

    case_dir = Path(args.case)
    try:
        summary = security_review_summary(case_dir)
    except SecurityReviewError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=True, indent=2))
        return 1
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    return 0


def cmd_generate(args: argparse.Namespace) -> int:

    case_dir = Path(args.case)

    input_path = case_dir / "input.json"

    if not input_path.exists():

        print(f"Missing {input_path}", file=sys.stderr)

        return 1



    payload = json.loads(input_path.read_text(encoding="utf-8"))

    template_id = args.template or payload.get("templates_in_set", ["spec_requirements"])[0]

    template_file = TEMPLATE_FILES.get(template_id)

    if not template_file:

        print(f"Unknown template_id: {template_id}", file=sys.stderr)

        return 1



    template_path = TEMPLATES_EC_SW / template_file

    if not template_path.exists():

        print(f"Missing template: {template_path}", file=sys.stderr)

        return 1



    out_path = case_dir / (args.output or DEFAULT_OUTPUTS.get(template_id, "output.docx"))

    facts = _case_facts(payload)

    if template_id == "spec_requirements":
        mdsr_path = case_dir / "mdsr_content.json"
        if mdsr_path.exists() and not facts.get("mdsr_content"):
            facts["mdsr_content"] = json.loads(mdsr_path.read_text(encoding="utf-8"))

    if template_id == "spec_design":
        mddr_path = case_dir / "mddr_content.json"
        if mddr_path.exists() and not facts.get("mddr_content"):
            facts["mddr_content"] = json.loads(mddr_path.read_text(encoding="utf-8"))



    if template_id == "report_security_verification":

        tests_path = case_dir / CASE_PAYLOAD_FILES[template_id]

        if not tests_path.exists():

            print(f"Hint: run extract-security-tests --case {case_dir} first", file=sys.stderr)

            return 1

        security_payload = json.loads(tests_path.read_text(encoding="utf-8"))

        result = fill_xxcs_report(template_path, facts, security_payload, out_path)

        print(json.dumps(result, ensure_ascii=False, indent=2))

        return 0



    schema_path = SCHEMAS_EC_SW / f"{template_id}.schema.json"

    if not schema_path.exists():

        print("Schema missing — run: python -m document_ai.cli export-schema", file=sys.stderr)

        return 1



    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    extra_payload = None

    content_payload = None
    design_items_payload = None

    payload_file = case_dir / CASE_PAYLOAD_FILES.get(template_id, "")

    if payload_file.exists():

        extra_payload = json.loads(payload_file.read_text(encoding="utf-8"))

        if template_id == "spec_design":

            content_payload = extra_payload

    if template_id == "spec_design":
        design_items_path = case_dir / "design_items.json"
        if design_items_path.exists():
            design_items_payload = json.loads(design_items_path.read_text(encoding="utf-8"))



    if template_id == "spec_requirements" and not extra_payload:

        print(f"Hint: run extract-requirements --case {case_dir} first", file=sys.stderr)



    result = fill_from_facts(

        template_path,

        schema,

        facts,

        out_path,

        requirements_payload=extra_payload if template_id == "spec_requirements" else None,

        content_payload=content_payload,

        design_items_payload=design_items_payload,

        overwrite_requirements=template_id == "spec_requirements",

    )

    print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0





def cmd_generate_all(args: argparse.Namespace) -> int:

    case_dir = Path(args.case)

    input_path = case_dir / "input.json"

    if not input_path.exists():

        print(f"Missing {input_path}", file=sys.stderr)

        return 1



    payload = json.loads(input_path.read_text(encoding="utf-8"))

    templates = payload.get("templates_in_set", list(TEMPLATE_FILES.keys()))

    results: dict[str, dict] = {}

    for template_id in templates:

        gen_args = argparse.Namespace(case=str(case_dir), template=template_id, output=None)

        rc = cmd_generate(gen_args)

        if rc != 0:

            return rc

        out_name = DEFAULT_OUTPUTS.get(template_id, "output.docx")

        results[template_id] = {"output": str(case_dir / out_name)}

    print(json.dumps({"case": str(case_dir), "documents": results}, ensure_ascii=False, indent=2))

    return 0


def cmd_harness_generate(args: argparse.Namespace) -> int:
    """End-to-end harness pipeline: intake → retrieval → form-fill → render → review."""
    case_dir = Path(args.case)
    if not (case_dir / "input.json").exists():
        print(f"Missing {case_dir / 'input.json'}", file=sys.stderr)
        return 1

    harness = DocumentHarness(
        use_retrieval=not args.no_retrieval,
        materialize=True,
        force_form_fill=args.force_form_fill,
    )
    report = harness.generate(
        case_dir,
        template_id=args.template,
        use_retrieval=not args.no_retrieval,
        force_form_fill=args.force_form_fill,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if report.get("ok") else 1


def cmd_case_intake(args: argparse.Namespace) -> int:
    case_dir = Path(args.case)
    text = (args.text or "").strip()
    if not text and not args.text_file:
        print("Provide --text or --text-file", file=sys.stderr)
        return 1
    if args.text_file:
        text = Path(args.text_file).read_text(encoding="utf-8").strip()
    if not text:
        print("Intake text is empty", file=sys.stderr)
        return 1

    case_id = args.case_id or case_dir.name
    out_path = Path(args.out) if args.out else case_dir / "input.json"

    draft = parse_intake_text(
        text,
        case_id=case_id,
        domain=args.domain or "",
        product_name=args.product_name or "",
        product_code=args.product_code or "",
        author_org=args.author_org or "",
        confirm=args.confirm,
    )
    save_intake_draft(draft, out_path)

    result = draft.to_dict()
    result["output"] = str(out_path)
    result["intake_log"] = str(out_path.parent / "intake_log.json")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if draft.missing_fields and not args.confirm:
        return 2
    return 0


def cmd_document_validate(args: argparse.Namespace) -> int:
    case_dir = Path(args.case)
    if not case_dir.exists():
        print(f"Missing case dir: {case_dir}", file=sys.stderr)
        return 1

    gold_mdsr = Path(args.gold_mdsr) if args.gold_mdsr else None
    gold_mddr = Path(args.gold_mddr) if args.gold_mddr else None
    gold_fields = Path(args.gold_fields) if getattr(args, "gold_fields", None) else None
    report_md = Path(args.report) if args.report else case_dir / "validation_report.md"
    report_json = Path(args.report_json) if args.report_json else case_dir / "validation_report.json"

    result = run_document_validation(
        case_dir,
        gold_mdsr=gold_mdsr,
        gold_mddr=gold_mddr,
        gold_fields_path=gold_fields,
        report_md_path=report_md,
        report_json_path=report_json,
    )
    if not result.get("scores", {}).get("overall") and result.get("errors"):
        print("Validation failed: missing generated or gold documents.", file=sys.stderr)
        for err in result["errors"]:
            print(f"  - {err}", file=sys.stderr)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    print(
        json.dumps(
            {
                "case": result["case"],
                "status": result["status"],
                "scores": result["scores"],
                "metrics": result.get("metrics", {}),
                "report_paths": result.get("report_paths", {}),
                "high_risk_count": len(result.get("high_risk_differences", [])),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["status"] != "FAIL" else 1


def cmd_document_quality(args: argparse.Namespace) -> int:
    case_dir = Path(args.case)
    if not case_dir.exists():
        print(f"Missing case dir: {case_dir}", file=sys.stderr)
        return 1

    report_path = Path(args.report) if args.report else case_dir / "quality_report.md"
    gold_mdsr = Path(args.gold_mdsr) if args.gold_mdsr else None
    gold_mddr = Path(args.gold_mddr) if args.gold_mddr else None

    result = run_document_quality(
        case_dir,
        gold_mdsr=gold_mdsr,
        gold_mddr=gold_mddr,
        report_path=report_path,
    )
    print(json.dumps(
        {
            "case": result["case"],
            "status": result["status"],
            "scores": result["scores"],
            "auto_fixable_count": result["auto_fixable_count"],
            "human_review_count": result["human_review_count"],
            "report_path": result.get("report_path"),
            "comparison": result.get("comparison", {}).get("aggregate"),
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0 if result["status"] != "FAIL" else 1


def cmd_impact(args: argparse.Namespace) -> int:
    case_dir = Path(args.case)
    change_path = Path(args.change)
    if not change_path.exists():
        print(f"Missing {change_path}", file=sys.stderr)
        return 1
    result = run_change_pipeline(
        case_dir,
        change_path,
        dry_run=True,
        apply=False,
        change_path=change_path,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_apply_change(args: argparse.Namespace) -> int:
    case_dir = Path(args.case)
    change_path = Path(args.change)
    if not change_path.exists():
        print(f"Missing {change_path}", file=sys.stderr)
        return 1
    result = run_change_pipeline(
        case_dir,
        change_path,
        dry_run=args.dry_run,
        apply=not args.dry_run,
        change_path=change_path,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_project_validate(args: argparse.Namespace) -> int:
    case_dir = Path(args.case)
    if not case_dir.exists():
        print(f"Missing case dir: {case_dir}", file=sys.stderr)
        return 1

    gold_mdsr = Path(args.gold_mdsr) if args.gold_mdsr else None
    gold_mddr = Path(args.gold_mddr) if args.gold_mddr else None

    result = run_project_e2e_validation(
        case_dir,
        force_generate=args.force_generate,
        gold_mdsr=gold_mdsr,
        gold_mddr=gold_mddr,
        skip_generate=args.skip_generate,
    )
    print(
        json.dumps(
            {
                "case_id": result.get("case_id"),
                "status": result.get("status"),
                "harness_ok": result.get("checks", {}).get("harness_ok"),
                "quality": result.get("quality", {}).get("scores"),
                "validation": result.get("validation", {}).get("scores"),
                "e2e_report_path": result.get("e2e_report_path"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.get("status") == "PASS" else 1


def cmd_eval_document_set(args: argparse.Namespace) -> int:
    domains = None
    if getattr(args, "domains", None):
        domains = [d.strip() for d in str(args.domains).split(",") if d.strip()]
    case_ids = None
    if getattr(args, "case_ids", None):
        case_ids = [c.strip() for c in str(args.case_ids).split(",") if c.strip()]
    try:
        payload = run_benchmark(
            manifest_path=Path(args.manifest) if args.manifest else None,
            domains=domains,
            case_ids=case_ids,
            output_dir=Path(args.output_dir) if args.output_dir else None,
            no_writer=bool(args.no_writer),
            repeat=int(args.repeat or 1),
            fail_on_unsafe=bool(args.fail_on_unsafe),
        )
    except DatasetValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except Exception as exc:  # noqa: BLE001
        print(f"eval-document-set error: {exc}", file=sys.stderr)
        return 1
    summary = payload.get("summary") or {}
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(
            json.dumps(
                {
                    "run_id": summary.get("run_id"),
                    "output_dir": payload.get("output_dir"),
                    "document_macro_f1": summary.get("document_macro_f1"),
                    "false_patch_rate": summary.get("false_patch_rate"),
                    "e2e_success_rate": summary.get("e2e_success_rate"),
                    "unsafe_failure_rate": summary.get("unsafe_failure_rate"),
                    "safety_status": summary.get("safety_status"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    if payload.get("exit_hint") == 2:
        return 2
    return 0


def cmd_eval_document_set_v2(args: argparse.Namespace) -> int:
    from document_ai.evaluation.document_set_v2 import run_benchmark_v2
    from document_ai.evaluation.document_set_v2.dataset_loader import BenchmarkV2ValidationError

    domains = None
    if getattr(args, "domains", None):
        domains = [d.strip() for d in str(args.domains).split(",") if d.strip()]
    splits = None
    if getattr(args, "split", None):
        splits = [s.strip() for s in str(args.split).split(",") if s.strip()]
    try:
        payload = run_benchmark_v2(
            manifest_path=Path(args.manifest) if args.manifest else None,
            splits=splits,
            domains=domains,
            output_dir=Path(args.output_dir) if args.output_dir else None,
            no_writer=bool(args.no_writer),
            repeat=int(args.repeat or 1),
            run_metamorphic=bool(args.run_metamorphic),
            run_format_check=bool(args.run_format_check),
            fail_on_unsafe=bool(args.fail_on_unsafe),
            fail_on_protocol_violation=bool(args.fail_on_protocol_violation),
        )
    except BenchmarkV2ValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except Exception as exc:  # noqa: BLE001
        print(f"eval-document-set-v2 error: {exc}", file=sys.stderr)
        return 1
    summary = payload.get("summary") or {}
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(
            json.dumps(
                {
                    "run_id": summary.get("run_id"),
                    "output_dir": payload.get("output_dir"),
                    "protocol_status": summary.get("protocol_status"),
                    "regression_doc_f1": (summary.get("regression") or {}).get("document_macro_f1"),
                    "holdout_doc_f1": (summary.get("holdout") or {}).get("document_macro_f1"),
                    "holdout_e2e": (summary.get("holdout") or {}).get("e2e_success_rate"),
                    "safety_status": summary.get("safety_status"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    hint = payload.get("exit_hint") or 0
    if hint:
        return int(hint)
    return 0


def cmd_run_pilot_session(args: argparse.Namespace) -> int:
    from pathlib import Path as _Path

    from document_ai.pilot_v2 import cli_support

    root = _Path(args.root) if args.root else None
    result, code = cli_support.run_pilot_session(
        args.scenario,
        participant_id=args.participant_id,
        routing_mode=args.routing_mode,
        dry_review=bool(args.dry_review),
        approve_all=bool(args.approve_all),
        writer_enabled=bool(args.writer_enabled),
        root=root,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


def cmd_materialize_pilot_demo(args: argparse.Namespace) -> int:
    from document_ai.pilot_v2 import demo_pack

    payload = demo_pack.materialize_demo_dataset(force=bool(args.force))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_run_pilot_demo(args: argparse.Namespace) -> int:
    from pathlib import Path as _Path

    from document_ai.pilot_v2 import demo_pack

    root = _Path(args.root) if args.root else None
    summary = demo_pack.run_flagship_demos(
        dry_review=not bool(args.approve_all),
        approve_all=bool(args.approve_all),
        writer_enabled=bool(args.writer_enabled),
        root=root,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary.get("all_exit_ok") else 1


def cmd_evaluate_pilot(args: argparse.Namespace) -> int:
    from pathlib import Path as _Path

    from document_ai.pilot_v2 import cli_support

    root = _Path(args.root) if args.root else None
    out_dir = _Path(args.output_dir) if args.output_dir else None
    session_ids = [s.strip() for s in str(args.session_ids).split(",") if s.strip()] if args.session_ids else None
    payload, code = cli_support.evaluate_pilot(session_ids=session_ids, root=root, output_dir=out_dir)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            json.dumps(
                {
                    "run_id": payload.get("run_id"),
                    "n_sessions": payload.get("n_sessions"),
                    "verdict": payload.get("verdict"),
                    "verdict_reasons": payload.get("verdict_reasons"),
                    "output_path": payload.get("output_path"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return code


def cmd_harness_benchmark(args: argparse.Namespace) -> int:
    report = run_harness_benchmark(
        config_path=args.config,
        out_dir=args.out,
        force_generate=args.force_generate,
        case_filter=args.case,
        split=getattr(args, "split", None),
        holdout_only=bool(getattr(args, "holdout_only", False)),
    )
    if args.merge_platform_report:
        merge_into_platform_benchmark(report, args.merge_platform_report)
    print(
        json.dumps(
            {
                "overall_score": report.get("overall_score"),
                "train": report.get("train"),
                "holdout": report.get("holdout"),
                "passed": report.get("passed"),
                "failed": report.get("failed"),
                "output_paths": report.get("output_paths"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report.get("failed", 0) == 0 else 1


def cmd_bootstrap_gold(args: argparse.Namespace) -> int:
    case_dir = Path(args.case)
    if not case_dir.exists():
        print(f"Missing case dir: {case_dir}", file=sys.stderr)
        return 1
    try:
        result = bootstrap_gold_from_case(
            case_dir,
            case_id=args.case_id,
            split=args.split,
            approve=bool(args.approve),
            include_xxcs=True if args.include_xxcs else None,
        )
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_bootstrap_golden_fields(args: argparse.Namespace) -> int:
    case_dir = Path(args.case)
    if not case_dir.exists():
        print(f"Missing case dir: {case_dir}", file=sys.stderr)
        return 1
    out_path = Path(args.out) if args.out else None
    rows = bootstrap_golden_fields_jsonl_from_case(
        case_dir,
        out_path=out_path,
        include_requirements=bool(args.include_requirements),
        append=bool(args.append),
    )
    result = {
        "case_dir": str(case_dir),
        "row_count": len(rows),
        "append": bool(args.append),
        "out": str(out_path or "data/eval/golden_fields.jsonl"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_field_f1(args: argparse.Namespace) -> int:
    case_dir = Path(args.case) if args.case else None
    golden_path = Path(args.golden) if args.golden else None
    result = compute_field_f1(
        case_dir=case_dir,
        case_id=args.case_id,
        golden_path=golden_path,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.fail_under is not None and result.get("field_f1", 0) < args.fail_under:
        return 1
    return 0


def cmd_document_agent(args: argparse.Namespace) -> int:
    case_dir = Path(args.case)
    if not case_dir.exists():
        print(f"Missing case dir: {case_dir}", file=sys.stderr)
        return 1
    change = Path(args.change) if args.change else None
    try:
        result = run_document_agent(
            case_dir,
            mode=args.mode,
            change=change,
            dry_run=not args.apply,
            apply=bool(args.apply),
            ablation_variant=args.ablation,
        )
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.out:
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("result", {}).get("ok", True) else 1


def cmd_ablation_suite(args: argparse.Namespace) -> int:
    case_dir = Path(args.case)
    if not case_dir.exists():
        print(f"Missing case dir: {case_dir}", file=sys.stderr)
        return 1
    golden_path = Path(args.golden) if args.golden else None
    change = Path(args.change) if args.change else None
    scorecard = Path(args.scorecard) if args.scorecard else None
    result = run_ablation_suite(
        case_dir,
        mode=args.mode,
        golden_path=golden_path,
        change=change,
        scorecard_path=scorecard,
    )
    if args.out:
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_tnr_scorecard(args: argparse.Namespace) -> int:
    from document_ai.eval.ablation_runner import evaluate_tnr_scorecards

    path = Path(args.scorecard)
    if not path.exists():
        print(f"Missing scorecard: {path}", file=sys.stderr)
        return 1
    if path.is_dir() or args.batch:
        result = evaluate_tnr_scorecards(path)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("tnr_rate", 0) == 1.0 else 1
    result = tnr_from_scorecard_file(path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("tnr_satisfied") else 1


def cmd_rq3_experiment(args: argparse.Namespace) -> int:
    out_dir = Path(args.out) if args.out else None
    closure_cases = None
    if args.closure_cases:
        closure_cases = [Path(p.strip()) for p in args.closure_cases.split(",") if p.strip()]
    result = run_rq3_experiment(
        out_dir=out_dir,
        pilot_summary=Path(args.pilot_summary) if args.pilot_summary else None,
        pilot_scorecard=Path(args.pilot_scorecard) if args.pilot_scorecard else None,
        writer_expectations=Path(args.writer_expectations) if args.writer_expectations else None,
        closure_cases=closure_cases,
        include_priority1=not bool(args.skip_priority1),
    )
    p1 = result.get("priority1") or {}
    summary = {
        "output_json": result.get("output_json"),
        "output_md": result.get("output_md"),
        "pilot_tnr_satisfied": (result.get("pilot") or {}).get("observed_tnr", {}).get("tnr_satisfied"),
        "holdout_all_gated": (result.get("holdout_writer_expectations") or {}).get("all_gated"),
        "holdout_safety_status": (p1.get("holdout_safety_scorecard") or {}).get("safety_status"),
        "holdout_tnr_satisfied": (p1.get("holdout_observed_tnr") or {}).get("tnr_satisfied"),
        "impact_doc_f1": ((p1.get("impact_quality") or {}).get("document") or {}).get("f1"),
        "impact_node_f1": ((p1.get("impact_quality") or {}).get("node") or {}).get("f1"),
        "impact_recall_at_3": (p1.get("impact_quality") or {}).get("required_node_recall_at_3"),
        "ablation_full_tnr": (result.get("ablation") or {}).get("full", {}).get("tnr_satisfied"),
        "ablation_no_gate_tnr": (result.get("ablation") or {}).get("no_gate", {}).get("tnr_satisfied"),
        "closure_delta": (result.get("closure_evidence") or {}).get("total_closure_delta"),
        "field_f1_secondary": {
            cid: row.get("field_f1")
            for cid, row in ((result.get("field_f1_secondary") or {}).get("by_case") or {}).items()
        },
        "priority1_md": ((p1.get("artifacts") or {}).get("md")),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    ok = bool(summary.get("pilot_tnr_satisfied") and summary.get("ablation_full_tnr"))
    if summary.get("holdout_tnr_satisfied") is False:
        ok = False
    return 0 if ok else 1


def cmd_regulatory_bench_run(args: argparse.Namespace) -> int:
    from document_ai.eval.regulatory_bench.runner import run_case

    if args.mode == "artifact_only" and not args.artifacts:
        raise SystemExit("--artifacts is required when --mode artifact_only")

    result = run_case(
        args.case,
        artifacts_path=args.artifacts,
        mode=args.mode,
        out_dir=args.out,
        recall_k=args.recall_k,
        approve=not getattr(args, "no_approve", False),
    )
    primary = (result.get("score") or {}).get("primary") or {}
    summary = {
        "case_id": result.get("case_id"),
        "out_dir": result.get("out_dir"),
        "score_path": result.get("score_path"),
        "mu_zero": primary.get("mu_zero"),
        "mu": primary.get("mu"),
        "doc_f1": primary.get("doc_f1"),
        "node_recall_at_3": primary.get("node_recall_at_3"),
        "cell_f1": primary.get("cell_f1"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if primary.get("mu_zero") else 1



def cmd_regulatory_bench_scorecard(args: argparse.Namespace) -> int:
    from document_ai.eval.regulatory_bench.scorecard import run_scorecard

    modes = [m.strip() for m in (args.modes or "demo_safe,live").split(",") if m.strip()]
    result = run_scorecard(
        cases_root=Path(args.cases_root) if args.cases_root else None,
        out_dir=Path(args.out) if args.out else None,
        modes=modes,
    )
    summary = (result.get("scorecard") or {}).get("summary") or {}
    print(json.dumps({"paths": result.get("paths"), "summary": summary}, ensure_ascii=False, indent=2))
    return 0




def cmd_regulatory_bench_paper_tables(args: argparse.Namespace) -> int:
    from document_ai.eval.regulatory_bench.paper_tables import run_paper_tables

    modes = [m.strip() for m in (args.modes or "demo_safe,live").split(",") if m.strip()]
    result = run_paper_tables(
        cases_root=Path(args.cases_root) if args.cases_root else None,
        out_dir=Path(args.out) if args.out else None,
        modes=modes,
    )
    print(json.dumps({"paths": result.get("paths"), "tables": result.get("tables")}, ensure_ascii=False, indent=2))
    return 0


def cmd_regulatory_bench_ablation_table(args: argparse.Namespace) -> int:
    from document_ai.eval.regulatory_bench.ablation_table import run_ablation_mu_table

    case_ids = None
    if args.cases:
        case_ids = [c.strip() for c in args.cases.split(",") if c.strip()]
    result = run_ablation_mu_table(
        cases_root=Path(args.cases_root) if args.cases_root else None,
        out_dir=Path(args.out) if args.out else None,
        case_ids=case_ids,
    )
    print(json.dumps({"paths": result.get("paths"), "summary": result.get("summary")}, ensure_ascii=False, indent=2))
    return 0


def cmd_document_tnr_mu_align(args: argparse.Namespace) -> int:
    from document_ai.safety.document_tnr import mu_pilot_key_alignment

    payload = mu_pilot_key_alignment()
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_regulatory_bench_score(args: argparse.Namespace) -> int:
    from document_ai.eval.regulatory_bench.scorer import score_case

    artifacts = json.loads(Path(args.artifacts).read_text(encoding="utf-8"))
    score = score_case(args.case, artifacts, recall_k=args.recall_k)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(score, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(score.get("primary") or score, ensure_ascii=False, indent=2))
    if args.json:
        print(json.dumps(score, ensure_ascii=False, indent=2))
    return 0 if score.get("mu_zero") else 1


def cmd_rq3_priority1(args: argparse.Namespace) -> int:
    from document_ai.eval.rq3_holdout_suite import run_priority1_suite

    domains = None
    if args.domains:
        domains = [d.strip() for d in args.domains.split(",") if d.strip()]
    result = run_priority1_suite(
        out_dir=Path(args.out) if args.out else None,
        domains=domains,
    )
    summary = {
        "output_json": result.get("output_json"),
        "output_md": result.get("output_md"),
        "output_scorecard": result.get("output_scorecard"),
        "safety_status": (result.get("holdout_safety") or {})
        .get("safety_scorecard", {})
        .get("safety_status"),
        "tnr_satisfied": (result.get("holdout_safety") or {})
        .get("observed_tnr", {})
        .get("tnr_satisfied"),
        "impact_doc_f1": ((result.get("impact_quality") or {}).get("document") or {}).get("f1"),
        "impact_node_f1": ((result.get("impact_quality") or {}).get("node") or {}).get("f1"),
        "recall_at_3": (result.get("impact_quality") or {}).get("required_node_recall_at_3"),
        "ablation": {
            k: {"tnr": v.get("tnr_satisfied"), "violations": v.get("total_violations")}
            for k, v in ((result.get("sandbox_ablation") or {}).get("variants") or {}).items()
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary.get("tnr_satisfied") else 1


def cmd_prepare_review(args: argparse.Namespace) -> int:
    case_id = args.case_id or Path(args.case).name
    result = prepare_review_package(
        case_id,
        case_dir=args.case,
        review_root=args.out,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_review_summary(args: argparse.Namespace) -> int:
    review_dir = Path(args.review_dir) if args.review_dir else Path("data/review") / args.case
    try:
        summary = summarize_human_evaluation(review_dir)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def cmd_eval_impact(args: argparse.Namespace) -> int:
    cases_path = Path(args.cases)
    expected_path = Path(args.expected)
    out_dir = Path(args.out)
    if not cases_path.exists():
        print(f"Missing {cases_path}", file=sys.stderr)
        return 1
    if not expected_path.exists():
        print(f"Missing {expected_path}", file=sys.stderr)
        return 1
    result = run_evaluation(cases_path, expected_path, out_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_trial_init(args: argparse.Namespace) -> int:
    try:
        result = init_trial(
            trial_id=args.trial_id,
            case=args.case,
            trial_type=args.type,
            system_version=args.system_version,
            system_commit=args.system_commit,
            synthetic=bool(args.synthetic),
            force=bool(args.force),
        )
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_trial_check_input(args: argparse.Namespace) -> int:
    try:
        result = check_trial_input(args.trial)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 2


def cmd_trial_generate(args: argparse.Namespace) -> int:
    try:
        result = generate_trial(
            args.trial,
            force_generate=bool(args.force_generate),
            skip_generate=True if args.skip_generate else (False if args.force_generate else None),
        )
    except (FileNotFoundError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


def cmd_trial_prepare_review(args: argparse.Namespace) -> int:
    try:
        result = prepare_trial_review(args.trial)
    except (FileNotFoundError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_trial_analyze(args: argparse.Namespace) -> int:
    try:
        result = analyze_trial(args.trial)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_trial_summary(args: argparse.Namespace) -> int:
    try:
        result = summarize_trial(args.trial)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_baseline_freeze(args: argparse.Namespace) -> int:
    result = freeze_baseline(
        system_version=args.system_version,
        system_commit=args.system_commit,
        out_root=args.out,
        run_pytest=bool(args.run_pytest),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_dataset_manifest(args: argparse.Namespace) -> int:
    path = ensure_dataset_manifest(args.path)
    manifest = load_dataset_manifest(path)
    result = validate_dataset_manifest(manifest)
    payload = {"path": str(path), "validation": result, "manifest": manifest}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 2


def cmd_draft_change(args: argparse.Namespace) -> int:
    case_dir = Path(args.case)
    request_text = _read_change_request(args)
    if not request_text:
        print("Provide --request, --request-file, or both --req and --description", file=sys.stderr)
        return 1

    requirements_payload = load_requirements_payload(case_dir)
    change = draft_change_from_request(
        request_text,
        requirements_payload=requirements_payload,
        explicit_req_id=args.req,
        explicit_description=args.description,
        summary=args.summary,
        sync_design_from_requirement=not args.no_sync_design,
    )

    if args.dry_run:
        preview = {"change": change}
        if change.get("requirement_changes"):
            preview["impact"] = compute_impact(case_dir, change)
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        return 0 if change["intake"]["confirmed"] else 2

    out_path = Path(args.output) if args.output else case_dir / "changes" / f"{change['change_id']}.json"
    save_change(change, out_path)

    impact = compute_impact(case_dir, change) if change.get("requirement_changes") else None
    append_intake_log(
        case_dir,
        {
            "type": "draft_change",
            "change_id": change.get("change_id"),
            "output": str(out_path),
            "confidence": change["intake"]["confidence"],
            "confirmed": change["intake"]["confirmed"],
        },
    )

    result: dict[str, Any] = {
        "output": str(out_path),
        "change": change,
        "impact": impact,
    }

    if args.apply:
        if not change["intake"]["confirmed"]:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            print("Clarification needed before apply.", file=sys.stderr)
            return 2
        apply_result = apply_change(case_dir, out_path, dry_run=False)
        result["apply"] = apply_result

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if change["intake"]["confirmed"] else 2


def _read_change_request(args: argparse.Namespace) -> str:
    if args.request_file:
        return Path(args.request_file).read_text(encoding="utf-8").strip()
    if args.request:
        return args.request.strip()
    if args.req and args.description:
        return f"{args.req}: {args.description}"
    return ""


def main(argv: list[str] | None = None) -> int:

    parser = argparse.ArgumentParser(prog="document-ai", description="EC-SW document form-fill CLI")

    sub = parser.add_subparsers(dest="command", required=True)



    p_export = sub.add_parser("export-schema", help="Export MDSR/MDDR schema JSON from blank+filled diff")

    p_export.set_defaults(func=cmd_export_schema)



    p_skel = sub.add_parser("xxcs-skeleton", help="Create XXCS skeleton from filled report")

    p_skel.add_argument("--filled", help="Filled XXCS path")

    p_skel.add_argument("--output", help="Output skeleton path")

    p_skel.set_defaults(func=cmd_xxcs_skeleton)



    p_ext = sub.add_parser("extract-requirements", help="Extract Req.+traceability from filled MDSR")

    p_ext.add_argument("--case", required=True, help="Case dir for requirements.json output")

    p_ext.add_argument("--from-doc", help="Filled MDSR path")

    p_ext.add_argument("--output", help="Output JSON path")

    p_ext.set_defaults(func=cmd_extract_requirements)



    p_design = sub.add_parser("extract-design", help="Extract MDDR field values from filled design spec")

    p_design.add_argument("--case", required=True, help="Case dir for design_content.json output")

    p_design.add_argument("--from-doc", help="Filled MDDR path")
    p_design.add_argument("--from-schema", action="store_true", help="Bootstrap from schema example_value")
    p_design.add_argument("--output", help="Output JSON path")

    p_design.set_defaults(func=cmd_extract_design)

    p_design_items = sub.add_parser("extract-design-items", help="Extract MDDR Req. design blocks")
    p_design_items.add_argument("--case", required=True, help="Case dir for design_items.json output")
    p_design_items.add_argument("--from-doc", help="Filled MDDR path")
    p_design_items.add_argument("--output", help="Output JSON path")
    p_design_items.set_defaults(func=cmd_extract_design_items)

    p_import_srs = sub.add_parser("import-srs", help="Import IEEE-style SRS markdown into requirements.json")
    p_import_srs.add_argument("--case", required=True, help="Case dir e.g. data/cases/stt_srs")
    p_import_srs.add_argument("--from-md", help="SRS markdown path (default: case/source_srs.md)")
    p_import_srs.add_argument("--output", help="Output requirements.json path")
    p_import_srs.set_defaults(func=cmd_import_srs)

    p_sec = sub.add_parser("extract-security-tests", help="Extract XXCS test rows from filled report")

    p_sec.add_argument("--case", required=True, help="Case dir for security_tests.json output")

    p_sec.add_argument("--from-doc", help="Filled XXCS path")

    p_sec.add_argument("--output", help="Output JSON path")

    p_sec.set_defaults(func=cmd_extract_security_tests)

    p_import_sec = sub.add_parser(
        "import-security-results",
        help="Import external security test execution results into case overlay",
    )
    p_import_sec.add_argument("--case", required=True, help="Case directory e.g. data/cases/lab_ec_sw")
    p_import_sec.add_argument(
        "--results",
        required=True,
        help="Execution results JSON (schemas/security_test_execution.schema.json)",
    )
    p_import_sec.add_argument(
        "--no-accept",
        action="store_true",
        help="Do not mark this execution as the latest accepted batch",
    )
    p_import_sec.set_defaults(func=cmd_import_security_results)

    p_run_sec = sub.add_parser(
        "run-security-tests",
        help="Run allowlisted read-only security checks and emit execution JSON",
    )
    p_run_sec.add_argument("--case", required=True, help="Case directory")
    p_run_sec.add_argument("--config", required=True, help="Security runner config JSON")
    p_run_sec.add_argument("--output", required=True, help="Execution JSON output path")
    p_run_sec.add_argument("--check", help="Run one security_test_id or check_id")
    p_run_sec.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and show planned checks without network access",
    )
    p_run_sec.add_argument(
        "--synthetic",
        action="store_true",
        help="Use fixture-only synthetic mode; network is always disabled",
    )
    p_run_sec.add_argument(
        "--no-network",
        action="store_true",
        help="Use configured fixtures and perform no network requests",
    )
    p_run_sec.add_argument("--timeout", type=float, help="Per-check timeout seconds")
    p_run_sec.add_argument("--execution-id", help="Execution id (must start with exec-)")
    p_run_sec.set_defaults(func=cmd_run_security_tests)

    p_prep_sec_review = sub.add_parser(
        "prepare-security-review",
        help="Build human review package for an imported security execution",
    )
    p_prep_sec_review.add_argument("--case", required=True, help="Case directory")
    p_prep_sec_review.add_argument("--execution-id", required=True, help="Execution id e.g. exec-20260717-synthetic-001")
    p_prep_sec_review.add_argument(
        "--out",
        help="Package output directory (default: data/review/{case_id}/{execution_id})",
    )
    p_prep_sec_review.set_defaults(func=cmd_prepare_security_review)

    p_import_sec_review = sub.add_parser(
        "import-security-review",
        help="Import filled execution review decisions into case overlay",
    )
    p_import_sec_review.add_argument("--case", required=True, help="Case directory")
    p_import_sec_review.add_argument("--review", required=True, help="Filled execution_review.json path")
    p_import_sec_review.add_argument(
        "--allow-synthetic-demo",
        action="store_true",
        help="Allow synthetic fixture results to be selected for demo reports only",
    )
    p_import_sec_review.set_defaults(func=cmd_import_security_review)

    p_sec_review_summary = sub.add_parser(
        "security-review-summary",
        help="Summarize security execution review status and final report readiness",
    )
    p_sec_review_summary.add_argument("--case", required=True, help="Case directory")
    p_sec_review_summary.set_defaults(func=cmd_security_review_summary)

    p_gen = sub.add_parser("generate", help="Fill one template from case input.json")

    p_gen.add_argument("--case", required=True, help="Case directory e.g. data/cases/mindrium_xa")

    p_gen.add_argument("--template", help="template_id override")

    p_gen.add_argument("--output", help="Output filename inside case dir")

    p_gen.set_defaults(func=cmd_generate)



    p_all = sub.add_parser("generate-all", help="Generate MDSR, MDDR, and XXCS for a case")

    p_all.add_argument("--case", required=True, help="Case directory e.g. data/cases/mindrium_xa")

    p_all.set_defaults(func=cmd_generate_all)

    p_harness = sub.add_parser(
        "harness-generate",
        help="Harness pipeline: intake → retrieval → form-fill → render → review",
    )
    p_harness.add_argument("--case", required=True, help="Case directory e.g. data/cases/inventory_mgmt")
    p_harness.add_argument("--template", help="Generate single template_id only")
    p_harness.add_argument("--no-retrieval", action="store_true", help="Skip case retrieval step")
    p_harness.add_argument("--force-form-fill", action="store_true", help="Overwrite payload JSON from retrieval")
    p_harness.add_argument("--out", help="Write harness report JSON to file")
    p_harness.set_defaults(func=cmd_harness_generate)

    p_intake = sub.add_parser(
        "case-intake",
        help="Build draft input.json from natural-language case description",
    )
    p_intake.add_argument("--case", required=True, help="Case directory e.g. data/cases/new_case")
    p_intake.add_argument("--text", help="Natural-language case description")
    p_intake.add_argument("--text-file", help="Text file with case description")
    p_intake.add_argument("--out", help="Output input.json path (default: case/input.json)")
    p_intake.add_argument("--case-id", help="Case id override (default: case directory name)")
    p_intake.add_argument("--confirm", action="store_true", help="Set confirmed=true on output")
    p_intake.add_argument("--domain", help="Domain override e.g. hospital_reservation")
    p_intake.add_argument("--product-name", help="Product name override")
    p_intake.add_argument("--product-code", help="Product code override e.g. HRS")
    p_intake.add_argument("--author-org", help="Author organization override")
    p_intake.set_defaults(func=cmd_case_intake)

    p_quality = sub.add_parser(
        "document-quality",
        help="Analyze generated DOCX quality and write quality_report.md",
    )
    p_quality.add_argument("--case", required=True, help="Case directory e.g. data/cases/inventory_mgmt")
    p_quality.add_argument("--report", help="Report path (default: case/quality_report.md)")
    p_quality.add_argument("--gold-mdsr", help="Gold MDSR DOCX for comparison")
    p_quality.add_argument("--gold-mddr", help="Gold MDDR DOCX for comparison")
    p_quality.set_defaults(func=cmd_document_quality)

    p_validate = sub.add_parser(
        "document-validate",
        help="Validate generated DOCX against gold reference documents",
    )
    p_validate.add_argument("--case", required=True, help="Case directory e.g. data/cases/jm_collection")
    p_validate.add_argument("--gold-mdsr", help="Gold MDSR DOCX (default: independent gold or case/gold_mdsr.docx)")
    p_validate.add_argument("--gold-mddr", help="Gold MDDR DOCX (default: independent gold or case/gold_mddr.docx)")
    p_validate.add_argument("--gold-fields", help="Structured gold_fields JSON path")
    p_validate.add_argument("--report", help="Markdown report path (default: case/validation_report.md)")
    p_validate.add_argument("--report-json", help="JSON report path (default: case/validation_report.json)")
    p_validate.set_defaults(func=cmd_document_validate)

    p_bootstrap_gold = sub.add_parser(
        "document-bootstrap-gold",
        help="Copy case outputs into data/gold and build gold_fields.json",
    )
    p_bootstrap_gold.add_argument("--case", required=True, help="Case directory with output_*.docx")
    p_bootstrap_gold.add_argument("--case-id", help="Override gold case_id (default: directory name)")
    p_bootstrap_gold.add_argument(
        "--split",
        choices=["train", "holdout"],
        default="train",
        help="Benchmark split label",
    )
    p_bootstrap_gold.add_argument(
        "--approve",
        action="store_true",
        help="Mark gold as human_approved (default: provisional)",
    )
    p_bootstrap_gold.add_argument(
        "--include-xxcs",
        action="store_true",
        help="Also copy output_xxcs.docx when present",
    )
    p_bootstrap_gold.set_defaults(func=cmd_bootstrap_gold)

    p_bootstrap_fields = sub.add_parser(
        "bootstrap-golden-fields",
        help="Build flat data/eval/golden_fields.jsonl from case input.json facts",
    )
    p_bootstrap_fields.add_argument("--case", required=True, help="Case directory e.g. data/cases/hospital_reservation")
    p_bootstrap_fields.add_argument("--out", help="Output JSONL path (default: data/eval/golden_fields.jsonl)")
    p_bootstrap_fields.add_argument(
        "--include-requirements",
        action="store_true",
        help="Add first requirement description row",
    )
    p_bootstrap_fields.add_argument(
        "--append",
        action="store_true",
        help="Merge into existing golden_fields.jsonl (replace same case_id rows)",
    )
    p_bootstrap_fields.set_defaults(func=cmd_bootstrap_golden_fields)

    p_field_f1 = sub.add_parser(
        "field-f1",
        help="Compute Field precision/recall/F1 against golden_fields.jsonl",
    )
    p_field_f1.add_argument("--case", help="Case directory (optional if --case-id filters golden rows)")
    p_field_f1.add_argument("--case-id", help="Filter golden rows by case_id")
    p_field_f1.add_argument("--golden", help="Golden JSONL path (default: data/eval/golden_fields.jsonl)")
    p_field_f1.add_argument(
        "--fail-under",
        type=float,
        help="Exit 1 if field_f1 is below this threshold",
    )
    p_field_f1.set_defaults(func=cmd_field_f1)

    p_doc_agent = sub.add_parser(
        "document-agent",
        help="Dual-mode agent: new (form-fill) or change (impact pipeline)",
    )
    p_doc_agent.add_argument("--case", required=True, help="Case directory")
    p_doc_agent.add_argument(
        "--mode",
        choices=["new", "change"],
        default="new",
        help="new=form-fill harness; change=impact pipeline",
    )
    p_doc_agent.add_argument("--change", help="Change JSON path (change mode)")
    p_doc_agent.add_argument("--apply", action="store_true", help="Apply patches (change mode; default dry-run)")
    p_doc_agent.add_argument(
        "--ablation",
        choices=["full", "no_gate", "no_closure", "no_copy_only"],
        help="Document-TNR ablation variant (reporting)",
    )
    p_doc_agent.add_argument("--out", help="Write full result JSON to file")
    p_doc_agent.set_defaults(func=cmd_document_agent)

    p_ablation = sub.add_parser(
        "ablation-suite",
        help="Run Document-TNR ablation variants and collect Field F1 / closure metrics",
    )
    p_ablation.add_argument("--case", required=True, help="Case directory")
    p_ablation.add_argument(
        "--mode",
        choices=["new", "change"],
        default="new",
        help="Harness mode for variant runs",
    )
    p_ablation.add_argument("--golden", help="Golden JSONL for Field F1")
    p_ablation.add_argument("--change", help="Change JSON path (change mode)")
    p_ablation.add_argument("--scorecard", help="Optional safety scorecard for observed TNR")
    p_ablation.add_argument("--out", help="Write suite JSON to file")
    p_ablation.set_defaults(func=cmd_ablation_suite)

    p_tnr = sub.add_parser(
        "tnr-scorecard",
        help="Assess Document-TNR from a pilot/benchmark safety scorecard JSON",
    )
    p_tnr.add_argument("--scorecard", required=True, help="Safety scorecard JSON path or directory")
    p_tnr.add_argument(
        "--batch",
        action="store_true",
        help="Treat --scorecard as a directory and aggregate all *scorecard*.json",
    )
    p_tnr.set_defaults(func=cmd_tnr_scorecard)

    p_rq3 = sub.add_parser(
        "rq3-experiment",
        help="RQ1–RQ3 Document-TNR package: pilot/holdout TNR + ablation tables + Field F1 secondary",
    )
    p_rq3.add_argument("--out", help="Output dir (default: data/eval/results/document_tnr)")
    p_rq3.add_argument("--pilot-summary", help="Override pilot_summary.json path")
    p_rq3.add_argument("--pilot-scorecard", help="Override safety_scorecard.json path")
    p_rq3.add_argument("--writer-expectations", help="Override holdout writer_expectations.jsonl")
    p_rq3.add_argument(
        "--closure-cases",
        help="Comma-separated case dirs for C1 closure evidence",
    )
    p_rq3.add_argument(
        "--skip-priority1",
        action="store_true",
        help="Skip holdout safety / sandbox ablation / impact-quality suite",
    )
    p_rq3.add_argument("--json", action="store_true", help="Also print full experiment JSON")
    p_rq3.set_defaults(func=cmd_rq3_experiment)

    p_rq3p1 = sub.add_parser(
        "rq3-priority1",
        help="Holdout safety scorecard + sandbox ablation + impact location quality",
    )
    p_rq3p1.add_argument("--out", help="Output dir (default: data/eval/results/document_tnr)")
    p_rq3p1.add_argument("--domains", help="Comma-separated domains e.g. ec_sw,general_report")
    p_rq3p1.set_defaults(func=cmd_rq3_priority1)

    p_rb_run = sub.add_parser(
        "regulatory-bench-run",
        help="Small-A regulatory bench: run case and score μ/DocF1/R@3/cellF1",
    )
    p_rb_run.add_argument("--case", required=True, help="Case dir e.g. data/eval/regulatory_bench/case_000")
    p_rb_run.add_argument(
        "--mode",
        choices=["demo_safe", "artifact_only", "materialize", "pipeline", "live"],
        default="demo_safe",
        help=(
            "demo_safe=gold oracle; materialize=write synthetic MDSR/MDDR+fp; "
            "pipeline=heuristic gated dump; live=compute_impact + copy-only writes; "
            "artifact_only needs --artifacts"
        ),
    )
    p_rb_run.add_argument("--artifacts", help="Precomputed artifacts JSON (required for artifact_only)")
    p_rb_run.add_argument("--out", help="Output dir (default: <case>/runs/latest)")
    p_rb_run.add_argument("--recall-k", type=int, default=3)
    p_rb_run.add_argument(
        "--no-approve",
        action="store_true",
        help="For pipeline mode: leave approval pending (expect unapproved_write)",
    )
    p_rb_run.add_argument("--json", action="store_true")
    p_rb_run.set_defaults(func=cmd_regulatory_bench_run)

    p_rb_score = sub.add_parser(
        "regulatory-bench-score",
        help="Score regulatory_bench artifacts against case gold (μ + impact + cell F1)",
    )
    p_rb_score.add_argument("--case", required=True)
    p_rb_score.add_argument("--artifacts", required=True, help="artifacts.json path")
    p_rb_score.add_argument("--out", help="Optional score.json path")
    p_rb_score.add_argument("--recall-k", type=int, default=3)
    p_rb_score.add_argument("--json", action="store_true")
    p_rb_score.set_defaults(func=cmd_regulatory_bench_score)

    p_rb_sc = sub.add_parser(
        "regulatory-bench-scorecard",
        help="Export μ scorecard CSV/JSON (Safety-first) + consistency stub + sandbox ablation",
    )
    p_rb_sc.add_argument("--cases-root", help="Cases root (default: data/eval/regulatory_bench)")
    p_rb_sc.add_argument("--out", help="Reports output dir")
    p_rb_sc.add_argument("--modes", default="demo_safe,live", help="Comma-separated modes")
    p_rb_sc.set_defaults(func=cmd_regulatory_bench_scorecard)


    p_rb_paper = sub.add_parser(
        "regulatory-bench-paper-tables",
        help="Sealed holdout + Safety-first paper tables (μ=0 → R@3 → cell F1 → field F1)",
    )
    p_rb_paper.add_argument("--cases-root", help="Cases root (default: data/eval/regulatory_bench)")
    p_rb_paper.add_argument("--out", help="Reports output dir")
    p_rb_paper.add_argument("--modes", default="demo_safe,live", help="Comma-separated modes")
    p_rb_paper.set_defaults(func=cmd_regulatory_bench_paper_tables)

    p_rb_abl = sub.add_parser(
        "regulatory-bench-ablation-table",
        help="One-shot sandbox ablation μ table (no_gate/no_copy_only/no_closure) — counterfactual only",
    )
    p_rb_abl.add_argument("--cases-root", help="Cases root (default: data/eval/regulatory_bench)")
    p_rb_abl.add_argument("--cases", help="Optional comma-separated case_ids (default: all)")
    p_rb_abl.add_argument("--out", help="Reports output dir")
    p_rb_abl.set_defaults(func=cmd_regulatory_bench_ablation_table)

    p_mu_align = sub.add_parser(
        "document-tnr-mu-align",
        help="Export Document-TNR μ ↔ Pilot Safety key alignment (RQ1 plain language)",
    )
    p_mu_align.add_argument("--out", help="Optional JSON output path")
    p_mu_align.set_defaults(func=cmd_document_tnr_mu_align)




    p_prepare_review = sub.add_parser(
        "document-prepare-review",
        help="Assemble human review package under data/review/{case_id}",
    )
    p_prepare_review.add_argument(
        "--case",
        required=True,
        help="Case directory e.g. data/cases/hospital_reservation",
    )
    p_prepare_review.add_argument("--case-id", help="Override case_id (default: directory name)")
    p_prepare_review.add_argument(
        "--out",
        default="data/review",
        help="Review root directory (default: data/review)",
    )
    p_prepare_review.set_defaults(func=cmd_prepare_review)

    p_review_summary = sub.add_parser(
        "document-review-summary",
        help="Build human_evaluation_summary from review_result.json",
    )
    p_review_summary.add_argument(
        "--case",
        default="hospital_reservation",
        help="Case id under data/review/ (default: hospital_reservation)",
    )
    p_review_summary.add_argument(
        "--review-dir",
        help="Explicit review directory (overrides --case)",
    )
    p_review_summary.set_defaults(func=cmd_review_summary)

    p_project = sub.add_parser(
        "project-validate",
        help="E2E validate real project: harness → quality → validation",
    )
    p_project.add_argument("--case", required=True, help="Case directory e.g. data/cases/lab_ec_sw")
    p_project.add_argument("--gold-mdsr", help="Gold MDSR DOCX override")
    p_project.add_argument("--gold-mddr", help="Gold MDDR DOCX override")
    p_project.add_argument("--force-generate", action="store_true", help="Re-run harness-generate")
    p_project.add_argument("--skip-generate", action="store_true", help="Skip harness, only quality/validate")
    p_project.set_defaults(func=cmd_project_validate)

    p_harness_bench = sub.add_parser(
        "harness-benchmark",
        help="Run document harness E2E benchmark across registered cases",
    )
    p_harness_bench.add_argument(
        "--config",
        default="data/eval/document_harness_benchmark.json",
        help="Benchmark config path",
    )
    p_harness_bench.add_argument(
        "--out",
        default="data/eval/harness_benchmark",
        help="Output directory for harness_benchmark_report",
    )
    p_harness_bench.add_argument("--case", help="Run single case_id only")
    p_harness_bench.add_argument(
        "--split",
        choices=["train", "holdout"],
        help="Run only train or holdout cases",
    )
    p_harness_bench.add_argument(
        "--holdout-only",
        action="store_true",
        help="Shortcut for --split holdout; scores holdout cases only",
    )
    p_harness_bench.add_argument("--force-generate", action="store_true", help="Re-generate all cases")
    p_harness_bench.add_argument(
        "--merge-platform-report",
        help="Merge results into existing platform benchmark_report.json",
    )
    p_harness_bench.set_defaults(func=cmd_harness_benchmark)

    p_impact = sub.add_parser("impact", help="Compute affected documents for a requirement change")
    p_impact.add_argument("--case", required=True, help="Case directory")
    p_impact.add_argument("--change", required=True, help="Path to change JSON")
    p_impact.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Analyze impact only; writes impact_report.json (default)",
    )
    p_impact.set_defaults(func=cmd_impact)

    p_apply = sub.add_parser("apply-change", help="Patch only impacted documents for a change")
    p_apply.add_argument("--case", required=True, help="Case directory")
    p_apply.add_argument("--change", required=True, help="Path to change JSON")
    p_apply.add_argument("--dry-run", action="store_true", help="Show impact without patching files")
    p_apply.set_defaults(func=cmd_apply_change)

    p_eval = sub.add_parser("eval-impact", help="Run change-impact evaluation against labeled cases")
    p_eval.add_argument("--cases", default="data/eval/change_cases.jsonl", help="Evaluation cases JSONL")
    p_eval.add_argument(
        "--expected",
        default="data/eval/expected_impacts.jsonl",
        help="Expected impact labels JSONL",
    )
    p_eval.add_argument("--out", default="data/eval/results", help="Output directory for metrics")
    p_eval.set_defaults(func=cmd_eval_impact)

    p_draft = sub.add_parser("draft-change", help="Parse natural-language/CLI request into change JSON")
    p_draft.add_argument("--case", required=True, help="Case directory")
    p_draft.add_argument("--request", help="Natural-language change request")
    p_draft.add_argument("--request-file", help="Text file containing change request")
    p_draft.add_argument("--req", help="Explicit Req. id e.g. Req. 6")
    p_draft.add_argument("--description", help="Explicit requirement description")
    p_draft.add_argument("--summary", help="Change summary override")
    p_draft.add_argument("--output", help="Output change JSON path")
    p_draft.add_argument("--dry-run", action="store_true", help="Parse/preview only, do not write change file")
    p_draft.add_argument("--apply", action="store_true", help="After draft, run apply-change")
    p_draft.add_argument("--no-sync-design", action="store_true", help="Do not sync MDDR from MDSR description")
    p_draft.set_defaults(func=cmd_draft_change)

    p_platform_plan = sub.add_parser("platform-plan", help="Plan platform workflow from a goal")
    p_platform_plan.add_argument("--goal", required=True, help="Natural-language goal")
    p_platform_plan.add_argument("--case", help="Case directory (default: .)")
    p_platform_plan.add_argument("--change", help="Change JSON path or operation description")
    p_platform_plan.add_argument("--sample-dir", help="Operation sample directory for hybrid/ops goals")
    p_platform_plan.add_argument("--request-id", help="Planner request id")
    p_platform_plan.add_argument("--apply", action="store_true", help="Plan for apply mode instead of dry-run")
    p_platform_plan.add_argument("--out", help="Write plan JSON to file instead of stdout")
    p_platform_plan.set_defaults(func=cmd_platform_plan)

    p_platform_run = sub.add_parser("platform-run", help="Run platform workflow via Goal Orchestrator")
    p_platform_run.add_argument("--case", required=True, help="Case directory")
    p_platform_run.add_argument("--change", required=True, help="Change JSON path or operation description")
    p_platform_run.add_argument("--goal", help="Natural-language goal override")
    p_platform_run.add_argument("--sample-dir", help="Operation sample directory")
    p_platform_run.add_argument("--request-id", help="Runtime request id")
    p_platform_run.add_argument("--apply", action="store_true", help="Apply document changes instead of dry-run")
    p_platform_run.add_argument("--out", help="Write runtime result JSON to file")
    p_platform_run.set_defaults(func=cmd_platform_run)

    p_platform_ops = sub.add_parser(
        "platform-ops-analyze",
        help="Analyze GPU/Docker incident samples via Operation Harness",
    )
    p_platform_ops.add_argument(
        "--samples",
        default="data/ops/samples",
        help="Sample logs directory (default: data/ops/samples)",
    )
    p_platform_ops.add_argument("--out", help="Write incident report JSON to file")
    p_platform_ops.set_defaults(func=cmd_platform_ops_analyze)

    p_platform_improve = sub.add_parser(
        "platform-improve",
        help="Analyze prior executions and emit self-improvement feedback",
    )
    p_platform_improve.add_argument("--case", required=True, help="Case directory")
    p_platform_improve.add_argument("--correlation-id", help="Filter memory by correlation id")
    p_platform_improve.add_argument("--out", help="Write improvement feedback JSON to file")
    p_platform_improve.set_defaults(func=cmd_platform_improve)

    p_platform_benchmark = sub.add_parser(
        "platform-benchmark",
        help="Run platform benchmark scenarios and generate benchmark_report",
    )
    p_platform_benchmark.add_argument(
        "--out",
        default="data/platform/benchmark",
        help="Output directory for benchmark_report.json and .md",
    )
    p_platform_benchmark.add_argument(
        "--baseline",
        help="Baseline JSON for regression comparison (default: data/eval/platform_baseline.json)",
    )
    p_platform_benchmark.add_argument(
        "--work-dir",
        help="Temporary working directory for isolated benchmark case copies",
    )
    p_platform_benchmark.add_argument(
        "--update-baseline",
        action="store_true",
        help="Save current benchmark results as the new baseline",
    )
    p_platform_benchmark.set_defaults(func=cmd_platform_benchmark)

    p_trial_init = sub.add_parser(
        "trial-init",
        help="Initialize an isolated real-world trial workspace under data/trials/",
    )
    p_trial_init.add_argument("--trial-id", required=True, help="Trial id e.g. trial-001-lab-ec-sw")
    p_trial_init.add_argument("--case", required=True, help="Source case directory")
    p_trial_init.add_argument(
        "--type",
        default="change_update",
        choices=["change_update", "new_document_generation"],
        help="Trial type",
    )
    p_trial_init.add_argument(
        "--system-version",
        default=BASELINE_SYSTEM_VERSION,
        help=f"Frozen system version tag (default: {BASELINE_SYSTEM_VERSION})",
    )
    p_trial_init.add_argument(
        "--system-commit",
        default=BASELINE_COMMIT,
        help=f"Frozen system commit (default: {BASELINE_COMMIT})",
    )
    p_trial_init.add_argument(
        "--synthetic",
        action="store_true",
        help="Seed synthetic fixture inputs (framework validation only)",
    )
    p_trial_init.add_argument("--force", action="store_true", help="Rebuild trial layout if present")
    p_trial_init.set_defaults(func=cmd_trial_init)

    p_trial_check = sub.add_parser(
        "trial-check-input",
        help="Validate trial inputs and data-leakage policy",
    )
    p_trial_check.add_argument("--trial", required=True, help="Trial directory or trial id")
    p_trial_check.set_defaults(func=cmd_trial_check_input)

    p_trial_gen = sub.add_parser(
        "trial-generate",
        help="Generate trial documents into isolated generated/ (never overwrite source case)",
    )
    p_trial_gen.add_argument("--trial", required=True, help="Trial directory or trial id")
    p_trial_gen.add_argument(
        "--force-generate",
        action="store_true",
        help="Re-run harness inside trial workdir (still isolated from source case)",
    )
    p_trial_gen.add_argument(
        "--skip-generate",
        action="store_true",
        help="Use copied existing outputs only",
    )
    p_trial_gen.set_defaults(func=cmd_trial_generate)

    p_trial_prep = sub.add_parser(
        "trial-prepare-review",
        help="Prepare human revision package for a trial",
    )
    p_trial_prep.add_argument("--trial", required=True, help="Trial directory or trial id")
    p_trial_prep.set_defaults(func=cmd_trial_prepare_review)

    p_trial_analyze = sub.add_parser(
        "trial-analyze",
        help="Diff generated vs human_revised and compute trial metrics",
    )
    p_trial_analyze.add_argument("--trial", required=True, help="Trial directory or trial id")
    p_trial_analyze.set_defaults(func=cmd_trial_analyze)

    p_trial_summary = sub.add_parser(
        "trial-summary",
        help="Write trial_report and presentation summaries/tables",
    )
    p_trial_summary.add_argument("--trial", required=True, help="Trial directory or trial id")
    p_trial_summary.set_defaults(func=cmd_trial_summary)

    p_baseline = sub.add_parser(
        "baseline-freeze",
        help="Freeze v0.5 baseline artifacts under reports/baselines/ (no case overwrite)",
    )
    p_baseline.add_argument("--system-version", default=BASELINE_SYSTEM_VERSION)
    p_baseline.add_argument("--system-commit", default=BASELINE_COMMIT)
    p_baseline.add_argument("--out", help="Output baseline directory override")
    p_baseline.add_argument(
        "--run-pytest",
        action="store_true",
        help="Also run pytest and store pytest_result.txt",
    )
    p_baseline.set_defaults(func=cmd_baseline_freeze)

    p_dataset = sub.add_parser(
        "dataset-manifest",
        help="Ensure/validate data/evaluation/dataset_manifest.json",
    )
    p_dataset.add_argument("--path", help="Manifest path override")
    p_dataset.set_defaults(func=cmd_dataset_manifest)

    p_eval_ds = sub.add_parser(
        "eval-document-set",
        help="Run Generic Document Set benchmark (EC-SW MDTM + General Report)",
    )
    p_eval_ds.add_argument(
        "--manifest",
        default=str(PROJECT_ROOT / "data" / "eval" / "document_set_benchmark" / "manifest.json"),
        help="Benchmark manifest path",
    )
    p_eval_ds.add_argument("--domains", help="Comma-separated domains (ec_sw,general_report)")
    p_eval_ds.add_argument("--case-ids", help="Comma-separated case_id filter")
    p_eval_ds.add_argument("--output-dir", help="Results root directory")
    p_eval_ds.add_argument("--no-writer", action="store_true", help="Skip writer stage (still gated path)")
    p_eval_ds.add_argument("--repeat", type=int, default=1)
    p_eval_ds.add_argument("--fail-on-unsafe", action="store_true")
    p_eval_ds.add_argument("--json", action="store_true", help="Print full summary JSON")
    p_eval_ds.set_defaults(func=cmd_eval_document_set)

    p_eval_ds2 = sub.add_parser(
        "eval-document-set-v2",
        help="Run Document Set Benchmark v2 (regression/development/holdout)",
    )
    p_eval_ds2.add_argument(
        "--manifest",
        default=str(PROJECT_ROOT / "data" / "eval" / "document_set_benchmark_v2" / "manifest.json"),
    )
    p_eval_ds2.add_argument(
        "--split",
        default="regression,development,holdout",
        help="Comma-separated splits",
    )
    p_eval_ds2.add_argument(
        "--domains",
        help="Comma-separated domains (ec_sw,general_report,business_proposal)",
    )
    p_eval_ds2.add_argument("--output-dir", help="Results root directory")
    p_eval_ds2.add_argument("--no-writer", action="store_true")
    p_eval_ds2.add_argument("--repeat", type=int, default=1)
    p_eval_ds2.add_argument("--run-metamorphic", action="store_true", default=True)
    p_eval_ds2.add_argument("--run-format-check", action="store_true", default=True)
    p_eval_ds2.add_argument("--fail-on-unsafe", action="store_true")
    p_eval_ds2.add_argument("--fail-on-protocol-violation", action="store_true")
    p_eval_ds2.add_argument("--json", action="store_true")
    p_eval_ds2.set_defaults(func=cmd_eval_document_set_v2)

    p_pilot_run = sub.add_parser(
        "run-pilot-session",
        help="Run a Real User Document Pilot v2 scenario end-to-end (non-interactive)",
    )
    p_pilot_run.add_argument("--scenario", required=True, help="Scenario id e.g. pilot_ec_req_single")
    p_pilot_run.add_argument("--participant-id", help="Participant id override (default: anonymous Pxxx)")
    p_pilot_run.add_argument(
        "--routing-mode",
        default="assisted",
        choices=["assisted", "auto", "explicit"],
        help="Document identity routing mode (default: assisted)",
    )
    p_pilot_run.add_argument(
        "--dry-review",
        action="store_true",
        help="Auto-HOLD all pending review items (never approves; safe default for CI)",
    )
    p_pilot_run.add_argument(
        "--approve-all",
        action="store_true",
        help="Auto-APPROVE all pending review items (still requires --writer-enabled to attempt a write)",
    )
    p_pilot_run.add_argument(
        "--writer-enabled",
        action="store_true",
        help="Allow the gated copy-only writer to run (only takes effect with --approve-all "
        "AND CONTROLLED_WRITER_ENABLED=true in the environment); default is writer disabled",
    )
    p_pilot_run.add_argument("--root", help="Pilot sessions root override (default: data/pilot/real_user_document_pilot/sessions)")
    p_pilot_run.set_defaults(func=cmd_run_pilot_session)

    p_demo_mat = sub.add_parser(
        "materialize-pilot-demo",
        help="Copy pilot fixtures into data/pilot/demo/ with README / Change Request / Expected Result",
    )
    p_demo_mat.add_argument("--force", action="store_true", help="Overwrite existing demo .docx copies")
    p_demo_mat.set_defaults(func=cmd_materialize_pilot_demo)

    p_demo_run = sub.add_parser(
        "run-pilot-demo",
        help="Run EC-SW / General Report / Business Proposal flagship demo sessions end-to-end",
    )
    p_demo_run.add_argument(
        "--approve-all",
        action="store_true",
        help="Auto-APPROVE review items (default is dry-review HOLD; safe for presentation)",
    )
    p_demo_run.add_argument(
        "--writer-enabled",
        action="store_true",
        help="Attempt gated copy-only writer (needs CONTROLLED_WRITER_ENABLED=true)",
    )
    p_demo_run.add_argument("--root", help="Pilot sessions root override")
    p_demo_run.set_defaults(func=cmd_run_pilot_demo)

    p_pilot_eval = sub.add_parser(
        "evaluate-pilot",
        help="Aggregate Real User Document Pilot v2 sessions into completion/accuracy/writer/usability/safety scorecards",
    )
    p_pilot_eval.add_argument("--session-ids", help="Comma-separated session ids (default: all sessions in manifest)")
    p_pilot_eval.add_argument("--root", help="Pilot sessions root override")
    p_pilot_eval.add_argument("--output-dir", help="Output directory for pilot_run_*.json (default: data/pilot/real_user_document_pilot/runs)")
    p_pilot_eval.add_argument("--json", action="store_true", help="Print full scorecards JSON")
    p_pilot_eval.set_defaults(func=cmd_evaluate_pilot)

    args = parser.parse_args(argv)

    return args.func(args)





if __name__ == "__main__":

    raise SystemExit(main())

