# Read-only Automated Security Test Runner MVP 상세 보고서

> **Historical (lab_ec_sw / JM COLLECTION)** — **Not used in Trial 1**  
> 이 문서는 과거 스프린트·벤치마크·진단 기록이다.  
> Real-world Trial 1 확정 case는 **Mindrium XA** (`trial-001-mindrium-xa`)이다.  
> Trial 1 문서: `docs/trial1_case_decision_mindrium.md`, `docs/README.md` § Trial 1


## 1. 요약

이번 Sprint에서 Document Harness용 **read-only 보안 시험 Runner MVP**를 구현했다.

Runner는 허용된 대상에 대해 읽기 전용 검사만 수행하고, 기존 `schemas/security_test_execution.schema.json` 형식의 execution JSON과 evidence를 생성한다. 생성 결과는 기존 `import-security-results → review → XXCS` 흐름에 그대로 연결된다.

MVP 검증은 **synthetic fixture만** 사용했으며, 외부 네트워크 요청은 수행하지 않았다.

## 2. 목표와 경계

### 목표

- 안전한 read-only 보안 시험을 자동 실행
- execution JSON + evidence 생성
- 기존 import / review / XXCS 파이프라인과 호환

### 이번 Sprint에서 하지 않은 것

| 제외 항목 | 이유 |
|-----------|------|
| Operation Harness 연동 | 별도 시스템 경계 |
| 장애 분석 / 실시간 로그 / 복구 | Runner 범위 밖 |
| 서버 상태 변경 시험 | 읽기 전용 원칙 |
| 로그인·계정 잠금·데이터 생성/삭제 | 부작용 금지 |
| 컨테이너 restart / 방화벽 변경 | 부작용 금지 |
| GPU / Docker / disk / journalctl | Local Infrastructure Runner로 이관 |
| 자동 import / 자동 승인 | Human review 분리 |

## 3. 아키텍처

```text
security_runner_config.json
        │
run-security-tests
        │
        ├── policy 검증 (method, allowlist, SSRF, 제한값)
        ├── check registry
        ├── read-only executor
        └── sanitized evidence writer
        │
execution JSON + evidence/
        │
import-security-results
        → prepare-security-review
        → import-security-review
        → security-review-summary
        → harness-generate / document-validate
```

주요 모듈:

| 모듈 | 역할 |
|------|------|
| `models.py` | Check 프로토콜, 결과·컨텍스트·evidence 모델 |
| `registry.py` | 내장 runner 등록 |
| `executor.py` | 검증, retry, rate limit, metrics, JSON 출력 |
| `policy.py` | allowlist, method, URL 검증, SSRF 규칙 |
| `evidence.py` | 헤더 마스킹, body hash, evidence JSON, manifest |
| `runners/*.py` | TLS / Header / API Health / Port 검사 |

관련 문서:

- 구조: `docs/security_runner_architecture.md`
- PASS/FAIL: `docs/security_runner_pass_fail_policy.md`
- 안전장치: `docs/security_runner_safety.md`

## 4. 지원 Runner

| Runner | 검사 내용 | Fixture 커버리지 |
|--------|-----------|------------------|
| `tls_check` | TLS 버전, 인증서 유효기간, hostname 일치 | PASS, version FAIL, 만료 FAIL |
| `http_header_check` | HSTS/CSP/XCTO/frame 보호 등 | PASS, HSTS 누락 FAIL, timeout |
| `api_health_check` | GET/HEAD, status, latency, content-type, JSON key | PASS, status FAIL, body limit |
| `port_connectivity_check` | allowlist 단일 TCP 연결 (banner 금지) | PASS, timeout REVIEW_REQUIRED |

공통 규칙:

- HTTP method는 `GET` / `HEAD`만 허용
- PASS/FAIL은 config의 `expected`로만 판정
- 근거 부족·timeout·네트워크 오류는 `REVIEW_REQUIRED`
- disabled check는 `NOT_EXECUTED`

## 5. CLI

```powershell
python -m document_ai.cli run-security-tests `
  --case data/cases/lab_ec_sw `
  --config data/cases/lab_ec_sw/security_runner_config.synthetic.json `
  --synthetic `
  --execution-id exec-20260718-runner-synthetic-001 `
  --output data/executions/lab_ec_sw/runner.synthetic.json
