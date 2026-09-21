# XXCS Gold Dataset

## Layout

- `plan/` — plan-based XXCS gold (method/procedure/expected; NOT_EXECUTED placeholders OK)
- `execution/` — human-approved real execution gold only (`reviewer_verified`, synthetic=false)

Do not mix plan and execution gold in the same comparison bucket.
Synthetic fixtures must never be promoted to `execution/`.
