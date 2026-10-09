"""Review policy preserves human decisions and separates reference/model edits."""
from copy import deepcopy

from .batch_repository import BatchConflict


def review_basis(source, translation, term):
    return {"source": source, "translation": translation, "sense": term.get("sense", ""),
            "context_keys": term.get("context_keys", [])}


def apply_review_change(row, request, change):
    metadata = deepcopy(row.raw_metadata)
    detail = metadata["terminology"]
    if detail.get("locale") != request.locale:
        raise BatchConflict("terminology_locale_conflict", "Choose the glossary's terminology locale.", 400)
    origin = request.review_origin
    if origin == "reference":
        if (change.translation is not None or change.sense is not None or change.confidence is not None or change.aliases is not None
                or change.review_state != detail["review_state"]):
            raise BatchConflict("reference_cannot_change_decision", "Reference enrichment must preserve translations and review state.", 400)
    if origin == "model":
        if detail.get("review_state") == "approved" or detail.get("human_review", {}).get("decision") == "approved":
            raise BatchConflict("protected_human_decision", "Model review cannot overwrite a human-confirmed term.")
        if change.review_state == "approved":
            raise BatchConflict("model_cannot_human_approve", "Model review cannot claim human confirmation.", 400)
    translations = deepcopy(row.translations)
    variants = deepcopy(row.variants or {})
    if change.historical_reference is not None:
        detail["historical_reference"] = change.historical_reference.model_dump()
    if origin != "reference":
        review = {"reviewer": request.reviewer, "reason": change.reason, "decision": change.review_state,
                  "previous_translation": row.translations.get(request.locale), "previous_sense": detail.get("sense"),
                  "previous_confidence": detail.get("confidence"),
                  "previous_aliases": variants.get("en", detail.get("aliases", []))}
        alias_only = (change.aliases is not None and change.translation is None and change.sense is None
                      and change.confidence is None and change.review_state == detail["review_state"])
        review_key = "alias_review" if alias_only else "human_review" if origin == "human" else "model_review"
        detail[review_key] = {**review, "origin": origin}
        if change.translation is not None:
            translations[request.locale] = change.translation
        if change.sense is not None:
            detail["sense"] = change.sense
            metadata["remarks"] = change.sense
        if change.aliases is not None:
            detail["aliases"] = list(change.aliases)
            variants["en"] = list(change.aliases)
            detail["alias_review_basis"] = list(change.aliases)
        if change.confidence is not None:
            detail["confidence"] = change.confidence
        detail["review_state"] = change.review_state
        dimension = "human_terminology_decision" if origin == "human" else "model_community_consistency_review"
        if dimension not in detail.get("review_dimensions", []):
            detail["review_dimensions"] = [*detail.get("review_dimensions", []), dimension]
        if change.review_state in {"reviewed", "approved"}:
            detail["review_basis"] = review_basis(metadata["source_text"], translations[request.locale], detail)
    row.translations, row.raw_metadata, row.variants = translations, metadata, variants
