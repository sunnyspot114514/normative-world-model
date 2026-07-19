# Codex adjudication: public weight-plan metadata closure

Date: 2026-07-20

Status: **LOCAL PASS FOR METADATA-ONLY V3; K3 HAS NO VERDICT**

Because K3 was unavailable, Codex performed the requested checks and found two
blocking defects before allowing the metadata-only step:

1. `json.loads(..., parse_constant=...)` rejects literal `NaN` and `Infinity`
   but does not reject a finite-looking JSON exponent such as `1e309`, which
   Python converts to infinity. The inert parser now also supplies a
   finite-checking `parse_float`, and tests cover all four forms.
2. The first resolver patch incorrectly required
   `index.metadata.total_size == sum(publisher LFS file sizes)`. The official
   Hugging Face sharder constructs `total_size` by accumulating tensor storage
   sizes, while LFS sizes are full safetensors container bytes. Both real
   checkpoints reproduced the expected small positive header difference. The
   resolver now records these quantities separately, rejects only an index
   tensor total that exceeds publisher container bytes, and reports the exact
   difference.

The first generated plan was then found to lack implementation-source binding.
It is preserved as exploratory v1. V2 added source binding and thereby exposed
one more parser issue: an integer-valued JSON float outside exact binary64 range
could round into the allowed range before the resolver saw it. The inert parser
now cross-checks the original decimal literal against its float conversion and
rejects integer drift or loss of a fractional part. That source change correctly
invalidated v2. V3 binds the exact bytes and SHA-256 values of the preflight,
metadata verifier, weight-plan builder, and serialization resolver sources. Its
verifier revalidates the metadata bundle and independently rebuilds the complete
document.

The local decision permits only this metadata artifact. It does not permit
network fetching, model-weight download, population selection, project-prompt
access, rental, GPU execution, confirmation access, or science. A completed K3
review remains useful at the next combined Lock-A review rather than being
misrepresented as having occurred here.

Official implementation reference:
<https://github.com/huggingface/huggingface_hub/blob/main/src/huggingface_hub/serialization/_base.py>
