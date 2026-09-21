# -*- coding: utf-8 -*-
"""
Generate node_evaluation_eligibility.jsonl from case structure + existing gold.

Rules are based on change_request shape / tags / document fixtures — NOT predictions.
Does not auto-mutate gold node_ids from model output.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BASE = REPO / "data" / "eval" / "document_set_benchmark"
LABELS = BASE / "labels"


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main() -> None:
    manifest = json.loads((BASE / "manifest.json").read_text(encoding="utf-8"))
    node_gold = _load_jsonl(LABELS / "node_impacts.jsonl")
    gold_by = {}
    for r in node_gold:
        gold_by.setdefault(r["case_id"], []).append(r)

    # Rule table: justified by CR type / tags / fixture notes (human-interpretable)
    # semantic_only: MDTM rows lack descriptive text → document REVIEW, no unique row → OPTIONAL
    # schedule_table: fixture has 일정 heading; template has schedule section → AMBIGUOUS group
    # no-impact / unrelated doc status → NOT_APPLICABLE
    RULES: dict[str, dict] = {
        "ec_sw_exact_req_single": {
            "mode": "REQUIRED",
            "rationale": "Exact Req. ID targets a single MDTM TABLE_ROW",
        },
        "ec_sw_exact_req_multi_mention": {
            "mode": "REQUIRED",
            "rationale": "Exact Req. ID (repeated mention) still one row",
        },
        "ec_sw_multi_req_ids": {
            "mode": "REQUIRED",
            "rationale": "Multiple exact Req. IDs → multiple required rows",
        },
        "ec_sw_design_id_only": {
            "mode": "REQUIRED",
            "rationale": "Design ID maps to a concrete MDTM row via corpus identifiers",
        },
        "ec_sw_test_id_only": {
            "mode": "REQUIRED",
            "rationale": "Test ID maps to a concrete MDTM row via corpus identifiers",
        },
        "ec_sw_semantic_only": {
            "mode": "OPTIONAL",
            "rationale": "No Req ID; MDTM cells lack descriptive text — document REVIEW only, no unique row gold",
        },
        "ec_sw_duplicate_req_row": {
            "mode": "REQUIRED",
            "rationale": "Exact Req. ID row grounding required",
        },
        "ec_sw_missing_identifier": {
            "mode": "NOT_APPLICABLE",
            "rationale": "Document UNRELATED / no node grounding expected",
        },
        "ec_sw_empty_row_context": {
            "mode": "NOT_APPLICABLE",
            "rationale": "Document UNRELATED / no node grounding expected",
        },
        "ec_sw_no_impact": {
            "mode": "NOT_APPLICABLE",
            "rationale": "No-impact marketing CR",
        },
        "ec_sw_ambiguous_request": {
            "mode": "NOT_APPLICABLE",
            "rationale": "Document-level ambiguity only; no required node",
        },
        "ec_sw_writer_blocked_review": {
            "mode": "REQUIRED",
            "rationale": "Exact Req. ID with writer gated",
        },
        "ec_sw_bad_req_format": {
            "mode": "NOT_APPLICABLE",
            "rationale": "Malformed ID → no exact node evidence expected",
        },
        "ec_sw_mdtm_only_multi_doc": {
            "mode": "REQUIRED",
            "rationale": "Exact Req. ID on MDTM only",
        },
        "ec_sw_req101_exact": {
            "mode": "REQUIRED",
            "rationale": "Exact Req. ID single row",
        },
        "gr_methodology_source": {
            "mode": "REQUIRED",
            "rationale": "Methodology section is the grounded target",
        },
        "gr_results_finding": {
            "mode": "REQUIRED",
            "rationale": "Results section is the grounded target",
        },
        "gr_conclusion_recommendation": {
            "mode": "REQUIRED",
            "rationale": "Conclusion section is the grounded target",
        },
        "gr_schedule_table": {
            "mode": "AMBIGUOUS",
            "rationale": "Fixture contains 일정 heading; template schedule section equally valid",
            "acceptable_node_ids": ["general_report_v1.schedule"],
            "acceptable_node_groups": [
                ["general_report_v1.schedule", "general_report_v1.schedule.tables"]
            ],
            "primary_node_id": "general_report_v1.schedule",
        },
        "gr_duplicate_heading": {
            "mode": "AMBIGUOUS",
            "rationale": "Duplicate 결과 headings — results section id is acceptable representative",
            "acceptable_node_ids": ["general_report_v1.results"],
            "acceptable_node_groups": [["general_report_v1.results"]],
            "primary_node_id": "general_report_v1.results",
        },
        "gr_missing_section": {
            "mode": "NOT_APPLICABLE",
            "rationale": "Nonexistent section → document UNRELATED",
        },
        "gr_semantic_similar": {
            "mode": "OPTIONAL",
            "rationale": "Semantic similarity without unique section mandate",
        },
        "gr_no_impact": {
            "mode": "NOT_APPLICABLE",
            "rationale": "No-impact CR",
        },
        "gr_table_cell": {
            "mode": "REQUIRED",
            "rationale": "Results/table section is the grounded target in fixture",
        },
    }

    elig_rows = []
    enriched_nodes = []
    now = datetime.now(timezone.utc).isoformat()

    for rel in manifest["cases"]:
        case = json.loads((BASE / rel).read_text(encoding="utf-8"))
        cid = case["case_id"]
        rule = RULES.get(cid)
        if not rule:
            raise SystemExit(f"missing rule for {cid}")
        mode = rule["mode"]
        golds = gold_by.get(cid) or []
        primary = rule.get("primary_node_id")
        if not primary and golds:
            primary = golds[0].get("node_id")
        acc = list(rule.get("acceptable_node_ids") or [])
        groups = list(rule.get("acceptable_node_groups") or [])
        if mode == "REQUIRED" and primary and primary not in acc:
            # primary is the gold; acceptable may be empty
            pass
        if mode == "AMBIGUOUS" and primary and primary not in acc:
            acc = [primary] + [a for a in acc if a != primary]

        elig_rows.append(
            {
                "case_id": cid,
                "domain": case["domain"],
                "document_id": (case.get("enabled_documents") or ["UNKNOWN"])[0],
                "node_evaluation_mode": mode,
                "primary_node_id": primary,
                "acceptable_node_ids": acc,
                "acceptable_node_groups": groups,
                "label_rationale": rule["rationale"],
                "labeled_by": "rule_based_fixture_audit",
                "labeled_at": now,
                "confidence": 0.9 if mode in {"REQUIRED", "NOT_APPLICABLE"} else 0.7,
            }
        )

        # Enrich existing node gold rows with mode fields (no id changes from predictions)
        if golds:
            for g in golds:
                enriched_nodes.append(
                    {
                        **g,
                        "node_evaluation_mode": mode,
                        "primary_node_id": primary or g.get("node_id"),
                        "acceptable_node_ids": g.get("acceptable_node_ids") or acc,
                        "acceptable_node_groups": g.get("acceptable_node_groups") or groups,
                        "label_rationale": rule["rationale"],
                        "labeled_by": "rule_based_fixture_audit",
                        "labeled_at": now,
                        "confidence": 0.9,
                    }
                )
        elif mode == "AMBIGUOUS" and primary:
            # Add justified gold for schedule/duplicate from document/template structure
            enriched_nodes.append(
                {
                    "case_id": cid,
                    "document_id": elig_rows[-1]["document_id"],
                    "node_id": primary,
                    "gold_status": "REVIEW_REQUIRED",
                    "node_evaluation_mode": mode,
                    "primary_node_id": primary,
                    "acceptable_node_ids": acc,
                    "acceptable_node_groups": groups,
                    "expected_location_type": "section",
                    "expected_node_type": "SECTION",
                    "expected_section_id": primary.split(".")[-1] if primary else None,
                    "label_rationale": rule["rationale"],
                    "labeled_by": "rule_based_fixture_audit",
                    "labeled_at": now,
                    "confidence": 0.85,
                }
            )
        # OPTIONAL / NOT_APPLICABLE: intentionally no node gold rows

    # Preserve other gold rows not overwritten: rebuild full file from enriched + untouched REQUIRED already in enriched
    # Any gold for OPTIONAL should be dropped (none currently for semantic)
    elig_path = LABELS / "node_evaluation_eligibility.jsonl"
    elig_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in elig_rows) + "\n",
        encoding="utf-8",
    )

    # Merge: for cases with existing gold use enriched; for AMBIGUOUS without prior add new
    by_key = {}
    for r in enriched_nodes:
        by_key[(r["case_id"], r["node_id"])] = r
    (LABELS / "node_impacts.jsonl").write_text(
        "\n".join(json.dumps(by_key[k], ensure_ascii=False) for k in sorted(by_key)) + "\n",
        encoding="utf-8",
    )

    proposed = {
        "automatic_gold_mutation": False,
        "note": "Eligibility + justified AMBIGUOUS schedule/duplicate gold from fixture structure; semantic_only left OPTIONAL without inventing row gold.",
        "changes": [
            {
                "case_id": "gr_schedule_table",
                "action": "add_ambiguous_node_gold",
                "primary_node_id": "general_report_v1.schedule",
                "rationale": "Fixture has 일정 heading; template exposes schedule section",
                "from_prediction": False,
            },
            {
                "case_id": "ec_sw_semantic_only",
                "action": "set_mode_optional_no_node_gold",
                "rationale": "No unique MDTM row text for CR concepts",
                "from_prediction": False,
            },
        ],
    }
    (BASE / "proposed_label_changes.json").write_text(
        json.dumps(proposed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"eligibility={len(elig_rows)} node_gold={len(by_key)}")
    modes = {}
    for r in elig_rows:
        modes[r["node_evaluation_mode"]] = modes.get(r["node_evaluation_mode"], 0) + 1
    print(modes)


if __name__ == "__main__":
    main()
