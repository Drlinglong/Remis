"""Restartable new-output apply; file, archive and registration stay separate."""
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
import uuid
from contextlib import nullcontext
import json

from .batch_apply_archive import apply_archive, before_values, ensure_source_version
from .batch_artifacts import digest_file, fingerprint
from .batch_rendering import render_outputs
from .batch_repository import BatchConflict
from .batch_sources import language_configuration, require_current_sources


class BatchApplyService:
    def __init__(self, repository, artifacts, manager, archive, output_root, project_guard=None):
        self.repository, self.artifacts = repository, artifacts
        self.manager, self.archive = manager, archive
        self.output_root = Path(output_root).resolve()
        self.project_guard = project_guard or (lambda project_id: nullcontext())

    async def plan(self, job, plan, snapshot, collection, selected=None):
        await require_current_sources(self.manager, snapshot)
        selected = list(collection["complete_file_ids"] if selected is None else selected)
        if not selected or len(set(selected)) != len(selected) or not set(selected).issubset(collection["complete_file_ids"]):
            raise BatchConflict("incomplete_file_selection", "Apply only resources with every eligible entry validated.")
        identity = "apply_" + fingerprint([job["id"], plan["fingerprint"], sorted(selected), fingerprint(collection)])[:24]
        try:
            return self.repository.get(identity, "apply")
        except BatchConflict as exc:
            if exc.status != 404:
                raise
        settings = plan["settings"]
        outputs = render_outputs(snapshot, selected, collection["translations"],
                                 language_configuration(settings["target_locale"], settings.get("game_language_slot")))
        if ".remis-batch-output.json" in outputs:
            raise BatchConflict("reserved_output_path", "A resource uses the reserved batch manifest name.")
        hashes = {path: hashlib.sha256(content.encode("utf-8")).hexdigest() for path, content in outputs.items()}
        journal = {"id": identity, "project_id": job["project_id"], "job_id": job["id"],
            "plan_id": plan["id"], "source_artifact": plan["source_artifact"],
            "collection_artifact": job["collection_artifact"], "outputs_artifact": self.artifacts.put(outputs),
            "file_ids": selected, "target_locale": settings["target_locale"],
            "game_language_slot": settings.get("game_language_slot"), "file_hashes": hashes,
            "final_parent": str(self.output_root / identity),
            "archive_before": before_values(self.archive, snapshot, selected, settings["target_locale"]),
            "archive_version_id": None, "stage": "planned", "fingerprint": fingerprint([plan["fingerprint"], selected, hashes])}
        if Path(journal["final_parent"]).exists():
            raise BatchConflict("target_already_exists", "New batch outputs must not overwrite an existing directory.")
        return self.repository.put("apply", journal)

    def verify_files(self, journal):
        parent = Path(journal["final_parent"])
        root = parent / journal["target_locale"]
        if parent.is_symlink() or parent.parent.resolve() != self.output_root or not root.is_dir() or root.resolve() != root or any(path.is_symlink() or not path.resolve().is_relative_to(root) for path in root.rglob("*")):
            raise BatchConflict("output_integrity_conflict", "The managed output path changed.")
        manifest_path = parent / ".remis-batch-output.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise BatchConflict("output_integrity_conflict", "The managed output manifest is missing or invalid.") from None
        if manifest_path.is_symlink() or manifest != self.manifest(journal):
            raise BatchConflict("output_integrity_conflict", "The managed output manifest changed.")
        actual = {path.relative_to(root).as_posix(): digest_file(path) for path in root.rglob("*") if path.is_file()}
        if actual != journal["file_hashes"]:
            raise BatchConflict("output_integrity_conflict", "An output resource changed after apply began.")
        return root

    @staticmethod
    def manifest(journal):
        return {key: journal[key] for key in ("id", "project_id", "job_id", "source_artifact", "collection_artifact", "target_locale", "game_language_slot", "file_hashes")}

    def publish_files(self, journal):
        parent = Path(journal["final_parent"])
        if parent.exists():
            return self.verify_files(journal)
        self.output_root.mkdir(parents=True, exist_ok=True)
        if parent.parent.resolve() != self.output_root:
            raise BatchConflict("unsafe_output_root", "The managed output root changed.")
        stage = Path(tempfile.mkdtemp(dir=self.output_root, prefix=".batch-"))
        try:
            root = stage / journal["target_locale"]
            root.mkdir()
            for relative, content in self.artifacts.get(journal["outputs_artifact"]).items():
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("x", encoding="utf-8", newline="") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
            manifest = self.manifest(journal)
            with (stage / ".remis-batch-output.json").open("x", encoding="utf-8") as stream:
                from .batch_repository import encode
                stream.write(encode(manifest))
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.rename(stage, parent)
            except FileExistsError:
                pass  # Another caller must have produced exactly the same hashes.
            return self.verify_files(journal)
        finally:
            if stage.exists() and stage.resolve().is_relative_to(self.output_root) and stage.name.startswith(".batch-"):
                shutil.rmtree(stage)

    async def apply(self, job, journal, approved):
        if not approved:
            raise BatchConflict("approval_required", "Applying translations requires explicit authorization.")
        if journal["job_id"] != job["id"]:
            raise BatchConflict("apply_plan_mismatch", "Apply plan belongs to another job.")
        if job["apply_status"] == "applied" and job.get("apply_plan_id") == journal["id"]:
            self.verify_files(journal)
            return job
        with self.project_guard(job["project_id"]):
            return await self._apply(job, self.repository.get(journal["id"], "apply"))

    async def _apply(self, job, journal):
        snapshot = self.artifacts.get(journal["source_artifact"])
        await require_current_sources(self.manager, snapshot)
        self.repository.claim_apply(job["id"], journal["id"])
        try:
            self.repository.update(journal["id"], {"stage": "publishing"})
            root = self.publish_files(journal)
            await require_current_sources(self.manager, snapshot)
            if journal["archive_version_id"] is None:
                journal = self.repository.update(journal["id"], {"archive_version_id": ensure_source_version(self.archive, snapshot)})
            collection = self.artifacts.get(journal["collection_artifact"])
            count = apply_archive(self.archive, snapshot, journal, collection["translations"])
            self.repository.update(journal["id"], {"stage": "archive_committed", "archived_entries": count})
            await self.manager.add_translation_path(job["project_id"], str(root))
            await require_current_sources(self.manager, snapshot)
            found = {str(Path(row["file_path"]).resolve()) for row in await self.manager.get_project_files(job["project_id"])}
            if not {str((root / relative).resolve()) for relative in journal["file_hashes"]}.issubset(found):
                raise BatchConflict("output_registration_failed", "Not every translated resource was registered.")
            self.verify_files(journal)
            self.repository.update(journal["id"], {"stage": "completed"})
            return self.repository.update(job["id"], {"apply_status": "applied", "output_paths": [str(root)], "archived_entries": count})
        except Exception:
            self.repository.update(job["id"], {"apply_status": "recovery_required"})
            raise
