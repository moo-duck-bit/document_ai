# User Scenario Runner

Independent evaluation harness that reuses Trial 2 B1–B5 **library** code.

**Not a new Trial.** Does not modify Trial 1/2 frozen evidence.

## Quick start

1. Create a scenario folder:

```
data/user_scenarios/<scenario_id>/
  input/
    change_request.txt
    reference/
      MDSR.docx          # any filename containing MDSR/mdsr/요구사항
      MDDR.docx          # any filename containing MDDR/mddr/설계
  output/                # created by runner (do not put secrets here)
```

2. Run:

```powershell
python scripts/run_user_scenario.py --scenario data/user_scenarios/<scenario_id>
```

3. Review:

- `output/documents/updated_MDSR.docx`
- `output/documents/updated_MDDR.docx`
- `output/review/CHANGE_SUMMARY.md`
- `output/review/REVIEW_REQUIRED.md`
- `output/execution_report.json`

## Rules

- Inputs are never overwritten (hash-checked).
- `expected_impact` / target Req IDs are **not** used.
- Frozen trials (`data/trials/trial-001-*`, `trial-002-*`) cannot be scenario roots.
- Auto-patch only when consistency is CONSISTENT; CONFLICT blocks patch.

See also: `docs/user_scenario_runner/REUSE_AND_HARDCODING_AUDIT.md`
