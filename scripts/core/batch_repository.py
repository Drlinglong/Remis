"""Durable, independently versioned ledger for Agent batch workflows."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import time
import uuid


class BatchConflict(ValueError):
    def __init__(self, code, message, status=409):
        super().__init__(message)
        self.code, self.status = code, status


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class BatchRepository:
    """Transactions never span an HTTP request or another database."""
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise BatchConflict("unsupported_batch_schema", "Batch database is newer than this build.")
            db.execute("CREATE TABLE IF NOT EXISTS batch_records (id TEXT PRIMARY KEY, kind TEXT NOT NULL, project_id TEXT NOT NULL, body TEXT NOT NULL, updated REAL NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS batch_intents (project_id TEXT NOT NULL, idempotency_key TEXT NOT NULL, plan_id TEXT NOT NULL UNIQUE, fingerprint TEXT NOT NULL, job_id TEXT NOT NULL UNIQUE, PRIMARY KEY(project_id,idempotency_key))")
            db.execute("CREATE INDEX IF NOT EXISTS ix_batch_records_kind_project ON batch_records(kind,project_id,updated)")
            db.execute("PRAGMA user_version=1")

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _put(db, kind, body):
        db.execute("INSERT INTO batch_records VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body,updated=excluded.updated",
                   (body["id"], kind, body.get("project_id", ""), encode(body), time.time()))

    def put(self, kind, body):
        with self.transaction() as db:
            self._put(db, kind, body)
        return body

    def get(self, identifier, kind=None):
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT kind,body FROM batch_records WHERE id=?", (identifier,)).fetchone()
        if not row or (kind and kind != row[0]):
            raise BatchConflict("batch_record_not_found", "Batch record not found.", 404)
        return json.loads(row[1])

    def update(self, identifier, changes):
        with self.transaction() as db:
            row = db.execute("SELECT kind,body FROM batch_records WHERE id=?", (identifier,)).fetchone()
            if not row:
                raise BatchConflict("batch_record_not_found", "Batch record not found.", 404)
            body = json.loads(row["body"])
            body.update(changes)
            self._put(db, row["kind"], body)
        return body

    def list_jobs(self, project_id=None, limit=50, offset=0, kind="job"):
        query = "SELECT body FROM batch_records WHERE kind=?"
        params = [kind]
        if project_id:
            query += " AND project_id=?"
            params.append(project_id)
        query += " ORDER BY updated DESC,id LIMIT ? OFFSET ?"
        with sqlite3.connect(self.path) as db:
            rows = db.execute(query, [*params, limit, offset]).fetchall()
        return [json.loads(row[0]) for row in rows]

    def reserve(self, plan, key, kind="job"):
        """Only the transaction winner may send the paid create request.

        Intentionally record unknown *before* HTTP: a crash at any following
        instruction cannot make an accepted request eligible for blind retry.
        """
        if kind not in {"job", "review_job", "conversion"}:
            raise BatchConflict("invalid_job_kind", "Unsupported paid workflow kind.", 400)
        with self.transaction() as db:
            row = db.execute("SELECT * FROM batch_intents WHERE project_id=? AND idempotency_key=?",
                             (plan["project_id"], key)).fetchone()
            if row:
                if row["fingerprint"] != plan["fingerprint"]:
                    raise BatchConflict("idempotency_conflict", "The key belongs to a different plan.")
                body = db.execute("SELECT body FROM batch_records WHERE id=?", (row["job_id"],)).fetchone()
                return json.loads(body[0]), False
            if db.execute("SELECT 1 FROM batch_intents WHERE plan_id=?", (plan["id"],)).fetchone():
                raise BatchConflict("plan_already_submitted", "Use the existing job; create a retry plan for failed items.")
            prefix = {"review_job": "review_", "conversion": "conversion_"}.get(kind, "batch_")
            job = {"id": prefix + uuid.uuid4().hex, "project_id": plan["project_id"],
                   "plan_id": plan["id"], "fingerprint": plan["fingerprint"], "created_at": time.time(),
                   "execution_mode": plan.get("execution_mode", plan.get("settings", {}).get("execution_mode", "batch")),
                   "submission_state": "submission_unknown", "remote_status": None,
                   "remote_id": None, "collection_status": "not_collected", "apply_status": "not_applied"}
            db.execute("INSERT INTO batch_intents VALUES (?,?,?,?,?)",
                       (plan["project_id"], key, plan["id"], plan["fingerprint"], job["id"]))
            self._put(db, kind, job)
        return job, True

    def find_intent(self, project_id, key):
        with sqlite3.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM batch_intents WHERE project_id=? AND idempotency_key=?", (project_id, key)).fetchone()
        return dict(row) if row else None

    def update_review_response(self, job_id, custom_id, changes):
        """Merge one response atomically so concurrent polling cannot lose sibling IDs."""
        with self.transaction() as db:
            row = db.execute("SELECT body FROM batch_records WHERE id=? AND kind='review_job'", (job_id,)).fetchone()
            if not row:
                raise BatchConflict("batch_record_not_found", "Review job not found.", 404)
            job = json.loads(row[0])
            records = job.get("response_submissions", {})
            if custom_id not in records:
                raise BatchConflict("unknown_custom_id", "Response is not in the persisted review plan.")
            existing = records[custom_id]
            if existing.get("response_id") and changes.get("response_id", existing["response_id"]) != existing["response_id"]:
                raise BatchConflict("remote_identity_conflict", "A native response ID cannot be replaced.")
            terminal = existing.get("response_status") in {"completed", "failed", "incomplete", "cancelled"}
            if not terminal:
                changes = dict(changes)
                if existing.get("acceptance_artifact"):
                    changes.pop("acceptance_artifact", None)
                existing.update(changes)
                self._put(db, "review_job", job)
        return job

    def claim_apply(self, job_id, apply_plan_id):
        with self.transaction() as db:
            row = db.execute("SELECT body FROM batch_records WHERE id=? AND kind='job'", (job_id,)).fetchone()
            if not row:
                raise BatchConflict("batch_record_not_found", "Batch job not found.", 404)
            job = json.loads(row[0])
            existing = job.get("apply_plan_id")
            if existing and existing != apply_plan_id:
                raise BatchConflict("apply_in_progress", "Recover the existing apply before choosing a new plan.")
            job.update(apply_plan_id=apply_plan_id, apply_status="in_progress")
            self._put(db, "job", job)
        return job
