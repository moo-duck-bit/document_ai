# Execution Summary — exec-20260718-runner-synthetic-001

- case_id: `lab_ec_sw`
- executed_at: 2026-07-17T16:08:10Z
- executor: document-ai-security-runner
- synthetic: True
- result_count: 9

| Test ID | Status | Actual (truncated) | Evidence |
|---------|--------|------------------|----------|
| SI-01 | PASS | TLS connection succeeded with TLSv1.3; certificate valid for | 1 |
| SI-02 | FAIL | TLSv1.0 is below required TLSv1.2 | 1 |
| SI-03 | PASS | HTTP 200; required security headers satisfied | 1 |
| SI-04 | FAIL | missing required header: strict-transport-security; optional | 1 |
| SI-05 | REVIEW_REQUIRED | HTTP header result uncertain: TimeoutError: synthetic timeou | 1 |
| SI-06 | PASS | API health endpoint returned HTTP 200 in 25ms | 1 |
| SI-07 | FAIL | HTTP status 503 not in [200] | 1 |
| SI-08 | PASS | TCP connection to allowlisted fixture.example.com:443 succee | 1 |
| SI-09 | REVIEW_REQUIRED | TCP connectivity uncertain: TimeoutError: synthetic connecti | 1 |
