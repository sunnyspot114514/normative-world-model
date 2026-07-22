# Phase-5 V11 internal review — round 1 — 2026-07-22

Decision: **CHANGES REQUIRED, THEN RE-REVIEW**

## Findings and disposition

1. **Blocking — post-hoc normalization risk.** Stripping the V10 `<think>`
   envelope and calling the same run a pass would invalidate the preregistered
   gate. Fixed by preserving V10 as a failure, choosing a new estimand, and
   forbidding diagnostic tail extraction from every PASS path.
2. **Blocking — protocol/estimand contradiction.** The prior draft made common
   serialization the headline scientific contrast, while the proposed V11
   gate made native chat primary. Fixed by revising the protocol to an explicit
   deployment-package comparison and removing project prompts from the common
   diagnostic path.
3. **High — reused observed toy.** Reusing `17,5` would test a response already
   seen during V10. Fixed with the prospectively frozen `23,7` probe and a new
   seed.
4. **High — diagnostic could silently become a gate.** Fixed with machine-
   readable `pass_predicate=false`, verifier output that reports the diagnostic
   separately, and tests showing common-text drift does not change a valid
   native PASS.
5. **High — native path could inherit the same recovery logic.** Fixed with a
   negative test proving a native reasoning wrapper fails strict parsing even
   when its tail is the exact oracle.
6. **Governance — stale V10 trust root remained registered.** Fixed by resetting
   the deployment registry to `None`. V11 now fails before side effects until a
   new acceptance is registered through the two-commit process.

No GPU, HTTP, retained data, project prompt, or scientific execution occurred
during this review.
