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
    CorpusSourceItem,
    InMemoryCorpus,
    ReadOnlyRemisCorpusTools,
)
from scripts.core.services.context_research_harness_backend import (
    PydanticAIContextResearchBackend,
)
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

    root = Path(source_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"--source-root must be a directory: {root}")
    paths = _source_files(root)
    if not paths:
        raise ValueError(f"--source-root contains no .yml/.yaml/.json/.csv files: {root}")
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
        "root": str(root),
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


def _build_model(arguments: argparse.Namespace) -> tuple[Any, Any | None, str]:
    """Build the selected model while keeping provider secrets in memory only."""

    if arguments.provider == "openrouter":
        runtime = resolve_provider_runtime_snapshot("openrouter", arguments.model)
        model, _, selected_model = build_help_model(
            "openrouter",
            arguments.model,
            {},
            provider_runtime=runtime,
        )
        return model, runtime, selected_model

    provider = OpenAIProvider(
        base_url=arguments.base_url.rstrip("/") + "/",
        api_key="local-no-key-required",
    )
    model = OpenAIChatModel(arguments.model, provider=provider)
    return model, None, arguments.model


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
    request = ContextAnalysisRequest(
        request_id=arguments.request_id,
        project_id=project_id,
        research_question=(
            "Separate concrete event chains from archive-only founding lore and static "
            "reference assets. Build an evidence-backed register of plot-central named "
            "people, organizations, places, polities, technologies, concepts, and items, "
            "then link concrete event steps to those entities. Treat repeated dot-number, "
            "dot-letter, or other suffix "
            "families as structural hints, confirm membership against text, and cite "
            "source_item_id evidence for every published item."
        ),
        source_items=source_items,
        game_name=game_name,
        target_language=arguments.target_language,
        reasoning_language=arguments.reasoning_language,
        description_language=arguments.description_language,
    )
    return request, ReadOnlyRemisCorpusTools(InMemoryCorpus(corpus_items)), manifest


async def _run(arguments: argparse.Namespace) -> dict[str, Any]:
    request, tools, source_manifest = _request_and_corpus(arguments)
    model, runtime, selected_model = _build_model(arguments)
    metadata: dict[str, Any] = {
        "provider": arguments.provider,
        "model": selected_model,
        "request_id": request.request_id,
        "project_id": request.project_id,
        "game_name": request.game_name,
        "description_language": request.description_language,
        "reasoning_language": request.reasoning_language,
        "source_root": source_manifest["root"],
        "dry_run": bool(arguments.dry_run),
    }
    if runtime is not None:
        # safe_metadata deliberately omits api_key; do not serialize runtime itself.
        metadata["provider_runtime"] = runtime.safe_metadata()
    events, usage = _Events(), _Usage()
    draft = None
    if not arguments.dry_run:
        backend = PydanticAIContextResearchBackend(corpus_tools=tools, model=model)
        draft = await asyncio.wait_for(
            backend.analyze(
                request,
                AgentExecutionContext(
                    provider_selection_id=arguments.provider,
                    model_id=selected_model,
                    provider_runtime=runtime,
                    cancellation=_NeverCancelled(),
                    events=events,
                    usage=usage,
                ),
            ),
            timeout=arguments.timeout_seconds,
        )
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
            "model": selected_model,
            "profile": "full",
            "description_language": request.description_language,
            "compiler": "context-research-compiler-v1",
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
        "usage": usage.values,
        "metadata": metadata,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("lm_studio", "openrouter"), default="lm_studio")
    parser.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    parser.add_argument("--model", required=True)
    parser.add_argument("--source-root", help="Read-only localization directory to parse as UTF-8")
    parser.add_argument("--project-id", default=None)
    parser.add_argument("--project-name", default=None)
    parser.add_argument("--release-id", default=None)
    parser.add_argument("--game-name", default=None)
    parser.add_argument("--target-language", default="Chinese")
    parser.add_argument("--reasoning-language", default="Chinese")
    parser.add_argument("--description-language", default="zh-CN")
    parser.add_argument("--request-id", default="context-research-smoke")
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    parser.add_argument("--dry-run", action="store_true", help="Parse/build only; do not call the model")
    parser.add_argument("--output")
    arguments = parser.parse_args()
    result = asyncio.run(_run(arguments))
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if arguments.output:
        Path(arguments.output).write_text(rendered, encoding="utf-8")
    print(rendered.encode("unicode_escape").decode("ascii"))


if __name__ == "__main__":
    main()
