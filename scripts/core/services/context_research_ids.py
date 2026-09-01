"""Deterministic short IDs for the Context Research model boundary.

The model should never have to reproduce a long source-item identity.  This
module keeps that concern at the request boundary: aliases are positional,
one-based, exact, and only resolve against the immutable request snapshot.
Canonical IDs remain the only IDs used by collectors, compilers, and stored
evidence.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import re
from typing import Any, Literal


IdKind = Literal["source", "unit"]
_ALIAS_PATTERNS = {
    "source": re.compile(r"^[sS](\d+)$"),
    "unit": re.compile(r"^[uU](\d+)$"),
}


@dataclass(frozen=True)
class IdRejection:
    """A safe, actionable rejection returned to a model-facing tool call."""

    kind: IdKind
    value: str
    code: str
    message: str
    suggestion: str | None = None

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "kind": self.kind,
            "value": self.value,
            "code": self.code,
            "message": self.message,
        }
        if self.suggestion is not None:
            result["suggestion"] = self.suggestion
        return result


@dataclass(frozen=True)
class ShortIdRegistry:
    """Exact bidirectional aliases for one request-bound corpus snapshot."""

    source_by_alias: Mapping[str, str]
    alias_by_source: Mapping[str, str]
    unit_by_alias: Mapping[str, str]
    alias_by_unit: Mapping[str, str]

    @classmethod
    def from_snapshot(
        cls, source_item_ids: Sequence[str], local_unit_ids: Sequence[str],
    ) -> "ShortIdRegistry":
        source_ids = _unique_clean(source_item_ids)
        unit_ids = _unique_clean(local_unit_ids)
        return cls(
            source_by_alias={f"S{index:03d}": value for index, value in enumerate(source_ids, 1)},
            alias_by_source={value: f"S{index:03d}" for index, value in enumerate(source_ids, 1)},
            unit_by_alias={f"U{index:03d}": value for index, value in enumerate(unit_ids, 1)},
            alias_by_unit={value: f"U{index:03d}" for index, value in enumerate(unit_ids, 1)},
        )

    @classmethod
    def from_objects(cls, source_items: Sequence[Any], local_units: Sequence[Any]) -> "ShortIdRegistry":
        source_ids = [str(getattr(item, "source_item_id", item)).strip() for item in source_items]
        unit_ids = [str(getattr(item, "unit_id", item)).strip() for item in local_units]
        return cls.from_snapshot(source_ids, unit_ids)

    def source_alias(self, canonical_id: str) -> str:
        return self.alias_by_source[canonical_id]

    def unit_alias(self, canonical_id: str) -> str:
        return self.alias_by_unit[canonical_id]

    def resolve(
        self,
        kind: IdKind,
        value: Any,
        *,
        allowed_canonical_ids: Iterable[str] | None = None,
    ) -> tuple[str | None, IdRejection | None]:
        """Resolve an exact alias/canonical ID without fuzzy matching."""

        raw = str(value or "").strip()
        alias_map = self.source_by_alias if kind == "source" else self.unit_by_alias
        canonical_map = self.alias_by_source if kind == "source" else self.alias_by_unit
        allowed = None if allowed_canonical_ids is None else {
            str(item).strip() for item in allowed_canonical_ids
        }
        canonical = alias_map.get(raw)
        if canonical is None and raw in canonical_map:
            canonical = raw
        if canonical is None:
            canonical, suggestion = self._format_candidate(kind, raw, alias_map)
            if canonical is None:
                return None, IdRejection(
                    kind, raw, "unknown_id",
                    f"unknown {kind} ID; use an exact ID from the leased tool output",
                    suggestion,
                )
            if allowed is not None and canonical not in allowed:
                return None, IdRejection(
                    kind, raw, "outside_lease",
                    f"{kind} ID is outside the current delegation lease",
                    None,
                )
            return canonical, IdRejection(
                kind, raw, "normalized_id",
                f"accepted normalized {kind} ID; use the exact short ID in future calls",
                alias_map.get(next(key for key, item in alias_map.items() if item == canonical)),
            )
        if allowed is not None and canonical not in allowed:
            return None, IdRejection(
                kind, raw, "outside_lease",
                f"{kind} ID is outside the current delegation lease",
            )
        return canonical, None

    def resolve_many(
        self,
        kind: IdKind,
        values: Iterable[Any],
        *,
        allowed_canonical_ids: Iterable[str] | None = None,
    ) -> tuple[tuple[str, ...], tuple[IdRejection, ...]]:
        resolved: list[str] = []
        rejected: list[IdRejection] = []
        for value in values:
            canonical, rejection = self.resolve(
                kind, value, allowed_canonical_ids=allowed_canonical_ids,
            )
            if canonical is not None and canonical not in resolved:
                resolved.append(canonical)
            if rejection is not None and rejection.code != "normalized_id":
                rejected.append(rejection)
        return tuple(resolved), tuple(rejected)

    def modelize_record(self, record: Mapping[str, Any], kind: IdKind) -> dict[str, Any]:
        """Replace a known canonical ID in a tool record with its short alias."""

        result = dict(record)
        field = "source_item_id" if kind == "source" else "local_unit_id"
        value = str(result.get(field, ""))
        alias = self.alias_by_source.get(value) if kind == "source" else self.alias_by_unit.get(value)
        if alias is not None:
            result[field] = alias
        return result

    def modelize_ids(self, values: Iterable[str], kind: IdKind) -> list[str]:
        mapping = self.alias_by_source if kind == "source" else self.alias_by_unit
        return [mapping.get(str(value), str(value)) for value in values]

    def normalize_memo_payload(
        self, payload: Mapping[str, Any],
    ) -> tuple[dict[str, Any], tuple[IdRejection, ...]]:
        """Restore model-facing memo references before collector validation."""

        result = dict(payload)
        rejected: list[IdRejection] = []

        def normalize_list(parent: dict[str, Any], field: str, kind: IdKind) -> None:
            values = parent.get(field)
            if not isinstance(values, (list, tuple)):
                return
            resolved, errors = self.resolve_many(kind, values)
            parent[field] = list(resolved) + [item.value for item in errors]
            rejected.extend(errors)

        normalize_list(result, "core_local_unit_ids", "unit")
        normalize_list(result, "overlap_local_unit_ids", "unit")
        for unit in result.get("units", ()) if isinstance(result.get("units"), (list, tuple)) else ():
            if not isinstance(unit, dict):
                continue
            normalize_list(unit, "evidence", "source")
            values = unit.get("local_unit_id")
            canonical, error = self.resolve("unit", values)
            if canonical is not None:
                unit["local_unit_id"] = canonical
            if error is not None and error.code != "normalized_id":
                rejected.append(error)
            findings = unit.get("findings")
            finding_groups: list[tuple[str, Any]] = []
            if isinstance(findings, dict):
                finding_groups.extend(
                    (finding_group, findings.get(finding_group))
                    for finding_group in (
                        "archive_narratives", "entities", "event_chains",
                        "reference_assets", "unresolved",
                    )
                )
            finding_groups.append(("entities", unit.get("entity_mentions")))
            for finding_group, group_values in finding_groups:
                for finding in group_values if isinstance(group_values, (list, tuple)) else ():
                    if not isinstance(finding, dict):
                        continue
                    if finding_group == "event_chains":
                        normalize_list(finding, "local_unit_ids", "unit")
                    if finding_group == "reference_assets":
                        value = finding.get("local_unit_id")
                        if value is not None:
                            canonical, error = self.resolve("unit", value)
                            if canonical is not None:
                                finding["local_unit_id"] = canonical
                            if error is not None and error.code != "normalized_id":
                                rejected.append(error)
                    for evidence in finding.get("evidence", ()) if isinstance(finding.get("evidence"), (list, tuple)) else ():
                        if isinstance(evidence, dict):
                            normalize_list(evidence, "source_item_ids", "source")
        return result, tuple(rejected)

    def normalize_findings_payload(
        self, payload: Mapping[str, Any],
    ) -> tuple[dict[str, Any], tuple[IdRejection, ...]]:
        """Restore source/unit aliases in a legacy or repair findings payload."""

        result = dict(payload)
        rejected: list[IdRejection] = []
        for finding_group in (
            "archive_narratives", "entities", "event_chains",
            "reference_assets", "unresolved",
        ):
            findings = result.get(finding_group)
            if not isinstance(findings, (list, tuple)):
                continue
            for finding in findings:
                if not isinstance(finding, dict):
                    continue
                if finding_group == "event_chains":
                    values = finding.get("local_unit_ids", ())
                    resolved, errors = self.resolve_many("unit", values)
                    finding["local_unit_ids"] = list(resolved) + [item.value for item in errors]
                    rejected.extend(errors)
                if finding_group == "reference_assets" and finding.get("local_unit_id") is not None:
                    canonical, error = self.resolve("unit", finding["local_unit_id"])
                    if canonical is not None:
                        finding["local_unit_id"] = canonical
                    if error is not None and error.code != "normalized_id":
                        rejected.append(error)
                for evidence in finding.get("evidence", ()) if isinstance(finding.get("evidence"), (list, tuple)) else ():
                    if not isinstance(evidence, dict):
                        continue
                    values = evidence.get("source_item_ids", ())
                    resolved, errors = self.resolve_many("source", values)
                    evidence["source_item_ids"] = list(resolved) + [item.value for item in errors]
                    rejected.extend(errors)
        return result, tuple(rejected)

    @staticmethod
    def _format_candidate(
        kind: IdKind, raw: str, alias_map: Mapping[str, str],
    ) -> tuple[str | None, str | None]:
        match = _ALIAS_PATTERNS[kind].fullmatch(raw)
        if match is None:
            return None, None
        index = int(match.group(1))
        canonical = alias_map.get(f"{'S' if kind == 'source' else 'U'}{index:03d}")
        suggestion = f"{'S' if kind == 'source' else 'U'}{index:03d}"
        return canonical, suggestion if canonical is not None else None


def _unique_clean(values: Sequence[str]) -> tuple[str, ...]:
    cleaned = tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
    if len(cleaned) != len(values):
        raise ValueError("short-ID registry requires unique non-empty canonical IDs")
    return cleaned


__all__ = ["IdKind", "IdRejection", "ShortIdRegistry"]
