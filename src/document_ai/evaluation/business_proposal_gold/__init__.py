# -*- coding: utf-8 -*-
"""Business Proposal node gold labeling & blind evaluation (Cycle 6).

This package builds REQUIRED/AMBIGUOUS/OPTIONAL/NOT_APPLICABLE node gold labels
for the ``business_proposal`` domain of ``document_set_benchmark_v2`` **from
document structure and change_request text only** — it never reads prediction
artifacts (ranking results, alignments, structural match matrices, etc.) to
derive or adjust labels.

Modules:

- ``schema``: gold row dataclasses.
- ``policy``: deterministic mode/primary-selection policy.
- ``document_inventory``: DOCX structure scanner (headings/paragraphs/tables/sections).
- ``labeling_pass``: two independent labeling passes + disagreement detection.
- ``validation``: gold row validation rules.
- ``protocol``: draft/review/sealed directory + hash/seal/freeze helpers.
- ``project_to_benchmark``: project sealed gold into benchmark label JSONLs.
- ``official_metrics``: official (gold-based) node metrics for BP REQUIRED cases.
- ``error_analysis``: miss classification taxonomy.
- ``audit``: case labeling audit table.
"""

from __future__ import annotations
