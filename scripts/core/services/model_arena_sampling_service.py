from __future__ import annotations

import hashlib
import random
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Iterable, Optional, Sequence

from scripts.core.loc_parser import parse_loc_file_with_lines
from scripts.schemas.model_arena import ModelArenaCandidate


class ModelArenaSamplingService:
    """Build and sample a representative, reproducible localization candidate pool."""

    SAMPLER_VERSION = "stratified-coverage-v1"
    SUPPORTED_SUFFIXES = {".yml", ".yaml", ".json"}
    _PURE_VARIABLE_RE = re.compile(
        r"^\s*(?:\$[^$\r\n]+\$|\[[^\]\r\n]+\]|§[^§\r\n]+§|#[^#\r\n]+#)\s*$"
    )
    _PROTECTED_RE = re.compile(
        r"\$[^$\r\n]+\$|\[[^\]\r\n]+\]|§[^§\r\n]+§|#[^#\r\n]+#"
    )
    _QUOTE_RE = re.compile(r"""["'“”‘’«»„]""")
    _COMPLEX_PUNCTUATION_RE = re.compile(r"[,:;!?，。！？；：、—–…]")
    _COVERAGE_TAGS = {
        "length:short",
        "length:medium",
        "length:long",
        "protected_format",
        "newline",
        "quotes",
        "complex_punctuation",
        "glossary_term",
        "duplicate_text",
    }

    @staticmethod
    def generate_seed() -> str:
        return random.SystemRandom().getrandbits(128).to_bytes(16, "big").hex()

    @staticmethod
    def _sha256(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _normalized_source(value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value)
        return " ".join(normalized.split())

    @staticmethod
    def _candidate_identity(
        relative_file_path: str,
        entry_key: str,
        line_number: Optional[int],
        source_sha256: str,
    ) -> str:
        material = "\0".join(
            (
                relative_file_path,
                entry_key,
                "" if line_number is None else str(line_number),
                source_sha256,
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @staticmethod
    def _length_thresholds(lengths: Sequence[int]) -> tuple[int, int]:
        ordered = sorted(lengths)
        if not ordered:
            return 0, 0
        lower_index = (len(ordered) - 1) // 3
        upper_index = (2 * (len(ordered) - 1)) // 3
        return ordered[lower_index], ordered[upper_index]

    @staticmethod
    def _length_tag(length: int, lower: int, upper: int) -> str:
        if length <= lower:
            return "length:short"
        if length <= upper:
            return "length:medium"
        return "length:long"

    @staticmethod
    def _contains_glossary_term(text: str, glossary_terms: Sequence[str]) -> bool:
        folded = text.casefold()
        return any(term.casefold() in folded for term in glossary_terms)

    def collect_candidates(
        self,
        source_root: str | Path,
        *,
        file_paths: Optional[Iterable[str | Path]] = None,
        glossary_terms: Iterable[str] = (),
    ) -> list[ModelArenaCandidate]:
        """Read supported source files and return a normalized, de-duplicated pool."""
        root = Path(source_root).resolve()
        terms = tuple(
            sorted(
                {
                    unicodedata.normalize("NFKC", str(term)).strip()
                    for term in glossary_terms
                    if str(term).strip()
                }
            )
        )
        if file_paths is None:
            paths = [
                path
                for path in root.rglob("*")
                if path.is_file() and path.suffix.lower() in self.SUPPORTED_SUFFIXES
            ]
        else:
            paths = []
            for raw_path in file_paths:
                path = Path(raw_path)
                if not path.is_absolute():
                    path = root / path
                path = path.resolve()
                try:
                    path.relative_to(root)
                except ValueError as exc:
                    raise ValueError("Model arena source files must stay within source_root") from exc
                if path.is_file() and path.suffix.lower() in self.SUPPORTED_SUFFIXES:
                    paths.append(path)

        parsed: list[dict[str, object]] = []
        for path in sorted(set(paths), key=lambda item: item.as_posix().casefold()):
            relative_path = path.relative_to(root).as_posix()
            for entry_key, raw_text, line_number in parse_loc_file_with_lines(path):
                source_text = str(raw_text)
                normalized_source = self._normalized_source(source_text)
                if not normalized_source or self._PURE_VARIABLE_RE.fullmatch(source_text):
                    continue
                parsed.append(
                    {
                        "entry_key": str(entry_key),
                        "relative_file_path": relative_path,
                        "line_number": int(line_number),
                        "source_text": source_text,
                        "normalized_source": normalized_source,
                    }
                )

        parsed.sort(
            key=lambda item: (
                str(item["relative_file_path"]).casefold(),
                int(item["line_number"]),
                str(item["entry_key"]),
            )
        )
        duplicate_counts = Counter(
            str(item["normalized_source"]) for item in parsed
        )
        deduplicated: list[dict[str, object]] = []
        seen_text: set[str] = set()
        for item in parsed:
            normalized_source = str(item["normalized_source"])
            if normalized_source in seen_text:
                continue
            seen_text.add(normalized_source)
            deduplicated.append(item)

        lower, upper = self._length_thresholds(
            [len(str(item["normalized_source"])) for item in deduplicated]
        )
        candidates: list[ModelArenaCandidate] = []
        for item in deduplicated:
            source_text = str(item["source_text"])
            normalized_source = str(item["normalized_source"])
            source_sha256 = self._sha256(source_text)
            tags = {
                self._length_tag(len(normalized_source), lower, upper),
                f"file:{item['relative_file_path']}",
            }
            if self._PROTECTED_RE.search(source_text):
                tags.add("protected_format")
            if "\n" in source_text or "\r" in source_text:
                tags.add("newline")
            if self._QUOTE_RE.search(source_text):
                tags.add("quotes")
            if self._COMPLEX_PUNCTUATION_RE.search(source_text):
                tags.add("complex_punctuation")
            if terms and self._contains_glossary_term(source_text, terms):
                tags.add("glossary_term")
            if duplicate_counts[normalized_source] > 1:
                tags.add("duplicate_text")

            relative_file_path = str(item["relative_file_path"])
            entry_key = str(item["entry_key"])
            line_number = int(item["line_number"])
            candidates.append(
                ModelArenaCandidate(
                    candidate_id=self._candidate_identity(
                        relative_file_path,
                        entry_key,
                        line_number,
                        source_sha256,
                    ),
                    entry_key=entry_key,
                    relative_file_path=relative_file_path,
                    line_number=line_number,
                    source_text=source_text,
                    source_sha256=source_sha256,
                    feature_tags=sorted(tags),
                )
            )
        return candidates

    @staticmethod
    def _tie_rank(seed: str, candidate_id: str) -> str:
        material = f"{seed}\0{candidate_id}".encode("utf-8")
        return hashlib.sha256(material).hexdigest()

    @staticmethod
    def _reservoir_sample(
        candidates: Sequence[ModelArenaCandidate],
        count: int,
        seed: str,
    ) -> list[ModelArenaCandidate]:
        if count <= 0:
            return []
        rng = random.Random(seed)
        reservoir: list[ModelArenaCandidate] = []
        for index, candidate in enumerate(
            sorted(candidates, key=lambda item: item.candidate_id)
        ):
            if index < count:
                reservoir.append(candidate)
                continue
            replacement_index = rng.randint(0, index)
            if replacement_index < count:
                reservoir[replacement_index] = candidate
        return reservoir

    def select_candidates(
        self,
        candidates: Sequence[ModelArenaCandidate | dict],
        *,
        sample_size: int,
        seed: str,
        max_per_file: int = 2,
    ) -> list[ModelArenaCandidate]:
        """Select coverage-first samples, then use seeded reservoir fill."""
        if not 3 <= sample_size <= 12:
            raise ValueError("Model arena sample_size must be between 3 and 12")
        if not seed:
            raise ValueError("Model arena sampling requires a non-empty seed")
        normalized = [
            candidate
            if isinstance(candidate, ModelArenaCandidate)
            else ModelArenaCandidate.model_validate(candidate)
            for candidate in candidates
        ]
        unique = {candidate.candidate_id: candidate for candidate in normalized}
        pool = list(unique.values())
        if len(pool) < sample_size:
            raise ValueError(
                f"Not enough eligible entries: requested {sample_size}, found {len(pool)}"
            )
        if max_per_file < 1:
            raise ValueError("max_per_file must be at least 1")

        available_tags = {
            tag
            for candidate in pool
            for tag in candidate.feature_tags
            if tag in self._COVERAGE_TAGS
        }
        uncovered = set(available_tags)
        selected: list[ModelArenaCandidate] = []
        selected_ids: set[str] = set()
        file_counts: Counter[str] = Counter()

        while uncovered and len(selected) < sample_size:
            within_cap = [
                candidate
                for candidate in pool
                if candidate.candidate_id not in selected_ids
                and file_counts[candidate.relative_file_path] < max_per_file
            ]
            choices = within_cap or [
                candidate
                for candidate in pool
                if candidate.candidate_id not in selected_ids
            ]
            if not choices:
                break
            ranked = sorted(
                choices,
                key=lambda candidate: (
                    -len(set(candidate.feature_tags) & uncovered),
                    file_counts[candidate.relative_file_path] > 0,
                    self._tie_rank(seed, candidate.candidate_id),
                ),
            )
            best = ranked[0]
            gain = set(best.feature_tags) & uncovered
            if not gain:
                break
            selected.append(best)
            selected_ids.add(best.candidate_id)
            file_counts[best.relative_file_path] += 1
            uncovered.difference_update(gain)

        remaining_count = sample_size - len(selected)
        if remaining_count:
            remaining = [
                candidate
                for candidate in pool
                if candidate.candidate_id not in selected_ids
                and file_counts[candidate.relative_file_path] < max_per_file
            ]
            if len(remaining) < remaining_count:
                remaining = [
                    candidate
                    for candidate in pool
                    if candidate.candidate_id not in selected_ids
                ]
            fill = self._reservoir_sample(
                remaining,
                remaining_count,
                f"{seed}\0reservoir",
            )
            selected.extend(fill)
        return selected

    def sample_project(
        self,
        source_root: str | Path,
        *,
        sample_size: int = 6,
        seed: Optional[str] = None,
        file_paths: Optional[Iterable[str | Path]] = None,
        glossary_terms: Iterable[str] = (),
    ) -> tuple[list[ModelArenaCandidate], int, str]:
        effective_seed = seed or self.generate_seed()
        candidates = self.collect_candidates(
            source_root,
            file_paths=file_paths,
            glossary_terms=glossary_terms,
        )
        selected = self.select_candidates(
            candidates,
            sample_size=sample_size,
            seed=effective_seed,
        )
        return selected, len(candidates), effective_seed

    def build_samples(
        self,
        run_id: str,
        selected: Sequence[ModelArenaCandidate | dict],
        *,
        contestant_ids: Sequence[str],
        seed: str,
    ) -> list[dict[str, object]]:
        if len(set(contestant_ids)) not in {2, 3}:
            raise ValueError("Model arena requires 2 or 3 distinct contestants")
        samples: list[dict[str, object]] = []
        for ordinal, raw_candidate in enumerate(selected):
            candidate = (
                raw_candidate
                if isinstance(raw_candidate, ModelArenaCandidate)
                else ModelArenaCandidate.model_validate(raw_candidate)
            )
            sample_id = "arena-sample-" + self._sha256(
                f"{run_id}\0{candidate.candidate_id}"
            )[:24]
            permutation = sorted(
                contestant_ids,
                key=lambda contestant_id: self._sha256(
                    f"{seed}\0{sample_id}\0{contestant_id}"
                ),
            )
            samples.append(
                {
                    "sample_id": sample_id,
                    "ordinal": ordinal,
                    "entry_key": candidate.entry_key,
                    "relative_file_path": candidate.relative_file_path,
                    "line_number": candidate.line_number,
                    "source_text": candidate.source_text,
                    "source_sha256": candidate.source_sha256,
                    "feature_tags": list(candidate.feature_tags),
                    "display_permutation": permutation,
                }
            )
        return samples
