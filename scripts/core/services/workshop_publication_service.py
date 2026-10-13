"""Governed publication orchestration over immutable snapshots and a worker."""
import json
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.core.services.workshop_publication_inputs import digest, file_hash, package_files, reject_links
from scripts.schemas.workshop_publication import PublicationError

TERMINAL = {"succeeded", "failed", "unknown", "legal_agreement_required"}


class WorkshopPublicationService:
    def __init__(self, repository, inputs, adapter, storage_root, projection=None):
        self.repository, self.inputs, self.adapter = repository, inputs, adapter
        self.storage_root = Path(storage_root).absolute()
        self.projection = projection

    def _project_task(self, plan_id):
        if self.projection:
            self.projection.project(self.repository.get(plan_id))

    def recover(self):
        for plan_id in self.repository.recover_interrupted():
            self._project_task(plan_id)

    def public(self, record):
        payload = record["payload"]
        request = payload["request"]
        can_submit = record["status"] == "preview" and payload["runtime"].get("ready") is True
        return {key: value for key, value in {
            "plan_id": record["plan_id"], "task_id": record.get("task_id"),
            "workspace_id": record["workspace_id"], "fingerprint": record["fingerprint"],
            "created_at": record["created_at"], "status": record["status"],
            "target": request, "content_path": payload["content_path"],
            "file_count": len(payload["files"]), "total_bytes": sum(item["size"] for item in payload["files"]),
            "files": payload["files"], "validation": payload["validation"],
            "cover_version_id": payload["cover_version_id"], "description_version_id": payload["description_version_id"],
            "description": payload["description"], "runtime": payload["runtime"],
            "progress": record["progress"], "result": record["result"],
            "requires_approval": record["status"] == "preview",
            "allowed_actions": (["approve_publication"] if can_submit else
                                ["verify_remote_outcome"] if record["status"] in {"unknown", "legal_agreement_required"} else []),
        }.items()}

    def verify_remote(self, workspace_id, plan_id, request):
        record = self.repository.get(plan_id)
        if record["workspace_id"] != workspace_id:
            raise PublicationError("plan_not_found", "Publication plan not found", 404)
        if not request["verified"]:
            raise PublicationError("verification_required", "Confirm you inspected the remote Workshop outcome")
        item_id = request.get("published_file_id")
        if request["resolution"] == "item_present":
            if not item_id or int(item_id) > 2**64 - 1:
                raise PublicationError("invalid_target", "Provide the verified remote item ID")
        elif item_id:
            raise PublicationError("invalid_target", "An absent-item verification must not include an item ID")
        record = self.repository.verify_remote(plan_id, request["resolution"], item_id)
        self._project_task(plan_id)
        return self.public(record)

    def _directory(self, name):
        directory = self.storage_root / name
        directory.mkdir(parents=True, exist_ok=True)
        reject_links(directory)
        return directory

    def plan(self, workspace_id, project, request):
        payload = self.inputs.inspect(workspace_id, project, request)
        probe_dir = self._directory("probe-" + uuid.uuid4().hex)
        payload["runtime"] = self.adapter.probe(request["app_id"], probe_dir, request.get("published_file_id"))
        record = self.repository.save_plan(workspace_id, digest(payload), payload)
        return self.public(record)

    def approve(self, workspace_id, plan_id, project, approved, fingerprint):
        record = self.repository.get(plan_id)
        if record["workspace_id"] != workspace_id:
            raise PublicationError("plan_not_found", "Publication plan not found in this workspace", 404)
        if not approved:
            raise PublicationError("approval_required", "Explicit approval is required before Steam publication")
        if fingerprint != record["fingerprint"]:
            raise PublicationError("approval_identity_mismatch", "Approve the exact preview fingerprint")
        if record["status"] != "preview":
            return self.public(record), False
        if datetime.now(timezone.utc) - datetime.fromisoformat(record["created_at"]) > timedelta(hours=24):
            raise PublicationError("plan_expired", "Create a fresh publication preview")
        current = self.inputs.inspect(workspace_id, project, record["payload"]["request"])
        current["runtime"] = record["payload"]["runtime"]
        if digest(current) != record["fingerprint"]:
            raise PublicationError("stale_plan", "Publication inputs changed. Create and approve a fresh preview")
        if not current["runtime"].get("ready") or not current["runtime"].get("steam_id"):
            raise PublicationError("steam_not_ready", "Configure the Steam SDK and sign in to Steam before previewing again")
        claimed = self.repository.claim(plan_id)
        if claimed:
            try:
                self._project_task(plan_id)
            except Exception as exc:
                self.repository.finish(plan_id, "failed", {"code": "task_persistence_failed"})
                raise PublicationError("task_persistence_failed", "Task storage failed; Steam was not invoked") from exc
        return self.public(self.repository.get(plan_id)), claimed

    def _snapshot(self, plan_id, payload):
        directory = self._directory(plan_id)
        content = directory / "content"
        content.mkdir(exist_ok=False)
        source = Path(payload["content_path"])
        for entry in payload["files"]:
            relative = Path(entry["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise PublicationError("unsafe_snapshot", "Invalid publication manifest")
            original, target = source / relative, content / relative
            reject_links(original)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, target)
            if file_hash(target) != entry["sha256"]:
                raise PublicationError("stale_plan", "Package changed while preparing the immutable upload snapshot")
        if package_files(content) != payload["files"] or package_files(source) != payload["files"]:
            raise PublicationError("stale_plan", "Package changed while preparing the upload snapshot")
        preview = directory / "preview.png"
        reject_links(payload["preview_path"])
        shutil.copyfile(payload["preview_path"], preview)
        if file_hash(preview) != payload["preview_sha256"]:
            raise PublicationError("stale_plan", "Selected cover changed while preparing publication")
        return directory, {**payload["request"], "description": payload["description"],
                           "content_path": str(content), "preview_path": str(preview),
                           "steam_id": payload["runtime"]["steam_id"]}

    def run(self, plan_id):
        record = self.repository.get(plan_id)
        if record["status"] != "running":
            return
        if not self.repository.begin_execution(plan_id):
            return
        remote_started = False
        worker_started = False
        remote_id = record["payload"]["request"].get("published_file_id")

        def event(item):
            nonlocal remote_started, remote_id
            if item["type"] == "remote_started":
                remote_started = True
            if item["type"] == "created":
                remote_id = item.get("published_file_id")
            self.repository.progress(plan_id, {**item, "published_file_id": remote_id})
            self._project_task(plan_id)

        try:
            directory, upload = self._snapshot(plan_id, record["payload"])
            # Persist intent before entering native code. Any process interruption
            # thereafter is uncertain even when no IPC event survives.
            self.repository.progress(plan_id, {"type": "worker_started", "published_file_id": remote_id})
            worker_started = True
            result = self.adapter.publish(upload, directory, event)
            status = result.get("status", "unknown")
            if status not in TERMINAL:
                status = "unknown"
            remote_id = result.get("published_file_id") or remote_id
            valid_id = str(remote_id or "").isdigit() and 0 < int(remote_id) < 2**64
            requested_id = record["payload"]["request"].get("published_file_id")
            if status == "succeeded" and (result.get("eresult") != 1 or not valid_id or
                                           requested_id is not None and str(remote_id) != requested_id):
                status = "unknown"
            result = {key: value for key, value in result.items()
                      if key in {"code", "eresult", "published_file_id", "legal_agreement_required"}}
            result.update({"published_file_id": remote_id, "requires_remote_verification": status == "unknown"})
            if valid_id:
                result["workshop_url"] = f"https://steamcommunity.com/sharedfiles/filedetails/?id={remote_id}"
            self.repository.finish(plan_id, status, result)
            (directory / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        except PublicationError as exc:
            self.repository.finish(plan_id, "failed", {"code": exc.code})
        except Exception:
            self.repository.finish(plan_id, "unknown" if worker_started or remote_started else "failed",
                                   {"code": "publication_interrupted", "published_file_id": remote_id,
                                    "requires_remote_verification": worker_started or remote_started})
        finally:
            self._project_task(plan_id)
