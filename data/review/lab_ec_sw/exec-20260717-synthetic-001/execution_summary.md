# Execution Summary — exec-20260717-synthetic-001

- case_id: `lab_ec_sw`
- executed_at: 2026-07-17T14:30:00Z
- executor: document-ai-synthetic-fixture
- synthetic: True
- result_count: 4

| Test ID | Status | Actual (truncated) | Evidence |
|---------|--------|------------------|----------|
| SI-01 | PASS | TLS 1.2+ enforced on API gateway; certificate chain validate | 1 |
| IA-01-T01 | FAIL | Account lockout triggered after 3 failed attempts but notifi | 1 |
| UC-01 | NOT_EXECUTED |  | 0 |
| DC-01 | REVIEW_REQUIRED | Encryption-at-rest configuration partially documented; manua | 1 |
