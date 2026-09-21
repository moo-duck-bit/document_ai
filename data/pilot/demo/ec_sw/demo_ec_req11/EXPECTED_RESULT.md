# Expected Result

- Domain: `ec_sw`
- Scenario: `pilot_ec_req_single`
- Talk track: 요구사항 ID가 있는 추적성 행을 찾아 검토·승인 후 복사본을 남긴다.
- Writer hint: `True`
- Failure / special: `wrong_req_row, original_modified`

Expected user path:
1. Upload document copy
2. Confirm identity / domain pack
3. Analyze change request
4. Review candidates (APPROVE / REJECT / HOLD)
5. Optional gated copy-only writer
6. Diff / validation / download / human review
