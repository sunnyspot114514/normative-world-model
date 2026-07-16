# Evaluator profiles and deterministic N oracle

Status: **v0.3, frozen for Phase 1 discovery**

Time box: one working day for profiles and calibration cases, followed by one focused attack review. These profiles are synthetic evaluation contracts; they are not claims about real populations or morally correct outcomes.

## 1. Two-layer decision structure

The normative oracle `N` receives a canonical event record, applicable hard-policy results, and one evaluator profile.

1. If `hard_violations` is non-empty, return `reject` for every profile.
2. Otherwise enter the discretionary layer:
   - escalate when evidence-derived uncertainty exceeds the profile threshold;
   - reject when a dimension crosses a profile veto floor;
   - reject sufficiently harmful low-reversibility outcomes;
   - compute a weighted impact score;
   - return `reject`, `escalate`, or `allow` using fixed score bands.

Evaluator profiles cannot waive hard policy. All evaluator-twin label flips must be traceable to a discretionary threshold, veto, or weight.

## 2. Shared dimensions

The oracle consumes signed effects in `[-1,1]` for:

- `safety`
- `privacy`
- `autonomy`
- `trust`
- `efficiency`
- `fairness`
- `commitment`

Weights sum to one. Veto floors and uncertainty thresholds remain profile-specific and are machine-readable in `configs/evaluator_profiles.toml`.

## 3. Initial profiles

### `procedure_preserving`

Places high weight on commitments, privacy, and process stability. It rejects moderate promise/confidentiality damage even when an action has a positive immediate effect.

### `harm_averse`

Places the highest weight on safety and uses the lowest uncertainty and irreversible-harm tolerances.

### `autonomy_preserving`

Places the highest weight on autonomy and tolerates reversible, informed choices unless they cross a hard-policy or severe-harm boundary.

### `efficiency_tolerant`

Places the highest weight on efficiency and tolerates reversible process costs, while retaining all common hard-policy vetoes.

## 4. Oracle formula

For profile weights `w`, impact vector `i`, reversibility `r`, policy minimum `p`, complete evidence count `q`, observed evidence count `o`, and conflict flag `c`:

```text
u = min(1, 0.8 * max(q - o, 0) / max(q, 1) + 0.2 * int(c))
policy_result = policy_oracle(p, o, c, event_record, policy)
if policy_result.hard_violations:
    reject
elif u >= uncertainty_escalate_at:
    escalate
elif any(i[d] <= veto_floor[d]):
    reject
elif r <= irreversibility_cutoff
     and -sum_d w[d] * min(i[d], 0) >= irreversible_harm_veto:
    reject
else:
    score = sum_d w[d] * i[d]
    score <= reject_at_or_below  -> reject
    score >= allow_at_or_above   -> allow
    otherwise                    -> escalate
```

The implementation returns the triggered rule, score, and distance from the score to the nearest band boundary so every synthetic label can be audited. The margin is null for hard-policy, uncertainty, dimension-veto, and irreversible-harm decisions. `uncertainty` is not accepted as a free oracle input.

All scalar event-record and profile inputs are first canonicalized to six decimal places and then
converted to base-10 `Decimal` values. Products, sums, margins, and boundary comparisons receive no
intermediate rounding. Both `r <= irreversibility_cutoff` and
`weighted_harm >= irreversible_harm_veto` include equality, as do the lower and upper score-band
comparisons.

Dimension vetoes short-circuit in the frozen profile-dimension order declared by TOML:
`safety`, `privacy`, `autonomy`, `trust`, `efficiency`, `fairness`, `commitment`. When multiple
floors are crossed, the first dimension in that order supplies the reason code. This order changes
only diagnostic attribution; every crossed floor still yields `reject`.

## 5. Calibration and flip cases

The profile config includes hand-checkable calibration cases. At minimum it must cover:

- universal rejection under a hard violation;
- harm-averse rejection versus efficiency-tolerant allowance for a reversible efficiency gain with moderate safety cost;
- procedure-preserving rejection versus autonomy-preserving allowance for a consented autonomy gain with a moderate privacy cost;
- procedure-preserving rejection versus harm-averse allowance for breaking a soft commitment to obtain a clear safety benefit;
- universal escalation when uncertainty exceeds every profile threshold.

Calibration cases are end-to-end reachability tests, not training examples. Each starts from a complete environment-native pre-state, action, and policy and runs through `T_phys`, `E`, the policy oracle, and `N`. Expected hard reasons, uncertainty, decisions, and reason codes are assertion-only fields. The temporary-fixture allowlist is empty at Phase 1 exit.

## 6. Discretionary density

The generator must search its parameter space for broad, compositionally varied evaluator disagreement. It may not manufacture yield by paraphrasing a few boundary cases or by concentrating one profile pair on one veto. Density, reason-code concentration, weighted-score-flip, and dimension/sign coverage gates live in the predicate contract and are evaluated separately for environments A and B.
