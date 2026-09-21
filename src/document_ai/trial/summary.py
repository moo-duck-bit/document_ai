"""trial-summary: reports, presentation summaries, CSV tables."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from document_ai.trial.paths import load_manifest, read_json, rel_to_project, save_manifest, trial_dir, write_json, write_text


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def summarize_trial(trial: str | Path) -> dict[str, Any]:
    path = trial_dir(trial)
    manifest = load_manifest(path)
    metrics_path = path / "metrics.json"
    if not metrics_path.exists():
        from document_ai.trial.analyze import analyze_trial

        analyze_trial(path)
    metrics = read_json(metrics_path)
    generation = (
        read_json(path / "generation_manifest.json")
        if (path / "generation_manifest.json").exists()
        else {}
    )

    synthetic = bool(manifest.get("synthetic"))
    completion_label = (
        "synthetic_framework_validation"
        if synthetic
        else (
            "real_world_trial_complete"
            if metrics.get("real_world_trial_complete")
            else "real_trial_pending"
        )
    )

    presentation = {
        "trial_id": manifest.get("trial_id"),
        "system_version": manifest.get("system_version"),
        "system_commit": manifest.get("system_commit"),
        "trial_type": manifest.get("trial_type"),
        "case_id": manifest.get("case_id"),
        "completion_label": completion_label,
        "synthetic": synthetic,
        "baseline_metrics": manifest.get("baseline_metrics_snapshot"),
        "trial_metrics": metrics,
        "document_scores": {
            "quality": ((generation.get("quality") or {}).get("scores") or {}),
            "validation": ((generation.get("validation") or {}).get("scores") or {}),
        },
        "human_ratings": metrics.get("human_ratings"),
        "time_data": metrics.get("time"),
        "error_counts": metrics.get("error_counts"),
        "edit_ratios": (metrics.get("auto") or {}).get("diff"),
        "traceability": (metrics.get("auto") or {}).get("traceability"),
        "readiness": metrics.get("readiness"),
    }
    write_json(path / "presentation" / "presentation_summary.json", presentation)
    write_json(path / "presentation_summary.json", presentation)

    q = presentation["document_scores"]["quality"]
    v = presentation["document_scores"]["validation"]
    time_data = presentation["time_data"] or {}
    md = f"""# Presentation Summary — {manifest.get('trial_id')}

## 1. 프로젝트 목표

완성 문서와 입력 자료로 MDSR/MDDR/XXCS를 생성하고, 추적성·품질·human review를
포함한 Document Harness를 구축한다.

## 2. v0.5 시스템 구조

- system_version: `{manifest.get('system_version')}`
- system_commit: `{manifest.get('system_commit')}`
- Rule-based + Retrieval(light) + (LLM free-text는 이번 Trial 범위 밖)

## 3. 현재 지원 문서

{', '.join(manifest.get('document_types') or [])}

## 4. Trial 목적

v0.5 기준선에서 실제 업무 유사 환경의 문서 작성 수준을 측정한다.
이번 실행 completion_label: **{completion_label}**

## 5. Trial 입력과 조건

- case_id: `{manifest.get('case_id')}`
- trial_type: `{manifest.get('trial_type')}`
- synthetic: `{synthetic}`
- data_leakage_checked: `{manifest.get('data_leakage_checked')}`

## 6. 생성 결과

- outputs: `{json.dumps(generation.get('outputs') or {}, ensure_ascii=False)}`
- duration_seconds: `{generation.get('duration_seconds')}`

## 7. 자동 평가 결과

- quality overall: `{q.get('overall')}`
- validation overall: `{v.get('overall')}`

## 8. 사람 평가 결과

- human record present: `{metrics.get('human_record_present')}`
- ratings overall: `{((metrics.get('human_ratings') or {}).get('overall'))}`

## 9. 수정 시간

- time_saving_rate: `{time_data.get('time_saving_rate')}`
- status: `{time_data.get('status')}`
- reason: `{time_data.get('reason', '')}`

## 10. 오류 유형 분포

```json
{json.dumps(metrics.get('error_counts') or {}, ensure_ascii=False, indent=2)}
```

## 11. 잘된 사례 / 12. 실패 사례

실무 Trial 완료 후 reviewer notes와 verified annotations를 채워 발표에 사용한다.
synthetic 실행에서는 사례를 실적으로 보고하지 않는다.

## 13. 현재 한계

- Embedding retrieval / LLM free-text 미적용
- Real-world 입력·human revision이 없으면 Trial 1 미완료
- Security runner는 synthetic MVP로 동결

## 14. Trial 2 개선 계획

Trial 1 오류 분석 후 Embedding Retrieval → Hybrid + LLM free-text 우선순위를 결정한다.
"""
    write_text(path / "presentation" / "presentation_summary.md", md)
    write_text(path / "presentation_summary.md", md)

    report = f"""# Trial Report — {manifest.get('trial_id')}

## Status

