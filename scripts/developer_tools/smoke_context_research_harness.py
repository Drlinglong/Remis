"""Smoke the developer-only Context Research Harness.

The default corpus remains a tiny synthetic fixture for quick local checks.
``--source-root`` switches to a real, read-only localization snapshot.  The
runner can construct either the local LM Studio model or a Remis-configured
OpenRouter model; ``--dry-run`` validates parsing and provider wiring without
making a model request.  It never writes archive state or publishes results.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import sys
import time
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from scripts.core.copilot.help_agent_models import build_help_model
from scripts.core.copilot.runtime import resolve_provider_runtime_snapshot
from scripts.core.neologism_extraction import SourceItem
from scripts.core.services.context_research_contract import (
    AgentExecutionContext,
    ContextAnalysisRequest,
)
from scripts.core.services.context_research_corpus_tools import (
    CorpusToolLimits,
    CorpusSourceItem,
    InMemoryCorpus,
    ReadOnlyRemisCorpusTools,
)
from scripts.core.services.context_research_harness_backend import (
    PydanticAIContextResearchBackend,
)
from scripts.core.services.context_research_external_context import load_external_context
from scripts.core.services.context_source_parser import ContextSourceParser


@dataclass
class _Events:
    values: list[dict[str, Any]] = field(default_factory=list)

    def emit(self, event: str, payload: dict[str, Any] | None = None) -> None:
        self.values.append({"event": event, "payload": payload or {}})


@dataclass
class _Usage:
    values: list[dict[str, Any]] = field(default_factory=list)

    def record(self, event: str, **metadata: Any) -> None:
        self.values.append({"event": event, **metadata})


class _NeverCancelled:
    def is_cancelled(self) -> bool:
        return False


def _corpus() -> tuple[CorpusSourceItem, ...]:
    """Return the original synthetic corpus used by the developer smoke test."""

    return (
        CorpusSourceItem(
            "source-1",
            "The Verdant Order begins a pilgrimage after its oracle reports a poisoned star.",
            path="events/pilgrimage.yml",
            key="verdant_order.1.desc",
        ),
        CorpusSourceItem(
            "source-2",
            "At Meridian Gate the knights recover a cracked reliquary and lose their guide.",
            path="events/pilgrimage.yml",
            key="verdant_order.2.desc",
        ),
        CorpusSourceItem(
            "source-3",
            "The recovered reliquary reveals the next destination beneath the toxic moon.",
            path="events/pilgrimage.yml",
            key="verdant_order.3.desc",
        ),
        CorpusSourceItem(
            "source-4",
            "The Verdant Order was founded centuries earlier to catalogue dangerous relics.",
            path="lore/order.yml",
            key="verdant_order_origin_desc",
        ),
        CorpusSourceItem(
            "source-5",
            "MERIDIAN_GATE_NAME: Meridian Gate",
            path="localization/places.yml",
            key="MERIDIAN_GATE_NAME",
        ),
    )


def _source_files(source_root: Path) -> tuple[Path, ...]:
    """Find parseable localization files below a caller-owned source root."""

    suffixes = {".csv", ".json", ".yaml", ".yml"}
    return tuple(sorted(
        path for path in source_root.rglob("*")
        if path.is_file() and path.suffix.lower() in suffixes
    ))


def _load_source_root(source_root: str) -> tuple[tuple[SourceItem, ...], tuple[CorpusSourceItem, ...], dict[str, Any]]:
    """Parse a UTF-8 localization tree into request and read-only corpus items."""

    target = Path(source_root).resolve(strict=True)
    root = target.parent if target.is_file() else target
    if not target.is_file() and not target.is_dir():
        raise ValueError(f"--source-root must be a file or directory: {target}")
    paths = (target,) if target.is_file() else _source_files(target)
    if not paths:
        raise ValueError(f"--source-root contains no .yml/.yaml/.json/.csv files: {target}")
    parsed_files = ContextSourceParser().parse_files((str(path) for path in paths), str(root))
    source_items = tuple(item for parsed in parsed_files for item in parsed.items)
    corpus_items = tuple(
        CorpusSourceItem(
            item.source_item_id,
            item.source_text,
            path=item.relative_path,
            key=item.item_key or "",
            metadata={
                "source_order": item.source_order,
                "duplicate_key_ordinal": item.duplicate_key_ordinal,
                "provenance": item.provenance,
            },
        )
        for item in source_items
    )
    manifest = {
        "root": str(target),
        "file_count": len(parsed_files),
        "item_count": len(source_items),
        "files": [
            {
                "relative_path": parsed.relative_path,
                "item_count": len(parsed.items),
                "parse_summary": parsed.parse_summary,
            }
            for parsed in parsed_files
        ],
    }
    return source_items, corpus_items, manifest


def _build_models(
    arguments: argparse.Namespace,
) -> tuple[Any, Any, Any | None, str, str]:
    """Build role models while keeping provider secrets in memory only."""

    lead_model_id = arguments.lead_model or arguments.model
    subagent_model_id = arguments.subagent_model or arguments.model

    if arguments.provider == "openrouter":
        runtime = resolve_provider_runtime_snapshot("openrouter", lead_model_id)
        lead_model, _, selected_lead = build_help_model(
            "openrouter",
            lead_model_id,
            {},
            provider_runtime=runtime,
        )
        subagent_runtime = resolve_provider_runtime_snapshot(
            "openrouter", subagent_model_id,
        )
        subagent_model, _, selected_subagent = build_help_model(
            "openrouter",
            subagent_model_id,
            {},
            provider_runtime=subagent_runtime,
        )
        return lead_model, subagent_model, runtime, selected_lead, selected_subagent

    provider = OpenAIProvider(
        base_url=arguments.base_url.rstrip("/") + "/",
        api_key="local-no-key-required",
    )
    lead_model = OpenAIChatModel(lead_model_id, provider=provider)
    subagent_model = OpenAIChatModel(subagent_model_id, provider=provider)
    return lead_model, subagent_model, None, lead_model_id, subagent_model_id


def _reasoning_settings(effort: str | None) -> dict[str, Any] | None:
    if effort is None:
        return None
    return {
        "extra_body": {
            "reasoning": {"effort": effort, "exclude": True},
        },
    }


def _request_and_corpus(arguments: argparse.Namespace) -> tuple[
    ContextAnalysisRequest, ReadOnlyRemisCorpusTools, dict[str, Any]
]:
    if arguments.source_root:
        source_items, corpus_items, manifest = _load_source_root(arguments.source_root)
        project_id = arguments.project_id or "context-research-source-root"
        game_name = arguments.game_name or "Paradox Mod"
    else:
        corpus_items = _corpus()
        source_items = tuple(
            SourceItem(
                source_item_id=item.source_item_id,
                relative_path=item.path or "synthetic/source.txt",
                item_key=item.key or None,
                source_order=index,
                source_text=item.text,
            )
            for index, item in enumerate(corpus_items)
        )
        project_id = arguments.project_id or "context-research-smoke"
        game_name = arguments.game_name or "Synthetic Paradox Mod"
        manifest = {
            "root": None,
            "file_count": len({item.path for item in corpus_items}),
            "item_count": len(source_items),
            "synthetic": True,
        }
    external_context = load_external_context(
        arguments.source_root,
        arguments.game_id,
        arguments.workshop_item_id,
    ) if arguments.source_root or arguments.workshop_item_id else None
    request = ContextAnalysisRequest(
        request_id=arguments.request_id,
        project_id=project_id,
        game_id=arguments.game_id,
        research_question=(
            "Classify every local unit by content_role (event_narrative, "
            "background_narrative, static_reference, or utility_or_noise) and independently "
            "by delivery_route (event, reference, or none). Build entity_mentions from every "
            "content role for plot-central or materially recurring people, organizations, "
            "places, polities, technologies, concepts, and items, then link concrete event "
            "steps to the aggregated entities. Treat repeated dot-number, "
            "dot-letter, or other suffix "
            "families as structural hints, confirm membership against text, and cite "
            "source_item_id evidence for every published item."
        ),
        source_items=source_items,
        game_name=game_name,
        target_language=arguments.target_language,
        reasoning_language=arguments.reasoning_language,
        description_language=arguments.description_language,
        source_root=arguments.source_root,
        workshop_item_id=arguments.workshop_item_id,
        external_context=external_context,
    )
    large_corpus = len(source_items) > 64
    tool_limits = CorpusToolLimits(
        max_items=12,
        max_item_chars=4000 if large_corpus else 1200,
        max_total_chars=24000 if large_corpus else 8000,
    )
    manifest["tool_profile"] = "large" if large_corpus else "standard"
    manifest["local_unit_count"] = len(request.local_units)
    return (
        request,
        ReadOnlyRemisCorpusTools(InMemoryCorpus(corpus_items), tool_limits),
        manifest,
    )


async def _run(arguments: argparse.Namespace) -> dict[str, Any]:
    request, tools, source_manifest = _request_and_corpus(arguments)
    lead_model, subagent_model, runtime, selected_lead, selected_subagent = (
        _build_models(arguments)
    )
    metadata: dict[str, Any] = {
        "provider": arguments.provider,
        "model": selected_lead,
        "lead_model": selected_lead,
        "subagent_model": selected_subagent,
        "lead_reasoning_effort": arguments.lead_reasoning_effort,
        "subagent_reasoning_effort": arguments.subagent_reasoning_effort,
        "request_id": request.request_id,
        "project_id": request.project_id,
        "game_name": request.game_name,
        "description_language": request.description_language,
        "reasoning_language": request.reasoning_language,
        "source_root": source_manifest["root"],
        "dry_run": bool(arguments.dry_run),
        "external_context": (
            request.external_context.model_dump(mode="json")
            if request.external_context else None
        ),
    }
    if runtime is not None:
        # safe_metadata deliberately omits api_key; do not serialize runtime itself.
        metadata["provider_runtime"] = runtime.safe_metadata()
    events, usage = _Events(), _Usage()
    draft = None
    trace_output = arguments.trace_output
    if not trace_output and arguments.output:
        output_path = Path(arguments.output)
        trace_output = str(output_path.with_name(f"{output_path.stem}.trace.json"))
    trace_summary = None
    elapsed_seconds = 0.0
    if not arguments.dry_run:
        backend = PydanticAIContextResearchBackend(
            corpus_tools=tools,
            lead_model=lead_model,
            subagent_model=subagent_model,
            lead_model_settings=_reasoning_settings(arguments.lead_reasoning_effort),
            subagent_model_settings=_reasoning_settings(
                arguments.subagent_reasoning_effort,
            ),
            trace_output_path=trace_output,
        )
        started_at = time.perf_counter()
        try:
            draft = await asyncio.wait_for(
                backend.analyze(
                    request,
                    AgentExecutionContext(
                        provider_selection_id=arguments.provider,
                    model_id=selected_lead,
                        provider_runtime=runtime,
                        cancellation=_NeverCancelled(),
                        events=events,
                        usage=usage,
                    ),
                ),
                timeout=arguments.timeout_seconds,
            )
        finally:
            elapsed_seconds = time.perf_counter() - started_at
        trace = backend.last_trace_snapshot or {}
        corpus_read = dict(trace.get("corpus_read") or {})
        corpus_read.pop("observations", None)
        trace_summary = {
            "trace_output": trace_output,
            "delegations": [
                {
                    key: item.get(key)
                    for key in ("delegation_id", "role", "shard", "status", "model")
                }
                for item in trace.get("delegations", ())
            ],
            "usage": trace.get("usage", {}).get("summary", {}),
            "corpus_read_amplification": corpus_read,
            "repair_attempt_count": len(trace.get("repair", {}).get("attempts", ())),
            "adjudication": {
                "status": trace.get("adjudication", {}).get("status"),
                "candidate_count": trace.get("adjudication", {})
                .get("packet", {}).get("candidate_count", 0),
                "eligible_candidate_count": trace.get("adjudication", {})
                .get("packet", {}).get("eligible_candidate_count", 0),
                "accepted_edge_count": trace.get("adjudication", {})
                .get("output", {}).get("diagnostics", {}).get("accepted_edge_count", 0),
                "rejected_edge_count": trace.get("adjudication", {})
                .get("output", {}).get("diagnostics", {}).get("rejected_edge_count", 0),
                "usage": next(
                    (
                        {
                            "model": item.get("model"),
                            "requests": item.get("requests", 0),
                            "output_tokens": item.get("output_tokens", 0),
                            "cost": item.get("cost"),
                        }
                        for item in trace.get("usage", {}).get("records", ())
                        if item.get("scope") == "adjudication"
                    ),
                    None,
                ),
            },
        }
    draft_json = draft.model_dump(mode="json") if draft is not None else None
    event_json = [event.model_dump(mode="json") for event in draft.event_chains] if draft else []
    return {
        "project": {
            "project_id": request.project_id,
            "name": arguments.project_name or request.project_id,
            "game_name": request.game_name,
            "research_question": request.research_question,
        },
        "release": {
            "release_id": arguments.release_id or request.request_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "read_only": True,
            "published": False,
        },
        "provenance": {
            "provider": arguments.provider,
            "model": selected_lead,
            "lead_model": selected_lead,
            "subagent_model": selected_subagent,
            "lead_reasoning_effort": arguments.lead_reasoning_effort,
            "subagent_reasoning_effort": arguments.subagent_reasoning_effort,
            "profile": "full",
            "description_language": request.description_language,
            "compiler": "context-research-compiler-v2",
            "event_adjudication": "context-research-event-adjudication-v1",
            "source": "developer-only context research smoke",
        },
        "source": source_manifest,
        "source_items": [
            {
                "source_item_id": item.source_item_id,
                "path": item.relative_path,
                "key": item.item_key,
                "text": item.source_text,
            }
            for item in request.source_items
        ],
        "draft": draft_json,
        "events": event_json,
        "external_context": (
            request.external_context.model_dump(mode="json")
            if request.external_context else None
        ),
        "usage": usage.values,
        "trace": trace_summary,
        "corpus_read_amplification": (
            (trace_summary or {}).get("corpus_read_amplification")
            if trace_summary is not None else None
        ),
        "metadata": metadata,
        "execution": {
            "elapsed_seconds": elapsed_seconds,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("lm_studio", "openrouter"), default="lm_studio")
    parser.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    parser.add_argument("--model", required=True)
    parser.add_argument("--lead-model")
    parser.add_argument("--subagent-model")
    reasoning_choices = ("none", "low", "medium", "high", "xhigh", "max")
    parser.add_argument("--lead-reasoning-effort", choices=reasoning_choices)
    parser.add_argument("--subagent-reasoning-effort", choices=reasoning_choices)
    parser.add_argument(
        "--source-root", help="Read-only localization file or directory to parse as UTF-8",
    )
    parser.add_argument("--project-id", default=None)
    parser.add_argument("--project-name", default=None)
    parser.add_argument("--release-id", default=None)
    parser.add_argument("--game-name", default=None)
    parser.add_argument("--game-id", default="", help="Game profile ID used to locate metadata")
    parser.add_argument("--target-language", default="Chinese")
    parser.add_argument("--reasoning-language", default="Chinese")
    parser.add_argument("--description-language", default="zh-CN")
    parser.add_argument(
        "--workshop-item-id", default=None,
        help="Optional numeric Steam Workshop published-file ID",
    )
    parser.add_argument("--request-id", default="context-research-smoke")
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    parser.add_argument("--dry-run", action="store_true", help="Parse/build only; do not call the model")
    parser.add_argument("--output")
    parser.add_argument("--trace-output", help="UTF-8 debug trace ledger output path")
    arguments = parser.parse_args()
    result = asyncio.run(_run(arguments))
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if arguments.output:
        Path(arguments.output).write_text(rendered, encoding="utf-8")
    print(rendered.encode("unicode_escape").decode("ascii"))


if __name__ == "__main__":
    main()