```

주요 옵션:

| 옵션 | 의미 |
|------|------|
| `--dry-run` | config 검증·예정 check만 출력, 네트워크 미사용 |
| `--synthetic` | fixture 전용, 네트워크 강제 비활성 |
| `--no-network` | fixture/mock만 사용 |
| `--check` | 특정 `security_test_id`만 실행 |
| `--timeout` | check별 timeout |
| `--execution-id` | `exec-...` 형식 ID |

Runner는 실행 후 **자동 import하지 않는다**.

## 6. Synthetic 실행 결과

| 지표 | 값 |
|------|---:|
| 설정 / 실행 check | 9 / 9 |
| PASS | 4 |
| FAIL | 3 |
| REVIEW_REQUIRED | 2 |
| Evidence 파일 | 9 |
| Network requests | 0 |
| synthetic | true |

결과 파일:

- Execution: `data/executions/lab_ec_sw/runner.synthetic.json`
- Evidence: `data/executions/lab_ec_sw/runner.synthetic/`
- Manifest: `data/executions/lab_ec_sw/runner.synthetic/manifest.json`

Evidence는 제한된 metadata만 저장한다. execution JSON에는 상대 경로와 SHA-256만 기록한다. 응답 본문 전체·Cookie·Authorization은 저장하지 않는다.

## 7. Import / Review E2E

완료된 흐름:

```text
run-security-tests
  → import-security-results
  → prepare-security-review
  → import-security-review
  → security-review-summary
```

검토 결과:

| 항목 | 결과 |
|------|------|
| 검토 상태 | `test_fixture_verified` |
| 최종 보고서 선택 | `selected_for_report=false` |
| execution gold 승격 | 차단 |
| real execution count | 0 |
| final report mode | `plan_only` |
| readiness | true |

즉 synthetic Runner 결과는 파이프라인 검증용으로만 유지되며, 실제 XXCS 최종 결과나 human-approved gold로 승격되지 않는다.

## 8. Validation / Benchmark 영향

Runner metric은 execution JSON에 별도 저장한다. 실제 실행이 없으면 Document Harness score에 강제 반영하지 않는다.

Synthetic 결과가 선택되지 않았으므로 XXCS는 plan 데이터를 유지한다.

| 항목 | 결과 |
|------|------|
| MDSR validation | 100.0 |
| MDDR validation | 92.0 |
| XXCS plan score | 97.1 |
| Integrated validation | 96.2 PASS |
| Document quality | 96.8 PASS |
| Harness benchmark | 92.8 |
| Pytest | **297 passed** |

## 9. 안전장치 요약

| 항목 | 적용 |
|------|------|
| HTTP method | GET / HEAD만 |
| 대상 범위 | URL / host / port allowlist |
| SSRF | scheme, credential, hostname, DNS, redirect 검증 |
| Private network | `allow_private_network=true`일 때만 |
| Redirect | 최대 횟수 제한, HTTPS→HTTP 기본 차단 |
| Timeout / body size / retry | config + hard cap |
| 민감 헤더 | 마스킹 |
| Port check | 단일 포트만, send/recv/banner 금지 |
| Shell / subprocess | 미사용 |
| SSL verify | 기본 활성 |

상세: `docs/security_runner_safety.md`

## 10. 실제 서버 실행 전 필요한 입력

1. 승인된 정확한 base URL / endpoint
2. hostname과 단일 port
3. private network 허용 여부
4. TLS 최소 버전 / 인증서 잔여일수
5. required vs optional header
6. API expected status, Content-Type, JSON key, latency
7. timeout / redirect / body / retry 제한
8. read-only 시험 수행 권한 확인

절차:

1. synthetic config를 `security_runner_config.json`으로 복사
2. `synthetic` 및 모든 `fixture` 제거
3. 실제 target·allowlist·expected 설정
4. `--dry-run`으로 사전 검증
5. `--synthetic` / `--no-network` 없이 실행
6. `import-security-results`와 human review를 **별도** 수행

## 11. 남은 한계

- 인증이 필요한 API 검사는 미지원
- 실서버 대상 네트워크 실행은 이번 Sprint에서 수행하지 않음
- Local host telemetry(GPU/disk/journal)는 미구현
- Runner metric은 Document Harness score와 분리되어 있으며, real execution gold 승격 전용 UI/CLI는 review workflow에 종속

## 12. 다음 단계 제안

1. **Local infrastructure runner** — 명시적으로 승인된 host-local read-only telemetry (별도 안전 모델)
2. **Embedding retrieval** — free_text few-shot 품질 개선
3. **Lightweight XXCS template** — merged-cell/경로 취약성 완화

## 13. 변경 파일 (핵심)

| 구분 | 경로 |
|------|------|
| Runner 코드 | `src/document_ai/security_runner/` |
| CLI | `src/document_ai/cli.py` (`run-security-tests`) |
| Config schema | `schemas/security_runner_config.schema.json` |
| Synthetic config | `data/cases/lab_ec_sw/security_runner_config.synthetic.json` |
| 실행 산출물 | `data/executions/lab_ec_sw/runner.synthetic.json` |
| 테스트 | `tests/test_security_runner.py` |
| 문서 | `docs/security_runner_*.md` |
