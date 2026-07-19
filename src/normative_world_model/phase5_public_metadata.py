"""Restricted Phase-5 downloader for public tokenizer/config metadata only.

The public entry point has no caller-controlled repository, revision, URL, path,
or destination. Model weights are outside this module's allowlist.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .phase5_preflight import (
    STAGE2_CONFIG_SEMANTIC_SHA256,
    default_phase5_config_path,
    load_phase5_config,
    validate_stage2_contract,
)
from .phase5_serialization import (
    normalize_hf_publisher_siblings,
    validate_public_metadata_path,
)

DOWNLOAD_FORMAT_VERSION = "phase5-public-metadata-v1"
API_RESPONSE_MAX_BYTES = 16 * 1024 * 1024
PER_FILE_MAX_BYTES = 32 * 1024 * 1024
TOTAL_FILE_MAX_BYTES = 96 * 1024 * 1024
TOTAL_BUNDLE_FILE_MAX_BYTES = 192 * 1024 * 1024
NETWORK_TIMEOUT_SECONDS = 20.0
MAX_ATTEMPTS = 2
MAX_REDIRECTS = 5
REQUESTED_METADATA_FILENAMES = (
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
)
REQUIRED_METADATA_FILENAMES = frozenset(
    {
        "config.json",
        "model.safetensors.index.json",
        "tokenizer.json",
        "tokenizer_config.json",
    }
)


@dataclass(frozen=True)
class FrozenPublicCheckpoint:
    checkpoint: str
    repo_id: str
    revision: str


@dataclass(frozen=True)
class FetchResult:
    body: bytes
    final_url: str
    redirect_chain: tuple[str, ...]
    declared_content_length: int | None


FetchBytes = Callable[[str, int], FetchResult]


def _canonical_sha256(value: Any) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256((canonical + "\n").encode("utf-8")).hexdigest()


def _reject_duplicate_json_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"JSON object contains a duplicate key: {key!r}")
        result[key] = value
    return result


def _load_inert_json(body: bytes, *, label: str) -> Any:
    try:
        return json.loads(
            body.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_json_pairs,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid inert JSON content: {label}") from error


def _validate_inert_metadata_content(relative: str, body: bytes) -> None:
    if not body:
        raise ValueError(f"public metadata file is empty: {relative}")
    if relative.endswith(".json"):
        value = _load_inert_json(body, label=relative)
        if not isinstance(value, dict):
            raise ValueError(f"public metadata JSON must contain an object: {relative}")
    else:
        try:
            body.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(f"public metadata text is not UTF-8: {relative}") from error


def _git_blob_sha1(body: bytes) -> str:
    preimage = f"blob {len(body)}\0".encode("ascii") + body
    return hashlib.sha1(preimage, usedforsecurity=False).hexdigest()


def _is_allowed_huggingface_host(host: str) -> bool:
    return (
        host == "huggingface.co"
        or host.endswith(".huggingface.co")
        or host.endswith(".hf.co")
    )


def validate_huggingface_url(value: str, *, initial: bool) -> str:
    """Validate an initial Hub URL or an official HTTPS redirect target."""

    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or not parsed.path.startswith("/")
        or parsed.fragment
    ):
        raise ValueError(f"unsafe Hugging Face URL: {value!r}")
    if initial:
        if host != "huggingface.co":
            raise ValueError(f"initial Hugging Face host is not exact: {host!r}")
    elif not _is_allowed_huggingface_host(host):
        raise ValueError(f"redirect host is outside the Hugging Face boundary: {host!r}")
    return value


class _RestrictedRedirectHandler(HTTPRedirectHandler):
    def __init__(self) -> None:
        super().__init__()
        self.redirect_chain: list[str] = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        if len(self.redirect_chain) >= MAX_REDIRECTS:
            raise HTTPError(req.full_url, code, "too many redirects", headers, fp)
        validate_huggingface_url(newurl, initial=False)
        self.redirect_chain.append(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _parse_content_length(value: str | None, *, maximum_bytes: int) -> int | None:
    if value is None:
        return None
    if not value.isascii() or not value.isdecimal():
        raise ValueError("response Content-Length is not a decimal integer")
    length = int(value)
    if length > maximum_bytes:
        raise ValueError(f"response Content-Length exceeds cap: {length} > {maximum_bytes}")
    return length


def fetch_restricted_https_bytes(url: str, maximum_bytes: int) -> FetchResult:
    """Fetch one bounded public byte object with restricted redirects."""

    validate_huggingface_url(url, initial=True)
    if not isinstance(maximum_bytes, int) or isinstance(maximum_bytes, bool) or maximum_bytes <= 0:
        raise ValueError("maximum_bytes must be a positive integer")
    redirect_handler = _RestrictedRedirectHandler()
    opener = build_opener(redirect_handler)
    request = Request(
        url,
        headers={
            "Accept-Encoding": "identity",
            "User-Agent": "normative-world-model-phase5-public-metadata/1",
        },
        method="GET",
    )
    with opener.open(request, timeout=NETWORK_TIMEOUT_SECONDS) as response:
        final_url = response.geturl()
        validate_huggingface_url(final_url, initial=final_url == url)
        content_encoding = response.headers.get("Content-Encoding")
        if content_encoding not in (None, "identity"):
            raise ValueError(f"unexpected response Content-Encoding: {content_encoding!r}")
        declared_length = _parse_content_length(
            response.headers.get("Content-Length"),
            maximum_bytes=maximum_bytes,
        )
        body = bytearray()
        while True:
            block = response.read(min(1024 * 1024, maximum_bytes - len(body) + 1))
            if not block:
                break
            body.extend(block)
            if len(body) > maximum_bytes:
                raise ValueError(f"response body exceeds cap: {len(body)} > {maximum_bytes}")
        if declared_length is not None and declared_length != len(body):
            raise ValueError(
                f"response length differs from Content-Length: {len(body)} != {declared_length}"
            )
    return FetchResult(
        body=bytes(body),
        final_url=final_url,
        redirect_chain=tuple(redirect_handler.redirect_chain),
        declared_content_length=declared_length,
    )


def _fetch_with_retry(fetcher: FetchBytes, url: str, maximum_bytes: int) -> FetchResult:
    last_error: BaseException | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            result = fetcher(url, maximum_bytes)
            validate_huggingface_url(url, initial=True)
            validate_huggingface_url(result.final_url, initial=result.final_url == url)
            for redirect in result.redirect_chain:
                validate_huggingface_url(redirect, initial=False)
            if len(result.redirect_chain) > MAX_REDIRECTS:
                raise ValueError("fetch result contains too many redirects")
            if len(result.body) > maximum_bytes:
                raise ValueError("fetcher returned bytes above the requested cap")
            return result
        except HTTPError as error:
            last_error = error
            if error.code != 429 and not 500 <= error.code <= 599:
                raise
        except (URLError, TimeoutError, ConnectionError, OSError) as error:
            last_error = error
        if attempt == MAX_ATTEMPTS:
            break
    if last_error is None:
        raise RuntimeError("bounded fetch failed without an exception")
    raise RuntimeError(f"bounded fetch failed after {MAX_ATTEMPTS} attempts") from last_error


def _frozen_public_checkpoints(config: Mapping[str, Any]) -> tuple[FrozenPublicCheckpoint, ...]:
    if validate_stage2_contract(config):
        raise ValueError("Stage-2 contract is not at its reviewed semantic binding")
    authorization = config.get("authorization", {})
    if authorization.get("public_metadata_download") is not True:
        raise ValueError("public metadata download is not authorized")
    if authorization.get("model_download") is not False:
        raise ValueError("model download must remain unauthorized")
    models = config.get("models", {})
    checkpoints = []
    for checkpoint in ("agentworld", "base"):
        model = models.get(checkpoint, {})
        repo_id = model.get("model_id")
        revision = model.get("observed_revision_2026_07_18")
        if (
            not isinstance(repo_id, str)
            or repo_id.count("/") != 1
            or not isinstance(revision, str)
            or len(revision) != 40
            or any(character not in "0123456789abcdef" for character in revision)
        ):
            raise ValueError(f"invalid frozen public source identity: {checkpoint}")
        checkpoints.append(FrozenPublicCheckpoint(checkpoint, repo_id, revision))
    return tuple(checkpoints)


def _api_url(source: FrozenPublicCheckpoint) -> str:
    repo = quote(source.repo_id, safe="/")
    return (
        f"https://huggingface.co/api/models/{repo}/revision/{source.revision}"
        "?blobs=true"
    )


def _file_url(source: FrozenPublicCheckpoint, relative: str) -> str:
    repo = quote(source.repo_id, safe="/")
    path = quote(validate_public_metadata_path(relative), safe="/")
    return f"https://huggingface.co/{repo}/resolve/{source.revision}/{path}?download=true"


def _publisher_file_plan(
    source: FrozenPublicCheckpoint,
    api_body: bytes,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    document = _load_inert_json(api_body, label=f"publisher API/{source.checkpoint}")
    if not isinstance(document, dict):
        raise ValueError("publisher API response must be an object")
    if document.get("sha") != source.revision:
        raise ValueError(f"publisher API revision mismatch: {source.checkpoint}")
    siblings = document.get("siblings")
    if not isinstance(siblings, list):
        raise ValueError("publisher API response lacks a sibling list")
    normalized = normalize_hf_publisher_siblings(siblings)
    by_path = {str(row["rfilename"]): row for row in normalized}
    raw_by_path = {str(row.get("rfilename")): row for row in siblings if isinstance(row, dict)}
    present = set(REQUESTED_METADATA_FILENAMES) & set(by_path)
    missing = REQUIRED_METADATA_FILENAMES - present
    if missing:
        raise ValueError(f"publisher snapshot lacks required metadata: {sorted(missing)}")
    rows = []
    total = 0
    for relative in REQUESTED_METADATA_FILENAMES:
        if relative not in present:
            continue
        validate_public_metadata_path(relative)
        metadata = by_path[relative]
        size = metadata["size"]
        if size <= 0 or size > PER_FILE_MAX_BYTES:
            raise ValueError(f"publisher metadata file size violates cap: {relative}={size}")
        total += size
        raw = raw_by_path[relative]
        blob_id = raw.get("blobId", raw.get("blob_id"))
        if blob_id is not None and (
            not isinstance(blob_id, str)
            or len(blob_id) != 40
            or any(character not in "0123456789abcdef" for character in blob_id)
        ):
            raise ValueError(f"publisher blob ID is malformed: {relative}")
        lfs_digest = metadata.get("lfs_sha256")
        if lfs_digest is None and blob_id is None:
            raise ValueError(f"publisher exposes no verifiable hash for metadata: {relative}")
        rows.append(
            {
                "path": relative,
                "bytes": size,
                "publisher_lfs_sha256": lfs_digest,
                "publisher_blob_id": blob_id,
            }
        )
    if total > TOTAL_FILE_MAX_BYTES:
        raise ValueError(f"publisher metadata aggregate exceeds cap: {total}")
    return document, rows


def _write_once(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".part")
    if path.exists() or partial.exists():
        raise FileExistsError(f"refusing to overwrite metadata output: {path}")
    try:
        with partial.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(partial, path)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def _download_checkpoint(
    source: FrozenPublicCheckpoint,
    root: Path,
    fetcher: FetchBytes,
) -> dict[str, Any]:
    api_url = _api_url(source)
    api_result = _fetch_with_retry(fetcher, api_url, API_RESPONSE_MAX_BYTES)
    api_document, publisher_plan = _publisher_file_plan(source, api_result.body)
    checkpoint_root = root / source.checkpoint
    _write_once(checkpoint_root / "publisher_api_response.json", api_result.body)
    downloaded = []
    for expected in publisher_plan:
        relative = str(expected["path"])
        url = _file_url(source, relative)
        result = _fetch_with_retry(fetcher, url, min(PER_FILE_MAX_BYTES, expected["bytes"]))
        if len(result.body) != expected["bytes"]:
            raise ValueError(
                f"downloaded metadata size mismatch: {relative} "
                f"{len(result.body)} != {expected['bytes']}"
            )
        digest = hashlib.sha256(result.body).hexdigest()
        publisher_digest = expected["publisher_lfs_sha256"]
        if publisher_digest is not None and digest != publisher_digest:
            raise ValueError(f"downloaded metadata SHA-256 differs from publisher LFS: {relative}")
        publisher_blob_id = expected["publisher_blob_id"]
        if publisher_digest is None and _git_blob_sha1(result.body) != publisher_blob_id:
            raise ValueError(f"downloaded metadata differs from publisher Git blob: {relative}")
        _validate_inert_metadata_content(relative, result.body)
        _write_once(checkpoint_root / "files" / relative, result.body)
        downloaded.append(
            {
                **expected,
                "sha256": digest,
                "publisher_verification_kind": (
                    "lfs_sha256" if publisher_digest is not None else "git_blob_sha1"
                ),
                "request_url": url,
                "final_url": result.final_url,
                "redirect_chain": list(result.redirect_chain),
            }
        )
    snapshot = {
        "format_version": DOWNLOAD_FORMAT_VERSION,
        "checkpoint": source.checkpoint,
        "repo_id": source.repo_id,
        "revision": source.revision,
        "api_request_url": api_url,
        "api_final_url": api_result.final_url,
        "api_redirect_chain": list(api_result.redirect_chain),
        "api_response_bytes": len(api_result.body),
        "api_response_sha256": hashlib.sha256(api_result.body).hexdigest(),
        "publisher_document_sha256": _canonical_sha256(api_document),
        "files": downloaded,
        "file_count": len(downloaded),
        "total_file_bytes": sum(row["bytes"] for row in downloaded),
    }
    snapshot["snapshot_manifest_sha256"] = _canonical_sha256(snapshot)
    _write_once(
        checkpoint_root / "snapshot_manifest.json",
        (json.dumps(snapshot, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return snapshot


def _download_frozen_sources_to_root(
    sources: tuple[FrozenPublicCheckpoint, ...],
    root: Path,
    fetcher: FetchBytes,
) -> dict[str, Any]:
    if root.exists():
        raise FileExistsError(f"metadata output root already exists: {root}")
    root.mkdir(parents=True)
    try:
        snapshots = [_download_checkpoint(source, root, fetcher) for source in sources]
        bundle_bytes = sum(snapshot["total_file_bytes"] for snapshot in snapshots)
        if bundle_bytes > TOTAL_BUNDLE_FILE_MAX_BYTES:
            raise ValueError(
                f"public metadata bundle exceeds aggregate cap: "
                f"{bundle_bytes} > {TOTAL_BUNDLE_FILE_MAX_BYTES}"
            )
        manifest = {
            "format_version": DOWNLOAD_FORMAT_VERSION,
            "stage2_config_semantic_sha256": STAGE2_CONFIG_SEMANTIC_SHA256,
            "requested_metadata_filenames": list(REQUESTED_METADATA_FILENAMES),
            "required_metadata_filenames": sorted(REQUIRED_METADATA_FILENAMES),
            "api_response_max_bytes": API_RESPONSE_MAX_BYTES,
            "per_file_max_bytes": PER_FILE_MAX_BYTES,
            "total_file_max_bytes": TOTAL_FILE_MAX_BYTES,
            "total_bundle_file_max_bytes": TOTAL_BUNDLE_FILE_MAX_BYTES,
            "total_bundle_file_bytes": bundle_bytes,
            "network_timeout_seconds": NETWORK_TIMEOUT_SECONDS,
            "maximum_attempts": MAX_ATTEMPTS,
            "maximum_redirects": MAX_REDIRECTS,
            "sources": [asdict(source) for source in sources],
            "snapshots": snapshots,
        }
        manifest["manifest_sha256"] = _canonical_sha256(manifest)
        _write_once(
            root / "manifest.json",
            (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        )
        return manifest
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise


def default_public_metadata_root() -> Path:
    project_root = default_phase5_config_path().resolve().parents[1]
    return (
        project_root
        / ".cache"
        / "phase5_public_metadata"
        / f"v1-{STAGE2_CONFIG_SEMANTIC_SHA256[:12]}"
    )


def download_frozen_public_metadata() -> dict[str, Any]:
    """Download the two reviewed public metadata snapshots into the ignored cache."""

    config = load_phase5_config()
    sources = _frozen_public_checkpoints(config)
    root = default_public_metadata_root()
    project_root = default_phase5_config_path().resolve().parents[1]
    allowed_parent = (project_root / ".cache" / "phase5_public_metadata").resolve()
    root.resolve().relative_to(allowed_parent)
    return _download_frozen_sources_to_root(sources, root, fetch_restricted_https_bytes)
