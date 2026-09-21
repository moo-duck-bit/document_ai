# Codex Prompt — Document AI v2 발표 PPT 생성

아래 블록 전체를 Codex에 복사해 넣으세요.

---

```text
당신은 기술 발표용 PowerPoint를 만드는 에이전트다.
Document AI v2 프로젝트를 설명하는 발표 PPT(.pptx)를 생성하라.

==================================================
0. 산출물
==================================================

1) docs/presentation/Document_AI_v2_Full_Presentation.pptx
2) 같은 폴더에 슬라이드 원고 Markdown도 함께 생성:
   docs/presentation/Document_AI_v2_Full_Presentation.md

발표 시간: 12–15분
언어: 한국어
톤: 학술·기술 발표 (과장 금지, 사실 기반)
디자인:
- 슬라이드당 메시지 1개
- 불릿은 짧게 (한 줄 20자 전후 권장, 최대 2줄)
- 다이어그램은 텍스트/도형으로 단순하게
- 코드 슬라이드는 글꼴 작게, 핵심 10–20줄만
- 표지/구분 슬라이드 제외하고 본문 약 18–24장
- AI 기본 보라 그라데이션·과도한 카드 UI 남발 금지
- 남색/그레이 계열의 깔끔한 기술 발표 톤

==================================================
1. 프로젝트 팩트 (반드시 반영, 추측 금지)
==================================================

North Star:
- 완성 문서로 학습해, 빈 양식과 새 케이스만으로 문서를 자동 작성하는 Agent
- 다만 이번 발표의 구현 초점(v2 Pilot)은
  “문서 변경 요청 → 영향 위치 탐색 → 사람 승인 → 복사본만 안전 저장”

현재 판정/상태:
- READY_FOR_PILOT_RELEASE
- REAL_USER_PILOT_RUN_01_COMPLETE (Writer OFF dry-run, 9세션)
- Pilot Run 02 = 실사용자 UI 진행용 준비 완료

두 층 아키텍처:
1) Form Fill Agent (최종 목표)
   학습: 완성본+빈양식 → parse/OCR → template-learn → case-index
   작성: case-intake → case-retrieval → form-fill → render
2) Document Change / Pilot v2 (현재 데모 중심)
   Upload → Identity/Routing → Change Request → Analysis → Review/Approval
   → Controlled Writer(gated, copy-only) → Result / Human Review

지원 Domain Pack:
- EC-SW (MDSR/MDDR/MDTM 등 표·추적성 중심)
- General Report
- Business Proposal

핵심 컴포넌트:
- Document Parsing (DOCX, python-docx)
- Template Abstraction
- Semantic / Structural Locator
- Patch Targeting
- Physical Locator
- Patch Contract
- Controlled Writer (승인·fingerprint·copy-only)
- Approval / Diff / Rollback / Validation
- Document Identity Resolution
- Auto / Assisted Domain Pack Routing
- Stable Node Identity
- Structural Node Ranking
- Pilot UI (/pilot-v2)
- Human Review 10 dimensions

중요 제약 (반드시 슬라이드에 명시):
- Pilot 경로에서 원격 LLM / 원격 Embedding 사용하지 않음
- 자동 승인 없음
- 원본 직접 수정 없음 (세션 복사본만)
- Writer는 feature flag + 명시적 APPROVE 없으면 BLOCKED
- Benchmark/Gold를 Pilot 결과로 자동 수정하지 않음

Benchmark (immutable reference):
- Holdout Document F1: 0.956
- Holdout E2E: 0.957
- False Patch: 0
- Unsafe Failure: 0
- Original Preservation: 1.000
- BP Required Top-1: 0.929
- GR Node Top-1: 1.000
- EC-SW Stable Identity: 1.000

Pilot Run 01 결과 요약:
- 9 sessions (EC-SW 3 / GR 3 / BP 3)
- Completion Rate 1.0
- Document Agreement 0.889 / Node Agreement 0.889
- Mean Trust 3.778 / Mean Usability 4.0
- Safety PASS (원본변경 0, 무단 Writer 0)
- Known issue: EC-SW 의미 기반 요청에서 후보 0건 (bug candidate로만 기록)

실행 방법:
- UI: uvicorn / Docker → /pilot-v2
- Docker: host 0.0.0.0:8765
- CLI: run-pilot-session / run-pilot-demo / evaluate-pilot
- CONTROLLED_WRITER_ENABLED=false 가 Pilot 기본

레포 참고 경로 (코드 인용 시 실제 파일에서 읽어 사용):
- src/document_ai/pilot_v2/orchestrator.py
- src/document_ai/pilot_ui/app.py
- src/document_ai/workflow/orchestrator.py
- src/document_ai/document_identity/
- src/document_ai/domain_packs/
- src/document_ai/controlled_writer/
- docs/pilot/REAL_USER_PILOT_GUIDE.md
- docs/pilot/DEMO_SCRIPT.md
- data/pilot/real_runs/pilot_run_02/SCENARIOS.md
- AGENTS.md

==================================================
2. 발표 스토리라인 (이 순서로 슬라이드 구성)
==================================================

A. 오프닝
1. 표지: Document AI v2 — 문서 변경을 안전하게 찾는 Pilot
2. Agenda
3. 문제 정의: 문서는 연결돼 있고, 자동 수정은 원본 손상 위험이 큼
4. 해결 한 줄: 찾고 → 보여주고 → 사람이 승인 → 복사본만 저장

B. 제품/목표
5. North Star vs 현재 v2 범위 (Form-Fill 최종목표 / Change Pilot 현재)
6. 무엇을 했고 무엇을 안 했는지 (LLM 미사용, 자동승인 없음 등)

C. 전체 구성
7. 시스템 아키텍처 다이어그램
   Pilot UI/CLI → Workflow → Domain Packs → Controlled Writer
8. 모듈 맵 (Identity, Locator, Patch Contract, Writer, Eval)
9. 데이터/세션 레이아웃 (sessions/, pilot demo/, results/)

D. 사용자 6단계 프로세스 (핵심 — 각 단계 1슬라이드 이상)
10. Step1 업로드: 세션 복사본, fingerprint, path safety
11. Step2 문서 유형: Identity signals + Domain Pack routing + 사용자 확정
12. Step3 변경 요청: 자연어 intent를 분석 쿼리로 사용
13. Step4 분석: Intent → Locator → Ranking → Physical Locator → Patch Contract
14. Step5 검토·승인: APPROVE/REJECT/HOLD, 자동승인 없음
15. Step6 결과: Writer 게이트, Diff/Validation, Human Review 10점
16. 단계별 “사람 / 시스템 / AI역할” 한 장 요약표
    - 강조: 현재 AI = 규칙·구조·의미매칭 기반 후보 탐색기 (생성형 LLM 아님)

E. 사용 시나리오
17. 시나리오 A EC-SW: Req.11 추적성 행 검토
18. 시나리오 B General Report: 방법론 데이터 출처 보강
19. 시나리오 C Business Proposal: 예산/인건비 항목 검토
20. (짧게) 실패/관찰 케이스: 의미 기반 요청 후보 0건 → 왜 중요한지

F. 구동 방법
21. 로컬 실행 / Docker 실행 / /pilot-v2 접속
22. Writer OFF 기본과 안전 게이트 조건 체크리스트

G. 코드로 보는 핵심 (3–4장)
실제 레포 파일을 읽고, 발표용으로 축약한 코드 블록을 넣어라.
각 코드 슬라이드에 “이 코드가 하는 일” 1문장.

추천 코드 포인트:
23. pilot_v2 orchestrator 파이프라인 함수 흐름
    create_session → upload → resolve_identity → analyze → apply_decisions → writer → human_review
24. workflow run_analysis: impacted_documents / patch_candidates / review_required 생성
25. document_identity resolve + pack routing (assisted 확인)
26. controlled writer gate (APPROVE + flag + fingerprint + copy-only)

H. 검증 결과
27. Benchmark scorecard
28. Pilot Run 01 scorecard + Safety
29. 한계와 Next (Pilot Run 02 실사용자, Writer ON 소규모, 텍스트 apply는 이후)

I. 클로징
30. Takeaways 3줄
31. Q&A

==================================================
3. 슬라이드 작성 규칙
==================================================

- 제목은 결론형으로 (예: “원본은 절대 직접 수정하지 않는다”)
- 전문 용어는 처음 등장 시 한 줄 해설
  예: Physical Locator = DOCX 표/행/셀의 실제 위치 해석기
- “AI”라고 쓸 때는 반드시 역할 범위를 한정:
  “생성형 LLM이 문장을 쓰는 단계가 아니라,
   변경 위치를 찾고 순위를 매기는 분석 엔진”
- 데모 시나리오는 발표자가 따라 할 수 있게
  UI에서 고를 시나리오명 / 기대 결과 / 사람 액션을 명시
- 코드는 동작 원리 이해용. 줄번호 필요 시 `파일경로`만 각주
- 숫자/지표는 위에 준 값만 사용. 없는 수치는 만들지 말 것
- 영어 약어(EC-SW, MDSR, MDDR, F1)는 유지하되 한국어 설명 병기

==================================================
4. 다이어그램 요구
==================================================

최소 아래 3개를 슬라이드에 포함:
1) End-to-End 6-step user flow
2) Engine internal pipeline
   parse → intent → locate → rank → physical resolve → patch contract → review
3) Safety gate before writer
   APPROVE ∧ routing confirmed ∧ contract VALID ∧ locator RESOLVED ∧ fingerprint OK ∧ env flag ∧ copy path

==================================================
5. 발표자 노트
==================================================

각 주요 슬라이드(문제, 아키텍처, 6단계, 시나리오, 코드, 결과)에
Speaker Notes 2–4문장 작성:
- 말로 할 해설
- 청중에게 강조할 한 문장
- 데모 전환 시점 안내 (해당 시)

==================================================
6. 작업 절차
==================================================

1. 레포에서 위 경로의 문서/코드를 읽고 사실 확인
2. Markdown 원고를 먼저 완성
3. python-pptx 등으로 .pptx 생성
4. 슬라이드 수, 파일 경로, 포함 다이어그램/코드 파일 목록을 마지막에 요약 보고
5. 엔진/벤치마크/도메인팩 코드는 수정하지 말 것 (발표 자료만 생성)

완료 보고 형식:
- PPTX path
- MD path
- slide count
- key diagrams
- code slides (file references)
- suggested demo order (EC / GR / BP)
```

---

## 사용 팁

1. Codex 작업 디렉터리를 `document_AI` 레포 루트로 둔다.
2. 위 프롬프트를 한 번에 넣고, 필요하면 후속으로:
   - “슬라이드 22장으로 더 압축해줘”
   - “교수/산업체 청중용으로 용어를 더 쉽게”
   - “코드 슬라이드를 EC-SW Req.11 시나리오 중심으로 바꿔줘”
3. 발표 당일 데모는 `docs/pilot/DEMO_SCRIPT.md` + `/pilot-v2` 를 같이 켠다.
