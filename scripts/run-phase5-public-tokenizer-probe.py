from __future__ import annotations

import json

from normative_world_model.phase5_tokenizer_probe import (
    default_public_tokenizer_probe_path,
    run_public_tokenizer_probe,
)


def main() -> int:
    result = run_public_tokenizer_probe()
    print(
        json.dumps(
            {
                "status": result["status"],
                "input_tokenization_status": result["input_tokenization_status"],
                "probe_sha256": result["probe_sha256"],
                "prompt_count": result["common_prompt_proof"]["prompt_count"],
                "output_path": str(default_public_tokenizer_probe_path()),
                "lock_a_required_actions": result["lock_a_required_actions"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
