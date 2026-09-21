# 용어 정정 패치 (팀 공유용)

**적용 대상:** 0908 진경 초안 (Related Work / Method / Ablation)  
**목적:** LEDGER 대비 차별점 서사는 유지하되, 코드·Document-TNR 정의와 어긋나는 용어를 맞춘다.

---

## 패치 문단 (슬랙/노션에 그대로 붙여넣기)

우리 파이프라인에서 **gate / C1 closure / human approval**은 서로 다른 장치입니다. 앞으로 초안·논문·이슈에서는 아래 이름으로만 쓰겠습니다.

1. **Impact consistency gate (B4)**  
   변경 요청이 *이 요구사항/노드에* 반영되어도 의미·책임이 깨지지 않는지를 규칙으로 판정합니다 (`CONSISTENT` / `CONFLICT` / `NEEDS_REVIEW`). LLM 판정이 아니며, `CONSISTENT`일 때만 자동 패치 후보가 됩니다. 탐색 정밀도(Node F1)가 낮아도 여기서 REVIEW로 걸러져 **바로 쓰기로 이어지지 않습니다.**

2. **Human approval gate (C2)**  
   사람이 `APPROVED` / `REJECTED` / `MANUAL_REQUIRED`를 내리는 승인 단계입니다. 승인이 없으면 controlled writer는 진행하지 않습니다. μ의 **`unapproved_write`** 에 대응합니다.  
   ※ 초안에서 “C1 closure = 사람 승인”으로 쓴 부분은 **이 항목(C2)** 으로 고칩니다.

3. **C1 dependency closure**  
   Req 하나(또는 시드 노드)를 건드리면 traceability/의존 그래프를 따라 **연결된 설계·시험 노드까지 후보를 확장**하는 단계입니다. 사람 승인이 아닙니다. Ablation에서 `no_closure`는 **`false_patch`**(의존 누락)로 셉니다.

4. **Copy-only writer**  
   모든 쓰기는 원본이 아니라 복사본에만 가해지고, 실행 전후 원본 SHA-256(fingerprint)이 같아야 합니다. μ의 **`original_broken`** 에 대응합니다.

5. **Activation / capability gate**  
   실제 DOCX 쓰기가 허용되려면 env 플래그(`CONTROLLED_WRITER_ENABLED`, `DOCX_ACTIVATION_ENABLED`) + approval + fingerprint + contract ready 등이 **모두** 통과해야 합니다. μ의 **`unsafe_write`**(정책 위반 쓰기 경로)와 맞닿습니다.

**Ablation 대응 (정정본)**

| 제거한 것 | 예상 μ 위반 |
|-----------|-------------|
| impact/approval **gate** (`no_gate`) | `unapproved_write`, `unsafe_write` |
| **copy-only** (`no_copy_only`) | `original_broken` |
| **C1 closure** (`no_closure`) | `false_patch` |

**Ablation 서술 정정:** 현재 RQ3 priority-1 ablation은 **sandbox dry-run / counterfactual**입니다. “시뮬레이션이 아니라 live로 안전장치를 끈 실제 실행”이라고 쓰지 않습니다. Live ablation을 할 경우에도 **승인된 fixture 복사본**에서만, 원본 corpus는 절대 건드리지 않습니다.

**LEDGER consistency 검사기 서술 정정:** LEDGER의 programmatic validator는 reference / terminology / **hierarchy(structure)** 입니다. 우리 초안의 “임베딩 θ=0.7 의미 검사”를 LEDGER와 동일한 세 검사기라고 쓰지 말고, **규제 문서용으로 재정의한 consistency suite**(traceability 참조 유효성 · 용어 · 구조/계층)라고 씁니다.

---

## 한 줄 요약

> **찾기(B1–B3) → 일관성 gate(B4) → C1으로 후보 확장 → copy-only 쓰기 → 사람 승인(C2)**  
> LEDGER는 “찾기→수정→사후 검사”이고, 우리는 **쓰기 전에 gate·폐포·copy-only·승인을 계약으로 건다.**


---

## Surviving claim (논문 한 줄 · 민주)

> 다문서 Change Impact → writable scope → μ=(false_patch, unsafe_write, original_broken, unapproved_write) 를 하나의 프로그래밍 벤치로 측정한다.

LEDGER-style consistency는 **reference / terminology / hierarchy stub** 비교 열만 사용한다 (임베딩 θ 금지, full port 아님).
Ablation은 **sandbox counterfactual**이며 live harness flip이 아니다.
