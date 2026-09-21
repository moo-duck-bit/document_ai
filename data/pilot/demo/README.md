# Pilot Demo Dataset

Presentation and pilot sample documents. Fixtures are **copies** of
`data/pilot/real_user_document_pilot/scenarios/fixtures/` — never
benchmark, Desktop, or `data/examples` originals.

## Layout

```
data/pilot/demo/
  ec_sw/<demo_id>/
  general_report/<demo_id>/
  business_proposal/<demo_id>/
  demo_scenarios.json
  results/          # produced by run-pilot-demo
```

Catalog size: 12 demos (3 flagship).

Materialize / refresh:

```powershell
python -m document_ai.cli materialize-pilot-demo
```
