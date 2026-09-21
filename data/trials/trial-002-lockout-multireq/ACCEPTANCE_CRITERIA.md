# Trial 2 Acceptance Criteria (고정)

> **실행 전 고정. Trial 중간 완화·변경 금지.**  
> 기반: 기존 Trial 2 AC + A1 lockout multi-req 최소 확인 항목.

## 최소 기준

1. Exact-ID가 CR에 없어도 의미적으로 관련된 Req 후보를 찾는다.
2. **Req.105**가 retrieval 후보에 포함된다 (첫 검증 포인트).
3. 후보 검색(retrieval)과 실제 영향 판단(impact judgment)이 분리된다.
4. Semantic consistency validation passes / 필드 간 모순 없음.
5. MDDR은 **PATCHED** 또는 **SKIPPED_WITH_REASON** (조용한 no-op 금지).
6. CR → … → validation 의 **propagation trace** JSON이 남는다.
7. 원본 문서 구조가 보존된다.
8. Cross-document propagation trace가 생성된다.

## 실패 시

- 결과를 재패치해 성공으로 만들지 않고 **그대로 freeze**한다.
- Trial 1 `generated_patch_preserving` 등 Frozen 산출물을 수정하지 않는다.

## 범위 제외

- 관리자 모드 신규 추가
- XXCS 전파
- form-fill 본선 개선
