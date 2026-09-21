# -*- coding: utf-8 -*-
"""Pilot demo package — materialize sample docs + run flagship demo sessions.

Does not change analysis/ranking/writer engines. Reuses ``pilot_v2`` scenarios
and orchestrator only.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from document_ai.pilot_v2 import cli_support, scenarios

REPO = Path(__file__).resolve().parents[3]
DEMO_ROOT = REPO / "data" / "pilot" / "demo"
DEMO_SCENARIOS_JSON = DEMO_ROOT / "demo_scenarios.json"

# Presentation / release demos (subset of the 12 pilot scenarios + aliases).
FLAGSHIP_SCENARIO_IDS: tuple[str, ...] = (
    "pilot_ec_req_single",
    "pilot_gr_methodology",
    "pilot_bp_budget",
)

DEMO_CATALOG: list[dict[str, Any]] = [
    {
        "demo_id": "demo_ec_req11",
        "scenario_id": "pilot_ec_req_single",
        "domain": "ec_sw",
        "title": "EC-SW · Req.11 변경",
        "talk_track": "요구사항 ID가 있는 추적성 행을 찾아 검토·승인 후 복사본을 남긴다.",
        "flagship": True,
    },
    {
        "demo_id": "demo_ec_multi_req",
        "scenario_id": "pilot_ec_design_review",
        "domain": "ec_sw",
        "title": "EC-SW · 복수 Req 영향",
        "talk_track": "여러 요구사항 ID가 함께 언급될 때 후보를 나란히 검토한다.",
        "flagship": False,
    },
    {
        "demo_id": "demo_ec_semantic",
        "scenario_id": "pilot_ec_semantic",
        "domain": "ec_sw",
        "title": "EC-SW · 의미 기반 요청",
        "talk_track": "ID 없이 정책 문구만 있을 때 REVIEW가 뜨는 흐름을 보여준다.",
        "flagship": False,
    },
    {
        "demo_id": "demo_ec_no_impact",
        "scenario_id": "pilot_ec_no_impact",
        "domain": "ec_sw",
        "title": "EC-SW · 무관 요청",
        "talk_track": "문서와 무관한 요청은 영향이 없거나 Writer가 막혀야 한다.",
        "flagship": False,
    },
    {
        "demo_id": "demo_gr_methodology",
        "scenario_id": "pilot_gr_methodology",
        "domain": "general_report",
        "title": "일반보고서 · 방법론 수정",
        "talk_track": "방법론 섹션을 찾아 데이터 출처 보강 요청을 검토한다.",
        "flagship": True,
    },
    {
        "demo_id": "demo_gr_schedule",
        "scenario_id": "pilot_gr_schedule_table",
        "domain": "general_report",
        "title": "일반보고서 · 일정표 변경",
        "talk_track": "일정 표 셀을 대상으로 하는 변경을 보여준다.",
        "flagship": False,
    },
    {
        "demo_id": "demo_gr_conclusion",
        "scenario_id": "pilot_gr_conclusion",
        "domain": "general_report",
        "title": "일반보고서 · 결론 추가",
        "talk_track": "결론·향후 계획 문단 후보를 검토한다.",
        "flagship": False,
    },
    {
        "demo_id": "demo_gr_no_impact",
        "scenario_id": "pilot_gr_no_impact",
        "domain": "general_report",
        "title": "일반보고서 · No-impact",
        "talk_track": "표지 색상처럼 본문과 무관한 요청의 대조 케이스.",
        "flagship": False,
    },
    {
        "demo_id": "demo_bp_budget",
        "scenario_id": "pilot_bp_budget",
        "domain": "business_proposal",
        "title": "사업제안서 · 예산 변경",
        "talk_track": "예산 표·인건비 항목을 찾아 승인 후 복사본을 만든다.",
        "flagship": True,
    },
    {
        "demo_id": "demo_bp_schedule",
        "scenario_id": "pilot_bp_schedule",
        "domain": "business_proposal",
        "title": "사업제안서 · 수행 일정",
        "talk_track": "수행 일정 문구·표 후보를 검토한다.",
        "flagship": False,
    },
    {
        "demo_id": "demo_bp_risk",
        "scenario_id": "pilot_bp_risk",
        "domain": "business_proposal",
        "title": "사업제안서 · 위험관리 보강",
        "talk_track": "위험 대응 문단을 찾아 보강 요청을 검토한다.",
        "flagship": False,
    },
    {
        "demo_id": "demo_bp_labor_cell",
        "scenario_id": "pilot_bp_no_impact",
        "domain": "business_proposal",
        "title": "사업제안서 · 인건비 셀(고위험)",
        "talk_track": "셀 단위 고위험 변경은 자동 승인 없이 REVIEW/차단을 강조한다.",
        "flagship": False,
    },
]


def _domain_dir(domain: str) -> Path:
    return DEMO_ROOT / domain


def materialize_demo_dataset(*, force: bool = False) -> dict[str, Any]:
    """Copy pilot fixtures into ``data/pilot/demo/{domain}/`` with README sidecars."""
    scenarios.ensure_scenarios_json()
    written: list[str] = []
    for row in DEMO_CATALOG:
        sc = scenarios.get_scenario(row["scenario_id"])
        fixture = scenarios.ensure_fixture(sc)
        domain_dir = _domain_dir(row["domain"])
        demo_dir = domain_dir / row["demo_id"]
        demo_dir.mkdir(parents=True, exist_ok=True)
        dest_docx = demo_dir / fixture.name
        if force or not dest_docx.is_file():
            shutil.copy2(fixture, dest_docx)
        cr_path = demo_dir / "CHANGE_REQUEST.md"
        exp_path = demo_dir / "EXPECTED_RESULT.md"
        readme = demo_dir / "README.md"
        cr_path.write_text(
            f"# Change Request\n\n{sc.change_request}\n",
            encoding="utf-8",
        )
        exp_path.write_text(
            "\n".join(
                [
                    "# Expected Result",
                    "",
                    f"- Domain: `{sc.domain}`",
                    f"- Scenario: `{sc.scenario_id}`",
                    f"- Talk track: {row['talk_track']}",
                    f"- Writer hint: `{sc.writer_enabled_hint}`",
                    f"- Failure / special: `{', '.join(sc.failure_conditions) or 'none'}`",
                    "",
                    "Expected user path:",
                    "1. Upload document copy",
                    "2. Confirm identity / domain pack",
                    "3. Analyze change request",
                    "4. Review candidates (APPROVE / REJECT / HOLD)",
                    "5. Optional gated copy-only writer",
                    "6. Diff / validation / download / human review",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        readme.write_text(
            "\n".join(
                [
                    f"# {row['title']}",
                    "",
                    f"- demo_id: `{row['demo_id']}`",
                    f"- scenario_id: `{row['scenario_id']}`",
                    f"- document: `{dest_docx.name}`",
                    f"- flagship: `{row['flagship']}`",
                    "",
                    row["talk_track"],
                    "",
                    "See `CHANGE_REQUEST.md` and `EXPECTED_RESULT.md`.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        written.append(row["demo_id"])

    DEMO_ROOT.mkdir(parents=True, exist_ok=True)
    (DEMO_ROOT / "README.md").write_text(
        "\n".join(
            [
                "# Pilot Demo Dataset",
                "",
                "Presentation and pilot sample documents. Fixtures are **copies** of",
                "`data/pilot/real_user_document_pilot/scenarios/fixtures/` — never",
                "benchmark, Desktop, or `data/examples` originals.",
                "",
                "## Layout",
                "",
                "```",
                "data/pilot/demo/",
                "  ec_sw/<demo_id>/",
                "  general_report/<demo_id>/",
                "  business_proposal/<demo_id>/",
                "  demo_scenarios.json",
                "  results/          # produced by run-pilot-demo",
                "```",
                "",
                f"Catalog size: {len(DEMO_CATALOG)} demos ({len(FLAGSHIP_SCENARIO_IDS)} flagship).",
                "",
                "Materialize / refresh:",
                "",
                "```powershell",
                "python -m document_ai.cli materialize-pilot-demo",
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )
    DEMO_SCENARIOS_JSON.write_text(
        json.dumps({"count": len(DEMO_CATALOG), "demos": DEMO_CATALOG}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return {"demo_root": str(DEMO_ROOT), "demos": written, "count": len(written)}


def run_flagship_demos(
    *,
    dry_review: bool = True,
    approve_all: bool = False,
    writer_enabled: bool = False,
    root: Path | None = None,
) -> dict[str, Any]:
    """Run EC-SW / GR / BP flagship demos end-to-end and write a results bundle."""
    materialize_demo_dataset()
    run_id = datetime.now(timezone.utc).strftime("demo_%Y%m%dT%H%M%SZ")
    out_dir = DEMO_ROOT / "results" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    sessions: list[dict[str, Any]] = []
    exit_codes: list[int] = []
    for sid in FLAGSHIP_SCENARIO_IDS:
        result, code = cli_support.run_pilot_session(
            sid,
            participant_id="DEMO",
            routing_mode="assisted",
            dry_review=dry_review and not approve_all,
            approve_all=approve_all,
            writer_enabled=writer_enabled,
            root=root,
        )
        exit_codes.append(code)
        session = (result.get("session") if isinstance(result, dict) else None) or {}
        row = {
            "scenario_id": sid,
            "exit_code": code,
            "session_id": session.get("session_id") or result.get("session_id"),
            "status": session.get("status"),
            "writer_status": (session.get("writer_result") or {}).get("status"),
            "result": result,
        }
        sessions.append(row)
        (out_dir / f"{sid}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    summary = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "flagship_scenario_ids": list(FLAGSHIP_SCENARIO_IDS),
        "dry_review": dry_review,
        "approve_all": approve_all,
        "writer_enabled": writer_enabled,
        "sessions": [
            {
                "scenario_id": s["scenario_id"],
                "session_id": s["session_id"],
                "exit_code": s["exit_code"],
                "status": s["status"],
                "writer_status": s["writer_status"],
            }
            for s in sessions
        ],
        "all_exit_ok": all(c == 0 for c in exit_codes),
        "output_dir": str(out_dir),
        "note": "Diff/validation artifacts live inside each pilot session workspace under data/pilot/real_user_document_pilot/sessions/<session_id>/",
    }
    (out_dir / "DEMO_RUN_SUMMARY.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "README.md").write_text(
        "\n".join(
            [
                f"# Demo run `{run_id}`",
                "",
                "Flagship sessions:",
                "",
                *[
                    f"- `{s['scenario_id']}` → session `{s['session_id']}` (exit {s['exit_code']}, writer {s['writer_status']})"
                    for s in summary["sessions"]
                ],
                "",
                "Open UI: `http://127.0.0.1:8000/pilot-v2`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return summary
