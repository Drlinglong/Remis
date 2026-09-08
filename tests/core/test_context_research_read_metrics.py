from __future__ import annotations

import asyncio
from types import SimpleNamespace

from scripts.core.services.context_research_corpus_tools import CorpusSourceItem
from scripts.core.services.context_research_read_metrics import CorpusReadMeter
from scripts.core.services.context_research_harness_agent import register_corpus_tools
from scripts.core.services.context_research_read_metrics import CorpusReadMeter


def _meter() -> CorpusReadMeter:
    return CorpusReadMeter((
        CorpusSourceItem("source-1", "alpha beta", path="one.yml", key="one"),
        CorpusSourceItem("source-2", "伽马 delta", path="two.yml", key="two"),
    ))


def test_counts_only_returned_body_and_repeated_reads() -> None:
    meter = _meter()
    meter.observe(
        "read_corpus",
        {"items": [{"source_item_id": "S001", "key": "ignored", "text": "alpha beta"}]},
        actor_role="lead",
        source_id_resolver={"S001": "source-1"}.get,
    )
    meter.observe(
        "search_corpus",
        {"items": [{"source_item_id": "S001", "text": "alpha beta"}]},
        actor_role="archive_lore",
        source_id_resolver={"S001": "source-1"}.get,
    )

    result = meter.snapshot()
    assert result["numerator_tokens"] == 4
    assert result["reread_tokens"] == 2
    assert result["unique_coverage_tokens"] == 2
    assert result["by_actor"] == {"lead": 2, "archive_lore": 2}
    assert result["by_tool"] == {"read_corpus": 2, "search_corpus": 2}


def test_metadata_tool_is_not_a_corpus_read() -> None:
    meter = _meter()
    meter.observe(
        "list_units",
        {"units": [{"local_unit_id": "U001", "entries": []}]},
        actor_role="lead",
    )
    result = meter.snapshot()
    assert result["numerator_tokens"] == 0
    assert result["call_count"] == 0


def test_unit_entries_are_counted_with_ownership_buckets() -> None:
    meter = _meter()
    meter.observe(
        "read_units",
        {"units": [{
            "local_unit_id": "U001",
            "ownership": "owned",
            "entries": [
                {"source_item_id": "S001", "text": "alpha beta", "ownership": "owned"},
                {"source_item_id": "S002", "text": "伽马 delta", "ownership": "context_only"},
            ],
        }]},
        actor_role="event_investigator",
        source_id_resolver={"S001": "source-1", "S002": "source-2"}.get,
    )
    result = meter.snapshot()
    assert result["by_role_tool"] == {"event_investigator:read_units": 6}
    assert result["by_ownership"]["owned"] == 2
    assert result["by_ownership"]["context_only"] == 4


def test_tool_failure_marks_metric_incomplete_without_character_fallback() -> None:
    meter = _meter()
    meter.record_failure("read_corpus", actor_role="lead", error=RuntimeError("failed"))
    result = meter.snapshot()
    assert result["complete"] is False
    assert result["value"] is None
    assert result["numerator_tokens"] == 0


def test_registered_tool_records_the_agent_role() -> None:
    class Agent:
        def __init__(self) -> None:
            self.tools = {}

        def tool(self, function):
            self.tools[function.__name__] = function
            return function

    meter = _meter()
    deps = SimpleNamespace(
        _corpus_read_meter=meter,
        read_source_items=lambda ids, _model_facing=False: {
            "items": [{"source_item_id": "source-1", "text": "alpha beta"}],
        },
    )
    agent = Agent()
    register_corpus_tools(agent, actor_role="archive_lore")
    asyncio.run(agent.tools["read_corpus"](
        SimpleNamespace(deps=deps), ["source-1"],
    ))
    assert meter.snapshot()["by_role_tool"] == {"archive_lore:read_corpus": 2}
