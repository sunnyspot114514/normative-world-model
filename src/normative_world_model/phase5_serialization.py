"""Phase-5 public-source and common-serialization proof primitives.

All functions are local and side-effect free apart from reading caller-supplied
files.  No network or model-weight download implementation lives here.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

PUBLIC_METADATA_FILENAMES = frozenset(
    {
        "added_tokens.json",
        "chat_template.jinja",
        "config.json",
        "generation_config.json",
        "merges.txt",
        "model.safetensors.index.json",
        "preprocessor_config.json",
        "special_tokens_map.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "vocab.json",
    }
)
TOKENIZER_FILES = ("tokenizer.json", "tokenizer_config.json")
COMPARABLE_TOKENIZER_SECTIONS = (
    "model",
    "normalizer",
    "pre_tokenizer",
    "post_processor",
    "decoder",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_public_metadata_path(value: str) -> str:
    """Accept only a small exact metadata set and never a weight blob."""

    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or not path.parts
        or path.is_absolute()
        or ".." in path.parts
        or path.name not in PUBLIC_METADATA_FILENAMES
        or normalized != path.as_posix()
    ):
        raise ValueError(f"not an allowlisted public metadata path: {value!r}")
    if path.name.endswith(".safetensors"):
        raise ValueError("model weights are not public-metadata downloads")
    return path.as_posix()


def _load_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON file must contain an object: {path}")
    return value


def inspect_tokenizer_packages(base_root: Path, agentworld_root: Path) -> dict[str, Any]:
    """Compare caller-supplied tokenizer snapshots and bind their exact bytes."""

    roots = {"base": base_root, "agentworld": agentworld_root}
    documents: dict[str, dict[str, dict[str, Any]]] = {}
    files: dict[str, dict[str, dict[str, Any]]] = {}
    for checkpoint, root in roots.items():
        documents[checkpoint] = {}
        files[checkpoint] = {}
        for name in TOKENIZER_FILES:
            path = root / name
            if not path.is_file() or path.is_symlink():
                raise ValueError(f"missing regular tokenizer file: {checkpoint}/{name}")
            documents[checkpoint][name] = _load_json_object(path)
            files[checkpoint][name] = {
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }

    base_tokenizer = documents["base"]["tokenizer.json"]
    agent_tokenizer = documents["agentworld"]["tokenizer.json"]
    base_vocab = base_tokenizer.get("model", {}).get("vocab")
    agent_vocab = agent_tokenizer.get("model", {}).get("vocab")
    if not isinstance(base_vocab, dict) or not isinstance(agent_vocab, dict):
        raise ValueError("tokenizer model.vocab must be an object")
    if base_vocab != agent_vocab:
        raise ValueError("tokenizer core vocabularies or token IDs differ")
    for section in COMPARABLE_TOKENIZER_SECTIONS:
        if base_tokenizer.get(section) != agent_tokenizer.get(section):
            raise ValueError(f"tokenizer preprocessing section differs: {section}")

    def added_by_id(document: Mapping[str, Any]) -> dict[int, str]:
        result = {}
        for entry in document.get("added_tokens", []):
            if not isinstance(entry, dict) or not isinstance(entry.get("id"), int):
                raise ValueError("added token entries must contain integer IDs")
            token_id = int(entry["id"])
            if token_id in result:
                raise ValueError(f"duplicate added token ID: {token_id}")
            result[token_id] = str(entry.get("content"))
        return result

    base_added = added_by_id(base_tokenizer)
    agent_added = added_by_id(agent_tokenizer)
    shared_ids = set(base_added) & set(agent_added)
    if any(base_added[token_id] != agent_added[token_id] for token_id in shared_ids):
        raise ValueError("shared added-token IDs differ in content")
    base_template = documents["base"]["tokenizer_config.json"].get("chat_template")
    agent_template = documents["agentworld"]["tokenizer_config.json"].get("chat_template")
    if not isinstance(base_template, str) or not isinstance(agent_template, str):
        raise ValueError("both tokenizer configs must contain string chat templates")
    return {
        "status": "PASS",
        "files": files,
        "core_vocab_entries": len(base_vocab),
        "core_vocab_identical": True,
        "shared_added_tokens": len(shared_ids),
        "base_only_added_tokens": {
            str(token_id): base_added[token_id]
            for token_id in sorted(set(base_added) - set(agent_added))
        },
        "agentworld_only_added_tokens": {
            str(token_id): agent_added[token_id]
            for token_id in sorted(set(agent_added) - set(base_added))
        },
        "base_chat_template_sha256": hashlib.sha256(base_template.encode("utf-8")).hexdigest(),
        "agentworld_chat_template_sha256": hashlib.sha256(
            agent_template.encode("utf-8")
        ).hexdigest(),
        "chat_templates_identical": base_template == agent_template,
    }


def render_common_base_prompt(
    base_tokenizer: Any,
    messages: Sequence[Mapping[str, str]],
) -> str:
    """Render the common prompt with Base's template and thinking disabled."""

    rendered = base_tokenizer.apply_chat_template(
        list(messages),
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    if not isinstance(rendered, str) or not rendered:
        raise ValueError("base chat template did not return a nonempty string")
    return rendered


def _token_ids(tokenizer: Any, text: str) -> list[int]:
    raw = tokenizer.encode(text, add_special_tokens=False)
    values = list(raw)
    if not values or any(
        not isinstance(item, int) or isinstance(item, bool) or item < 0
        for item in values
    ):
        raise ValueError("tokenizer.encode must return a nonempty integer sequence")
    return values


def prove_common_prompt_token_equality(
    rendered_prompts: Iterable[tuple[str, str]],
    *,
    base_tokenizer: Any,
    agentworld_tokenizer: Any,
) -> dict[str, Any]:
    """Prove exact token-ID equality for every supplied locally retained prompt."""

    rows = []
    seen_ids: set[str] = set()
    for prompt_id, text in rendered_prompts:
        if not isinstance(prompt_id, str) or not prompt_id:
            raise ValueError("prompt IDs must be nonempty strings")
        if not isinstance(text, str) or not text:
            raise ValueError(f"rendered prompt must be nonempty: {prompt_id}")
        if prompt_id in seen_ids:
            raise ValueError(f"duplicate prompt ID: {prompt_id}")
        seen_ids.add(prompt_id)
        base_ids = _token_ids(base_tokenizer, text)
        agent_ids = _token_ids(agentworld_tokenizer, text)
        if base_ids != agent_ids:
            limit = min(len(base_ids), len(agent_ids))
            mismatch = next(
                (
                    index
                    for index in range(limit)
                    if base_ids[index] != agent_ids[index]
                ),
                limit,
            )
            raise ValueError(f"token-ID mismatch for {prompt_id} at position {mismatch}")
        rows.append(
            {
                "prompt_id": prompt_id,
                "prompt_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "token_count": len(base_ids),
                "token_ids": base_ids,
            }
        )
    if not rows:
        raise ValueError("token equality proof requires at least one prompt")
    canonical = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "status": "PASS",
        "prompt_count": len(rows),
        "rows": rows,
        "proof_sha256": hashlib.sha256((canonical + "\n").encode("utf-8")).hexdigest(),
    }


