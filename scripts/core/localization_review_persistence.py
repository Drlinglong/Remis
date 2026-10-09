"""Shared report persistence for ordinary and native Batch review results."""
from scripts.app_settings import GAME_PROFILES_BY_ID
from .game_adapters.registry import get_adapter
from .localization_review_collection import collect_reviews
from .openai_batch_transport import usage_totals


def save_review_results(batch, plan, job_id, remote):
    entries = batch.artifacts.get(plan["entries_artifact"])
    snapshot = batch.artifacts.get(plan["source_artifact"])
    _, terms = batch._terms(plan["settings"], snapshot["game_id"])
    report = collect_reviews(entries, batch.artifacts.get(plan["requests_artifact"]), remote, terms,
                             get_adapter(GAME_PROFILES_BY_ID[snapshot["game_id"]]))
    report.update(source_job_id=plan["translation_job_id"], input_entries_artifact=plan["entries_artifact"],
                  validator_version="localization-quality/v2",
                  term_release_id=plan["settings"].get("term_release_id"), requested_reasoning=plan["settings"]["reasoning"])
    return batch.repository.update(job_id, {"remote_status": remote.get("status", "completed"), "remote_artifact": batch.artifacts.put(remote),
        "report_artifact": batch.artifacts.put(report), "usage": remote.get("usage") or usage_totals(remote.get("results", [])),
        "collection_status": "collected_with_errors" if report["diagnostics"] else "collected"})
