"""Focused tests for the developer-only context research trace ledger."""

from __future__ import annotations

import json

import pytest
from pydantic_ai import RunUsage
from pydantic_ai.messages import ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart

from scripts.core.services.context_research_trace_ledger import (
    ContextResearchTraceCollector,
    UsageRecord,
    extract_message_history_trace,
    usage_record_from_run_usage,
)


def test_trace_records_the_full_research_tree_without_lifecycle_methods():
    collector = ContextResearchTraceCollector("trace-1", project_id="stellaris-demo")
    collector.record_plan({"steps": ["map", "inspect", "compile"]}, model="luna")
    delegation_id = collector.record_delegation(
        role="event_investigator",
        shard="events-0",
        task={"source_item_ids": ["source-1"]},
        status="completed",
        model="luna",
        child_memo={"finding": "A concrete event."},
    )
    collector.record_tool_activity(
        tool="read_corpus",
        role="event_investigator",
        shard="events-0",
        model="luna",
        status="completed",
        metadata={"source_item_count": 1},
    )
    collector.record_findings({"event_chains": [{"chain_id": "demo"}]})
    collector.record_compiler_diagnostics({"published_counts": {"event_chains": 1}})
    collector.record_repair(
        packet={"issue": "missing link"}, output={"fixed": False}, attempt=1,
    )
    collector.record_final_draft({"event_chains": [{"chain_id": "demo"}]})

    snapshot = collector.snapshot()

    assert snapshot["plan"]["content"]["steps"] == ["map", "inspect", "compile"]
    assert snapshot["delegations"][0]["delegation_id"] == delegation_id
    assert snapshot["delegations"][0]["child_memo"]["finding"] == "A concrete event."
    assert snapshot["tool_activity"][0]["tool"] == "read_corpus"
    assert snapshot["repair"]["packet"]["issue"] == "missing link"
    assert snapshot["repair"]["attempts"][0]["attempt"] == 1
    assert snapshot["final_draft"]["event_chains"][0]["chain_id"] == "demo"
    assert not hasattr(collector, "resume")
    assert not hasattr(collector, "checkpoint")


def test_trace_persists_corpus_read_observations_separately_from_usage():
    collector = ContextResearchTraceCollector("trace-read")
    collector.record_corpus_read(
        {
            "actor_role": "lead", "tool": "read_corpus",
            "returned_corpus_text_tokens": 7, "text_item_count": 1,
            "ownership_tokens": {"unscoped": 7},
        },
        {
            "schema_version": "corpus-read-amplification-v1",
            "numerator_tokens": 7, "denominator_tokens": 4,
            "value": 1.75, "complete": True,
        },
    )
    snapshot = collector.snapshot()
    assert snapshot["corpus_read"]["value"] == 1.75
    assert snapshot["corpus_read"]["observations"][0]["returned_corpus_text_tokens"] == 7
    assert snapshot["tool_activity"][-1]["kind"] == "corpus_read"


def test_trace_marks_failed_corpus_read_incomplete(tmp_path):
    from scripts.core.services.context_research_read_metrics import CorpusReadMeter
    from scripts.core.services.context_research_corpus_tools import CorpusSourceItem

    path = tmp_path / "trace.json"
    collector = ContextResearchTraceCollector("trace-read-failure", output_path=path)
    meter = CorpusReadMeter((CorpusSourceItem("source-1", "text"),))
    meter.set_observation_sink(collector.record_corpus_read)
    meter.record_failure("read_corpus", actor_role="lead", error=RuntimeError("x"))

    snapshot = json.loads(path.read_text(encoding="utf-8"))
    assert snapshot["corpus_read"]["complete"] is False
    assert snapshot["corpus_read"]["unobserved_calls"] == 1


def test_delegation_can_be_updated_without_duplicate_trace_nodes():
    collector = ContextResearchTraceCollector("trace-2")
    delegation_id = collector.record_delegation(
        role="cartographer", shard="entities-0", task="Map entities", status="started",
    )
    collector.record_delegation(
        role="cartographer", shard="entities-0", task="Map entities", status="completed",
        delegation_id=delegation_id, child_memo="Remis is a polity.", finished_at="2026-09-01T00:00:01Z",
    )

    delegations = collector.snapshot()["delegations"]
    assert len(delegations) == 1
    assert delegations[0]["status"] == "completed"
    assert delegations[0]["child_memo"] == "Remis is a polity."


def test_usage_is_grouped_by_scope_role_shard_model_and_aggregated():
    collector = ContextResearchTraceCollector("trace-3")
    collector.record_usage(UsageRecord(
        scope="lead", model="luna", input_tokens=100, cache_read_tokens=20,
        output_tokens=30, reasoning_tokens=4, tool_calls=2, cost=0.5,
        duration_ms=1200, status="completed",
    ))
    collector.record_usage({
        "scope": "subagent", "role": "event_investigator", "shard": "events-0",
        "model": "luna", "input_tokens": 40, "output_tokens": 10,
        "reasoning_tokens": 2, "tool_calls": 1, "cost": 0.1,
        "duration_ms": 300, "status": "completed",
    })
    collector.record_usage({
        "scope": "subagent", "role": "event_investigator", "shard": "events-0",
        "model": "luna", "input_tokens": 60, "output_tokens": 20,
        "reasoning_tokens": 3, "tool_calls": 2, "cost": 0.2,
        "duration_ms": 500, "status": "failed",
    })

    usage = collector.snapshot()["usage"]
    group = next(item for item in usage["summary"]["groups"] if item["scope"] == "subagent")
    assert group["role"] == "event_investigator"
    assert group["shard"] == "events-0"
    assert group["input_tokens"] == 100
    assert group["output_tokens"] == 30
    assert group["reasoning_tokens"] == 5
    assert group["tool_calls"] == 3
    assert group["cost"] == pytest.approx(0.3)
    assert group["duration_ms"] == 800
    assert group["statuses"] == {"completed": 1, "failed": 1}
    assert usage["summary"]["totals"]["input_tokens"] == 200
    assert usage["summary"]["totals"]["cost"] == pytest.approx(0.8)


