"""Registered source snapshots and existing glossaries own reusable coverage scans."""
import uuid
import time

from .batch_repository import BatchConflict
from .batch_sources import freeze_sources
from .quality_reference import reference_table
from .terminology_coverage import scan_coverage


class TerminologyCoverageService:
    def __init__(self, batch, glossary):
        self.batch, self.glossary = batch, glossary

    async def scan(self, request):
        snapshot = await freeze_sources(self.batch.manager, request)
        await self.glossary.preview(request.glossary_id, request.locale)
        glossary, rows = await self.glossary._read(request.glossary_id)
        if glossary["game_id"] != snapshot["game_id"]:
            raise BatchConflict("glossary_game_conflict", "Choose a glossary for the source game.", 400)
        reference = reference_table(snapshot) if snapshot["adapter_id"] == "surviving_mars_csv" else {}
        report = scan_coverage(snapshot, rows, reference, request.minimum_occurrences, request.example_limit)
        identifier = "coverage_" + uuid.uuid4().hex
        return self.batch.repository.put("coverage", {"id": identifier, "project_id": request.project_id,
            "created_at": time.time(), "settings": request.model_dump(),
            "source_artifact": self.batch.artifacts.put(snapshot),
            "reference_artifact": self.batch.artifacts.put(snapshot),
            "glossary_artifact": self.batch.artifacts.put({"glossary": glossary, "entries": rows}),
            "report_artifact": self.batch.artifacts.put(report),
            "summary": {k: report[k] for k in ["entry_count", "candidate_count", "uncovered_count", "high_priority_uncovered_count"]},
            "paid_calls": 0, "allowed_actions": ["read_report"]})

    def get(self, scan_id):
        record = self.batch.repository.get(scan_id, "coverage")
        return {**record, "report": self.batch.artifacts.get(record["report_artifact"])}

    def artifact(self, scan_id, kind):
        record = self.batch.repository.get(scan_id, "coverage")
        if kind not in {"source", "reference", "glossary", "report"}:
            raise BatchConflict("artifact_unavailable", "Unknown coverage artifact kind.", 404)
        return self.batch.artifacts.get(record[kind + "_artifact"])

    def import_candidates(self, scan_id, request, store):
        from .terminology_candidate_bridge import persist_coverage_candidates
        record = self.get(scan_id)
        if not request.approved:
            raise BatchConflict("approval_required", "Importing pending archive candidates requires authorization.")
        selected = set(request.candidate_ids)
        by_id = {c["candidate_id"]: c for c in record["report"]["candidates"] if c["status"] == "uncovered"}
        if len(selected) != len(request.candidate_ids) or not selected.issubset(by_id):
            raise BatchConflict("invalid_candidate_selection", "Select unique uncovered candidates from this scan.", 400)
        result = persist_coverage_candidates(store, record["project_id"], [by_id[k] for k in request.candidate_ids],
            self.batch.artifacts.get(record["source_artifact"]), record["settings"]["locale"])
        return {"scan_id": scan_id, "project_id": record["project_id"], **result,
                "store": "existing_project_archive_candidates", "glossary_modified": False}
