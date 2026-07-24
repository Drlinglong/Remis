import json
import re
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.future import select

from scripts.core.db_manager import DatabaseConnectionManager
from scripts.core.db_models import Glossary, GlossaryEntry


def entry_source_text(entry: GlossaryEntry) -> str:
    """Return the canonical source text used by glossary asset operations."""
    metadata = entry.raw_metadata or {}
    translations = entry.translations or {}
    source_lang = metadata.get("source_lang")
    return str(
        metadata.get("source_text")
        or (translations.get(source_lang) if source_lang else None)
        or translations.get("en")
        or next((value for value in translations.values() if value), "")
        or ""
    ).strip()


def normalized_entry_source(entry: GlossaryEntry) -> str:
    return " ".join(entry_source_text(entry).casefold().split())


def semantic_entry_payload(entry: GlossaryEntry) -> Dict[str, Any]:
    metadata = deepcopy(entry.raw_metadata or {})
    for key in ("merge_sources", "merged_at", "updated_at"):
        metadata.pop(key, None)
    return {
        "translations": deepcopy(entry.translations or {}),
        "abbreviations": deepcopy(entry.abbreviations or {}),
        "variants": deepcopy(entry.variants or {}),
        "metadata": metadata,
    }


class GlossaryHealthService:
    """Build deterministic, read-only glossary health reports."""

    PLACEHOLDER_PATTERN = re.compile(r"\$[^$]+\$|\[[^\]]+\]|\{[^{}]+\}|%[^%]+%")
    ISSUE_DEFINITIONS = {
        "empty_source": ("error", "Entries without canonical source text"),
        "missing_translation": ("warning", "Entries with missing translations"),
        "edge_whitespace": ("warning", "Translations with edge whitespace"),
        "placeholder_mismatch": ("error", "Source and translation placeholders differ"),
        "duplicate_term": ("info", "Equivalent duplicate terms"),
        "conflicting_translation": ("error", "Same source term has conflicting data"),
    }
    SEVERITY_WEIGHTS = {"error": 8, "warning": 3, "info": 1}
    MAX_EVIDENCE_ITEMS = 25

    def __init__(self, db_manager: Optional[DatabaseConnectionManager] = None):
        self.db_manager = db_manager or DatabaseConnectionManager()

    async def check(
        self,
        glossary_ids: List[int],
        *,
        target_lang: Optional[str] = None,
    ) -> Dict[str, Any]:
        selected_ids = list(dict.fromkeys(int(item) for item in glossary_ids))
        if not selected_ids:
            raise ValueError("Select at least one glossary.")

        async for session in self.db_manager.get_async_session():
            glossary_result = await session.execute(
                select(Glossary).where(Glossary.glossary_id.in_(selected_ids))
            )
            glossary_by_id = {
                glossary.glossary_id: glossary
                for glossary in glossary_result.scalars().all()
            }
            if any(item not in glossary_by_id for item in selected_ids):
                raise ValueError("One or more selected glossaries no longer exist. Refresh and try again.")

            entry_result = await session.execute(
                select(GlossaryEntry).where(GlossaryEntry.glossary_id.in_(selected_ids))
            )
            entries = entry_result.scalars().all()
            issue_items: Dict[str, List[Dict[str, Any]]] = {
                code: [] for code in self.ISSUE_DEFINITIONS
            }
            groups: Dict[str, List[GlossaryEntry]] = {}

            def evidence(entry: GlossaryEntry, detail: str) -> Dict[str, Any]:
                glossary = glossary_by_id[entry.glossary_id]
                return {
                    "glossary_id": entry.glossary_id,
                    "glossary_name": glossary.name,
                    "game_id": glossary.game_id,
                    "entry_id": entry.entry_id,
                    "source": entry_source_text(entry),
                    "current_translation": (
                        (entry.translations or {}).get(target_lang)
                        if target_lang
                        else None
                    ),
                    "detail": detail,
                }

            for entry in entries:
                source = entry_source_text(entry)
                normalized_source = normalized_entry_source(entry)
                if not source:
                    issue_items["empty_source"].append(evidence(entry, "No canonical source text."))
                else:
                    groups.setdefault(normalized_source, []).append(entry)

                translations = entry.translations or {}
                if target_lang:
                    if not str(translations.get(target_lang) or "").strip():
                        issue_items["missing_translation"].append(
                            evidence(entry, f"Missing translation for {target_lang}.")
                        )
                    checked_translations = {target_lang: translations.get(target_lang)}
                else:
                    checked_translations = translations
                    if not any(str(value or "").strip() for value in translations.values()):
                        issue_items["missing_translation"].append(
                            evidence(entry, "No non-empty translations.")
                        )

                for language, value in checked_translations.items():
                    if not isinstance(value, str) or not value:
                        continue
                    if value != value.strip():
                        issue_items["edge_whitespace"].append(
                            evidence(entry, f"{language} has leading or trailing whitespace.")
                        )
                    source_tokens = sorted(self.PLACEHOLDER_PATTERN.findall(source))
                    target_tokens = sorted(self.PLACEHOLDER_PATTERN.findall(value))
                    if source_tokens != target_tokens:
                        issue_items["placeholder_mismatch"].append(
                            evidence(
                                entry,
                                f"{language} placeholders differ: {source_tokens} -> {target_tokens}.",
                            )
                        )

            for grouped_entries in groups.values():
                if len(grouped_entries) < 2:
                    continue
                fingerprints = {
                    json.dumps(semantic_entry_payload(entry), sort_keys=True, ensure_ascii=False)
                    for entry in grouped_entries
                }
                code = "duplicate_term" if len(fingerprints) == 1 else "conflicting_translation"
                issue_items[code].append(evidence(
                    grouped_entries[0],
                    f"Found in {len(grouped_entries)} entries: "
                    + ", ".join(entry.entry_id for entry in grouped_entries[:5]),
                ))

            issues = []
            penalty = 0
            for code, (severity, message) in self.ISSUE_DEFINITIONS.items():
                items = issue_items[code]
                if not items:
                    continue
                penalty += self.SEVERITY_WEIGHTS[severity] * min(len(items), 10)
                issues.append({
                    "code": code,
                    "severity": severity,
                    "count": len(items),
                    "message": message,
                    "items": items[:self.MAX_EVIDENCE_ITEMS],
                    "items_truncated": max(0, len(items) - self.MAX_EVIDENCE_ITEMS),
                })

            return {
                "glossary_ids": selected_ids,
                "glossary_count": len(selected_ids),
                "entry_count": len(entries),
                "target_lang": target_lang,
                "score": max(0, 100 - penalty),
                "issue_count": sum(issue["count"] for issue in issues),
                "issues": issues,
                "checked_at": datetime.now().isoformat(),
                "method": "deterministic",
                "mutations_applied": False,
            }
        return {}
