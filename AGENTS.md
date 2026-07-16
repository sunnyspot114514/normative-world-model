# Project boundary

These instructions apply to the entire `normative-world-model` tree.

- Treat this directory as a standalone project. Do not write to sibling projects.
- Keep the Python environment in `.venv/` and all tool/model caches in `.cache/`.
- Keep temporary files in `.tmp/`, experiment outputs in `runs/` or `artifacts/`, and downloaded weights in `models/`.
- Do not import data from sibling projects implicitly. Any future external input must be declared explicitly, treated as read-only, and copied into a versioned snapshot with a hash manifest.
- Never commit `.env`, API keys, downloaded models, raw/generated datasets, caches, or run artifacts.
- Preserve scenario-level split identifiers. Paraphrases of one underlying scenario must never cross train/validation/test boundaries.
- Run `scripts/check.ps1` before presenting a change as complete.

