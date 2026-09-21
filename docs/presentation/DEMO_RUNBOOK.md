# Live Demo Runbook — **참고용 (발표는 화면 캡처 PPT)**



현재 청중 PPT는 **라이브 실행 없이** `docs/presentation/screenshots/` 캡처로

UI 워크스루를 진행합니다.



재캡처 (서버 필요):



```powershell

$env:CONTROLLED_WRITER_ENABLED = "false"

python -m document_ai.cli materialize-pilot-demo

uvicorn document_ai.pilot_ui.app:app --host 127.0.0.1 --port 8000

# 다른 터미널

python scripts/capture_pilot_demo_screenshots.py

python scripts/build_lab_presentation.py

```



아래는 예전 라이브 데모용 클릭 가이드입니다 (필요 시만).



---



## 메인 시나리오 — EC-SW · Req.11



| 순서 | 동작 | 값 |

|------|------|-----|

| 1 | Participant ID | `DEMO` |

| 2 | 데모 시나리오 | **`[ec_sw] EC-SW 단일 Req ID 변경`** |

| 3 | | **세션 만들고 업로드** |

| 4 | 확인 방식 | 추천 후 사용자 확인 |

| 5 | | **유형 분석 실행** → **추천대로 확정** |

| 6 | 변경 요청 | `Req. 11 기능 설명을 갱신하고 관련 추적성 행을 검토한다.` |

| 7 | | **분석 실행** |

| 8 | 검토 | Req.11 관련 **승인** → **결정 저장** |

| 9 | 복사본 저장 허용 | **체크 해제** |

| 10 | Writer | `BLOCKED` · 원본 무변경 |



### 말할 한 줄

> “탐색임상 SW에서 요구사항 11번이 바뀌면, 추적성 표에서 어디를 건드릴지 찾아 보여줍니다.”



### 금지

- 발표 중 Writer ON

- 의미 기반 시나리오를 메인으로 사용

