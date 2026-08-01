from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.core.loc_parser import parse_loc_file


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "demo_smoke" / "issue_198_narrative"
ENTRY_LINE_RE = re.compile(
    r'^\s*(?P<key>[^:\s]+)\s*:\s*0\s+"(?P<value>(?:[^"\\]|\\.)*)"\s*$'
)


def _manifest() -> dict:
    return json.loads((FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8"))


def _localization_files(root: Path) -> list[Path]:
    return sorted((root / "localisation" / "english").glob("*.yml"))


def _read_entries(root: Path) -> tuple[dict[str, str], dict[str, str]]:
    entries: dict[str, str] = {}
    key_files: dict[str, str] = {}
    for path in _localization_files(root):
        content = path.read_text(encoding="utf-8")
        assert "\ufffd" not in content
        assert content.startswith("l_english:\n")
        for line in content.splitlines()[1:]:
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            match = ENTRY_LINE_RE.match(line)
            assert match, f"invalid Stellaris localization line: {path}:{line}"
            key = f"{match['key']}:0"
            assert key not in entries, f"duplicate localization key: {key}"
            entries[key] = match["value"]
            key_files[key] = path.relative_to(root).as_posix()
        assert parse_loc_file(path), f"parser found no entries in {path}"
    return entries, key_files


def _assert_spatial_contract(entries: dict[str, str], manifest: dict) -> None:
    spatial = manifest["spatial_contract"]
    for relation in spatial["relationship_keys"]:
        value = entries[relation["key"]]
        normalized = value.casefold()
        for term in relation["required_terms"]:
            assert term.casefold() in normalized, f"{relation['key']} missing spatial term {term}"
    all_text = "\n".join(entries.values()).casefold()
    for pattern in spatial["forbidden_patterns"]:
        assert pattern.casefold() not in all_text, f"spatial contradiction remains: {pattern}"


def test_issue_198_narrative_fixture_has_valid_coverage_and_cross_file_chain():
    manifest = _manifest()
    baseline_root = FIXTURE_ROOT / manifest["baseline_root"]
    provenance = {item["path"]: item for item in manifest["source_provenance"]}
    paths = _localization_files(baseline_root)
    entries, key_files = _read_entries(baseline_root)

    assert manifest["game_id"] == "stellaris"
    assert manifest["source_language"] == "en"
    assert len(paths) == manifest["expected_baseline"]["file_count"]
    assert len(entries) == manifest["expected_baseline"]["entry_count"]
    assert {path.relative_to(baseline_root).as_posix() for path in paths} == set(provenance)
    assert len({item["batch"] for item in provenance.values()}) >= manifest["expected_baseline"]["minimum_batches"]
    _assert_spatial_contract(entries, manifest)

    terms_text = "\n".join(entries.values())
    for item in manifest["recurring_terms"]:
        assert terms_text.count(item["term"]) >= item["minimum_occurrences"], item["term"]

    for alias_group in manifest["aliases"]:
        assert alias_group["canonical"] in terms_text
        for alias in alias_group["aliases"]:
            assert alias in terms_text

    event_ids = {step["id"] for step in manifest["event_chain"]}
    for step in manifest["event_chain"]:
        assert step["batch"] in {item["batch"] for item in provenance.values()}
        assert step["file"] in provenance
        assert step["file"] in {key_files[key] for key in step["keys"]}
        assert set(step["links_to"]) <= event_ids

    for group in manifest["event_groups"]:
        group_files = {key_files[key] for key in group["keys"]}
        key_prefixes = {key.split(":", 1)[0].split(".", 1)[0] for key in group["keys"]}
        assert len(group_files) >= group["minimum_distinct_files"]
        assert len(key_prefixes) >= group["minimum_distinct_key_prefixes"]

    for branch in manifest["branch_facts"]:
        branch_text = "\n".join(entries[key] for key in branch["keys"])
        for fact in branch["required_facts"]:
            assert fact in branch_text, f"{branch['branch']} missing {fact}"

    for conflict in manifest["mutually_exclusive_facts"]:
        assert conflict["concord_fact"] in entries[conflict["concord_key"]]
        assert conflict["warden_fact"] in entries[conflict["warden_key"]]
        assert entries[conflict["concord_key"]] != entries[conflict["warden_key"]]

    provenance_order = {item["path"]: index for index, item in enumerate(manifest["source_provenance"])}
    for callback in manifest["long_distance_callbacks"]:
        early_path = key_files[callback["early_key"]]
        late_path = key_files[callback["late_key"]]
        assert callback["term"] in entries[callback["early_key"]]
        assert callback["term"] in entries[callback["late_key"]]
        assert provenance_order[late_path] - provenance_order[early_path] >= callback["minimum_file_distance"]

    assert len({provenance[key]["batch"] for key in key_files.values()}) >= manifest["expected_baseline"]["minimum_batches"]


def test_issue_198_narrative_variant_has_explicit_changed_and_deleted_source_delta():
    manifest = _manifest()
    baseline_root = FIXTURE_ROOT / manifest["baseline_root"]
    variant_root = FIXTURE_ROOT / manifest["variant_root"]
    baseline_entries, _ = _read_entries(baseline_root)
    variant_entries, _ = _read_entries(variant_root)
    baseline_files = {path.relative_to(baseline_root).as_posix() for path in _localization_files(baseline_root)}
    variant_files = {path.relative_to(variant_root).as_posix() for path in _localization_files(variant_root)}
    delta = manifest["variant_delta"]
    _assert_spatial_contract(variant_entries, manifest)

    deleted_files = sorted(baseline_files - variant_files)
    added_files = sorted(variant_files - baseline_files)
    changed_keys = sorted(
        key for key in baseline_entries.keys() & variant_entries.keys()
        if baseline_entries[key] != variant_entries[key]
    )
    deleted_keys = sorted(set(baseline_entries) - set(variant_entries))
    added_keys = sorted(set(variant_entries) - set(baseline_entries))

    assert deleted_files == sorted(delta["deleted_files"])
    assert added_files == []
    assert changed_keys == sorted(delta["changed_keys"])
    assert deleted_keys == sorted(delta["deleted_keys"])
    assert added_keys == []
    assert all(baseline_entries[key] != variant_entries[key] for key in delta["changed_keys"])
