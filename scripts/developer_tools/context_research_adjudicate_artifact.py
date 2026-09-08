"""Run only the low-cost adjudication pass against a saved research artifact.

This developer tool intentionally skips Lead fan-out and translation.  It is a
cheap way to inspect whether a new adjudicator improves a semi-finished result
before spending on a complete Harness rerun.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.core.copilot.help_agent_models import build_help_model
from scripts.core.copilot.runtime import resolve_provider_runtime_snapshot
from scripts.core.neologism_extraction import SourceItem
from scripts.core.services.context_research_contract import ContextAnalysisRequest, ContextResearchDraft
from scripts.core.services.context_research_event_adjudication import (
    apply_event_chain_adjudications,
    build_event_adjudication_packet,
    event_adjudication_prompt,
)
from scripts.core.services.context_research_harness_agent import (
    build_adjudication_agent,
    run_adjudication,
)
from scripts.core.services.context_research_trace_usage import usage_record_from_run_usage


def _load(path: Path) -> tuple[ContextAnalysisRequest, ContextResearchDraft]:
    artifact = json.loads(path.read_text(encoding="utf-8"))
    source_items = tuple(SourceItem(
        source_item_id=item["source_item_id"],
        relative_path=item.get("path") or "unknown/source.txt",
        item_key=item.get("key"),
        source_order=index,
        source_text=item["text"],
    ) for index, item in enumerate(artifact.get("source_items", ())))
    metadata = artifact.get("metadata") or {}
    request = ContextAnalysisRequest(
        request_id=str(metadata.get("request_id") or "adjudication-artifact"),
        project_id=str(metadata.get("project_id") or "adjudication-artifact"),
        game_name=str(metadata.get("game_name") or "Paradox Mod"),
        description_language=str(metadata.get("description_language") or "en"),
        reasoning_language=str(metadata.get("reasoning_language") or "en"),
        source_items=source_items,
    )
    return request, ContextResearchDraft.model_validate(artifact["draft"])


async def _run(arguments: argparse.Namespace) -> dict[str, Any]:
    request, draft = _load(Path(arguments.artifact))
    runtime = resolve_provider_runtime_snapshot("openrouter", arguments.model)
    model, _, selected_model = build_help_model(
        "openrouter", arguments.model, {}, provider_runtime=runtime,
    )
    agent = build_adjudication_agent(model=model)
    packet = build_event_adjudication_packet(
        draft.event_chains,
        request.local_units,
        draft.diagnostics.get("compiler", {}).get("chain_consolidation", {}),
    )
    result = await run_adjudication(
        agent, event_adjudication_prompt(packet, request.description_language),
    )
    adjudicated_events, diagnostics = apply_event_chain_adjudications(
        draft.event_chains, result.output, packet, request.local_units,
    )
    updated_compiler = dict(draft.diagnostics.get("compiler", {}) or {})
    updated_compiler["adjudication"] = diagnostics
    updated_diagnostics = dict(draft.diagnostics)
    updated_diagnostics["compiler"] = updated_compiler
    updated_draft = draft.model_copy(update={
        "event_chains": adjudicated_events,
        "diagnostics": updated_diagnostics,
    })
    usage = result.usage() if callable(result.usage) else result.usage
    usage_record = usage_record_from_run_usage(
        usage, scope="adjudication", model=selected_model,
    ).to_dict()
    return {
        "provenance": {
            "provider": "openrouter",
            "model": selected_model,
            "source_artifact": str(Path(arguments.artifact).resolve()),
            "mode": "artifact-only-adjudication",
        },
        "packet_summary": {
            "candidate_count": packet["candidate_count"],
            "eligible_candidate_count": packet["eligible_candidate_count"],
            "hard_rejected_candidate_count": packet["hard_rejected_candidate_count"],
        },
        "adjudication": diagnostics,
        "usage": usage_record,
        "draft": updated_draft.model_dump(mode="json"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", default="openai/gpt-5.6-luna")
    arguments = parser.parse_args()
    result = asyncio.run(_run(arguments))
    Path(arguments.output).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps({
        "output": str(Path(arguments.output).resolve()),
        "candidate_count": result["packet_summary"]["candidate_count"],
        "accepted_edge_count": result["adjudication"].get("accepted_edge_count", 0),
        "cost": result["usage"].get("cost"),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