def resolve_publisher_weight_plan(
    model_index: Mapping[str, Any],
    publisher_siblings: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Resolve the index-declared weight set without assuming a shard count."""

    weight_map = model_index.get("weight_map")
    if not isinstance(weight_map, dict) or not weight_map:
        raise ValueError("model index has no nonempty weight_map")
    referenced = sorted({str(value) for value in weight_map.values()})
    siblings = {}
    for item in publisher_siblings:
        relative = str(item.get("rfilename"))
        if relative in siblings:
            raise ValueError(f"duplicate publisher sibling path: {relative}")
        siblings[relative] = item
    rows = []
    for relative in referenced:
        path = PurePosixPath(relative)
        if (
            path.is_absolute()
            or ".." in path.parts
            or path.as_posix() != relative
            or not relative.endswith(".safetensors")
        ):
            raise ValueError(f"invalid index weight path: {relative}")
        try:
            sibling = siblings[relative]
        except KeyError as error:
            raise ValueError(f"publisher metadata lacks referenced weight: {relative}") from error
        size = sibling.get("size")
        digest = sibling.get("lfs_sha256")
        if not isinstance(size, int) or size <= 0:
            raise ValueError(f"publisher weight has invalid size: {relative}")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError(f"publisher weight lacks a lowercase SHA-256: {relative}")
        rows.append({"path": relative, "bytes": size, "sha256": digest})
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    return {
        "weight_file_count": len(rows),
        "total_weight_bytes": sum(row["bytes"] for row in rows),
        "files": rows,
        "weight_plan_sha256": hashlib.sha256((canonical + "\n").encode("utf-8")).hexdigest(),
    }
