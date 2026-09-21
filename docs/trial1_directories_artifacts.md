# Trial 1 디렉터리·산출물

> **Trial 1 (Mindrium XA) — 현재 사용 문서**  
> case: `data/cases/mindrium_xa` · trial_id: `trial-001-mindrium-xa`  
> 인덱스: `docs/README.md` § Trial 1

## 루트

```
data/trials/trial-001-mindrium-xa/
├── reference/                    # Mindrium 원본 MDSR/MDDR/XXCS
├── input/                        # change_request 등
├── workdir/                      # 과거 실험 작업본 (참고)
├── generated/                    # INVALID_FOR_HR (재생성·오염)
├── generated_clean_mindrium/     # INVALID_FOR_HR (skeleton)
├── generated_patch_preserving/   # patch-in-place canonical
│   ├── output_mdsr.docx
│   └── output_mddr.docx          # XXCS 없음
├── logs/visual_qa/               # Word→PDF 렌더 증거
├── PRE_HUMAN_REVIEW_REPORT.md
├── GENERATION_CORRECTION_REPORT.md
└── execution_report.json
```

## Human Review

`execution_report.json`의 `pre_human_review_ready`가 true일 때만:

- MDSR/MDDR: `generated_patch_preserving/`
- XXCS: OUT_OF_SCOPE (reference만 유지)
