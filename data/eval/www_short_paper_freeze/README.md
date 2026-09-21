# WWW Short Paper Freeze Pack

Locked artifacts for slides / short-paper draft. Start at [`SNAPSHOT.md`](SNAPSHOT.md).

| path | content |
|---|---|
| `SNAPSHOT.md` | **Final numbers** + venue/claim locks |
| `reports/paper_safety_first.*` | holdout / dev / full Safety-first tables |
| `reports/sealed_holdout_split.json` | sealed holdout case ids |
| `reports/sandbox_ablation_mu.*` | full vs no_gate / no_copy_only / no_closure |
| `reports/mu_scorecard*` | μ scorecard dump |
| `reports/mu_pilot_key_alignment.json` | Pilot scorecard ↔ μ key map |
| `pilot_mu_table.*` | Pilot μ=0 one-table |
| `field_f1_holdout_live.*` | secondary structured Field F1 cells |
| `examples/failure_mode_live.*` | live failure-mode paper example (`case_025`) |
| `ABLATION_INTERPRETATION.md` | device-removal reading for RQ3 |
| `figures/` | camera-ready PNG/PDF |

**Policy:** do not retune hyperparameters against holdout after this freeze.
