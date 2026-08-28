"""Build the frozen Victoria 3 multilingual ``*_ADJ`` evaluation fixture.

The source corpus must be an official Victoria 3 ``game/localization``
directory. The generated fixture is intentionally small and deterministic so
it can be used for prompt A/B tests without copying the whole game corpus.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "vic3_adj_multilingual_v1"
    / "cases.json"
)

SOURCE_LANGUAGE = "english"
TARGET_LANGUAGES = (
    "simp_chinese",
    "japanese",
    "korean",
    "german",
    "french",
    "spanish",
    "braz_por",
    "polish",
    "russian",
    "turkish",
)


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    kind: str
    key: str
    referenced_adj_tokens: tuple[str, ...]
    focus: tuple[str, ...]


CASE_SPECS = (
    CaseSpec(
        "definition_chi_adj",
        "adj_definition",
        "CHI_ADJ",
        (),
        ("country adjective slot", "country-name stem", "Chinese ambiguity"),
    ),
    CaseSpec(
        "definition_egy_adj",
        "adj_definition",
        "EGY_ADJ",
        (),
        ("country adjective slot", "demonym ambiguity", "Issue 207 anchor"),
    ),
    CaseSpec(
        "definition_usa_adj",
        "adj_definition",
        "USA_ADJ",
        (),
        ("country adjective slot", "official exonym", "language-specific form"),
    ),
    CaseSpec(
        "definition_gbr_adj",
        "adj_definition",
        "GBR_ADJ",
        (),
        ("country adjective slot", "TAG differs from TAG_ADJ", "morphology"),
    ),
    CaseSpec(
        "definition_por_adj",
        "adj_definition",
        "POR_ADJ",
        (),
        ("country adjective slot", "Romance-language gender", "morphology"),
    ),
    CaseSpec(
        "reference_british_flagship",
        "adj_reference",
        "destroyed_british_flagship_tt",
        ("GBR_ADJ",),
        ("single ADJ reference", "particle or suffix", "variable preservation"),
    ),
    CaseSpec(
        "reference_portuguese_connection",
        "adj_reference",
        "lusofonia.2.t",
        ("POR_ADJ",),
        ("short title", "gender agreement", "official hard-coded rewrite"),
    ),
    CaseSpec(
        "reference_bharat_uprising",
        "adj_reference",
        "generic_revolt_india_pan_national",
        ("BHT_ADJ",),
        ("ADJ plus noun", "German/Russian suffix", "variable preservation"),
    ),
    CaseSpec(
        "reference_portugal_brazil_union",
        "adj_reference",
        "por_restoring_union_tt",
        ("POR_ADJ", "BRZ_ADJ"),
        ("two ADJ references", "hyphenated compound", "agreement"),
    ),
    CaseSpec(
        "reference_bilateral_trade_value",
        "adj_reference",
        "COUNTRY_TO_COUNTRY_TRADE_VALUE_DESC",
        ("FIRST_ADJ", "SECOND_ADJ"),
        ("dynamic ADJ slots", "two-party compound", "format preservation"),
    ),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_value(line: str, *, path: Path, line_number: int) -> str:
    first_quote = line.find('"')
    last_quote = line.rfind('"')
    if first_quote < 0 or last_quote <= first_quote:
        raise ValueError(f"Malformed localization entry: {path}:{line_number}")
    return line[first_quote + 1 : last_quote]


def _find_entry(localization_root: Path, language: str, key: str) -> dict[str, Any]:
    language_root = localization_root / language
    if not language_root.is_dir():
        raise FileNotFoundError(
            f"Missing localization language directory: {language_root}"
        )

    pattern = re.compile(rf"^\s*{re.escape(key)}\s*:(?:\d+)?\s*\"")
    matches: list[tuple[Path, int, str]] = []
    for path in sorted(language_root.rglob("*.yml")):
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            for line_number, raw_line in enumerate(stream, start=1):
                line = raw_line.rstrip("\r\n")
                if pattern.match(line):
                    matches.append((path, line_number, line))

    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one {language}:{key} entry, found {len(matches)}"
        )

    path, line_number, line = matches[0]
    return {
        "language": language,
        "value": _extract_value(line, path=path, line_number=line_number),
        "source_file": path.relative_to(localization_root).as_posix(),
        "source_line": line_number,
        "source_file_sha256": _sha256(path),
    }


def build_fixture(localization_root: Path) -> dict[str, Any]:
    localization_root = localization_root.resolve()
    languages = (SOURCE_LANGUAGE, *TARGET_LANGUAGES)
    cases: list[dict[str, Any]] = []

    for spec in CASE_SPECS:
        entries = {
            language: _find_entry(localization_root, language, spec.key)
            for language in languages
        }
        source = entries.pop(SOURCE_LANGUAGE)
        cases.append(
            {
                "id": spec.case_id,
                "kind": spec.kind,
                "key": spec.key,
                "referenced_adj_tokens": list(spec.referenced_adj_tokens),
                "focus": list(spec.focus),
                "source": source,
                "official_targets": entries,
            }
        )

    fingerprint_payload = json.dumps(
        cases,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    corpus_fingerprint = hashlib.sha256(fingerprint_payload).hexdigest()

    return {
        "schema_version": 1,
        "fixture_id": "vic3-adj-multilingual-v1",
        "game_id": "victoria3",
        "corpus": "Official Victoria 3 game/localization snapshot",
        "source_language": SOURCE_LANGUAGE,
        "target_languages": list(TARGET_LANGUAGES),
        "case_count": len(cases),
        "target_example_count": len(cases) * len(TARGET_LANGUAGES),
        "selection": {
            "adj_definition_count": sum(
                case.kind == "adj_definition" for case in CASE_SPECS
            ),
            "adj_reference_count": sum(
                case.kind == "adj_reference" for case in CASE_SPECS
            ),
            "policy": (
                "Same ten keys aligned across English and every official non-English "
                "localization shipped in this corpus snapshot."
            ),
        },
        "corpus_fingerprint_sha256": corpus_fingerprint,
        "cases": cases,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus-root",
        type=Path,
        required=True,
        help="Official Victoria 3 game/localization directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Fixture output path (default: {DEFAULT_OUTPUT})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fixture = build_fixture(args.corpus_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "case_count": fixture["case_count"],
                "target_example_count": fixture["target_example_count"],
                "corpus_fingerprint_sha256": fixture[
                    "corpus_fingerprint_sha256"
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
