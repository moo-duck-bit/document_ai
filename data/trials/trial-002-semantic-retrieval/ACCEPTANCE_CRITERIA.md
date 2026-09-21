# Trial 2 수용 기준

> **Trial 2 실행 전에 고정한다.**  
> Trial 중간에 결과에 맞춰 기준을 완화하지 않는다.

## 최소 기준

1. Req.105 is retrieved as an impact candidate.  
   (Req.105가 영향 후보로 검색·포함된다.)

2. Semantic consistency validation passes.  
   (의미적 일관성 검증을 통과한다.)

3. No contradiction exists among updated requirement fields.  
   (갱신된 요구사항 필드 간 모순이 없다.)

4. MDDR is correctly patched OR explicitly skipped with documented justification.  
   (MDDR이 올바르게 패치되거나, 문서화된 사유와 함께 명시적으로 생략된다.)

5. Cross-document propagation trace is generated.  
   (문서 간 전파 추적(trace)이 생성된다.)

## 고정 원칙

- Acceptance Criteria는 Trial 2 실행 전에 고정한다.
- Trial 중간에 결과에 맞춰 기준을 완화하지 않는다.
- Trial 1 Freeze 산출물을 재패치하여 기준을 “맞추는” 행위는 금지한다.
