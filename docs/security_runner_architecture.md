# Read-only 보안 Runner 아키텍처

> **Historical (lab_ec_sw / JM COLLECTION)** — **Not used in Trial 1**  
> 이 문서는 과거 스프린트·벤치마크·진단 기록이다.  
> Real-world Trial 1 확정 case는 **Mindrium XA** (`trial-001-mindrium-xa`)이다.  
> Trial 1 문서: `docs/trial1_case_decision_mindrium.md`, `docs/README.md` § Trial 1


## 범위

Runner는 allowlist 기반 read-only 검사 4종을 실행하고
`schemas/security_test_execution.schema.json`을 생성한다.

결과를 자동으로 import·승인·렌더링하지 않는다.

```text
security_runner_config.json
        |
run-security-tests
        |
        +-- policy 검증 (method, allowlist, SSRF, 제한값)
        +-- check registry
        +-- read-only executor
        +-- sanitized evidence writer
        |
execution JSON + evidence/
        |
import-security-results -> review -> selected results -> XXCS
```

## 모듈

| 모듈 | 역할 |
|------|------|
| `models.py` | Check 프로토콜, 결과·컨텍스트·evidence 모델 |
| `registry.py` | 내장 runner 등록 |
| `executor.py` | 검증, retry, rate limit, metrics, execution JSON |
| `policy.py` | allowlist, method, URL 검증, SSRF 규칙 |
| `evidence.py` | 헤더 마스킹, body hash, JSON evidence, manifest |
| `runners/tls_check.py` | TLS 협상 및 인증서 정책 |
| `runners/http_header_check.py` | HTTP 보안 헤더 및 redirect |
| `runners/api_health_check.py` | 제한된 GET/HEAD health endpoint |
| `runners/port_connectivity_check.py` | allowlist 단일 TCP 포트, banner 금지 |

## Check 인터페이스

```python
class SecurityCheck:
    check_id: str
    security_test_id: str

    def validate_config(self, config) -> list[str]: ...
    def run(self, context) -> SecurityCheckResult: ...
```

`SecurityCheckResult` 구성:

- `security_test_id`
- `status`
- `actual_result`
- `evidence`
- `started_at`, `completed_at`, `duration_ms`
- `error`
- `metadata` (runner, attempts, 제한된 관측값)

## 지원 검사

| Runner | 네트워크 동작 | 금지 동작 |
|--------|---------------|-----------|
| `tls_check` | TLS handshake | 명령 실행 금지 |
| `http_header_check` | GET 또는 HEAD | POST·인증·cookie 금지 |
| `api_health_check` | GET 또는 HEAD | body 저장 금지 |
| `port_connectivity_check` | 단일 TCP connect | scan·send·recv·banner 금지 |

## Runner와 Document Harness

Runner는 기존 execution import 인터페이스의 producer일 뿐이다. import,
review 선택, XXCS 렌더링, validation은 Document Harness가 담당한다.

Runner는 `reviewer_verified`나 `selected_for_report`를 설정할 수 없다.

## Operation Harness 경계

Runner는 다음을 하지 않는다.

- 실시간 로그 모니터링
- 장애 분석
- 서비스 재시작
- 방화벽·컨테이너·계정·데이터 변경
- shell 명령·subprocess 실행
- GPU·disk·kernel·journal telemetry 수집

인프라·복구 자동화는 별도의 향후 Runner 영역이다.

## Execution 출력

```json
{
  "case_id": "lab_ec_sw",
  "execution_id": "exec-20260718-runner-synthetic-001",
  "executed_at": "2026-07-17T16:08:10Z",
  "synthetic": true,
  "executor": {
    "type": "script",
    "name": "document-ai-security-runner",
    "version": "0.1.0"
  },
  "environment": {
    "target": "synthetic_fixture",
    "base_url": "https://fixture.example.com",
    "host": "fixture.example.com",
    "notes": "Synthetic fixture execution; no network requests performed."
  },
  "results": []
}
```
