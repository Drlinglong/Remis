from types import SimpleNamespace

import pytest

from scripts.core.neologism_extraction import SourceItem
from scripts.core.services.context_research_compiler import (
    ContextResearchDraftCompiler,
    ContextResearchFindings,
)
from scripts.core.services.context_research_contract import ContextAnalysisRequest
from scripts.core.services.context_research_harness_run import (
    ContextResearchRunCoordinator,
    DelegationTracker,
    apply_targeted_repairs,
)
from scripts.core.services.context_research_lead_decisions import LeadResearchResult
from scripts.core.services.context_research_shard_memo import ShardMemoCollector
from scripts.core.services.context_research_repair_policy import build_repair_packet
from scripts.core.services.context_research_repair_models import RepairPacket, RepairTarget
from scripts.core.services.context_research_trace_ledger import ContextResearchTraceCollector


def _request():
    return ContextAnalysisRequest(
        project_id="demo",
        source_items=(SourceItem(
            source_item_id="source-1",
            relative_path="events/demo.yml",
            item_key="demo.1.desc",
            source_order=0,
            source_text="Remis begins the reform.",
        ),),
    )


def _findings(entity_id="ghost", event="原始事件叙述"):
    return ContextResearchFindings.model_validate({
        "entities": [{
            "entity_id": "remis",
            "name": "Remis",
            "entity_type": "person",
            "summary": "核心人物。",
            "evidence": [{"source_item_ids": ["source-1"]}],
        }],
        "event_chains": [{
            "chain_id": "demo-chain",
            "sequence": 1,
            "event": event,
            "entity_ids": [entity_id],
            "evidence": [{"source_item_ids": ["source-1"]}],
        }],
    })


def test_targeted_repair_cannot_rewrite_fields_outside_compiler_permission():
    request = _request()
    original = _findings()
    draft = ContextResearchDraftCompiler().compile(original, request)
    packet = build_repair_packet(draft.diagnostics, original, request=request)
    repairs = _findings(entity_id="remis", event="试图覆盖原事件叙述")

    repaired = apply_targeted_repairs(original, repairs, packet)

    assert repaired.event_chains[0].entity_ids == ("remis",)
    assert repaired.event_chains[0].event == "原始事件叙述"


def test_uncallable_optional_link_repair_is_nonblocking_after_safe_compile_drop():
    request = _request()
    findings = _findings()
    draft = ContextResearchDraftCompiler().compile(findings, request)
    packet = build_repair_packet(
        {"unknown_entity_links": [{
            "chain_id": "demo-chain", "sequence": 1, "entity_id": "missing",
        }]},
        findings,
    )

    result = ContextResearchRunCoordinator._finish(
        draft, findings, DelegationTracker(SimpleNamespace(emit=lambda *args: None)),
        packet, 0, None,
    )

    assert packet.model_call_allowed is False
    assert result.diagnostics["run"]["status"] == "complete"
    assert result.diagnostics["run"]["publishable"] is True
    assert result.diagnostics["run"]["repair_remaining"] is False
    assert result.diagnostics["run"]["nonblocking_repair_target_count"] == 1


def test_repair_target_remaining_after_attempt_still_blocks_publication():
    request = _request()
    findings = _findings()
    draft = ContextResearchDraftCompiler().compile(findings, request)
    packet = RepairPacket(
        attempt=2, remaining_attempts=0,
        targets=(RepairTarget(
            finding_type="event_chain", finding_id="crisis", sequence=1,
            failure_codes=("unknown_entity_links",), classification="repairable",
            allowed_fields=("entity_ids",), source_allow_list=("source-1",),
        ),),
        valid_source_allow_list=("source-1",), model_call_allowed=False,
    )

    result = ContextResearchRunCoordinator._finish(
        draft, findings, DelegationTracker(SimpleNamespace(emit=lambda *args: None)),
        packet, 2, None,
    )

    assert result.diagnostics["run"]["status"] == "incomplete"
    assert result.diagnostics["run"]["publishable"] is False


