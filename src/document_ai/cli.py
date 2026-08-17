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

from document_ai.agents.orchestrator import run_change_pipeline
from document_ai.eval.runner import run_evaluation
from document_ai.impact.orchestrator import apply_change, compute_impact

from document_ai.intake.change_intake import (
    append_intake_log,
    draft_change_from_request,
    load_requirements_payload,
)
from document_ai.impact.change import save_change



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



    p_gen = sub.add_parser("generate", help="Fill one template from case input.json")

    p_gen.add_argument("--case", required=True, help="Case directory e.g. data/cases/mindrium_xa")

    p_gen.add_argument("--template", help="template_id override")

    p_gen.add_argument("--output", help="Output filename inside case dir")

    p_gen.set_defaults(func=cmd_generate)



    p_all = sub.add_parser("generate-all", help="Generate MDSR, MDDR, and XXCS for a case")

    p_all.add_argument("--case", required=True, help="Case directory e.g. data/cases/mindrium_xa")

    p_all.set_defaults(func=cmd_generate_all)

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

    args = parser.parse_args(argv)

    return args.func(args)





if __name__ == "__main__":

    raise SystemExit(main())

