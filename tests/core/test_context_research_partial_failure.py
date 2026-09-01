"""Failure-path tests for retaining a context-research partial artifact."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from scripts.core.services.context_research_compiler import ContextResearchFindings
from scripts.core.services.context_research_harness_backend import (
    PydanticAIContextResearchBackend,
    SUBAGENT_MAX_OUTPUT_TOKENS,
    SUBAGENT_OUTPUT_TOKEN_LIMIT,
    SUBAGENT_TOOL_CALL_LIMIT,
)
from scripts.core.services.context_research_harness_run import DelegationTracker
from scripts.core.services.context_research_corpus_tools import (
    CorpusSourceItem,
    InMemoryCorpus,
    ReadOnlyRemisCorpusTools,
)
from scripts.core.services.context_research_contract import (
    AgentExecutionContext,
    ContextAnalysisRequest,
)
from scripts.core.services.context_research_trace_ledger import ContextResearchTraceCollector


class _Events:
    def __init__(self):
        self.items = []

    def emit(self, event, payload=None):
        self.items.append((event, payload or {}))


class _Usage:
    def record(self, event, **metadata):
        del event, metadata


def _request():
    return ContextAnalysisRequest(project_id="partial-demo", source_item_ids=("source-1",))


def test_child_budget_allows_two_bounded_output_corrections():
    assert SUBAGENT_TOOL_CALL_LIMIT == 12
    assert SUBAGENT_MAX_OUTPUT_TOKENS == 8_000
    assert SUBAGENT_OUTPUT_TOKEN_LIMIT == 24_000


@pytest.mark.asyncio
async def test_tracked_child_error_is_recorded_with_role_and_stage(tmp_path):
    class Events:
        def emit(self, event, payload):
            del event, payload

    class Child:
        model = SimpleNamespace(model_name="luna-test")

        async def run(self, *args, **kwargs):
            del args, kwargs
            raise RuntimeError("provider message")

    trace = ContextResearchTraceCollector(
        "child-error", output_path=tmp_path / "trace.json",
    )
    tracker = DelegationTracker(Events(), trace)
    with pytest.raises(RuntimeError, match="provider message"):
        await tracker.wrap(Child(), "archive_lore").run("inspect shard")

    error = trace.snapshot()["errors"][0]
    assert error["stage"] == "subagent"
    assert error["role"] == "archive_lore"
    assert error["error_type"] == "RuntimeError"
    assert error["message"] == "provider message"


@pytest.mark.asyncio
async def test_lead_failure_runs_missing_role_completion_and_returns_partial_artifact(tmp_path):
    class UsageLimitExceeded(RuntimeError):
        pass

    class Result:
        output = ContextResearchFindings.model_validate({
            "archive_narratives": [{
                "narrative_id": "retained",
                "summary": "保留已经拿到的半成品。",
                "evidence": [{"source_item_ids": ["source-1"]}],
            }],
        })

        def usage(self):
            return {"requests": 1}

        def all_messages(self):
            return []

    class Lead:
        model = SimpleNamespace(model_name="luna-test")
        calls = 0

        async def run(self, *args, **kwargs):
            del args, kwargs
            self.calls += 1
            if self.calls == 1:
                raise UsageLimitExceeded("api_key=sk-do-not-record")
            return Result()

    class Backend(PydanticAIContextResearchBackend):
        def build_agent(self, *, delegation_tracker=None, **kwargs):
            del kwargs
            delegation_tracker.mark_bound()
            return Lead()

    events = _Events()
    trace_path = tmp_path / "trace.json"
    backend = Backend(
        corpus_tools=ReadOnlyRemisCorpusTools(InMemoryCorpus([
            CorpusSourceItem("source-1", "A grounded archive entry."),
        ])),
        model=object(),
        trace_output_path=trace_path,
    )

    draft = await backend.analyze(
        _request(), AgentExecutionContext("local-test", events=events, usage=_Usage()),
    )

    assert draft.archive_narratives[0].narrative_id == "retained"
    assert draft.diagnostics["run"]["status"] == "incomplete"
    assert draft.diagnostics["run"]["publishable"] is False
    assert any(event == "research_failed" and payload["partial_artifact_retained"] for event, payload in events.items)
    trace = backend.last_trace_snapshot
    assert trace is not None
    assert trace["errors"][0]["stage"] == "lead"
    assert "sk-do-not-record" not in str(trace["errors"])
    assert trace["final_draft"] is not None
    assert trace_path.is_file()