@pytest.mark.asyncio
async def test_tracked_child_persists_memo_and_whole_child_usage(tmp_path):
    class Events:
        def __init__(self):
            self.values = []

        def emit(self, event, payload):
            self.values.append((event, payload))

    class Child:
        model = SimpleNamespace(model_name="luna-test")

        async def run(self, task, **kwargs):
            del task, kwargs
            return SimpleNamespace(
                output="子代理备忘录",
                usage=lambda: {"requests": 2, "input_tokens": 40, "output_tokens": 8},
                new_messages=lambda: [],
            )

    path = tmp_path / "trace.json"
    trace = ContextResearchTraceCollector("trace", output_path=path)
    tracker = DelegationTracker(Events(), trace)

    result = await tracker.wrap(Child(), "cartographer").run("调查 shard A")

    snapshot = trace.snapshot()
    assert result.output == "子代理备忘录"
    assert snapshot["delegations"][0]["status"] == "completed"
    assert snapshot["delegations"][0]["child_memo"] == "子代理备忘录"
    assert snapshot["usage"]["records"][0]["role"] == "cartographer"
    assert snapshot["usage"]["records"][0]["input_tokens"] == 40
    assert path.is_file()


@pytest.mark.asyncio
async def test_accepted_typed_child_returns_compact_receipt_but_retains_full_memo(tmp_path):
    class Events:
        def emit(self, event, payload):
            del event, payload

    class Lease:
        core_local_unit_ids = ("unit-a",)
        overlap_local_unit_ids = ()

    class Deps:
        @staticmethod
        def validate_delegation_task(task):
            assert task == "inspect shard-a"
            return ("shard-a",)

        @staticmethod
        def shard_lease(shard_ids):
            assert shard_ids == ("shard-a",)
            return Lease()

        @staticmethod
        def owned_shard_view(shard_ids):
            assert shard_ids == ("shard-a",)
            return object()

    full_memo = {
        "role": "cartographer",
        "shard_ids": ["shard-a"],
        "core_local_unit_ids": ["unit-a"],
        "overlap_local_unit_ids": [],
        "units": [{
            "local_unit_id": "unit-a",
            "ownership": "core",
            "disposition": "modeled",
            "findings": {
                "archive_narratives": [{
                    "narrative_id": "secret-finding",
                    "summary": "SOURCE TEXT MUST NOT REACH LEAD",
                    "evidence": [{"source_item_ids": ["source-a"]}],
                }],
                "reference_assets": [{
                    "asset_id": "secret-route",
                    "name": "Archive asset",
                    "description": "Static context route.",
                    "local_unit_id": "unit-a",
                    "evidence": [{"source_item_ids": ["source-a"]}],
                }],
            },
        }],
    }

    class Child:
        model = SimpleNamespace(model_name="child-model")

        async def run(self, task, **kwargs):
            del task, kwargs
            return SimpleNamespace(
                output=full_memo,
                usage=lambda: {"requests": 1},
                new_messages=lambda: ["child message"],
            )

    trace = ContextResearchTraceCollector("typed-receipt", output_path=tmp_path / "trace.json")
    tracker = DelegationTracker(
        Events(), trace,
        memo_collector=ShardMemoCollector([{
            "shard_id": "shard-a",
            "core_local_unit_ids": ["unit-a"],
        }]),
    )

    result = await tracker.wrap(Child(), "cartographer").run(
        "inspect shard-a", deps=Deps(),
    )

    assert result.output == {
        "role": "cartographer",
        "shard_ids": ["shard-a"],
        "core_local_unit_count": 1,
        "overlap_local_unit_count": 0,
        "finding_counts": {
            "archive_narratives": 1,
            "entities": 0,
            "event_chains": 0,
            "reference_assets": 1,
            "unresolved": 0,
        },
        "collection_accepted": True,
    }
    assert "SOURCE TEXT MUST NOT REACH LEAD" not in str(result.output)
    assert result.usage() == {"requests": 1}
    assert result.new_messages() == ["child message"]
    collected = tracker.collect_memos()
    assert collected is not None
    assert collected.findings.archive_narratives[0].summary == "SOURCE TEXT MUST NOT REACH LEAD"
    assert trace.snapshot()["delegations"][0]["child_memo"]["units"]


