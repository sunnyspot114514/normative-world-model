# Codex pre-review addendum: resolved-runtime evidence

Date: 2026-07-20

This addendum narrows one claim made during the completed termination-v2 K3
review. It does not change the runtime-plan artifact or authorize execution.

## Required additional attack

The termination reviewer proposed `/server_info` as returned evidence for
`language_model_only=true`. Official vLLM `v0.25.1` registers this endpoint only
when `VLLM_SERVER_DEV_MODE=1`:

- `vllm/entrypoints/openai/api_server.py:198-201` gates all development routers;
- `vllm/envs.py:1312-1315` defaults the variable to `0`;
- `vllm/entrypoints/serve/dev/server_info/api_router.py:43-59` defines the
  endpoint.

The current common environment does not enable development mode. During the
runtime-plan audit, decide whether this is honest because runtime evidence
collection is still explicitly unresolved, and reject any claim that the
current launch vectors already expose `/server_info`. State what exact future
evidence contract is needed before the reusable client/orchestrator can freeze:

- reviewed loopback-only development mode plus raw server-info capture; or
- development mode disabled plus an equivalent exact argv/environment,
  startup-log, model-alias, and behavioral proof.

Also confirm that no new runtime-plan caller makes the known basename-only
metadata helper reachable. The helper remains mandatory pre-Lock-A hardening or
closure-exclusion debt, not a current execution authorization.
