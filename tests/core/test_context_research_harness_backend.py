import asyncio
from types import SimpleNamespace

import pytest
from pydantic_ai.models.test import TestModel
from scripts.core.services import context_research_harness_backend as harness_backend
from scripts.core.services import context_research_harness_agent as harness_agent

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
    MAX_ROLE_CALLS_PER_RUN,
    REQUIRED_ROLE_NAMES,
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
            return {
                "agent_name": self.delegate_name,
                "task": "Inspect exact shard investigation-000 only.",
            }
        return super().gen_tool_args(tool_def)


def _memo(role, findings=None):
    return {
        "role": role,
        "shard_ids": ["investigation-000"],
        "core_local_unit_ids": ["U001"],
        "overlap_local_unit_ids": [],
        "units": [{
            "local_unit_id": "U001",
            "ownership": "core",
            "disposition": "modeled" if findings else "intentionally_unmodeled",
            "findings": findings or {},
        }],
    }


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

    model = DelegateOnceTestModel(
        delegate_name="archive_lore",
        call_tools=["delegate_task"],
        custom_output_args={},
    )
    child_model = TestModel(
        call_tools=[],
        custom_output_args=_memo("archive_lore", {
            "archive_narratives": [{
                "narrative_id": "n-1",
                "summary": "A grounded archive observation.",
                "evidence": [{"source_item_ids": ["S001"]}],
            }],
            "reference_assets": [{
                "asset_id": "reference-1",
                "name": "Archive record",
                "description": "Static archive context, not an event delivery target.",
                "local_unit_id": "U001",
                "evidence": [{"source_item_ids": ["S001"]}],
            }],
        }),
    )
    tools = ReadOnlyRemisCorpusTools(InMemoryCorpus([
        CorpusSourceItem("source-1", "The archive records a concrete event."),
    ]))
    events, usage = Events(), Usage()
    backend = PydanticAIContextResearchBackend(
        corpus_tools=tools, model=model, subagent_model=child_model,
    )

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
    assert {
        "research_started", "research_fanout_planned", "research_role_completed",
        "research_completed",
    } <= {item[0] for item in events.items}


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
    child_model = TestModel(
        call_tools=["list_corpus"],
        custom_output_args=_memo("cartographer"),
    )
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
    assert all(item.max_calls == MAX_ROLE_CALLS_PER_RUN for item in subagents.agents)
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


def test_role_model_settings_are_merged_and_not_shared():
    source = {
        "extra_body": {"reasoning": {"effort": "low"}},
        "temperature": 0.1,
    }
    merged = harness_agent.merge_model_settings(8000, source)

    assert merged == {
        "max_tokens": 8000,
        "extra_body": {"reasoning": {"effort": "low"}},
        "temperature": 0.1,
    }
    merged["extra_body"]["reasoning"]["effort"] = "high"
    assert source["extra_body"]["reasoning"]["effort"] == "low"


def test_lead_and_child_models_receive_only_their_role_settings(monkeypatch):
    class FakeAgent:
        instances = []

        def __init__(self, model, **kwargs):
            self.model = model
            self.model_settings = kwargs["model_settings"]
            self._function_toolset = type("ToolSet", (), {"tools": {}})()
            type(self).instances.append(self)

        def tool(self, function):
            self._function_toolset.tools[function.__name__] = function
            return function

    class FakeCapability:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeSubAgent:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class FakeSubAgents(FakeCapability):
        pass

    class FakePlanning(FakeCapability):
        pass

    import pydantic_ai

    monkeypatch.setattr(pydantic_ai, "Agent", FakeAgent)
    monkeypatch.setattr(harness_agent, "HARNESS_AVAILABLE", True)
    monkeypatch.setattr(harness_agent, "Planning", FakePlanning)
    monkeypatch.setattr(harness_agent, "SubAgent", FakeSubAgent)
    monkeypatch.setattr(harness_agent, "SubAgents", FakeSubAgents)
    monkeypatch.setattr(harness_agent, "HarnessToolOutputLimits", None)
    monkeypatch.setattr(harness_agent, "ClearToolResults", None)
    monkeypatch.setattr(harness_agent, "WarnNearLimits", None)

    lead_model = object()
    child_model = object()
    harness_agent.build_lead_agent(
        model=lead_model,
        subagent_model=child_model,
        tool_limits=ReadOnlyRemisCorpusTools(InMemoryCorpus([])).limits,
        output_type=str,
        delegation_tracker=None,
        role_max_calls=1,
        lead_model_settings={
            "max_tokens": 1200,
            "extra_body": {"reasoning": {"effort": "low"}},
        },
        subagent_model_settings={
            "max_tokens": 300,
            "extra_body": {"reasoning": {"effort": "minimal"}},
        },
    )

    assert len(FakeAgent.instances) == 5
    children, lead = FakeAgent.instances[:4], FakeAgent.instances[4]
    assert lead.model is lead_model
    assert lead.model_settings == {
        "max_tokens": 1200,
        "extra_body": {"reasoning": {"effort": "low"}},
    }
    assert all(child.model is child_model for child in children)
    assert all(child.model_settings == {
        "max_tokens": 300,
        "extra_body": {"reasoning": {"effort": "minimal"}},
    } for child in children)


