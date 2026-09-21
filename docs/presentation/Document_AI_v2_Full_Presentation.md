# Document AI v2 — Full Presentation Manuscript

발표 시간: 12–15분 · 언어: 한국어  
산출물: `Document_AI_v2_Full_Presentation.pptx`

---

## 1. 표지
**Document AI v2**  
문서 변경을 안전하게 찾는 Pilot  
찾고 → 보여주고 → 사람이 승인 → 복사본만 저장

## 2. Agenda
- 문제 정의와 한 줄 해결
- 전체 구성 · 아키텍처
- 사용자 6단계
- 시나리오 (EC-SW / GR / BP)
- 구동 · 코드 · 검증 · Next

## 3. 문제
문서는 연결돼 있고, 자동 수정은 원본 손상 위험이 큼.

## 4. 해결
찾고 → 보여주고 → 승인 → 복사본만.

## 5. North Star vs 현재
- 최종: Form Fill Agent
- 현재: Change Pilot (`/pilot-v2`)
- READY_FOR_PILOT_RELEASE

## 6. 한 것 / 안 한 것
- LLM·자동승인·원본수정·Gold 자동수정 = 안 함

## 7–9. 구성
Pilot UI/CLI → Workflow → Domain Packs → Controlled Writer  
모듈: Identity, Locator, Contract, Writer, Human Review  
데이터: sessions / demo / results (benchmark와 분리)

## 10–16. 6단계
1. 업로드 — 복사·fingerprint  
2. 유형 — Identity + Pack, 사람 확정  
3. 요청 — 자연어 intent  
4. 분석 — locate/rank/contract (**AI 중심, LLM 생성 아님**)  
5. 승인 — APPROVE/REJECT/HOLD  
6. 결과 — Writer 게이트 + Human Review 10점

## 17–20. 시나리오
- A EC-SW Req.11  
- B GR 방법론  
- C BP 예산  
- 관찰: 의미 기반 후보 0건 (bug candidate)

## 21–26. 구동·코드
- uvicorn / Docker `:8765` / Writer OFF  
- orchestrator / run_analysis / identity / writer gate

## 27–29. 결과
- Benchmark F1 0.956 · E2E 0.957 · False/Unsafe 0  
- Pilot 01: 9세션, Trust 3.778, Usability 4.0, Safety PASS  
- Next: Run 02 실사용자 → Writer ON 소규모

## 30–31. Takeaways / Q&A
안전 변경 위치 탐색기 · 사람 승인 · 원본 무변경
