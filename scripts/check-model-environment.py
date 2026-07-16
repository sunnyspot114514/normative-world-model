"""Verify the isolated local-model runtime and CUDA device."""

from __future__ import annotations

import json
from importlib.metadata import version

import accelerate
import peft
import safetensors
import torch
import transformers


def main() -> int:
    result = {
        "accelerate": accelerate.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda_runtime": torch.version.cuda,
        "gpu": (
            torch.cuda.get_device_name(0)
            if torch.cuda.is_available()
            else None
        ),
        "hf_xet": version("hf-xet"),
        "peft": peft.__version__,
        "safetensors": safetensors.__version__,
        "torch": torch.__version__,
        "transformers": transformers.__version__,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["cuda_available"]:
        raise SystemExit("CUDA is unavailable after installing the model stack")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
