# Document Harness Demo

데모용 **End-to-End** 스크립트입니다.  
자연어 한 줄 입력부터 MDSR/MDDR 생성·품질 리포트까지 한 번에 실행합니다.

## 데모 목적

- 사용자가 `input.json`을 직접 작성하지 않아도 **case-intake**로 케이스를 만들 수 있음을 보여줍니다.
- 동일 파이프라인으로 **MDSR·MDDR**을 자동 생성합니다.
- **document-quality**로 생성 품질을 수치화해 제시합니다.

## 실행 전 준비

1. 프로젝트 루트에서 패키지 설치:

   ```powershell
   pip install -e ".[dev]"
   ```

2. Python 3.11+ 사용 가능 여부 확인:

   ```powershell
   python --version
   ```

3. (선택) 기존 `data/cases/demo_hospital`이 있으면 스크립트가 **초기화(삭제 후 재생성)** 합니다.

## 실행 명령어

프로젝트 루트(`document_AI`)에서:

```powershell
.\scripts\demo\run_document_harness_demo.ps1
```

또는:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\demo\run_document_harness_demo.ps1
```

## 데모 입력

- **Case:** `data/cases/demo_hospital`
- **자연어:** `scripts/demo/demo_hospital_intake.txt` (UTF-8)

## 예상 산출물

| 파일 | 설명 |
|------|------|
| `input.json` | confirmed intake 결과 |
| `intake_log.json` | domain·필드 추론 로그 |
| `output_mdsr.docx` | 생성된 요구사항 명세서 |
| `output_mddr.docx` | 생성된 설계 명세서 |
| `output_xxcs.docx` | 생성된 보안 검증 보고서 (templates에 XXCS 포함 시) |
| `security_tests.json` | XXCS IA/UC/SI 시험 항목 페이로드 |
| `quality_report.md` | 품질 분석 리포트 |

추가로 harness가 생성하는 중간 JSON(`requirements.json`, `mdsr_content.json`, `design_items.json` 등)도 함께 출력됩니다.

## 데모 포인트

1. **입력 단순화** — JSON 없이 자연어 → `case-intake` → `input.json`
2. **도메인 일반화** — 병원 예약 도메인(`hospital_reservation`) 자동 추론
3. **문서 자동 생성** — Harness가 MDSR/MDDR DOCX 생성
4. **품질 수치화** — Overall / Terminology / Traceability 점수
5. **확장성** — inventory·hospital 등 동일 파이프라인 재사용 (이전 검증 사례 언급)

## 확장 데모 (선택)

Gold 문서 bootstrap (`lab_ec_sw`):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\demo\bootstrap_lab_gold.ps1
```

Gold 문서가 준비된 경우 validation까지 실행:

```powershell
python -m document_ai.cli document-validate --case data/cases/demo_hospital `
  --gold-mdsr data/cases/demo_hospital/gold_mdsr.docx `
  --gold-mddr data/cases/demo_hospital/gold_mddr.docx
```

## 문제 해결

| 증상 | 조치 |
|------|------|
| `python` not found | PATH에 Python 3.11+ 등록 |
| harness 실패 | `input.json`의 `confirmed: true` 확인 |
| 한글 깨짐 | 터미널 UTF-8, `PYTHONIOENCODING=utf-8` (스크립트에 포함) |
