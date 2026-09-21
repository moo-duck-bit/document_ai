# Trial 1 필요 입력 체크리스트

> **Trial 1 (Mindrium XA) — 현재 사용 문서**  
> case: `data/cases/mindrium_xa` · trial_id: `trial-001-mindrium-xa`  
> 과거 lab_ec_sw / JM COLLECTION 기준 문서와 혼동하지 말 것.  
> 인덱스: `docs/README.md` § Trial 1


> Real-world Trial 1은 아래가 준비된 뒤에만 사용자가 직접 실행한다.  
> 코드/에이전트가 실제 Trial을 완료했다고 보고하지 않는다.  
> Case 결정: `docs/trial1_case_decision_mindrium.md` (**옵션 B: Mindrium XA**)

## Trial 확정안

| 항목 | 값 |
|------|-----|
| trial_id | `trial-001-mindrium-xa` |
| case | `data/cases/mindrium_xa` |
| trial_type | **change_update** |
| system_version | `v0.5-document-harness` |
| system_commit | `d73fc18` |
| 변경 대상 (기본) | `Req. 6` (로그인 시도 제한 정책 기입) |

---

## 레포에서 바로 쓸 수 있는 것 (실자료·참고)

| 구분 | 경로 | 비고 |
|------|------|------|
| **원본 MDSR/MDDR/XXCS** | `data/examples/ec_sw/spec_*.docx`, `report_xxcs_*.docx` | Mindrium 완성본 — **변경 전 기준 실자료** |
| Case facts | `data/cases/mindrium_xa/input.json` | 제품명·승인일 등 |
| Case 생성본 | `.../output_mdsr.docx`, `output_mddr.docx` | harness 출력 (원본과 구분) |
| requirements / design | `requirements.json`, `design_content.json` | payload (다수 Req description 공란 주의) |
| 변경 NL 후보 | `.../changes/request_req6.txt` | Trial 입력 후보 — 원본 문서 as-is 추출 아님 |
| 변경 JSON 후보 | `.../changes/req6_update.json` | workdir용; 원본 case apply 금지 |
| 템플릿 | `data/templates/ec_sw/` | 렌더용 |
| CLI·프레임 | trial-* 명령 | 준비 완료 |

**사용 안 함 (Trial 1):** `lab_ec_sw` / `trial-001-lab-ec-sw`  
**금지:** `data/gold/**`, holdout, synthetic execution을 실적으로 사용.

---

## A. 기준 문서 (사용자가 확정)

- [ ] 변경 전 MDSR — `examples/ec_sw` 원본 복사 + 버전/기준일
- [ ] 변경 전 MDDR — 동일
- [ ] 변경 전 XXCS — 동일 (생성 범위에 포함할지 명시)
- [ ] case `output_*`를 기준에 쓸지, 원본 예시만 쓸지 명시
- [ ] `VERSIONS.md` 작성

배치: `data/trials/trial-001-mindrium-xa/reference/`

## B. 변경 정보

- [ ] `change_request.txt` 확정 (`request_req6.txt` 사용 또는 수정본)
- [ ] (권장) 회의록·메신저·담당 확인 — 있으면 실무 CR로 격상, 없으면 리포트에 「준비된 Req.6 변경 패키지」로 표기
- [ ] 적용 범위: `Req. 6` (+ 연동 IA/SI/DC는 impact로 확인)
- [ ] 제외 범위: 다른 Req·정상 구간 수정 금지

배치: `data/trials/trial-001-mindrium-xa/input/`

## C. 평가용 정답 (격리)

- [ ] 변경 반영 최종본이 있으면 trial input 밖 보관
- [ ] `data/trials/_held_out_answers/trial-001-mindrium-xa/` 권장
- [ ] generation `input/`·`reference/`에 넣지 않음

## D. 시간 측정

- [ ] `manual_baseline_minutes` (실측 권장)
- [ ] 출처: measured / estimated / unknown
- [ ] `human_revision_minutes`

## E. 민감정보

마스킹: 계정·토큰·내부 IP·개인정보 → `[REDACTED]`  
`trial-check-input` sensitive warning 통과.

## F. 리뷰어

- [ ] 이름·역할
- [ ] 문서 담당 (MDSR/MDDR/XXCS)
- [ ] 평가 6차원 숙지

---

## 부족한 것 (한눈에)

| 항목 | 레포 | 사용자 |
|------|------|--------|
| Mindrium 완성본 (기준 문서) | ✅ examples/ec_sw | 버전·기준일 확정만 |
| Req.6 변경 문구 후보 | ✅ changes/ | Trial 입력으로 채택·수정 |
| 운영 CR·회의록 | ⚠️ 없으면 준비된 CR로 진행·표기 | 있으면 추가 |
| 수작업/수정 시간 | ❌ | 필수 |
| 리뷰어 | ❌ | 필수 |
| 최종본 격리 | ❌ | 권장 |
| XXCS case output | ❌ | reference 원본 사용 여부 결정 |
