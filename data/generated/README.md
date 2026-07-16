# Generated data

Procedurally generated scenarios, paraphrases, split manifests, and audit reports belong here. These files are ignored by Git; generators and schemas are tracked instead.

The current preregistration-v3 internal smoke corpus is generated with:

```powershell
. .\scripts\project-env.ps1
.\.venv\Scripts\python.exe .\scripts\run-phase1-v3-smoke.py --families 300 --seed 20260716
.\scripts\check-phase1-v3-smoke.ps1
```

The command writes 300 game and 300 organization families under `phase1_v3_smoke/`. The rejected
v3 revision-0 corpus remains archived under `phase1_v3_revision0_smoke/`, while revision-2 smoke data
remains under `phase1_revision2_smoke/`. Confirmation content is not generated. The retained
generator remains locked until an external acceptance record binds the exact v3 revision-1 smoke
manifest and both corpus hashes.

Phase-2 full-rollout derived views belong under `phase2_internal/`. Phase-3 one-step local-pilot
views belong under `phase3_internal/`; they retain exact source corpus hashes, use empty rollout
targets only for the one-step stage, and remain ignored.
