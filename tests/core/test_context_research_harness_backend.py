import asyncio
from types import SimpleNamespace

import pytest
from pydantic_ai.models.test import TestModel

from scripts.core.services.context_research_contract import (
    AgentExecutionContext,
    ContextAnalysisRequest,
    ContextResearchDraft,
)
from scripts.core.services.context_research_compiler import ContextResearchFindings
from scripts.core.services.context_research_corpus_tools import (
    CorpusSourceItem,
    InMemoryCorpus,
    ReadOnlyRemisCorpusTools,
)
from scripts.core.services.context_research_harness_backend import (
    HARNESS_AVAILABLE,
    SUBAGENT_OUTPUT_TOKEN_LIMIT,
    SUBAGENT_REQUEST_LIMIT,
    SUBAGENT_TIMEOUT_SECONDS,
    SUBAGENT_TOOL_CALL_LIMIT,
    PydanticAIContextResearchBackend,
)


class Events:
    def __init__(self):
        self.items = []

    def emit(self, event, payload=None):
        self.items.append((event, payload or {}))


class Usage:
    def __init__(self):
        self.items = []

    def record(self, event, **metadata):
        self.items.append((event, metadata))


class Cancellation:
    def __init__(self, cancelled=False):
        self.cancelled = cancelled

    def is_cancelled(self):
        return self.cancelled


class DelegateOnceTestModel(TestModel):
    """TestModel that emits one valid delegate call, then final output."""

    def __init__(self, *, delegate_name="cartographer", **kwargs):
        super().__init__(**kwargs)
        self.delegate_name = delegate_name
        self._delegate_sent = False

    def _get_tool_calls(self, parameters):
        if self._delegate_sent:
            self.call_tools = []
            return []
        self._delegate_sent = True
        tool = next(tool for tool in parameters.function_tools if tool.name == "delegate_task")
        return [(tool.name, tool)]

    def gen_tool_args(self, tool_def):
        if tool_def.name == "delegate_task":
            return {"agent_name": self.delegate_name, "task": "List the bound corpus."}
        return super().gen_tool_args(tool_def)


def _request():
    return ContextAnalysisRequest(
        project_id="project-a",
        research_question="Which event is grounded in the archive?",
        source_item_ids=("source-1",),
    )


@pytest.mark.asyncio
async def test_archive_description_language_is_explicit_in_the_lead_request():
    prompts = []

    class CaptureAgent:
        async def run(self, prompt, **kwargs):
            del kwargs
            prompts.append(prompt)
            return SimpleNamespace(
                output=ContextResearchFindings(),
                usage=lambda: {},
            )

    class CaptureBackend(PydanticAIContextResearchBackend):
        def build_agent(self, **kwargs):
            del kwargs
            return CaptureAgent()

    backend = CaptureBackend(
        corpus_tools=ReadOnlyRemisCorpusTools(InMemoryCorpus([
            CorpusSourceItem("source-1", "text"),
        ])),
        model=object(),
    )
    request = _request().model_copy(update={"description_language": "zh-CN"})

    await backend.analyze(request, AgentExecutionContext("local-test"))

    assert "Archive description language: zh-CN" in prompts[0]
    assert "human-readable archive field" in prompts[0]


@pytest.mark.asyncio
async def test_real_harness_agent_returns_typed_draft_and_usage_event():
    pytest.importorskip("pydantic_ai_harness")
    from pydantic_ai.models.test import TestModel

    model = TestModel(
        call_tools=[],
        custom_output_args={
            "archive_narratives": [{
                "narrative_id": "n-1",
                "summary": "A grounded archive observation.",
                "evidence": [{"source_item_ids": ["source-1"]}],
            }],
        },
    )
    tools = ReadOnlyRemisCorpusTools(InMemoryCorpus([
        CorpusSourceItem("source-1", "The archive records a concrete event."),
    ]))
    events, usage = Events(), Usage()
    backend = PydanticAIContextResearchBackend(corpus_tools=tools, model=model)

    draft = await backend.analyze(
        _request(), AgentExecutionContext("local-test", events=events, usage=usage),
    )

    assert isinstance(draft, ContextResearchDraft)
    assert draft.source_item_ids == ("source-1",)
    assert any(
        item[0] == "context_research" and item[1]["scope"] == "harness_run_observed"
        and isinstance(item[1]["usage"], dict)
        for item in usage.items
    )
    assert {item[0] for item in events.items} == {"research_started", "research_completed"}


