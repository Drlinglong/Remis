"""Reuse project archive terms-only contracts and the existing candidate store."""
from scripts.core.neologism_extraction import SourceEvidence, SourceItem
from scripts.core.services.context_tree_v2_term_candidate_service import ContextTreeV2TermCandidateService
from scripts.core.services.context_tree_v2_term_only import TermOnlyResult
from scripts.core.services.context_tree_v2_term_selection import TermOnlyTerm, TermOnlyVariant
from scripts.schemas.context_candidate import normalized_match_key
from scripts.core.batch_repository import BatchConflict


def persist_coverage_candidates(store, project_id, candidates, snapshot, locale):
    items = [SourceItem(source_item_id=e["id"], relative_path=f["relative_path"], item_key=e["key"],
                        source_order=i, source_text=e["source"])
             for f in snapshot["files"] for i, e in enumerate(f["entries"]) if f["selected"] and len(e["source"]) <= 20000]
    lookup = {item.source_item_id: item for item in items}
    by_key = {}
    for index, candidate in enumerate(candidates):
        evidence = [SourceEvidence(source_item_id=e["entry_id"], relative_path=lookup[e["entry_id"]].relative_path,
                    item_key=e["source_id"]) for e in candidate["examples"] if e["entry_id"] in lookup]
        if not evidence:
            continue
        variants = [TermOnlyVariant(variant_id=candidate["candidate_id"], batch_index=0, term_index=index,
                    original=candidate["source"], evidence=tuple(evidence[:5]))]
        key = normalized_match_key(candidate["source"], snapshot["source_locale"])
        if key in by_key:
            term = by_key[key]
            merged_evidence = tuple({e.source_item_id: e for e in [*term.evidence, *evidence]}.values())
            if len(term.variants) >= 100 or len(merged_evidence) > 500:
                raise BatchConflict("archive_candidate_contract_limit", "Select a smaller evidence group for this normalized term.", 400)
            term.variants.extend(variants)
            term.evidence = merged_evidence
        else:
            by_key[key] = TermOnlyTerm(normalized_key=key,
                    original=candidate["source"], evidence=tuple(evidence), variants=variants)
    return ContextTreeV2TermCandidateService(store, source_language=snapshot["source_locale"]).persist(
        project_id, TermOnlyResult(terms=list(by_key.values())), None, items, target_language=locale,
        review_language="zh-CN", append_evidence=True)
