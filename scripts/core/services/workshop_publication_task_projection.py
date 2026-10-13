"""Project durable publication outcomes into Remis's existing Task Center."""
from scripts.shared import task_state


class WorkshopPublicationTaskProjection:
    def project(self, record):
        task_id = record.get("task_id")
        if not task_id:
            return
        status = record["status"]
        result = record["result"]
        message = f"Steam Workshop publication: {status}"
        fields = {
            "result": {"types": ["steam_workshop_publication"], "summary": message,
                       "metadata": {"publication_status": status, "plan_id": record["plan_id"], **result}},
        }
        task_status = "completed" if status == "succeeded" else "running" if status == "running" else "failed"
        if task_state.get_task(task_id) is None:
            task_state.create_task(task_id, status=task_status, require_persistence=True, fields={
                **fields, "kind": "steam_workshop_publication", "blocking": False,
                "project_id": record["payload"]["project_id"], "title": "Steam Workshop publication",
                "source_route": f"/steam-workshop/{record['workspace_id']}/publish",
                "created_by": {"type": "user"},
                "idempotency_key": f"workshop-publication:{record['plan_id']}",
            })
        else:
            task_state.update_task(task_id, status=task_status, message=message, fields=fields)
        snapshot = task_state.get_task(task_id)
        if not snapshot or snapshot.get("persistence_failure"):
            raise RuntimeError("Publication Task Center persistence failed")