@pytest.mark.asyncio
async def test_harness_delegate_starts_a_child_with_a_distinct_model():
    pytest.importorskip("pydantic_ai_harness")
    from pydantic_ai.models.test import TestModel

    lead_model = DelegateOnceTestModel(
        call_tools=["delegate_task"],
        custom_output_args={
            "archive_narratives": [{
                "narrative_id": "n-1",
                "summary": "A grounded archive observation.",
                "evidence": [{"source_item_ids": ["source-1"]}],
            }],
        },
    )
    child_model = TestModel(call_tools=["list_corpus"], custom_output_text="child evidence")
    tools = ReadOnlyRemisCorpusTools(InMemoryCorpus([
        CorpusSourceItem("source-1", "The archive records a concrete event."),
    ]))
    backend = PydanticAIContextResearchBackend(
        corpus_tools=tools, model=lead_model, subagent_model=child_model,
    )

    draft = await backend.analyze(
        _request(), AgentExecutionContext("local-test"),
    )

    assert isinstance(draft, ContextResearchDraft)
    assert child_model.last_model_request_parameters is not None
    assert any(
        tool.name == "list_corpus"
        for tool in child_model.last_model_request_parameters.function_tools
    )


def test_real_agent_factory_contains_planning_and_subagents():
    pytest.importorskip("pydantic_ai_harness")
    from pydantic_ai.models.test import TestModel

    tools = ReadOnlyRemisCorpusTools(InMemoryCorpus([]))
    backend = PydanticAIContextResearchBackend(corpus_tools=tools, model=TestModel())
    agent = backend.build_agent(output_type=str)
    capability_names = {type(item).__name__ for item in agent.root_capability.capabilities}

    assert HARNESS_AVAILABLE is True
    assert {"Planning", "SubAgents"} <= capability_names
    subagents = next(item for item in agent.root_capability.capabilities if type(item).__name__ == "SubAgents")
    assert len(subagents.agents) == 4
    assert all(item.max_calls == 1 for item in subagents.agents)
    assert all(item.timeout_seconds == SUBAGENT_TIMEOUT_SECONDS for item in subagents.agents)
    assert all(item.usage_limits.request_limit == SUBAGENT_REQUEST_LIMIT for item in subagents.agents)
    assert all(item.usage_limits.tool_calls_limit == SUBAGENT_TOOL_CALL_LIMIT for item in subagents.agents)
    assert all(item.usage_limits.output_tokens_limit == SUBAGENT_OUTPUT_TOKEN_LIMIT for item in subagents.agents)


def test_factory_uses_distinct_optional_subagent_model():
    pytest.importorskip("pydantic_ai_harness")
    from pydantic_ai.models.test import TestModel

    lead_model, child_model = TestModel(), TestModel()
    backend = PydanticAIContextResearchBackend(
        corpus_tools=ReadOnlyRemisCorpusTools(InMemoryCorpus([])),
        model=lead_model,
        subagent_model=child_model,
    )
    agent = backend.build_agent(output_type=str)
    subagents = next(item for item in agent.root_capability.capabilities if type(item).__name__ == "SubAgents")

    assert all(delegate.agent.model is child_model for delegate in subagents.agents)
    assert all(
        any(tool.name == "list_units" for tool in delegate.agent._function_toolset.tools.values())
        for delegate in subagents.agents
    )


@pytest.mark.asyncio
async def test_cancellation_signal_is_checked_before_model_call():
    pytest.importorskip("pydantic_ai_harness")
    from pydantic_ai.models.test import TestModel

    backend = PydanticAIContextResearchBackend(
        corpus_tools=ReadOnlyRemisCorpusTools(InMemoryCorpus([
            CorpusSourceItem("source-1", "text"),
        ])),
        model=TestModel(),
    )
    with pytest.raises(asyncio.CancelledError):
        await backend.analyze(
            _request(),
            AgentExecutionContext("local-test", cancellation=Cancellation(True)),
        )


@pytest.mark.asyncio
async def test_cancellation_cancels_a_slow_agent_run_and_emits_event():
    class SlowAgent:
        async def run(self, *args, **kwargs):
            del args, kwargs
            await asyncio.sleep(30)

    class SlowBackend(PydanticAIContextResearchBackend):
        def build_agent(self, **kwargs):
            del kwargs
            return SlowAgent()

    cancellation = Cancellation()
    events = Events()
    backend = SlowBackend(
        corpus_tools=ReadOnlyRemisCorpusTools(InMemoryCorpus([
            CorpusSourceItem("source-1", "text"),
        ])),
        model=object(),
    )
    task = asyncio.create_task(backend.analyze(
        _request(), AgentExecutionContext("local-test", cancellation=cancellation, events=events),
    ))
    await asyncio.sleep(0.1)
    cancellation.cancelled = True
    with pytest.raises(asyncio.CancelledError):
        await task
    assert any(item[0] == "research_cancelled" for item in events.items)