def test_usage_derives_duration_and_preserves_missing_cost_as_null():
    collector = ContextResearchTraceCollector("trace-4")
    collector.record_usage({
        "scope": "repair", "model": "luna", "input_tokens": 8,
        "output_tokens": 4, "started_at": "2026-09-01T00:00:00Z",
        "finished_at": "2026-09-01T00:00:01.250Z", "status": "completed",
    })

    record = collector.snapshot()["usage"]["records"][0]
    summary = collector.snapshot()["usage"]["summary"]["groups"][0]
    assert record["duration_ms"] == 1250
    assert record["cost"] is None
    assert summary["missing_cost_calls"] == 1


def test_run_usage_helper_reads_details_and_keeps_unreported_values_missing():
    record = usage_record_from_run_usage(
        RunUsage(
            requests=2,
            input_tokens=100,
            cache_write_tokens=12,
            cache_read_tokens=20,
            output_tokens=30,
            details={"reasoning_tokens": 7},
        ),
        scope="lead",
        model="luna",
    )

    assert record.requests == 2
    assert record.input_tokens == 100
    assert record.cache_write_tokens == 12
    assert record.cache_read_tokens == 20
    assert record.output_tokens == 30
    assert record.reasoning_tokens == 7
    assert record.tool_calls is None
    assert record.cost is None


def test_message_history_helper_extracts_plans_and_compacts_tool_results():
    history = [
        ModelResponse(parts=[ToolCallPart(
            tool_name="write_plan",
            args={"plan": ["Inspect corpus"], "api_key": "do-not-persist"},
            tool_call_id="call-1",
        )], model_name="luna"),
        ModelRequest(parts=[ToolReturnPart(
            tool_name="read_corpus",
            content={"rows": "corpus " * 1000, "truncated": True},
            tool_call_id="call-2",
        )]),
    ]

    trace = extract_message_history_trace(history, result_max_chars=100)

    assert len(trace["planning"]) == 1
    assert trace["planning"][0]["tool"] == "write_plan"
    assert trace["planning"][0]["arguments"]["api_key"] == "[REDACTED]"
    assert trace["tool_activity"][0]["kind"] == "call"
    result = trace["tool_activity"][1]["result"]
    assert set(result) == {"sha256", "char_count", "truncated"}
    assert len(result["sha256"]) == 64
    assert result["truncated"] is True
    assert "corpus" not in str(trace["tool_activity"][1]["result"])


def test_collector_can_append_message_history_trace():
    collector = ContextResearchTraceCollector("trace-history")
    trace = collector.record_message_history([
        ModelResponse(parts=[ToolCallPart(
            tool_name="update_task_status",
            args={"task_id": "step-1", "status": "completed"},
        )], model_name="luna"),
    ])

    snapshot = collector.snapshot()
    assert trace["planning"][0]["tool"] == "update_task_status"
    assert snapshot["planning_events"][0]["tool"] == "update_task_status"
    assert snapshot["tool_activity"][0]["kind"] == "call"


def test_sensitive_values_are_redacted_in_trace_payloads():
    collector = ContextResearchTraceCollector("trace-5")
    collector.record_tool_activity(
        tool="provider_call",
        status="completed",
        metadata={
            "headers": {"Authorization": "Bearer should-not-persist"},
            "api_key": "sk-should-not-persist",
            "safe_count": 2,
        },
    )
    snapshot = collector.snapshot()
    metadata = snapshot["tool_activity"][0]["metadata"]
    assert metadata["headers"]["Authorization"] == "[REDACTED]"
    assert metadata["api_key"] == "[REDACTED]"
    assert metadata["safe_count"] == 2
    assert "should-not-persist" not in json.dumps(snapshot, ensure_ascii=False)


def test_error_trace_records_stage_and_redacts_message():
    collector = ContextResearchTraceCollector("trace-error")
    collector.record_error(
        RuntimeError("UsageLimitExceeded: api_key=sk-private authorization=Bearer-private"),
        stage="subagent",
        role="archive_lore",
        shard="archive_lore-1",
    )

    error = collector.snapshot()["errors"][0]
    assert error["stage"] == "subagent"
    assert error["role"] == "archive_lore"
    assert error["error_type"] == "RuntimeError"
    assert "sk-private" not in error["message"]
    assert "Bearer-private" not in error["message"]
    assert "[REDACTED]" in error["message"]


def test_persist_is_utf8_and_atomic_target_contains_complete_json(tmp_path):
    path = tmp_path / "trace" / "research.json"
    collector = ContextResearchTraceCollector("trace-6", project_id="玲珑")
    collector.record_plan({"summary": "中文档案计划"})

    persisted = collector.persist(path)

    assert persisted == path
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["project_id"] == "玲珑"
    assert payload["plan"]["content"]["summary"] == "中文档案计划"
    assert not list(path.parent.glob(f".{path.name}.*.tmp"))
