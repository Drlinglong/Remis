from scripts.core.services.context_publication_policy import evaluate_context_publication


def test_publication_policy_blocks_unresolved_and_uncovered_sources():
    assert evaluate_context_publication(unresolved_count=1).publishable is False
    uncovered = evaluate_context_publication(
        unresolved_count=0,
        uncovered_source_item_count=1,
    )
    assert uncovered.publishable is False
    assert uncovered.coverage_complete is False


def test_publication_policy_allows_complete_valid_draft():
    decision = evaluate_context_publication(
        unresolved_count=0,
        uncovered_source_item_count=0,
        validation_issue_count=0,
    )
    assert decision.publishable is True
    assert decision.status == "complete"
