# Presentation materials

| File | Use |
|------|-----|
| **[Document_AI_v2_Presentation.pptx](./Document_AI_v2_Presentation.pptx)** | **청중용 PPT — AI Engineering × Document AI** |
| [Document_AI_v2_Presentation.md](./Document_AI_v2_Presentation.md) | 원고 |
| [screenshots/](./screenshots/) | Pilot UI 실제 화면 캡처 |
| [DEMO_RUNBOOK.md](./DEMO_RUNBOOK.md) | 캡처 재생성·참고용 클릭 가이드 |
| [Document_AI_v2_Full_Presentation.pptx](./Document_AI_v2_Full_Presentation.pptx) | 이전 장편 PPT |

재생성:

```powershell
python scripts/capture_pilot_demo_screenshots.py
python scripts/build_lab_presentation.py
```

## 포인트
- 라이브 데모 없음 — PPT에 실제 `/pilot-v2` 화면으로 진행 설명
- AI Engineering: 하네스 · 평가 · 안전 · Pilot
- LLM 비사용 = 엔지니어링 결정

## PR9 paper artifacts

- `fig11_c1_c2_walkthrough.md` — Req→TRACE→copy-only→approval (RQ2)
- `mu_pilot_key_alignment.md` — Document-TNR μ ↔ Pilot Safety keys
- `sandbox_ablation_table.md` — ablation μ map + CLI