def test_compact_receipt_exposes_sparse_event_and_entity_decision_index():
    from scripts.core.services.context_research_delegation import _compact_memo_receipt
    from scripts.core.services.context_research_shard_memo import ShardMemo

    memo = ShardMemo.model_validate({
        "role": "event_investigator",
        "shard_ids": ["shard-a"],
        "core_local_unit_ids": ["unit-a"],
        "units": [{
            "local_unit_id": "unit-a",
            "ownership": "core",
            "disposition": "modeled",
            "findings": {
                "event_chains": [{
                    "chain_id": "local-fragment-a",
                    "sequence": 2,
                    "event": "  The knight   begins the same long quest.  ",
                    "local_unit_ids": ["unit-a"],
                    "evidence": [{"source_item_ids": ["source-a"]}],
                }],
                "entities": [{
                    "entity_id": "the-knight",
                    "name": "The Knight",
                    "entity_type": "person",
                    "summary": "Quest protagonist.",
                    "evidence": [{"source_item_ids": ["source-a"]}],
                }],
            },
        }],
    })

    receipt = _compact_memo_receipt(memo)

    assert receipt["decision_index"] == {
        "event_chains": [{
            "finding_id": "local-fragment-a",
            "sequence": 2,
            "local_unit_ids": ["unit-a"],
            "label": "The knight begins the same long quest.",
        }],
        "entities": [{
            "finding_id": "the-knight",
            "name": "The Knight",
            "entity_type": "person",
            "reported_by_unit_ids": ["unit-a"],
        }],
    }
    assert "source-a" not in str(receipt)


@pytest.mark.asyncio
async def test_tracked_child_rejects_open_ended_large_corpus_task_before_model_call():
    class Events:
        def emit(self, event, payload):
            del event, payload

    class Deps:
        @staticmethod
        def validate_delegation_task(task):
            raise ValueError(f"oversized task: {task}")

    class Child:
        model = SimpleNamespace(model_name="luna-test")
        called = False

        async def run(self, task, **kwargs):
            del task, kwargs
            self.called = True

    child = Child()
    trace = ContextResearchTraceCollector("trace")
    tracker = DelegationTracker(Events(), trace)

    with pytest.raises(ValueError, match="oversized task"):
        await tracker.wrap(child, "archive_lore").run("scan everything", deps=Deps())

    assert child.called is False
    assert trace.snapshot()["delegations"][0]["status"] == "failed"


@pytest.mark.asyncio
async def test_out_of_lease_memo_is_traced_but_cannot_pollute_collection():
    class Events:
        def __init__(self):
            self.values = []

        def emit(self, event, payload):
            self.values.append((event, payload))

    class Lease:
        core_local_unit_ids = ("unit-a",)
        overlap_local_unit_ids = ()

    class Deps:
        @staticmethod
        def validate_delegation_task(task):
            del task
            return ("shard-a",)

        @staticmethod
        def shard_lease(shard_ids):
            del shard_ids
            return Lease()

        @staticmethod
        def owned_shard_view(shard_ids):
            del shard_ids
            return object()

    class Child:
        model = SimpleNamespace(model_name="child-model")

        async def run(self, task, **kwargs):
            del task, kwargs
            return SimpleNamespace(
                output={
                    "role": "cartographer",
                    "shard_ids": ["shard-b"],
                    "core_local_unit_ids": ["unit-b"],
                    "units": [{
                        "local_unit_id": "unit-b",
                        "ownership": "core",
                        "disposition": "intentionally_unmodeled",
                        "findings": {},
                    }],
                },
                usage=lambda: {"requests": 1},
                new_messages=lambda: [],
            )

    events = Events()
    trace = ContextResearchTraceCollector("out-of-lease")
    tracker = DelegationTracker(
        events,
        trace,
        memo_collector=ShardMemoCollector([{
            "shard_id": "shard-a", "core_local_unit_ids": ["unit-a"],
        }]),
    )

    await tracker.wrap(Child(), "cartographer").run("inspect shard-a", deps=Deps())

    collection = tracker.collect_memos()
    assert collection is not None
    assert collection.missing_core_local_unit_ids == ("unit-a",)
    assert collection.unknown_shard_ids == ()
    assert tracker.memos == []
    assert trace.snapshot()["delegations"][0]["status"] == "rejected"
    assert events.values[-1][1]["partial_artifact_retained_in_trace"] is True


