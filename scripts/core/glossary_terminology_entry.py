"""Map reviewed terminology into the editable glossary schema."""

import uuid

from .batch_artifacts import fingerprint
from .db_models import GlossaryEntry
from .glossary_terminology_review import review_basis


def terminology_entry(glossary_id, locale, term):
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


def terminology_import_fingerprint(request):
    payload = request.model_dump(exclude={"approved"})
    for term in payload["terms"]:
        if term.get("historical_reference") is None:
            term.pop("historical_reference", None)
    return fingerprint(payload)