def test_backend_model_alias_and_lead_route_forward_role_configuration(monkeypatch):
    captured = {}

    def fake_build_lead_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(harness_backend, "build_lead_agent", fake_build_lead_agent)
    legacy_model, lead_model, child_model = object(), object(), object()
    backend = PydanticAIContextResearchBackend(
        corpus_tools=ReadOnlyRemisCorpusTools(InMemoryCorpus([])),
        model=legacy_model,
        lead_model=lead_model,
        subagent_model=child_model,
        lead_model_settings={"extra_body": {"reasoning": {"effort": "low"}}},
        subagent_model_settings={"max_tokens": 300},
    )

    backend.build_agent(output_type=str)

    assert backend.model is legacy_model
    assert backend.lead_model is lead_model
    assert backend.subagent_model is child_model
    assert captured["model"] is lead_model
    assert captured["subagent_model"] is child_model
    assert captured["lead_model_settings"] == {
        "max_tokens": 16000,
        "extra_body": {"reasoning": {"effort": "low"}},
    }
    assert captured["subagent_model_settings"] == {"max_tokens": 300}


def test_adaptive_role_budget_scales_with_local_unit_count():
    backend = object.__new__(PydanticAIContextResearchBackend)

    assert backend._adaptive_role_budget(0) == 1
    assert backend._adaptive_role_budget(12) == 1
    assert backend._adaptive_role_budget(13) == 3
    assert backend._adaptive_role_budget(64) == 3
    assert backend._adaptive_role_budget(65) == 8


@pytest.mark.asyncio
async def test_missing_required_roles_return_incomplete_draft_and_retain_findings():
    class FakeResult:
        def __init__(self, output):
            self.output = output
            self.usage = lambda: {"requests": 1}

        def all_messages(self):
            return []

    class IncompleteBackend(PydanticAIContextResearchBackend):
        def build_agent(self, *, delegation_tracker=None, **kwargs):
            del kwargs
            delegation_tracker.mark_bound()
            first = ContextResearchFindings.model_validate({
                "archive_narratives": [{
                    "narrative_id": "n-retained",
                    "summary": "Retain this grounded finding.",
                    "evidence": [{"source_item_ids": ["source-1"]}],
                }],
            })

            class FakeLead:
                calls = 0

                async def run(self, *args, **kwargs):
                    del args, kwargs
                    self.calls += 1
                    return FakeResult(first if self.calls == 1 else ContextResearchFindings())

            self.fake_lead = FakeLead()
            return self.fake_lead

    events, usage = Events(), Usage()
    backend = IncompleteBackend(
        corpus_tools=ReadOnlyRemisCorpusTools(InMemoryCorpus([
            CorpusSourceItem("source-1", "text"),
        ])),
        model=object(),
    )

    draft = await backend.analyze(
        _request(), AgentExecutionContext("local-test", events=events, usage=usage),
    )

    delegation = draft.diagnostics["model"]["delegation"]
    assert delegation["status"] == "incomplete"
    assert delegation["completion_attempted"] is True
    assert set(delegation["missing_roles"]) == set(REQUIRED_ROLE_NAMES)
    assert draft.archive_narratives[0].narrative_id == "n-retained"
    assert len([item for item in usage.items if item[0] == "context_research"]) == 2


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
