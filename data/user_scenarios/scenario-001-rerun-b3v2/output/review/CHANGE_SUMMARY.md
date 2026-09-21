# Change Summary (Human Review)

## Input CR

```
﻿최근 3일 동안 과제 수행 기록이 없는 환자를 비활성 환자로 분류하고,
의료진이 웹 대시보드에서 해당 환자를 쉽게 식별할 수 있도록 별도로 표시한다.
비활성 상태는 환자의 최근 과제 수행 기록을 기준으로 자동 갱신되어야 한다.
```

## Top retrieval candidates

- rank 1: Req. 203 [MDSR] hybrid=1.0
- rank 2: Req. 204 [MDSR] hybrid=0.670597
- rank 3: Req. 100 [MDSR] hybrid=0.65911
- rank 4: Req. 11 [MDDR] hybrid=0.630896
- rank 5: Req. 17 [MDDR] hybrid=0.630114
- rank 6: Req. 204 [MDDR] hybrid=0.582793
- rank 7: Req. 110 [MDSR] hybrid=0.51179
- rank 8: Req. 108 [MDSR] hybrid=0.509933
- rank 9: Req. 16 [MDDR] hybrid=0.505136
- rank 10: Req. 17 [MDSR] hybrid=0.409617

## Impacted (B3)

- Req. 203 [MDSR] — IMPACTED
- Req. 204 [MDSR] — IMPACTED
- Req. 100 [MDSR] — IMPACTED
- Req. 17 [MDDR] — IMPACTED
- Req. 204 [MDDR] — IMPACTED
- Req. 110 [MDSR] — IMPACTED

## MDSR actually patched

- (none)

## MDDR actually patched

- (none)

## Related but not modified (skip / conflict)


## Conflicts

- (none)

## NEEDS_REVIEW

- consistency Req. 203: Insufficient evidence to prove consistency or a hard conflict; defer to review.
- consistency Req. 204: Insufficient evidence to prove consistency or a hard conflict; defer to review.
- consistency Req. 100: Insufficient evidence to prove consistency or a hard conflict; defer to review.
- consistency Req. 110: Insufficient evidence to prove consistency or a hard conflict; defer to review.
- impact UNCERTAIN: {'id': 'Req. 2', 'doc': 'MDSR', 'change_type': 'NEW_REQUIREMENT_CANDIDATE'}

## NEW_REQUIREMENT_CANDIDATE

- flagged: `False`
- reason: (n/a)
- proposal: `(none)`

## Final execution notes

- Inputs were not overwritten; outputs are under `output/documents/`.
- Auto-patch requires B4 CONSISTENT + allow_auto_patch.

