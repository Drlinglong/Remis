"""Build a reproducible Victoria 3 official-country TAG catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


COUNTRY_TAG_RE = re.compile(r"^\s*([A-Z0-9]{3})\s*=\s*\{", re.MULTILINE)


def build_catalog(source_dir: Path) -> dict[str, object]:
    files = sorted(source_dir.glob("*.txt"), key=lambda path: path.name)
    if not files:
        raise ValueError(f"No country definition files found in {source_dir}")
    source_files = []
    tags: set[str] = set()
    for path in files:
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig")
        tags.update(COUNTRY_TAG_RE.findall(text))
        source_files.append(
            {
                "relative_path": path.name,
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    return {
        "schema_version": 1,
        "catalog_id": "vic3-official-country-tags-v1",
        "source": "Victoria 3 game/common/country_definitions/*.txt",
        "source_files": source_files,
        "tag_count": len(tags),
        "tags": sorted(tags),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    catalog = build_catalog(args.source_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