@pytest.mark.asyncio
async def test_tracked_child_records_provider_usage_when_output_validation_fails():
    class Events:
        def emit(self, event, payload):
            del event, payload

    class Child:
        model = SimpleNamespace(model_name="luna-test")

        async def run(self, task, **kwargs):
            del task
            usage = kwargs["usage"]
            usage.requests = 3
            usage.input_tokens = 120
            usage.output_tokens = 45
            usage.cost = 0.0123
            raise RuntimeError("structured output retries exhausted")

    trace = ContextResearchTraceCollector("failed-usage")
    tracker = DelegationTracker(Events(), trace)

    with pytest.raises(RuntimeError, match="structured output retries exhausted"):
        await tracker.wrap(Child(), "evidence_auditor").run("inspect shard-a")

    snapshot = trace.snapshot()
    assert snapshot["delegations"][0]["status"] == "failed"
    assert snapshot["usage"]["records"][0]["status"] == "failed"
    assert snapshot["usage"]["records"][0]["requests"] == 3
    assert snapshot["usage"]["records"][0]["input_tokens"] == 120
    assert snapshot["usage"]["records"][0]["output_tokens"] == 45
    assert snapshot["usage"]["records"][0]["cost"] == pytest.approx(0.0123)


@pytest.mark.asyncio
async def test_coordinator_runs_one_exact_gap_completion_pass_for_partial_memo():
    class Events:
        def emit(self, event, payload):
            del event, payload

    class Usage:
        def record(self, event, **metadata):
            del event, metadata

    class Result:
        output = LeadResearchResult()

        def usage(self):
            return {"requests": 1}

        def all_messages(self):
            return []

    class Agent:
        model = SimpleNamespace(model_name="lead-model")

    manifest = (
        {"shard_id": "s0", "core_local_unit_ids": ["unit_0"]},
        {"shard_id": "s1", "core_local_unit_ids": ["unit_1"]},
    )
    tracker = DelegationTracker(
        Events(),
        memo_collector=ShardMemoCollector(manifest),
    )
    tracker.bound = True
    tracker.successes = {
        "cartographer": 1,
        "event_investigator": 1,
        "archive_lore": 1,
        "evidence_auditor": 1,
    }
    tracker.accept_memo(
        role="cartographer",
        expected_shard_ids=("s0", "s1"),
        lease=SimpleNamespace(
            core_local_unit_ids=("unit_0", "unit_1"), overlap_local_unit_ids=(),
        ),
        output={
            "role": "cartographer",
            "shard_ids": ["s0"],
            "core_local_unit_ids": ["unit_0"],
            "units": [{
                "local_unit_id": "unit_0", "ownership": "core",
                "disposition": "intentionally_unmodeled", "findings": {},
            }],
        },
    )
    calls = []

    async def run_lead(agent, prompt, bound_tools, *, message_history=None):
        del agent, bound_tools, message_history
        calls.append(prompt)
        assert "Exact missing investigation shard IDs are: s1." in prompt
        tracker.accept_memo(
            role="archive_lore",
            expected_shard_ids=("s1",),
            lease=SimpleNamespace(
                core_local_unit_ids=("unit_1",), overlap_local_unit_ids=(),
            ),
            output={
                "role": "archive_lore",
                "shard_ids": ["s1"],
                "core_local_unit_ids": ["unit_1"],
                "units": [{
                    "local_unit_id": "unit_1", "ownership": "core",
                    "disposition": "intentionally_unmodeled", "findings": {},
                }],
            },
        )
        return Result()

    context = SimpleNamespace(events=Events(), usage=Usage())
    request = _request()
    draft = await ContextResearchRunCoordinator(
        ContextResearchDraftCompiler(), max_repair_attempts=0,
    ).finalize(
        initial_result=Result(), agent=Agent(), bound_tools=SimpleNamespace(),
        tracker=tracker, request=request, execution_context=context,
        run_lead=run_lead,
    )

    assert len(calls) == 1
    assert draft.diagnostics["run"]["status"] == "complete"
    assert draft.diagnostics["run"]["memo_collection_complete"] is True
