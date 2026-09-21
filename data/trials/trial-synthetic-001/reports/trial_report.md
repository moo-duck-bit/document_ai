# Trial Report — trial-synthetic-001

## Status

- completion_label: `synthetic_framework_validation`
- manifest_status: `review_pending`
- synthetic: `True`
- real_world_trial_complete: `False`

## System freeze

- version: `v0.5-document-harness`
- commit: `d73fc18`

## Automatic metrics

```json
{
  "quality": {
    "status": "PASS",
    "scores": {
      "structure": 100.0,
      "terminology": 100.0,
      "completeness": 100.0,
      "consistency": 100.0,
      "traceability": 100.0,
      "residual_text": 84.0,
      "overall": 96.8
    }
  },
  "validation": {
    "status": "PASS",
    "scores": {
      "overall": 90.5,
      "docx_overall": 89.7,
      "mdsr": 100.0,
      "mddr": 92.0,
      "xxcs": 77.1,
      "semantic": 95.0
    }
  },
  "diff": {
    "MDSR": {
      "unchanged_paragraph_ratio": null,
      "modified_paragraph_ratio": null,
      "added_paragraph_ratio": null,
      "deleted_paragraph_ratio": null,
      "unchanged_table_cell_ratio": null,
      "modified_table_cell_ratio": null,
      "document_level_edit_burden_score": null,
      "status": "SKIPPED"
    },
    "MDDR": {
      "unchanged_paragraph_ratio": null,
      "modified_paragraph_ratio": null,
      "added_paragraph_ratio": null,
      "deleted_paragraph_ratio": null,
      "unchanged_table_cell_ratio": null,
      "modified_table_cell_ratio": null,
      "document_level_edit_burden_score": null,
      "status": "SKIPPED"
    },
    "XXCS": {
      "unchanged_paragraph_ratio": null,
      "modified_paragraph_ratio": null,
      "added_paragraph_ratio": null,
      "deleted_paragraph_ratio": null,
      "unchanged_table_cell_ratio": null,
      "modified_table_cell_ratio": null,
      "document_level_edit_burden_score": null,
      "status": "SKIPPED"
    }
  },
  "traceability": {
    "validation_overall": 90.5,
    "mdsr": 100.0,
    "mddr": 92.0,
    "xxcs": 77.1
  }
}
```

## Human metrics

```json
{
  "ratings": {
    "per_dimension": {
      "content_accuracy": null,
      "completeness": null,
      "format_compliance": null,
      "traceability": null,
      "language_quality": null,
      "practical_usability": null
    },
    "overall": null,
    "documents_rated": 0
  },
  "time": {
    "time_saving_rate": null,
    "status": "N/A",
    "reason": "manual_baseline_minutes missing",
    "manual_baseline_minutes": null,
    "total_assisted_minutes": null
  },
  "readiness": {
    "usable_without_change": [],
    "internal_review_ready": [],
    "external_delivery_ready": []
  }
}
```

## Notes

This report must not claim "Real-world Trial 1 complete" unless
`real_world_trial_complete` is true and `synthetic` is false.
