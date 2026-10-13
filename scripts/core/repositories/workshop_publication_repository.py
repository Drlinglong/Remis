"""Atomic publication admission; a plan is submitted at most once."""
import json
import sqlite3
import uuid
from datetime import datetime, timezone

from scripts.schemas.workshop_publication import PublicationError


def now():
    return datetime.now(timezone.utc).isoformat()


class WorkshopPublicationRepository:
    def __init__(self, db_path):
        self.db_path = str(db_path)

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def save_plan(self, workspace_id, fingerprint, payload):
        plan_id = uuid.uuid4().hex
        with self._connect() as conn:
            conn.execute("INSERT INTO workshop_publication_plans VALUES (?, ?, ?, ?, ?)",
                         (plan_id, workspace_id, fingerprint,
                          json.dumps(payload, ensure_ascii=False), now()))
        return self.get(plan_id)

    @staticmethod
    def _decode(row):
        data = dict(row)
        data["payload"] = json.loads(data.pop("payload_json"))
        data["result"] = json.loads(data.pop("result_json") or "{}")
        data["progress"] = json.loads(data.pop("progress_json") or "{}")
        data["status"] = data.get("status") or "preview"
        return data

    def get(self, plan_id):
        with self._connect() as conn:
            row = conn.execute("""
                SELECT p.*, a.task_id, a.status, a.result_json, a.progress_json,
                       a.started_at, a.finished_at
                FROM workshop_publication_plans p
                LEFT JOIN workshop_publication_attempts a USING(plan_id)
                WHERE p.plan_id = ?
            """, (plan_id,)).fetchone()
        if row is None:
            raise PublicationError("plan_not_found", "Publication plan not found", 404)
        return self._decode(row)

    def list_plans(self, workspace_id):
        with self._connect() as conn:
            ids = [row[0] for row in conn.execute("""
                SELECT plan_id FROM workshop_publication_plans
                WHERE workspace_id = ? ORDER BY created_at DESC LIMIT 50
            """, (workspace_id,))]
        return [self.get(plan_id) for plan_id in ids]

    def claim(self, plan_id):
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute("SELECT 1 FROM workshop_publication_attempts WHERE plan_id = ?",
                                    (plan_id,)).fetchone()
            if existing:
                return False
            if conn.execute("SELECT 1 FROM workshop_publication_attempts WHERE status = 'running'").fetchone():
                raise PublicationError("publication_busy", "Another Steam publication is active")
            # An uncertain CreateItem outcome cannot be retried through a new preview.
            plan = conn.execute("SELECT workspace_id, payload_json FROM workshop_publication_plans WHERE plan_id = ?",
                                (plan_id,)).fetchone()
            uncertain = conn.execute("""
                SELECT 1 FROM workshop_publication_attempts a
                JOIN workshop_publication_plans p USING(plan_id)
                WHERE p.workspace_id = ? AND a.status IN ('unknown', 'legal_agreement_required')
            """, (plan[0],)).fetchone()
            if uncertain:
                raise PublicationError("remote_verification_required",
                                       "Verify the previous Workshop outcome before another publication")
            self._guard_recovered_item(conn, plan)
            conn.execute("""
                INSERT INTO workshop_publication_attempts(plan_id, task_id, status, started_at)
                VALUES (?, ?, 'running', ?)
            """, (plan_id, uuid.uuid4().hex, now()))
        return True

    @staticmethod
    def _guard_recovered_item(conn, plan):
        rows = conn.execute("""
            SELECT a.result_json FROM workshop_publication_attempts a
            JOIN workshop_publication_plans p USING(plan_id)
            WHERE p.workspace_id = ? AND a.status = 'resolved'
            ORDER BY a.finished_at DESC
        """, (plan["workspace_id"],)).fetchall()
        present = next((value for row in rows
                        if (value := json.loads(row["result_json"])).get("manual_resolution") == "item_present"), None)
        if not present:
            return
        request = json.loads(plan["payload_json"])["request"]
        if request["mode"] != "update" or request["published_file_id"] != present["published_file_id"]:
            raise PublicationError("recovered_item_requires_update",
                                   "Create an update preview for the manually verified existing item; do not create another item")

    def verify_remote(self, plan_id, resolution, published_file_id):
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT status, result_json FROM workshop_publication_attempts WHERE plan_id = ?", (plan_id,)).fetchone()
            if not row or row["status"] not in {"unknown", "legal_agreement_required"}:
                raise PublicationError("verification_not_applicable", "Only uncertain or legal-agreement outcomes require verification")
            previous = json.loads(row["result_json"])
            known_id = previous.get("published_file_id")
            if resolution == "item_present" and known_id and known_id != published_file_id:
                raise PublicationError("verification_target_mismatch", "Verify the item ID already returned by Steam")
            result = {**previous, "previous_status": row["status"], "verification_source": "user",
                      "manual_resolution": resolution, "verified_at": now(),
                      "published_file_id": published_file_id, "requires_remote_verification": False}
            result.pop("workshop_url", None)
            if published_file_id:
                result["workshop_url"] = f"https://steamcommunity.com/sharedfiles/filedetails/?id={published_file_id}"
            conn.execute("UPDATE workshop_publication_attempts SET status = 'resolved', result_json = ? WHERE plan_id = ?",
                         (json.dumps(result), plan_id))
        return self.get(plan_id)

    def progress(self, plan_id, event):
        with self._connect() as conn:
            conn.execute("UPDATE workshop_publication_attempts SET progress_json = ? WHERE plan_id = ? AND status = 'running'",
                         (json.dumps(event), plan_id))

    def begin_execution(self, plan_id):
        with self._connect() as conn:
            cursor = conn.execute("""
                UPDATE workshop_publication_attempts SET progress_json = '{"type":"preparing_snapshot"}'
                WHERE plan_id = ? AND status = 'running' AND progress_json = '{}'
            """, (plan_id,))
            return cursor.rowcount == 1

    def finish(self, plan_id, status, result):
        with self._connect() as conn:
            conn.execute("""
                UPDATE workshop_publication_attempts SET status = ?, result_json = ?, finished_at = ?
                WHERE plan_id = ? AND status = 'running'
            """, (status, json.dumps(result, ensure_ascii=False), now(), plan_id))

    def recover_interrupted(self):
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute("SELECT plan_id, progress_json FROM workshop_publication_attempts WHERE status = 'running'").fetchall()
            for row in rows:
                remote_id = json.loads(row["progress_json"]).get("published_file_id")
                result = {"code": "backend_restarted", "requires_remote_verification": True,
                          "published_file_id": remote_id}
                if remote_id:
                    result["workshop_url"] = f"https://steamcommunity.com/sharedfiles/filedetails/?id={remote_id}"
                conn.execute("""
                    UPDATE workshop_publication_attempts SET status = 'unknown', result_json = ?, finished_at = ?
                    WHERE plan_id = ? AND status = 'running'
                """, (json.dumps(result), now(), row["plan_id"]))
        return [row["plan_id"] for row in rows]
