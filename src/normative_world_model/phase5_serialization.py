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
    "truncation",
    "padding",
)
COMPARABLE_TOKENIZER_CONFIG_FIELDS = (
    "add_bos_token",
    "add_prefix_space",
    "additional_special_tokens",
    "bos_token",
    "clean_up_tokenization_spaces",
    "errors",
    "extra_special_tokens",
    "pad_token",
    "pretokenize_regex",
    "split_special_tokens",
    "tokenizer_class",
    "unk_token",
)
DIAGNOSTIC_TOKENIZER_CONFIG_FIELDS = ("eos_token", "model_max_length")
COMMON_ASSISTANT_PREFIX = "<|im_start|>assistant\n"
FORBIDDEN_COMMON_CONTROL_LITERALS = (
    "<tool_response>",
    "</tool_response>",
    "<think>",
    "</think>",
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
        or "\\" in value
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
        if not root.is_dir() or root.is_symlink():
            raise ValueError(f"tokenizer root must be a regular directory: {checkpoint}")
        resolved_root = root.resolve(strict=True)
        documents[checkpoint] = {}
        files[checkpoint] = {}
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise ValueError(f"tokenizer snapshot contains a symlink: {checkpoint}/{path.name}")
            if getattr(path, "is_junction", lambda: False)():
                raise ValueError(
                    f"tokenizer snapshot contains a junction: {checkpoint}/{path.name}"
                )
            if not path.is_file():
                continue
            try:
                path.resolve(strict=True).relative_to(resolved_root)
            except ValueError as error:
                raise ValueError(
                    f"tokenizer snapshot file escapes its root: {checkpoint}/{path.name}"
                ) from error
            relative = path.relative_to(root).as_posix()
            validate_public_metadata_path(relative)
            files[checkpoint][relative] = {
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        for name in TOKENIZER_FILES:
            path = root / name
            if not path.is_file() or path.is_symlink():
                raise ValueError(f"missing regular tokenizer file: {checkpoint}/{name}")
            documents[checkpoint][name] = _load_json_object(path)

    base_tokenizer = documents["base"]["tokenizer.json"]
    agent_tokenizer = documents["agentworld"]["tokenizer.json"]
    base_vocab = base_tokenizer.get("model", {}).get("vocab")
    agent_vocab = agent_tokenizer.get("model", {}).get("vocab")
    if not isinstance(base_vocab, dict) or not isinstance(agent_vocab, dict):
        raise ValueError("tokenizer model.vocab must be an object")
    if base_vocab != agent_vocab:
        raise ValueError("tokenizer core vocabularies or token IDs differ")

    def comparable_section(document: Mapping[str, Any], section: str) -> Any:
        value = document.get(section)
        if section == "model" and isinstance(value, dict) and value.get("type") == "BPE":
            value = dict(value)
            value.setdefault("ignore_merges", False)
        return value

    normalized_default_equivalences = []
    for section in COMPARABLE_TOKENIZER_SECTIONS:
        base_section = comparable_section(base_tokenizer, section)
        agent_section = comparable_section(agent_tokenizer, section)
        if base_section != agent_section:
            raise ValueError(f"tokenizer preprocessing section differs: {section}")
        if base_tokenizer.get(section) != agent_tokenizer.get(section):
            normalized_default_equivalences.append(f"{section}.ignore_merges:absent_equals_false")

    base_config = documents["base"]["tokenizer_config.json"]
    agent_config = documents["agentworld"]["tokenizer_config.json"]
    for field in COMPARABLE_TOKENIZER_CONFIG_FIELDS:
        if base_config.get(field) != agent_config.get(field):
            raise ValueError(f"tokenizer config preprocessing field differs: {field}")
    tokenizer_config_differences = {
        field: {"base": base_config.get(field), "agentworld": agent_config.get(field)}
        for field in DIAGNOSTIC_TOKENIZER_CONFIG_FIELDS
        if base_config.get(field) != agent_config.get(field)
    }

    def added_by_id(
        tokenizer_document: Mapping[str, Any],
        config_document: Mapping[str, Any],
    ) -> dict[int, dict[str, Any]]:
        result = {}
        entries = tokenizer_document.get("added_tokens", [])
        if not isinstance(entries, list):
            raise ValueError("tokenizer added_tokens must be a list")
        for entry in entries:
            if (
                not isinstance(entry, dict)
                or not isinstance(entry.get("id"), int)
                or isinstance(entry.get("id"), bool)
                or entry["id"] < 0
                or not isinstance(entry.get("content"), str)
                or not entry["content"]
            ):
                raise ValueError("added token entries must contain integer IDs")
            token_id = int(entry["id"])
            if token_id in result:
                raise ValueError(f"duplicate added token ID: {token_id}")
            result[token_id] = dict(entry)
        decoder = config_document.get("added_tokens_decoder", {})
        if not isinstance(decoder, dict):
            raise ValueError("tokenizer config added_tokens_decoder must be an object")
        for raw_token_id, attributes in decoder.items():
            if (
                not isinstance(raw_token_id, str)
                or not raw_token_id.isascii()
                or not raw_token_id.isdecimal()
                or not isinstance(attributes, dict)
                or "id" in attributes
            ):
                raise ValueError("tokenizer config added-token entry is malformed")
            token_id = int(raw_token_id)
            if raw_token_id != str(token_id):
                raise ValueError("tokenizer config added-token ID is not canonical")
            normalized = {"id": token_id, **attributes}
            if not isinstance(normalized.get("content"), str) or not normalized["content"]:
                raise ValueError("tokenizer config added-token content is malformed")
            if token_id in result and result[token_id] != normalized:
                raise ValueError(f"tokenizer package added-token sources disagree: {token_id}")
            result[token_id] = normalized
        return result

    base_added = added_by_id(base_tokenizer, base_config)
    agent_added = added_by_id(agent_tokenizer, agent_config)
    shared_ids = set(base_added) & set(agent_added)
    if any(base_added[token_id] != agent_added[token_id] for token_id in shared_ids):
        raise ValueError("shared added-token IDs differ in attributes")

    def resolved_template(checkpoint: str) -> str:
        inline = documents[checkpoint]["tokenizer_config.json"].get("chat_template")
        template_path = roots[checkpoint] / "chat_template.jinja"
        file_template = (
            template_path.read_text(encoding="utf-8") if template_path.is_file() else None
        )
        if inline is not None and not isinstance(inline, str):
            raise ValueError(f"tokenizer config chat_template must be a string: {checkpoint}")
        if inline is not None and file_template is not None and inline != file_template:
            raise ValueError(f"inline and file chat templates disagree: {checkpoint}")
        template = inline if inline is not None else file_template
        if not isinstance(template, str) or not template:
            raise ValueError(f"tokenizer package has no nonempty chat template: {checkpoint}")
        return template

    base_template = resolved_template("base")
    agent_template = resolved_template("agentworld")
    return {
        "status": "PASS",
        "files": files,
        "core_vocab_entries": len(base_vocab),
        "core_vocab_identical": True,
        "normalized_default_equivalences": normalized_default_equivalences,
        "tokenizer_config_differences": tokenizer_config_differences,
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
    """Render shared history, then append an exact assistant prefix without think tags."""

    history = base_tokenizer.apply_chat_template(
        list(messages),
        tokenize=False,
        add_generation_prompt=False,
        enable_thinking=False,
    )
    if not isinstance(history, str) or not history:
        raise ValueError("base chat template did not return a nonempty string")
    if history.endswith(COMMON_ASSISTANT_PREFIX):
        raise ValueError("base chat history unexpectedly contains an assistant prefix")
    present = [literal for literal in FORBIDDEN_COMMON_CONTROL_LITERALS if literal in history]
    if present:
        raise ValueError(f"common prompt contains forbidden control literals: {present}")
    rendered = history + COMMON_ASSISTANT_PREFIX
    return rendered


def _token_ids(tokenizer: Any, text: str) -> list[int]:
    raw = tokenizer.encode(text, add_special_tokens=False)
    values = list(raw)
    if not values or any(
        not isinstance(item, int) or isinstance(item, bool) or item < 0
        for item in values
    ):
        raise ValueError("tokenizer.encode must return a nonempty integer sequence")
    try:
        vocabulary_size = len(tokenizer)
    except (TypeError, AttributeError) as error:
        raise ValueError("tokenizer must expose its complete vocabulary size") from error
    if (
        not isinstance(vocabulary_size, int)
        or isinstance(vocabulary_size, bool)
        or vocabulary_size <= 0
        or any(item >= vocabulary_size for item in values)
    ):
        raise ValueError("tokenizer.encode returned an ID outside its vocabulary")
    return values


def _proof_snapshot_binding(report: Mapping[str, Any]) -> dict[str, Any]:
    if report.get("status") != "PASS" or report.get("core_vocab_identical") is not True:
        raise ValueError("tokenizer package report is not a passing core-vocabulary proof")
    files = report.get("files")
    if not isinstance(files, Mapping) or set(files) != {"base", "agentworld"}:
        raise ValueError("tokenizer package report lacks both snapshot file maps")
    binding: dict[str, dict[str, dict[str, Any]]] = {}
    for checkpoint in ("base", "agentworld"):
        checkpoint_files = files.get(checkpoint)
        if not isinstance(checkpoint_files, Mapping) or not checkpoint_files:
            raise ValueError(f"tokenizer package report has no files for {checkpoint}")
        binding[checkpoint] = {}
        for relative, metadata in sorted(checkpoint_files.items()):
            if not isinstance(relative, str) or not isinstance(metadata, Mapping):
                raise ValueError("tokenizer snapshot file binding is malformed")
            validate_public_metadata_path(relative)
            size = metadata.get("bytes")
            digest = metadata.get("sha256")
            if (
                not isinstance(size, int)
                or isinstance(size, bool)
                or size < 0
                or not isinstance(digest, str)
                or len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)
            ):
                raise ValueError("tokenizer snapshot file binding is malformed")
            binding[checkpoint][relative] = {"bytes": size, "sha256": digest}
    return binding


def prove_common_prompt_token_equality(
    rendered_prompts: Iterable[tuple[str, str]],
    *,
    base_tokenizer: Any,
    agentworld_tokenizer: Any,
    tokenizer_package_report: Mapping[str, Any],
) -> dict[str, Any]:
    """Prove exact token-ID equality for every supplied locally retained prompt."""

    snapshot_binding = _proof_snapshot_binding(tokenizer_package_report)
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
    proof_payload = {"tokenizer_snapshot_files": snapshot_binding, "rows": rows}
    canonical = json.dumps(
        proof_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    binding_canonical = json.dumps(snapshot_binding, sort_keys=True, separators=(",", ":"))
    return {
        "status": "PASS",
        "prompt_count": len(rows),
        "tokenizer_snapshot_files": snapshot_binding,
        "tokenizer_snapshot_binding_sha256": hashlib.sha256(
            (binding_canonical + "\n").encode("utf-8")
        ).hexdigest(),
        "rows": rows,
        "proof_sha256": hashlib.sha256((canonical + "\n").encode("utf-8")).hexdigest(),
    }


def _lowercase_sha256(value: Any) -> str:
    if isinstance(value, str) and value.startswith("sha256:"):
        value = value.removeprefix("sha256:")
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError("publisher LFS digest is not a lowercase SHA-256")
    return value


def normalize_hf_publisher_siblings(
    raw_siblings: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Normalize the reviewed Hugging Face blobs=true sibling shape."""

    normalized = []
    seen: set[str] = set()
    for item in raw_siblings:
        relative = item.get("rfilename")
        if not isinstance(relative, str):
            raise ValueError("publisher sibling lacks rfilename")
        path = PurePosixPath(relative)
        if (
            not relative
            or "\\" in relative
            or path.is_absolute()
            or ".." in path.parts
            or "." in path.parts
            or path.as_posix() != relative
        ):
            raise ValueError(f"publisher sibling path is invalid: {relative!r}")
        if relative in seen:
            raise ValueError(f"duplicate publisher sibling path: {relative}")
        seen.add(relative)
        size = item.get("size")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ValueError(f"publisher sibling has invalid size: {relative}")
        row: dict[str, Any] = {"rfilename": relative, "size": size}
        lfs = item.get("lfs")
        if lfs is not None:
            if not isinstance(lfs, Mapping):
                raise ValueError(f"publisher sibling has malformed LFS metadata: {relative}")
            candidates = [lfs[key] for key in ("sha256", "oid") if key in lfs]
            if not candidates:
                raise ValueError(f"publisher sibling LFS metadata lacks a digest: {relative}")
            digests = {_lowercase_sha256(value) for value in candidates}
            if len(digests) != 1:
                raise ValueError(f"publisher sibling LFS digests disagree: {relative}")
            lfs_size = lfs.get("size")
            if (
                not isinstance(lfs_size, int)
                or isinstance(lfs_size, bool)
                or lfs_size != size
            ):
                raise ValueError(f"publisher sibling and LFS sizes disagree: {relative}")
            row["lfs_sha256"] = next(iter(digests))
        normalized.append(row)
    return normalized


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
    for item in normalize_hf_publisher_siblings(publisher_siblings):
        relative = str(item.get("rfilename"))
        if relative in siblings:
            raise ValueError(f"duplicate publisher sibling path: {relative}")
        siblings[relative] = item
    rows = []
    for relative in referenced:
        path = PurePosixPath(relative)
        if (
            path.is_absolute()
            or "\\" in relative
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
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            raise ValueError(f"publisher weight has invalid size: {relative}")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError(f"publisher weight lacks a lowercase SHA-256: {relative}")
        rows.append({"path": relative, "bytes": size, "sha256": digest})
    index_metadata = model_index.get("metadata", {})
    if not isinstance(index_metadata, Mapping):
        raise ValueError("model index metadata must be an object")
    declared_total = index_metadata.get("total_size")
    if declared_total is not None:
        if (
            not isinstance(declared_total, int)
            or isinstance(declared_total, bool)
            or declared_total <= 0
        ):
            raise ValueError("model index metadata.total_size is invalid")
        if declared_total != sum(row["bytes"] for row in rows):
            raise ValueError("model index total_size disagrees with publisher weights")
    unreferenced = sorted(
        relative
        for relative in siblings
        if relative.endswith(".safetensors") and relative not in referenced
    )
    canonical = json.dumps(
        {"files": rows, "unreferenced_weight_files": unreferenced},
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "weight_file_count": len(rows),
        "total_weight_bytes": sum(row["bytes"] for row in rows),
        "files": rows,
        "unreferenced_weight_files": unreferenced,
        "weight_plan_sha256": hashlib.sha256((canonical + "\n").encode("utf-8")).hexdigest(),
    }
