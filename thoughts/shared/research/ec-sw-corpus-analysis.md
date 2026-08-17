# EC-SW 완성 문서 코퍼스 분석

## 요약

사용자 제공 **완성 DOCX 3건**을 `data/examples/ec_sw/`에 등록·분석했다.
**Mindrium (XA)** 의료기기 소프트웨어 문서 세트이며, IEC 62304 생명주기 문서이다.

| 문서 | 역할 | 구조 |
|------|------|------|
| MDSR | 요구사항 명세 | 표 45 — `Req. N` 반복 |
| MDDR | 설계 명세 | 표+본문 — 시스템 개요, Req. 대응 |
| XXCS | 보안 검증 보고 | 표 37 — IA/UC/SI 시험결과 |

## Form Fill Agent에 대한 시사점

### 1. placeholder DOCX가 아님

일반 `{{field_id}}` 양식이 **없다**. 셀 병합·고정 레이아웃·반복 표가 핵심.

**권장 학습 전략 (우선순위)**:
1. **표 행 템플릿**: XXCS의 `시험결과|적용|비고` 행 패턴을 requirement_id별 복제
2. **완성본 diff**: 동일 EC-SW 양식의 빈 템플릿 vs 완성본 (빈 양식 확보 시)
3. **v2**: docxtpl용 simplified template 별도 제작 (유지보수용)

### 2. 문서 세트 traceability

한 케이스 = MDSR + MDDR + XXCS 묶음.

```
case_id: mindrium_xa
  ├── spec_requirements  (Req. 1..N)
  ├── spec_design        (Req. → design)
  └── report_security_verification  (IA-01..SI-xx)
```

`input.json`은 **세트 공통 facts** + 문서별 repeating entities.

### 3. 케이스 입력 (case-intake) — 이 도메인에 맞게

| 채널 | EC-SW에서의 활용 |
|------|------------------|
| **채팅** | product_name, platform, 신규 Req. 요약 |
| **참고 DOCX** | 기존 MDSR/MDDR에서 Req.·설계 복제 후 수정 |
| **CSV/Excel** | XXCS 시험결과 bulk (IA-01~SI-xx) — **v2 강력 추천** |

보안 검증 보고서는 **요구사항 ID × 시험결과**가 표로 반복 → Excel/CSV intake가 채팅보다 효율적일 수 있음.

### 4. cold start (완성본 1종만)

유형당 1건뿐 → case-retrieval은 **동일 제품 내 문서 간** 참조 또는 **수동 schema** 우선.

추가 제품/버전 완성본이 쌓이면 few-shot 품질 상승.

## XXCS 보안 요구사항 샘플 (본문 추출)

- IA-01 ~ IA-08 (식별·인증)
- UC-01 ~ UC-07 (사용 통제)
- SI-01 ~ SI-03 (시스템 무결성)

표 컬럼: `사이ber보안 요구사항 | 해당기기 적용여부 | 적합성 입증 방법 | 시험결과 | 적용 | 비고`

## MDDR 핵심 내용 (샘플)

- 제품: Mindrium
- 표준: IEC 62304, ISO 14971
- 시스템: 환자 모바일 CBT 앱 ↔ 서버 ↔ 의사 모니터링
- 기술: iOS 15.6, Next.js / TypeScript 등

## 다음 구현 단계

1. **빈 EC-SW 양식** 확보 (있다면 `data/templates/ec_sw/`)
2. `template-learn` **표 행 추출** POC — XXCS 1개 요구사항 블록
3. case-intake: `mindrium_xa` input.json 기반 **세트 생성** CLI 스켈레ton
4. MDSR `Req. N` 파서 — 반복 entity JSON export

## 산출물

- `data/examples/ec_sw/*.docx` (복사본)
- `data/examples/ec_sw/corpus_analysis.json`
- `data/schemas/ec_sw/*.meta.json`
- `data/cases/mindrium_xa/input.json`
