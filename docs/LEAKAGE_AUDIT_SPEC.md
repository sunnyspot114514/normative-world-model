# Generator-exit leakage audit

Status: **revision-2 smoke gates implemented; external smoke acceptance pending**

Time box: implement only the three gates below for Phase 1. Additional linguistic analyses are diagnostics and cannot delay the smoke corpus once the gates pass.

## 1. Audit scope

Audit the fully rendered model input, not only the scenario body:

- system message;
- schema and fixed label enumeration;
- world-state rendering;
- action text;
- policy text;
- evaluator-profile text;
- conversation wrappers and separators.

For structured inputs, the audit first enforces the contract whitelist: only pre-transition state, candidate action, applicable policy, and evaluator profile may be serialized. Any physical delta, event-record field, impact coordinate, reversibility, uncertainty, hard-violation result, oracle reason, or target decision is a blocking leak regardless of lexical statistics.

Natural-language and structured profile shams live with each evaluator twin. Natural-language shams are meaning-preserving profile renderings. Structured shams parse to the identical typed profile object while changing key order, whitespace, and numeric presentation.

Occurrences that are constant across every example, such as a fixed output enumeration, are recorded and whitelisted. Any sample-dependent occurrence is audited.

### One input pipeline

Every structured baseline and structured-input audit consumes the canonical `model_input` object
stored in each family. The generator writes its canonical-byte SHA-256; the audit recomputes it
before feature extraction. A second filtered or hand-selected feature path is forbidden. In
particular, an audit cannot silently omit a field that a model receives.

Bookkeeping fields `state.turn` and `state.ticket` are absent from `model_input` and from natural
language. After output-order shuffling, the audit reports the maximum correlation between row
position and every model-input feature, plus the maximum per-feature uniqueness fraction.

## 2. Gate A — direct token and phrase audit

The non-causal scenario prose must contain zero unwhitelisted direct decision labels or generator-only target markers. A maintained audit lexicon covers exact labels, morphological variants, and tokenizer sequences.

Causal facts such as an observed hazard are not automatically removed. They must be represented across outcomes or checked conditionally rather than erased simply because they are predictive.

## 3. Gate B — conditional surface association

Token/phrase association is computed within strata that hold causal contract variables fixed, including profile, policy family, action family, and relevant predicate signature.

Candidate leaks are tokens that meet both:

- normalized conditional mutual information at least `0.02`; and
- permutation-test false-discovery-adjusted `q < 0.01`.

They are repaired by counterbalancing, template revision, or removal. Raw global mutual information is diagnostic only because policy and profile text has legitimate causal relevance to normative labels.

## 4. Gate C — grouped cheap-model exit test

Train word and character TF-IDF classifiers with splits grouped by scenario and template family.

Three views are reported:

1. `noncausal_surface_only`: causal structured values, policy, and evaluator content masked. This is the generator leak gate.
2. `causal_structured_only`: canonical variables without natural-language rendering. This measures intended task signal.
3. `full_rendered_input`: everything the model sees. This is a mandatory Static competitor, not automatically a generator failure.

For the noncausal surface view, the initial gate is:

- one-vs-rest macro AUC point estimate no greater than `0.55`; and
- 95% scenario-cluster upper bound no greater than `0.60`.

Both thresholds are enforced independently in each environment. The report also includes a pooled
diagnostic, but a pooled PASS cannot override an environment failure. The exact gate freezes before
discovery. Full-input TF-IDF remains in the Static envelope even when the generator passes.

The Gate C result is specifically the prespecified grouped word/character TF-IDF macro AUC and its
scenario-cluster interval. Exploratory token probes, alternative feature encodings, and permutation
tests are reported as diagnostics under their own names and cannot silently replace this estimand.

## 5. Cross-split integrity

- Assign `scenario_id` and environment-native state signatures before rendering.
- Keep every paraphrase, profile twin, sham twin, and rollout from one scenario family in one split.
- Detect exact and near-duplicate rendered texts across splits.
- Report template, action-family, predicate-signature, profile, and label distributions by split.

## 6. Cause-level twin integrity

The intervention and its consequence are separate gates. Each factual twin must change exactly
one `state.*` leaf; each actor twin exactly one `state.actor_values.*` leaf; and each policy twin
exactly one `policy.*` leaf. Source-field change is required for every family. Physical sensitivity
is then reported independently: factual twins must change the transition, policy twins must
preserve it, and actor twins retain the preregistered sensitivity floor.

Natural-language exit auditing also requires zero variable-article errors and directly renders
all five possible values for every ordinal field. For each field, the five rendered markers must
be present and injective; merely declaring a five-word vocabulary is not sufficient.

## 7. Required report

Every generated corpus emits:

- tokenizer/version and rendered-input hashes;
- direct-token violations with field provenance;
- conditional association table and repair decisions;
- grouped TF-IDF metrics with cluster intervals;
- cross-split duplicate report;
- density-gate report;
- reason-pair concentration and weighted-score-flip report;
- environment × impact-dimension × sign coverage matrix and marginal distributions;
- a final `PASS`, `FAIL`, or `UNIDENTIFIED` status.

Hash conventions are byte contracts:

- `natural_language_sha256` is SHA-256 of the exact stored natural-language string encoded as
  UTF-8, with no case folding, Unicode normalization, whitespace change, or appended newline;
- `raw_line_sha256` is SHA-256 of the exact UTF-8 JSONL line bytes after removing only its trailing
  CR/LF record separator;
- `model_input_sha256` is SHA-256 of UTF-8 canonical JSON with sorted keys and separators `,` and
  `:` and with non-ASCII characters preserved.

The generator may write a discovery corpus only after all mandatory gates pass. A failure cannot be hidden by dropping difficult scenario families after observing model behavior.
