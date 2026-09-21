# 보안 Runner PASS/FAIL 정책

> **Historical (lab_ec_sw / JM COLLECTION)** — **Not used in Trial 1**  
> 이 문서는 과거 스프린트·벤치마크·진단 기록이다.  
> Real-world Trial 1 확정 case는 **Mindrium XA** (`trial-001-mindrium-xa`)이다.  
> Trial 1 문서: `docs/trial1_case_decision_mindrium.md`, `docs/README.md` § Trial 1


## 상태 규칙

| 상태 | 조건 |
|------|------|
| `PASS` | 모든 필수 `expected` 조건이 관측되고 충족됨 |
| `FAIL` | 관측값이 필수 조건을 명시적으로 위반함 |
| `REVIEW_REQUIRED` | timeout, 연결 오류, 인증 필요, 관측 누락, 모호성 |
| `NOT_EXECUTED` | check가 명시적으로 비활성화됨 |
| `NOT_APPLICABLE` | 환경이 해당 check를 비적용으로 선언함 |

Runner는 plan 완성도나 데이터 부재로부터 PASS를 추론하지 않는다.

## TLS

| 조건 | 결과 |
|------|------|
| 협상 버전 ≥ `minimum_tls_version` | 충족 |
| 협상 버전 < 최소값 | `FAIL` |
| Hostname 불일치 | `FAIL` |
| 인증서 잔여일수 < 필수 최소값 | `FAIL` |
| Timeout, DNS 실패, 버전/만료 확인 불가 | `REVIEW_REQUIRED` |

인증서 검증 비활성화는 `ssl_verify=false`가 필요하다. evidence에 검증
비활성화 사실을 기록한다. 기본값은 검증 활성이다.

## HTTP 보안 헤더

필수 헤더는 `expected.headers`로 평가한다.

```json
{
  "headers": {
    "strict-transport-security": { "required": true },
    "content-security-policy": { "required": false }
  },
  "frame_protection_required": true
}
```

- 필수 헤더 누락: `FAIL`
- 선택 헤더 누락: finding만 기록
- frame protection 필수인데 `X-Frame-Options`와 CSP `frame-ancestors`가
  모두 없음: `FAIL`
- 예상치 못한 응답 status: `FAIL`
- Redirect 정책 오류·timeout: `REVIEW_REQUIRED`

## API health

- `status_code` / `status_codes` 범위 밖 status: `FAIL`
- `maximum_response_time_ms` 초과 응답 시간: `FAIL`
- Content-Type 불일치: `FAIL`
- 필수 JSON key 누락: `FAIL`
- 필수 JSON-key 검사인데 body 파싱 불가: `REVIEW_REQUIRED`
- 필수 검사를 막는 body 절단: `REVIEW_REQUIRED`

응답 body는 hash 및 요약만 한다. 저장하지 않는다.

## 포트 연결

- allowlist 단일 TCP 연결 성공: `PASS`
- Timeout, 거부, DNS 실패, 모호한 연결 상태: `REVIEW_REQUIRED`

포트 연결은 `FAIL`을 만들지 않는다. 닫힌 포트는 의도된 것일 수 있어,
향후 명시적 정책이 없는 한 human 해석이 필요하다.

## Retry

- 기본: 0회
- 최대: 1회
- transient `REVIEW_REQUIRED`만 retry
- `PASS`·`FAIL`은 절대 retry 안 함
- 모든 시도를 result metadata에 기록

## Review 경계

`import-security-results` 이후에도 모든 상태는 `imported`로 유지된다.
`reviewer_verified`, 거부, 최종 보고서 선택은 human review가 통제한다.
