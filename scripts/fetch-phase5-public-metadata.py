from __future__ import annotations

import json

from normative_world_model.phase5_public_metadata import (
    default_public_metadata_root,
    download_frozen_public_metadata,
)


def main() -> int:
    manifest = download_frozen_public_metadata()
    print(
        json.dumps(
            {
                "status": "PASS",
                "output_root": str(default_public_metadata_root()),
                "manifest_sha256": manifest["manifest_sha256"],
                "snapshots": [
                    {
                        "checkpoint": row["checkpoint"],
                        "revision": row["revision"],
                        "file_count": row["file_count"],
                        "total_file_bytes": row["total_file_bytes"],
                    }
                    for row in manifest["snapshots"]
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
