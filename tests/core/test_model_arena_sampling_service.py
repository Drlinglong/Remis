import json
from collections import Counter

import pytest

from scripts.core.services.model_arena_sampling_service import (
    ModelArenaSamplingService,
)
from scripts.schemas.model_arena import ModelArenaCandidate


def _write_yml(path, entries):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["l_english:"]
    lines.extend(
        f' {key}:0 "{value.replace(chr(34), chr(92) + chr(34))}"'
        for key, value in entries
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _candidate(index, *, file_name="source.yml", tags=None):
    return ModelArenaCandidate(
        candidate_id=f"candidate-{index}",
        entry_key=f"key_{index}",
        relative_file_path=file_name,
        line_number=index + 1,
        source_text=f"Text {index}",
        source_sha256=f"hash-{index}",
        feature_tags=tags or ["length:medium"],
    )


def test_collect_candidates_filters_variables_deduplicates_and_tags_features(tmp_path):
    source_root = tmp_path / "mod"
    _write_yml(
        source_root / "localization" / "english" / "first_l_english.yml",
        [
            ("short", "Go"),
            ("variable", "$ONLY_VARIABLE$"),
            ("protected", "Cost: $VALUE$!"),
            ("quoted", '\\"Victory\\" — at last!'),
            ("term", "The Admiralty commands the western fleet."),
            ("duplicate_a", "Duplicate text"),
        ],
    )
    _write_yml(
        source_root / "localization" / "english" / "second_l_english.yml",
        [
            ("duplicate_b", "  Duplicate   text  "),
            (
                "long",
                "This deliberately long localization sentence has enough words "
                "to land in the long length bucket.",
            ),
        ],
    )
    json_path = source_root / "localization" / "english" / "extra.json"
    json_path.write_text(
        json.dumps(
            {
                "multiline": "First line\nSecond line",
                "json_variable": "[ONLY_VARIABLE]",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    service = ModelArenaSamplingService()

    candidates = service.collect_candidates(
        source_root,
        glossary_terms=["Admiralty"],
    )

    assert len(candidates) == 7
    assert not any(
        candidate.entry_key.split(":", 1)[0] in {"variable", "json_variable"}
        for candidate in candidates
    )
    duplicate = next(
        candidate
        for candidate in candidates
        if candidate.entry_key.split(":", 1)[0] == "duplicate_a"
    )
    assert "duplicate_text" in duplicate.feature_tags
    assert duplicate.relative_file_path == "localization/english/first_l_english.yml"
    protected = next(
        candidate
        for candidate in candidates
        if candidate.entry_key.split(":", 1)[0] == "protected"
    )
    assert {"protected_format", "complex_punctuation"}.issubset(
        protected.feature_tags
    )
    term = next(
        candidate
        for candidate in candidates
        if candidate.entry_key.split(":", 1)[0] == "term"
    )
    assert "glossary_term" in term.feature_tags
    multiline = next(
        candidate for candidate in candidates if candidate.entry_key == "multiline"
    )
    assert "newline" in multiline.feature_tags
    assert all(
        not candidate.relative_file_path.startswith(str(source_root))
        for candidate in candidates
    )


def test_collect_candidates_rejects_files_outside_source_root(tmp_path):
    source_root = tmp_path / "mod"
    source_root.mkdir()
    outside = tmp_path / "outside.yml"
    _write_yml(outside, [("key", "Text")])

    with pytest.raises(ValueError, match="within source_root"):
        ModelArenaSamplingService().collect_candidates(
            source_root,
            file_paths=[outside],
        )


def test_seeded_selection_is_reproducible_covers_features_and_respects_file_cap():
    candidates = []
    tag_sets = [
        ["length:short", "protected_format"],
        ["length:medium", "quotes"],
        ["length:long", "complex_punctuation"],
        ["length:short", "glossary_term"],
        ["length:medium", "newline"],
        ["length:long", "duplicate_text"],
        ["length:short"],
        ["length:medium"],
        ["length:long"],
    ]
    for index, tags in enumerate(tag_sets):
        candidates.append(
            _candidate(index, file_name=f"file-{index % 3}.yml", tags=tags)
        )
    service = ModelArenaSamplingService()

    first = service.select_candidates(
        candidates,
        sample_size=6,
        seed="reproducible-seed",
    )
    second = service.select_candidates(
        list(reversed(candidates)),
        sample_size=6,
        seed="reproducible-seed",
    )

    assert [item.candidate_id for item in first] == [
        item.candidate_id for item in second
    ]
    selected_tags = {tag for item in first for tag in item.feature_tags}
    assert {
        "protected_format",
        "quotes",
        "complex_punctuation",
        "glossary_term",
        "newline",
        "duplicate_text",
    }.issubset(selected_tags)
    assert max(Counter(item.relative_file_path for item in first).values()) <= 2


def test_selection_relaxes_file_cap_only_when_required():
    candidates = [
        _candidate(index, file_name="only-file.yml")
        for index in range(5)
    ]

    selected = ModelArenaSamplingService().select_candidates(
        candidates,
        sample_size=3,
        seed="one-file",
    )

    assert len(selected) == 3
    assert {item.relative_file_path for item in selected} == {"only-file.yml"}


def test_build_samples_creates_stable_per_sample_anonymous_permutations():
    service = ModelArenaSamplingService()
    selected = [
        _candidate(index, file_name=f"file-{index}.yml")
        for index in range(3)
    ]

    samples = service.build_samples(
        "run-1",
        selected,
        contestant_ids=["contestant-a", "contestant-b", "contestant-c"],
        seed="display-seed",
    )
    repeated = service.build_samples(
        "run-1",
        selected,
        contestant_ids=["contestant-a", "contestant-b", "contestant-c"],
        seed="display-seed",
    )

    assert samples == repeated
    assert [sample["ordinal"] for sample in samples] == [0, 1, 2]
    assert len({sample["sample_id"] for sample in samples}) == 3
    assert all(
        sorted(sample["display_permutation"])
        == ["contestant-a", "contestant-b", "contestant-c"]
        for sample in samples
    )


def test_sampling_rejects_insufficient_pool():
    with pytest.raises(ValueError, match="Not enough eligible"):
        ModelArenaSamplingService().select_candidates(
            [_candidate(0), _candidate(1)],
            sample_size=3,
            seed="small-pool",
        )
