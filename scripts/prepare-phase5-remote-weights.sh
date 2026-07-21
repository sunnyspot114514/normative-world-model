#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 4 ]]; then
  echo "usage: $0 MANIFEST_TSV AGENTWORLD_SOURCE_ROOT TARGET_ROOT EVIDENCE_ROOT" >&2
  exit 64
fi

manifest_tsv=$1
agentworld_source_root=$2
target_root=$3
evidence_root=$4
lock_file="${evidence_root}.lock"

mkdir -p "$evidence_root"
exec 9>"$lock_file"
if ! flock -n 9; then
  echo "another Phase-5 weight preparation is already active" >&2
  exit 65
fi

exec > >(tee -a "$evidence_root/prepare.log") 2>&1
printf 'started_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

failure_marker="$evidence_root/FAILED"
pass_marker="$evidence_root/PASS"
rm -f "$failure_marker" "$pass_marker"
record_exit() {
  code=$?
  if (( code != 0 )); then
    printf 'exit_code=%s\n' "$code" > "$failure_marker"
  fi
}
trap record_exit EXIT

if [[ ! -f "$manifest_tsv" || -L "$manifest_tsv" ]]; then
  echo "manifest is not a regular non-symlink file" >&2
  exit 66
fi
if [[ ! -d "$agentworld_source_root" || ! -d "$target_root" ]]; then
  echo "source or target root is absent" >&2
  exit 67
fi
if ! command -v curl >/dev/null || ! command -v sha256sum >/dev/null; then
  echo "curl and sha256sum are required" >&2
  exit 68
fi

declare -i row_count=0
declare -i planned_bytes=0
while IFS=$'\t' read -r checkpoint repo revision relative expected_bytes expected_sha; do
  [[ -z "$checkpoint" ]] && continue
  if [[ "$checkpoint" != agentworld && "$checkpoint" != base ]]; then
    echo "unknown checkpoint: $checkpoint" >&2
    exit 69
  fi
  if [[ ! "$repo" =~ ^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$ ]]; then
    echo "unsafe repository ID" >&2
    exit 70
  fi
  if [[ ! "$revision" =~ ^[0-9a-f]{40}$ ]]; then
    echo "invalid revision" >&2
    exit 71
  fi
  if [[ ! "$relative" =~ ^[A-Za-z0-9._-]+\.safetensors$ ]]; then
    echo "unsafe weight path: $relative" >&2
    exit 72
  fi
  if [[ ! "$expected_bytes" =~ ^[1-9][0-9]*$ || ! "$expected_sha" =~ ^[0-9a-f]{64}$ ]]; then
    echo "invalid size or digest: $relative" >&2
    exit 73
  fi

  row_count+=1
  planned_bytes+=$expected_bytes
  destination_dir="$target_root/$checkpoint/$revision"
  destination="$destination_dir/$relative"
  partial="$destination.part"
  mkdir -p "$destination_dir"

  if [[ -e "$destination" || -L "$destination" ]]; then
    if [[ ! -f "$destination" || -L "$destination" ]]; then
      echo "destination is not a regular non-symlink file: $destination" >&2
      exit 74
    fi
    actual_bytes=$(stat -c %s "$destination")
    actual_sha=$(sha256sum "$destination" | cut -d' ' -f1)
    if [[ "$actual_bytes" != "$expected_bytes" || "$actual_sha" != "$expected_sha" ]]; then
      echo "existing destination differs: $destination" >&2
      exit 75
    fi
    printf 'verified_existing checkpoint=%s path=%s bytes=%s\n' \
      "$checkpoint" "$relative" "$actual_bytes"
    continue
  fi

  if [[ "$checkpoint" == agentworld ]]; then
    source_file="$agentworld_source_root/$relative"
    if [[ ! -e "$source_file" || ! -f "$source_file" ]]; then
      echo "AgentWorld cache source is absent: $source_file" >&2
      exit 76
    fi
    source_bytes=$(stat -Lc %s "$source_file")
    source_sha=$(sha256sum "$source_file" | cut -d' ' -f1)
    if [[ "$source_bytes" != "$expected_bytes" || "$source_sha" != "$expected_sha" ]]; then
      echo "AgentWorld cache source differs: $source_file" >&2
      exit 77
    fi
    if [[ -e "$partial" || -L "$partial" ]]; then
      echo "refusing pre-existing AgentWorld partial: $partial" >&2
      exit 78
    fi
    printf 'copying checkpoint=%s path=%s bytes=%s\n' \
      "$checkpoint" "$relative" "$expected_bytes"
    cp --reflink=auto --sparse=never --dereference -- "$source_file" "$partial"
  else
    if [[ -L "$partial" || ( -e "$partial" && ! -f "$partial" ) ]]; then
      echo "Base partial is not a regular file: $partial" >&2
      exit 79
    fi
    partial_bytes=0
    [[ -f "$partial" ]] && partial_bytes=$(stat -c %s "$partial")
    if (( partial_bytes > expected_bytes )); then
      echo "Base partial exceeds expected bytes: $partial" >&2
      exit 80
    fi
    url="https://huggingface.co/$repo/resolve/$revision/$relative?download=true"
    for attempt in $(seq 1 30); do
      partial_bytes=0
      [[ -f "$partial" ]] && partial_bytes=$(stat -c %s "$partial")
      if (( partial_bytes == expected_bytes )); then
        break
      fi
      if (( partial_bytes > expected_bytes )); then
        echo "Base partial exceeds expected bytes after download: $partial" >&2
        exit 80
      fi
      printf 'downloading checkpoint=%s path=%s attempt=%s resume_bytes=%s expected_bytes=%s\n' \
        "$checkpoint" "$relative" "$attempt" "$partial_bytes" "$expected_bytes"
      set +e
      curl --fail --location --continue-at - \
        --connect-timeout 30 --speed-time 120 --speed-limit 1024 \
        --header 'Accept-Encoding: identity' \
        --output "$partial" -- "$url"
      curl_code=$?
      set -e
      if (( curl_code == 0 )); then
        continue
      fi
      printf 'download_attempt_failed checkpoint=%s path=%s attempt=%s curl_code=%s\n' \
        "$checkpoint" "$relative" "$attempt" "$curl_code"
      sleep 5
    done
  fi

  actual_bytes=$(stat -c %s "$partial")
  actual_sha=$(sha256sum "$partial" | cut -d' ' -f1)
  if [[ "$actual_bytes" != "$expected_bytes" || "$actual_sha" != "$expected_sha" ]]; then
    echo "prepared bytes differ: $partial" >&2
    exit 81
  fi
  mv -- "$partial" "$destination"
  printf 'prepared checkpoint=%s path=%s bytes=%s sha256=%s\n' \
    "$checkpoint" "$relative" "$actual_bytes" "$actual_sha"
done < "$manifest_tsv"

if (( row_count != 35 || planned_bytes != 141225192536 )); then
  echo "manifest totals differ: rows=$row_count bytes=$planned_bytes" >&2
  exit 82
fi

sync "$target_root"
printf 'completed_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'rows=%s\nplanned_bytes=%s\n' "$row_count" "$planned_bytes" > "$pass_marker"
rm -f "$failure_marker"