- completion_label: `{completion_label}`
- manifest_status: `{manifest.get('status')}`
- synthetic: `{synthetic}`
- real_world_trial_complete: `{metrics.get('real_world_trial_complete')}`

## System freeze

- version: `{manifest.get('system_version')}`
- commit: `{manifest.get('system_commit')}`

## Automatic metrics

```json
{json.dumps(metrics.get('auto') or {}, ensure_ascii=False, indent=2)}
```

## Human metrics

```json
{json.dumps({
  'ratings': metrics.get('human_ratings'),
  'time': metrics.get('time'),
  'readiness': metrics.get('readiness'),
}, ensure_ascii=False, indent=2)}
```

## Notes

This report must not claim "Real-world Trial 1 complete" unless
`real_world_trial_complete` is true and `synthetic` is false.
"""
    write_text(path / "trial_report.md", report)
    write_text(path / "reports" / "trial_report.md", report)

    tables = path / "reports" / "tables"
    baseline = manifest.get("baseline_metrics_snapshot") or {}
    _write_csv(
        tables / "system_baseline.csv",
        [
            {
                "system_version": manifest.get("system_version"),
                "harness_benchmark_overall": (
                    (baseline.get("harness_benchmark") or {}).get("overall_score")
                ),
                "lab_e2e_status": ((baseline.get("lab_ec_sw_e2e") or {}).get("status")),
                "lab_quality": ((baseline.get("lab_ec_sw_e2e") or {}).get("quality_overall")),
                "lab_validation": ((baseline.get("lab_ec_sw_e2e") or {}).get("validation_overall")),
            }
        ],
        [
            "system_version",
            "harness_benchmark_overall",
            "lab_e2e_status",
            "lab_quality",
            "lab_validation",
        ],
    )
    _write_csv(
        tables / "document_quality.csv",
        [
            {
                "trial_id": manifest.get("trial_id"),
                "quality_overall": q.get("overall"),
                "validation_overall": v.get("overall"),
                "structure": q.get("structure"),
                "traceability": q.get("traceability"),
            }
        ],
        ["trial_id", "quality_overall", "validation_overall", "structure", "traceability"],
    )
    _write_csv(
        tables / "human_review.csv",
        [
            {
                "trial_id": manifest.get("trial_id"),
                "human_overall": ((metrics.get("human_ratings") or {}).get("overall")),
                "documents_rated": ((metrics.get("human_ratings") or {}).get("documents_rated")),
                "record_present": metrics.get("human_record_present"),
            }
        ],
        ["trial_id", "human_overall", "documents_rated", "record_present"],
    )
    _write_csv(
        tables / "time_savings.csv",
        [
            {
                "trial_id": manifest.get("trial_id"),
                "time_saving_rate": time_data.get("time_saving_rate"),
                "status": time_data.get("status"),
                "manual_baseline_minutes": time_data.get("manual_baseline_minutes"),
                "total_assisted_minutes": time_data.get("total_assisted_minutes"),
            }
        ],
        [
            "trial_id",
            "time_saving_rate",
            "status",
            "manual_baseline_minutes",
            "total_assisted_minutes",
        ],
    )
    error_rows = [
        {"trial_id": manifest.get("trial_id"), "error_type": k, "count": v}
        for k, v in (metrics.get("error_counts") or {}).items()
    ] or [{"trial_id": manifest.get("trial_id"), "error_type": "", "count": 0}]
    _write_csv(tables / "error_taxonomy.csv", error_rows, ["trial_id", "error_type", "count"])

    edit_rows = []
    for doc, meta in ((metrics.get("auto") or {}).get("diff") or {}).items():
        edit_rows.append(
            {
                "document_type": doc,
                "unchanged_paragraph_ratio": meta.get("unchanged_paragraph_ratio"),
                "modified_paragraph_ratio": meta.get("modified_paragraph_ratio"),
                "edit_burden_score": meta.get("document_level_edit_burden_score"),
                "status": meta.get("status"),
            }
        )
    if not edit_rows:
        edit_rows = [
            {
                "document_type": "",
                "unchanged_paragraph_ratio": "",
                "modified_paragraph_ratio": "",
                "edit_burden_score": "",
                "status": "SKIPPED",
            }
        ]
    _write_csv(
        tables / "edit_burden.csv",
        edit_rows,
        [
            "document_type",
            "unchanged_paragraph_ratio",
            "modified_paragraph_ratio",
            "edit_burden_score",
            "status",
        ],
    )

    if metrics.get("real_world_trial_complete") and not synthetic:
        manifest["status"] = "completed"
        save_manifest(path, manifest)

    return {
        "ok": True,
        "trial_dir": rel_to_project(path),
        "completion_label": completion_label,
        "presentation_summary_md": rel_to_project(path / "presentation_summary.md"),
        "trial_report_md": rel_to_project(path / "trial_report.md"),
        "metrics_json": rel_to_project(path / "metrics.json"),
    }
