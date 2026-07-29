"""Run a small real-provider Model Arena smoke test.

The caller must inject provider credentials through the process environment.
This tool never reads, prints, or writes credential values.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sqlite3
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.core.db_migrations import migrate_main_database
from scripts.core.repositories.model_arena_repository import ModelArenaRepository
from scripts.core.services.model_arena_service import ModelArenaService
from scripts.schemas.model_arena import (
    CreateModelArenaRunRequest,
    ModelArenaContestantSelection,
    ModelArenaVoteRequest,
)


class _SmokeProjectManager:
    def __init__(self, source_root: Path) -> None:
        self.source_root = source_root.resolve()

    async def get_project(self, project_id: str):
        return {
            "project_id": project_id,
            "name": self.source_root.name,
            "game_id": "victoria3",
            "source_language": "zh-CN",
            "source_path": str(self.source_root),
        }

    async def get_project_files(self, project_id: str):
        return [
            {"file_path": str(path), "file_type": "source"}
            for path in sorted(self.source_root.rglob("*"))
            if path.is_file()
            and path.suffix.lower() in {".yml", ".yaml"}
            and not any(part.startswith(".") for part in path.relative_to(self.source_root).parts)
        ]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--db-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=3)
    parser.add_argument("--seed", default="remis-real-smoke-v1")
    parser.add_argument("--local-model", default="google/gemma-4-31b-qat")
    parser.add_argument("--cloud-model", default="deepseek-v4-pro")
    return parser.parse_args()


def _initialize_database(db_path: Path, source_root: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    migrate_main_database(str(db_path))
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO projects (
                project_id, name, game_id, source_path, source_language, status
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "model-arena-real-smoke",
                source_root.name,
                "victoria3",
                str(source_root.resolve()),
                "zh-CN",
                "active",
            ),
        )


def main() -> int:
    args = _parse_args()
    source_root = args.source_root.resolve()
    if not source_root.is_dir():
        raise SystemExit("source root does not exist")
    _initialize_database(args.db_path, source_root)
    service = ModelArenaService(
        repository=ModelArenaRepository(str(args.db_path)),
        project_manager=_SmokeProjectManager(source_root),
    )
    draft = asyncio.run(
        service.create_run(
            CreateModelArenaRunRequest(
                project_id="model-arena-real-smoke",
                target_lang_code="en",
                sample_size=args.sample_size,
                sample_seed=args.seed,
                use_project_glossaries=False,
                use_mod_context=True,
                contestants=[
                    ModelArenaContestantSelection(
                        provider_id="lm_studio",
                        model_id=args.local_model,
                    ),
                    ModelArenaContestantSelection(
                        provider_id="deepseek",
                        model_id=args.cloud_model,
                    ),
                ],
            )
        )
    )
    service.prepare_start(
        draft["run_id"],
        idempotency_key=f"smoke:{args.seed}",
        task_id=f"smoke:{draft['run_id']}",
    )
    service.execute_run(draft["run_id"])
    run = service.repository.get_run(draft["run_id"])
    if run and run["status"] in {"voting", "partial_failed"}:
        outputs_by_sample: dict[str, list[dict]] = {}
        for output in run["outputs"]:
            outputs_by_sample.setdefault(output["sample_id"], []).append(output)
        for sample in run["samples"]:
            valid_count = sum(
                bool(output.get("translated_text"))
                for output in outputs_by_sample.get(sample["sample_id"], [])
            )
            service.save_vote(
                run["run_id"],
                sample["sample_id"],
                ModelArenaVoteRequest(
                    verdict="tie" if valid_count >= 2 else "unjudgeable",
                    reason_codes=[],
                    note="Automated technical smoke vote; no quality preference asserted.",
                ),
            )
        service.complete_run(run["run_id"])
        artifact = service.export_preview(run["run_id"], mode="evidence")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(artifact, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    final_run = service.repository.get_run(draft["run_id"]) or {}
    summary = {
        "run_id": draft["run_id"],
        "status": final_run.get("status"),
        "sample_size": final_run.get("sample_size"),
        "artifact_written": args.output.is_file(),
        "contestants": [
            {
                "provider_id": item.get("provider_id"),
                "model_id": item.get("model_id"),
                "status": item.get("status"),
                "request_count": item.get("request_count"),
                "failure_code": item.get("failure_code"),
            }
            for item in final_run.get("contestants", [])
        ],
    }
    print(json.dumps(summary, ensure_ascii=True))
    return 0 if summary["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
