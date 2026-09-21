# Read-only 보안 Runner 안전 레퍼런스

> **Historical (lab_ec_sw / JM COLLECTION)** — **Not used in Trial 1**  
> 이 문서는 과거 스프린트·벤치마크·진단 기록이다.  
> Real-world Trial 1 확정 case는 **Mindrium XA** (`trial-001-mindrium-xa`)이다.  
> Trial 1 문서: `docs/trial1_case_decision_mindrium.md`, `docs/README.md` § Trial 1


## 강제 가드

| 가드 | 강제 내용 |
|------|-----------|
| HTTP method | `GET`, `HEAD`만 |
| 대상 범위 | 명시적 URL/host/port allowlist |
| SSRF | scheme, credential, hostname, DNS 결과, redirect 대상 검증 |
| Private network | `allow_private_network=true`가 아니면 차단 |
| Redirect | 최대 0~5; HTTPS→HTTP downgrade 기본 차단 |
| Timeout | check별 timeout; 최대 정책 ≤ 60s 유지 권장 |
| Body size | 설정 byte까지만 읽음 (hard cap 1 MiB) |
| Body 저장 | hash·metadata만 |
| 민감 헤더 | Authorization, cookie, API key, token 마스킹 |
| 포트 검사 | 설정된 단일 포트만; range·send·recv·banner 금지 |
| Retry | 0~1; transient 불확실성만 |
| Rate limit | 네트워크 check 간 최소 간격 |
| TLS 검증 | 기본 활성 |
| 명령 | shell·subprocess 인터페이스 없음 |

## URL 검증

URL은 다음을 만족해야 한다.

1. `http` 또는 `https` 사용
2. 내장 credential 없음
3. `policy.allowed_urls` 또는 `policy.allowed_hosts`와 일치
4. private 접근이 활성화되지 않는 한 허용된 public 주소로만 resolve
5. 모든 redirect 이후에도 동일 정책 통과

DNS는 네트워크 요청 직전에 재확인한다. 이는 DNS rebinding과
public→private redirect 위험을 줄인다.

## Private 실험실 대상

세 값을 모두 명시한다.

```json
{
  "target": {
    "host": "10.20.0.15",
    "base_url": "https://10.20.0.15",
    "port": 443
  },
  "policy": {
    "allowed_hosts": ["10.20.0.15"],
    "allowed_urls": ["https://10.20.0.15"],
    "allowed_ports": [443],
    "allow_private_network": true
  }
}
```

좁은 host·port allowlist 없이 `allow_private_network=true`를 설정하지 말 것.

## 설정 secret

validator는 secret 유형 key를 거부한다.

- password
- token
- API key
- authorization 필드
- private key

인증이 필요한 검사는 이번 MVP 범위 밖이다.

## Evidence 노출

Evidence에 포함될 수 있는 것:

- 설정된 hostname과 port
- 최종 URL과 redirect chain
- 마스킹된 응답 헤더
- 인증서 subject, issuer, 유효기간
- 응답 byte 수와 SHA-256
- 오류 유형과 제한된 메시지

Evidence에 포함되지 않는 것:

- 전체 HTTP 응답 body
- cookie 또는 authorization 값
- TLS private key
- banner
- 임의 로그

## 안전 preflight

실제 네트워크 접근 전 dry-run을 실행한다.

```powershell
python -m document_ai.cli run-security-tests `
  --case data/cases/lab_ec_sw `
  --config data/cases/lab_ec_sw/security_runner_config.json `
  --output data/executions/lab_ec_sw/exec-lab.json `
  --dry-run
```

dry-run은 DNS 해석이나 네트워크 요청을 수행하지 않는다.

## 실제 실행 전 필요한 사용자 입력

- 정확한 base URL과 endpoint 경로
- 정확한 hostname과 단일 port
- public/private network 결정
- 필수 TLS 버전과 인증서 경고 기간
- 필수 vs 선택 헤더
- 예상 API status, Content-Type, JSON key, 응답 시간 한계
- Timeout, redirect 제한, body 제한, retry 횟수
- 대상이 read-only 시험에 대해 승인되었다는 확인
