"""Bridge editable Glossary/GlossaryEntry rows to frozen Batch terminology.

No separate editable term store. Imports create isolated standard glossaries;
the existing UI and CRUD API own subsequent edits. Snapshots never rewrite them.
"""
import uuid
from collections import Counter
from copy import deepcopy

from pydantic import ValidationError
from sqlmodel import select

from .batch_artifacts import fingerprint
from .batch_repository import BatchConflict
from .db_models import Glossary, GlossaryEntry
from .glossary_health_service import entry_source_text
from .glossary_terminology_review import apply_review_change, review_basis
from scripts.schemas.agent_batch import TermDefinition, TermReleaseRequest


def glossary_languages(languages):
    result = {key: {**value, "name_local": value.get("name_local", value["name"])}
              for key, value in languages.items()}
    result["zh-TW"] = {"code": "zh-TW", "name": "正體中文", "name_local": "正體中文",
                       "name_en": "Traditional Chinese"}
    return result


class GlossaryTerminologyService:
    def __init__(self, db_manager, releases):
        self.db_manager, self.releases = db_manager, releases

    @staticmethod
    def _entry(glossary_id, locale, term):
        data = term.model_dump(exclude={"historical_reference"} if term.historical_reference is None else set())
        translation, references = data.pop("translation"), data.pop("reference_translations")
        source = data.pop("source")
        if data["review_state"] in {"reviewed", "approved"}:
            data["review_basis"] = review_basis(source, translation, data)
        data.update({"schema_version": "glossary-terminology/1", "locale": locale})
        data["alias_review_basis"] = list(term.aliases)
        return GlossaryEntry(
            entry_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"remis:{glossary_id}:{term.concept_id}")),
            glossary_id=glossary_id,
            translations={**references, "en": source, locale: translation},
            variants={"en": term.aliases},
            raw_metadata={"source_lang": "en", "source_text": source, "target_lang": locale,
                          "remarks": term.sense, "terminology": data},
        )

    async def import_glossary(self, request):
        if not request.approved:
            raise BatchConflict("approval_required", "Importing terminology requires authorization.")
        if request.locale == "en":
            raise BatchConflict("source_locale_conflict", "Terminology source is English; choose another target locale.", 400)
        ids = [term.concept_id for term in request.terms]
        if len(ids) != len(set(ids)):
            raise BatchConflict("duplicate_concept_id", "Preserve distinct concept identities.", 400)
        import_payload = request.model_dump(exclude={"approved"})
        for item in import_payload["terms"]:
            if item.get("historical_reference") is None:
                item.pop("historical_reference", None)
        digest = fingerprint(import_payload)
        async with self.db_manager.async_session_scope() as session:
            # Serialize create-only imports across requests/processes on the main SQLite DB.
            await (await session.connection()).exec_driver_sql("BEGIN IMMEDIATE")
            result = await session.exec(select(Glossary).where(
                Glossary.game_id == request.game_id,
                Glossary.raw_metadata["terminology_import_key"].as_string() == request.import_key))
            glossary = result.one_or_none()
            if glossary:
                if glossary.raw_metadata.get("terminology_import_fingerprint") != digest:
                    raise BatchConflict("terminology_import_conflict", "This import key already exists; edit the glossary or use a new key.")
            else:
                glossary = Glossary(game_id=request.game_id, name=request.name, description=request.description,
                    is_main=False, raw_metadata={"kind": "standard", "terminology_locale": request.locale,
                        "terminology_scope_id": request.scope_id, "terminology_import_key": request.import_key,
                        "terminology_import_fingerprint": digest})
                session.add(glossary)
                await session.flush()
                session.add_all([self._entry(glossary.glossary_id, request.locale, term) for term in request.terms])
                await session.flush()
            glossary_id = glossary.glossary_id
        return await self.preview(glossary_id, request.locale)

    async def _read(self, glossary_id):
        async with self.db_manager.async_session_scope() as session:
            await (await session.connection()).exec_driver_sql("BEGIN")
            glossary = await session.get(Glossary, glossary_id)
            if not glossary:
                raise BatchConflict("glossary_not_found", "Glossary does not exist.", 404)
            result = await session.exec(select(GlossaryEntry).where(
                GlossaryEntry.glossary_id == glossary_id).order_by(GlossaryEntry.entry_id))
            return glossary.model_dump(), [row.model_dump() for row in result.all()]

    @staticmethod
    def _terms(rows, locale):
        terms, excluded, states = [], [], Counter()
        for row in rows:
            metadata = row["raw_metadata"] or {}
            detail = deepcopy(metadata.get("terminology") or {})
            if not isinstance(detail, dict):
                raise BatchConflict("invalid_terminology_metadata", f"Repair terminology fields for entry {row['entry_id']}.", 400)
            translation = row["translations"].get(locale, "")
            source = metadata.get("source_text") or entry_source_text(GlossaryEntry.model_validate(row))
            state = detail.get("review_state", "candidate")
            aliases = row.get("variants", {}).get("en", detail.get("aliases", []))
            if state not in {"candidate", "reviewed", "pending", "approved", "rejected"}:
                raise BatchConflict("invalid_review_state", f"Repair review state for entry {row['entry_id']}.", 400)
            if detail and detail.get("locale") != locale:
                raise BatchConflict("terminology_locale_conflict", "Choose the glossary's terminology locale.", 400)
            if state in {"reviewed", "approved"} and detail.get("review_basis") != review_basis(source, translation, detail):
                state = "candidate"  # Generic CRUD edits cannot silently retain stale approval.
            if state in {"reviewed", "approved"} and "alias_review_basis" in detail and detail["alias_review_basis"] != aliases:
                state = "candidate"
            states[state] += 1
            if state in {"pending", "rejected"} or not source or not str(translation).strip():
                excluded.append({"entry_id": row["entry_id"], "reason": state if state in {"pending", "rejected"} else "missing_text"})
                continue
            payload = {key: detail[key] for key in TermDefinition.model_fields if key in detail}
            payload.update({"concept_id": detail.get("concept_id", f"glossary:{row['glossary_id']}:{row['entry_id']}"),
                "source": source, "translation": translation,
                "sense": detail.get("sense") or metadata.get("remarks") or source,
                "aliases": aliases})
            if detail.get("historical_reference"):
                payload["evidence_refs"] = [*payload.get("evidence_refs", []),
                    {"role": "historical_community_translation", **detail["historical_reference"]}]
            try:
                terms.append(TermDefinition.model_validate(payload))
            except ValidationError:
                raise BatchConflict("invalid_terminology_metadata", f"Repair terminology fields for entry {row['entry_id']}.", 400) from None
        if len({term.concept_id for term in terms}) != len(terms):
            raise BatchConflict("duplicate_concept_id", "The glossary contains duplicate concept identities.", 400)
        return terms, excluded, dict(states)

    async def _snapshot(self, glossary_id, locale):
        glossary, rows = await self._read(glossary_id)
        primary_locale = glossary["raw_metadata"].get("terminology_locale")
        if primary_locale and primary_locale != locale:
            raise BatchConflict("terminology_locale_conflict", "Choose the glossary's terminology locale.", 400)
        terms, excluded, states = self._terms(rows, locale)
        digest = fingerprint([glossary["game_id"], glossary["raw_metadata"].get("terminology_scope_id"), locale, rows])
        return glossary, terms, {"glossary_id": glossary_id, "game_id": glossary["game_id"],
            "name": glossary["name"], "locale": locale, "fingerprint": digest,
            "entry_count": len(rows), "eligible_count": len(terms), "excluded": excluded, "review_states": states,
            "source_route": f"/glossary-manager?game_id={glossary['game_id']}&glossary_id={glossary_id}&target_lang={locale}"}

    async def preview(self, glossary_id, locale):
        _, _, preview = await self._snapshot(glossary_id, locale)
        return preview

    async def distribution(self, glossary_id, locale, expected_fingerprint):
        from .glossary_distribution import distribution_snapshot
        glossary, rows = await self._read(glossary_id)
        primary_locale = glossary["raw_metadata"].get("terminology_locale")
        if primary_locale and primary_locale != locale:
            raise BatchConflict("terminology_locale_conflict", "Choose the glossary's terminology locale.", 400)
        terms, excluded, states = self._terms(rows, locale)
        digest = fingerprint([glossary["game_id"], glossary["raw_metadata"].get("terminology_scope_id"), locale, rows])
        preview = {"game_id": glossary["game_id"], "locale": locale, "fingerprint": digest,
                   "entry_count": len(rows), "eligible_count": len(terms),
                   "excluded": excluded, "review_states": states}
        return distribution_snapshot(glossary, rows, terms, preview, expected_fingerprint)

    async def append(self, glossary_id, request):
        if not request.approved:
            raise BatchConflict("approval_required", "Adding glossary terms requires authorization.")
        if request.locale == "en":
            raise BatchConflict("source_locale_conflict", "Choose a target terminology locale.", 400)
        ids = [term.concept_id for term in request.terms]
        if len(ids) != len(set(ids)):
            raise BatchConflict("duplicate_concept_id", "Preserve distinct concept identities.", 400)
        async with self.db_manager.async_session_scope() as session:
            await (await session.connection()).exec_driver_sql("BEGIN IMMEDIATE")
            glossary = await session.get(Glossary, glossary_id)
            if not glossary:
                raise BatchConflict("glossary_not_found", "Glossary does not exist.", 404)
            locale = glossary.raw_metadata.get("terminology_locale")
            if locale and locale != request.locale:
                raise BatchConflict("terminology_locale_conflict", "Choose the glossary's terminology locale.", 400)
            result = await session.exec(select(GlossaryEntry).where(
                GlossaryEntry.glossary_id == glossary_id).order_by(GlossaryEntry.entry_id))
            rows = result.all()
            digest = fingerprint([glossary.game_id, glossary.raw_metadata.get("terminology_scope_id"),
                                  request.locale, [row.model_dump() for row in rows]])
            if digest != request.expected_fingerprint:
                raise BatchConflict("glossary_changed", "The glossary changed after preview; inspect it again.")
            existing = {row.raw_metadata.get("terminology", {}).get("concept_id") for row in rows}
            if existing.intersection(ids):
                raise BatchConflict("duplicate_concept_id", "Use review to edit existing concepts; append never overwrites.", 400)
            session.add_all([self._entry(glossary_id, request.locale, term) for term in request.terms])
            await session.flush()
        return await self.preview(glossary_id, request.locale)

    async def review(self, glossary_id, request):
        if not request.approved:
            raise BatchConflict("approval_required", "Changing glossary terms requires authorization.")
        ids = [change.concept_id for change in request.changes]
        if len(ids) != len(set(ids)):
            raise BatchConflict("duplicate_concept_id", "Review each concept at most once.", 400)
        async with self.db_manager.async_session_scope() as session:
            await (await session.connection()).exec_driver_sql("BEGIN IMMEDIATE")
            glossary = await session.get(Glossary, glossary_id)
            if not glossary:
                raise BatchConflict("glossary_not_found", "Glossary does not exist.", 404)
            result = await session.exec(select(GlossaryEntry).where(
                GlossaryEntry.glossary_id == glossary_id).order_by(GlossaryEntry.entry_id))
            rows = result.all()
            digest = fingerprint([glossary.game_id, glossary.raw_metadata.get("terminology_scope_id"),
                                  request.locale, [row.model_dump() for row in rows]])
            if digest != request.expected_fingerprint:
                raise BatchConflict("glossary_changed", "The glossary changed after preview; inspect it again.")
            by_concept = {row.raw_metadata.get("terminology", {}).get("concept_id"): row for row in rows}
            if set(ids) - by_concept.keys():
                raise BatchConflict("unknown_concept_id", "A requested concept is absent from this glossary.", 400)
            for change in request.changes:
                row = by_concept[change.concept_id]
                apply_review_change(row, request, change)
                session.add(row)
        return await self.preview(glossary_id, request.locale)

    async def publish(self, request):
        if not request.approved:
            raise BatchConflict("approval_required", "Freezing terminology requires authorization.")
        glossary, terms, preview = await self._snapshot(request.glossary_id, request.locale)
        if preview["fingerprint"] != request.expected_fingerprint:
            raise BatchConflict("glossary_changed", "The glossary changed after preview; inspect it again.")
        if not terms:
            raise BatchConflict("empty_term_release", "No eligible glossary terms to freeze.", 400)
        if request.maturity == "approved" and preview["review_states"].get("approved", 0) != len(terms):
            raise BatchConflict("unapproved_glossary_terms", "Confirm all included terms before freezing an approved release.")
        release = TermReleaseRequest(game_id=glossary["game_id"],
            scope_id=glossary["raw_metadata"].get("terminology_scope_id"), locale=request.locale,
            version=request.version, maturity=request.maturity, terms=terms, approved=True)
        return self.releases.publish(release, origin={"glossary_id": request.glossary_id,
            "fingerprint": preview["fingerprint"], "excluded": preview["excluded"]})
