"""Immutable sense-aware terminology releases, independent of sentence memory."""
from .batch_artifacts import fingerprint
from .batch_repository import BatchConflict


class TermReleaseService:
    def __init__(self, repository, artifacts):
        self.repository, self.artifacts = repository, artifacts

    def publish(self, request, origin=None):
        if not request.approved:
            raise BatchConflict("approval_required", "Publishing a terminology release requires authorization.")
        terms = [term.model_dump() for term in request.terms]
        identifiers = [term["concept_id"] for term in terms]
        if len(set(identifiers)) != len(identifiers):
            raise BatchConflict("duplicate_concept_id", "A release cannot contain duplicate concept identities.", 400)
        digest = self.artifacts.put(terms)
        identity = "terms_" + fingerprint([request.game_id, request.locale, request.version])[:24]
        if request.scope_id:
            identity = "terms_" + fingerprint([request.game_id, request.scope_id, request.locale, request.version])[:24]
        body = {"id": identity, "project_id": request.game_id, "game_id": request.game_id,
                "locale": request.locale, "version": request.version, "maturity": request.maturity,
                "artifact": digest, "term_count": len(terms)}
        if request.scope_id:
            body["scope_id"] = request.scope_id
        if origin is not None:
            body["origin"] = origin
        with self.repository.transaction() as db:
            row = db.execute("SELECT body FROM batch_records WHERE id=?", (identity,)).fetchone()
            if row:
                import json
                existing = json.loads(row[0])
                if existing != body:
                    raise BatchConflict("immutable_term_release", "Use a new version instead of changing a published release.")
                return existing
            self.repository._put(db, "term_release", body)
        return body

    def get(self, identifier, game_id=None, locale=None):
        record = self.repository.get(identifier, "term_release")
        if (game_id and record["game_id"] != game_id) or (locale and record["locale"] != locale):
            raise BatchConflict("term_release_identity_conflict", "Terminology release game or content locale differs.")
        return record, self.artifacts.get(record["artifact"])
