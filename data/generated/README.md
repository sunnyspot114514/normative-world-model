# Generated data

Procedurally generated scenarios, paraphrases, split manifests, and audit reports belong here. These files are ignored by Git; generators and schemas are tracked instead.

The revision-2 smoke corpus is generated with:

```powershell
. .\scripts\project-env.ps1
.\.venv\Scripts\python.exe -m normative_world_model phase1-smoke --families 300 --seed 20260715
```

The command writes 300 game and 300 organization families under `phase1_revision2_smoke/`.
Confirmation content is not generated. The retained generator remains locked until an external
acceptance record binds the exact smoke manifest and both corpus hashes.
