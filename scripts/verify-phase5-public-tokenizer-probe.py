from __future__ import annotations

import json

from normative_world_model.phase5_tokenizer_probe import verify_public_tokenizer_probe


def main() -> int:
    print(json.dumps(verify_public_tokenizer_probe(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
