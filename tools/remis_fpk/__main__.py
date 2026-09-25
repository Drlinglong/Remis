"""Command line interface for listing and extracting FLPK archives."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import ArchiveError, extract_archive, inspect_archive


def main() -> int:
    parser = argparse.ArgumentParser(prog="remis-fpk")
    subparsers = parser.add_subparsers(dest="command", required=True)
    listing = subparsers.add_parser("list", help="validate and list an archive")
    listing.add_argument("archive", type=Path)
    extraction = subparsers.add_parser("extract", help="extract to a new directory")
    extraction.add_argument("archive", type=Path)
    extraction.add_argument("destination", type=Path)
    extraction.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    try:
        result = (inspect_archive(args.archive) if args.command == "list" else
                  extract_archive(args.archive, args.destination,
                                  expected_sha256=args.expected_sha256))
    except (OSError, ArchiveError) as error:
        print(f"remis-fpk: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
