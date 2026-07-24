import csv
import hashlib
import json
import logging
import os
import re
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from scripts.app_settings import PROJECT_ROOT
from scripts.core.api_handler import get_handler
from scripts.core.file_parser import extract_translatable_content
from scripts.core.glossary_manager import glossary_manager
from scripts.core.neologism_miner import NeologismMiner
from scripts.shared import task_state


logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(PROJECT_ROOT, "data", "cache", "neologism_candidates")
ACTIVE_STATUSES = {"starting", "running"}
REVIEW_BATCH_SIZE = 20
SAFE_PROJECT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class CandidateStoreError(RuntimeError):
    """Raised when durable candidate state cannot be read or written safely."""


class ContextEvidence(BaseModel):
    snippet: str
    source_file: str
    line: Optional[int] = None


class Candidate(BaseModel):
    id: str
    project_id: str
    original: str
    context_snippets: List[str]
    suggestion: str
    reasoning: str
    status: Literal["pending", "approved", "ignored", "duplicate", "new_meaning"] = "pending"
    source_file: Optional[str] = None
    source_files: List[str] = Field(default_factory=list)
    context_evidence: List[ContextEvidence] = Field(default_factory=list)
    source_lang: str = "en"
    target_lang: str = "zh-CN"
    review_language: str = "en"
    duplicate_matches: List[Dict[str, Any]] = Field(default_factory=list)
    frequency: int = 0
    category: str = "other"
    confidence: float = 0.5


class NeologismManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._status_lock = threading.Lock()
        self._mining_status: Dict[str, Dict[str, Any]] = {}
        self._candidate_locks_guard = threading.Lock()
        self._candidate_locks: Dict[str, threading.RLock] = {}

    def _candidate_lock(self, project_id: str) -> threading.RLock:
        with self._candidate_locks_guard:
            return self._candidate_locks.setdefault(project_id, threading.RLock())

    @staticmethod
    def _default_status() -> Dict[str, Any]:
        return {
            "status": "idle",
            "processed_files": 0,
            "total_files": 0,
            "new_terms": 0,
            "duplicate_terms": 0,
            "current_file": None,
            "error": None,
            "task_id": None,
        }

    def _set_mining_status(self, project_id: str, **updates) -> None:
        with self._status_lock:
            current = self._mining_status.get(project_id, self._default_status())
            current.update(updates)
            self._mining_status[project_id] = current

    def reserve_mining(self, project_id: str, task_id: str, total_files: int) -> bool:
        """Atomically reserve one active mining run per project."""
        with self._status_lock:
            current = self._mining_status.get(project_id, self._default_status())
            if current.get("status") in ACTIVE_STATUSES:
                return False
            self._mining_status[project_id] = {
                **self._default_status(),
                "status": "starting",
                "total_files": total_files,
                "task_id": task_id,
            }
            return True

    def get_mining_status(self, project_id: str) -> Dict[str, Any]:
        with self._status_lock:
            return dict(self._mining_status.get(project_id, self._default_status()))

    def _push_task_status(
        self,
        task_id: Optional[str],
        project_id: str,
        *,
        status: Optional[str] = None,
        stage: Optional[str] = None,
        processed_files: Optional[int] = None,
        total_files: Optional[int] = None,
        current_file: Optional[str] = None,
        new_terms: Optional[int] = None,
        duplicate_terms: Optional[int] = None,
        error: Optional[str] = None,
        log_message: Optional[str] = None,
    ) -> None:
        if not task_id:
            return
        progress: Dict[str, Any] = {}
        if processed_files is not None:
            progress["current"] = processed_files
        if total_files is not None:
            progress["total"] = total_files
        if current_file is not None:
            progress["current_file"] = current_file or ""
        if stage is not None:
            progress["stage"] = stage
        if total_files and processed_files is not None:
            progress["percent"] = int((processed_files / total_files) * 100)

        summary: Dict[str, Any] = {"project_id": project_id}
        if new_terms is not None:
            summary["new_terms"] = new_terms
        if duplicate_terms is not None:
            summary["duplicate_terms"] = duplicate_terms
        if error is not None:
            summary["error"] = error

        task_state.update_task(
            task_id,
            status=status,
            append_log=log_message,
            progress=progress or None,
            summary=summary,
            fields={"kind": "neologism_mining"},
            push=True,
        )

    def _get_cache_file(self, project_id: str) -> str:
        if not SAFE_PROJECT_ID.fullmatch(project_id or ""):
            raise CandidateStoreError("Invalid project_id for candidate storage")
        cache_root = Path(CACHE_DIR)
        cache_root.mkdir(parents=True, exist_ok=True)
        cache_key = hashlib.sha256(project_id.encode("utf-8")).hexdigest()
        return str(cache_root / f"{cache_key}.json")

    def _load_candidates_unlocked(self, project_id: str) -> List[Candidate]:
        cache_file = self._get_cache_file(project_id)
        if not os.path.exists(cache_file):
            return []
        try:
            with open(cache_file, "r", encoding="utf-8") as file_handle:
                data = json.load(file_handle)
            return [Candidate(**item) for item in data]
        except Exception as exc:
            self.logger.exception(
                "Failed to load neologism candidates for project %s",
                project_id,
            )
            raise CandidateStoreError("Failed to load candidate storage") from exc

    def load_candidates(self, project_id: str) -> List[Candidate]:
        with self._candidate_lock(project_id):
            return self._load_candidates_unlocked(project_id)

    def _save_candidates_unlocked(self, project_id: str, candidates: List[Candidate]) -> None:
        cache_file = self._get_cache_file(project_id)
        temp_path: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                delete=False,
                encoding="utf-8",
                dir=os.path.dirname(cache_file),
                prefix=f".{Path(cache_file).stem}.",
                suffix=".tmp",
            ) as temp_file:
                temp_path = temp_file.name
                json.dump([candidate.model_dump() for candidate in candidates], temp_file, ensure_ascii=False, indent=2)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            os.replace(temp_path, cache_file)
        except Exception as exc:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            self.logger.exception(
                "Failed to save neologism candidates for project %s",
                project_id,
            )
            raise CandidateStoreError("Failed to save candidate storage") from exc

    def save_candidates(self, project_id: str, candidates: List[Candidate]) -> None:
        with self._candidate_lock(project_id):
            self._save_candidates_unlocked(project_id, candidates)

    def get_pending_candidates(self, project_id: str) -> List[Dict[str, Any]]:
        return self.get_candidates(project_id, view="pending")

    def get_candidates(self, project_id: str, *, view: str = "pending") -> List[Dict[str, Any]]:
        if view not in {"pending", "processed", "all"}:
            raise ValueError(f"Unsupported candidate view: {view}")
        return [
            candidate.model_dump()
            for candidate in self.load_candidates(project_id)
            if (
                view == "all"
                or (view == "pending" and candidate.status == "pending")
                or (view == "processed" and candidate.status != "pending")
            )
        ]

    async def approve_candidate(
        self,
        project_id: str,
        candidate_id: str,
        final_translation: str,
        glossary_id: Optional[int],
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None,
        resolution: str = "approve_project",
    ) -> bool:
        with self._candidate_lock(project_id):
            candidate = next(
                (item for item in self._load_candidates_unlocked(project_id) if item.id == candidate_id),
                None,
            )
        if not candidate:
            return False

        terminal_resolution = {
            "approved": "approve_project",
            "duplicate": "duplicate",
            "new_meaning": "new_meaning",
        }.get(candidate.status)
        if terminal_resolution:
            return terminal_resolution == resolution
        if candidate.status != "pending":
            return False

        if resolution == "duplicate":
            with self._candidate_lock(project_id):
                candidates = self._load_candidates_unlocked(project_id)
                latest = next((item for item in candidates if item.id == candidate_id), None)
                if not latest:
                    return False
                latest.status = "duplicate"
                self._save_candidates_unlocked(project_id, candidates)
            return True

        final_translation = final_translation.strip()
        if not final_translation or not glossary_id:
            return False

        resolved_source_lang = source_lang or candidate.source_lang or "en"
        resolved_target_lang = target_lang or candidate.target_lang or "zh-CN"
        translations = {
            resolved_source_lang: candidate.original,
        }
        translations[resolved_target_lang] = final_translation
        storage_entry = {
            "id": candidate.id,
            "translations": translations,
            "metadata": {
                "remarks": f"Auto-mined. Reasoning: {candidate.reasoning}",
                "source_text": candidate.original,
                "source_file": candidate.source_file,
                "source_files": candidate.source_files,
                "project_id": project_id,
                "source_lang": resolved_source_lang,
                "target_lang": resolved_target_lang,
                "neologism_resolution": resolution,
                "frequency": candidate.frequency,
                "category": candidate.category,
                "confidence": candidate.confidence,
            },
            "variants": {},
            "abbreviations": {},
        }

        if not await glossary_manager.add_entry(glossary_id, storage_entry):
            return False

        with self._candidate_lock(project_id):
            candidates = self._load_candidates_unlocked(project_id)
            latest = next((item for item in candidates if item.id == candidate_id), None)
            if not latest:
                raise CandidateStoreError(
                    f"Candidate {candidate_id} disappeared after its glossary entry was written"
                )
            latest.status = "new_meaning" if resolution == "new_meaning" else "approved"
            latest.suggestion = final_translation
            self._save_candidates_unlocked(project_id, candidates)
        self.logger.info("Approved candidate %s for project %s", candidate_id, project_id)
        return True

    def reject_candidate(self, project_id: str, candidate_id: str) -> Optional[str]:
        """Reject a pending candidate and return its status before the request."""
        with self._candidate_lock(project_id):
            candidates = self._load_candidates_unlocked(project_id)
            candidate = next((item for item in candidates if item.id == candidate_id), None)
            if not candidate:
                return None
            previous_status = candidate.status
            if candidate.status == "ignored":
                return previous_status
            if candidate.status != "pending":
                return previous_status
            candidate.status = "ignored"
            self._save_candidates_unlocked(project_id, candidates)
        return previous_status

    def restore_candidate(self, project_id: str, candidate_id: str) -> Optional[str]:
        with self._candidate_lock(project_id):
            candidates = self._load_candidates_unlocked(project_id)
            candidate = next((item for item in candidates if item.id == candidate_id), None)
            if not candidate:
                return None
            previous_status = candidate.status
            if candidate.status != "pending":
                candidate.status = "pending"
                self._save_candidates_unlocked(project_id, candidates)
        return previous_status

    def update_candidate_suggestion(self, project_id: str, candidate_id: str, suggestion: str) -> bool:
        with self._candidate_lock(project_id):
            candidates = self._load_candidates_unlocked(project_id)
            candidate = next((item for item in candidates if item.id == candidate_id), None)
            if not candidate:
                return False
            candidate.suggestion = suggestion.strip()
            self._save_candidates_unlocked(project_id, candidates)
        return True

    @staticmethod
    def _normalize_term(term: str) -> str:
        return " ".join((term or "").casefold().split())

    @staticmethod
    def _chunk_texts(texts: List[str], chunk_size: int = 50, overlap: int = 3) -> List[str]:
        if not texts:
            return []
        if len(texts) <= chunk_size:
            return ["\n".join(texts)]
        chunks: List[str] = []
        step = chunk_size - overlap
        for index in range(0, len(texts), step):
            chunks.append("\n".join(texts[index:index + chunk_size]))
            if index + chunk_size >= len(texts):
                break
        return chunks

    @staticmethod
    def _read_translatable_texts(file_path: str) -> List[str]:
        path = Path(file_path)
        if path.suffix.lower() == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
                return [
                    cell.strip()
                    for row in csv.reader(csv_file)
                    for cell in row
                    if cell and cell.strip()
                ]
        _, texts, _ = extract_translatable_content(str(path))
        return [text for text in texts if text and text.strip()]

    def _collect_evidence(
        self,
        original: str,
        file_texts: Dict[str, List[str]],
        max_snippets: int = 5,
    ) -> Dict[str, Any]:
        needle = original.casefold()
        snippets: List[str] = []
        source_files: List[str] = []
        context_evidence: List[Dict[str, Any]] = []
        frequency = 0
        for file_path, texts in file_texts.items():
            file_matched = False
            for text in texts:
                count = text.casefold().count(needle)
                if not count:
                    continue
                frequency += count
                file_matched = True
                normalized_text = text.strip()
                if (
                    len(context_evidence) < max_snippets
                    and not any(
                        item["snippet"] == normalized_text and item["source_file"] == file_path
                        for item in context_evidence
                    )
                ):
                    context_evidence.append({
                        "snippet": normalized_text,
                        "source_file": file_path,
                        "line": None,
                    })
                if len(snippets) < max_snippets and normalized_text not in snippets:
                    snippets.append(normalized_text)
            if file_matched:
                source_files.append(file_path)
        return {
            "context_snippets": snippets,
            "source_files": source_files,
            "context_evidence": context_evidence,
            "frequency": frequency,
        }

    def _fail_workflow(
        self,
        project_id: str,
        task_id: Optional[str],
        total_files: int,
        processed_files: int,
        error: Exception,
    ) -> None:
        message = str(error) or error.__class__.__name__
        self._set_mining_status(
            project_id,
            status="failed",
            processed_files=processed_files,
            total_files=total_files,
            current_file=None,
            error=message,
        )
        self._push_task_status(
            task_id,
            project_id,
            status="failed",
            stage="Failed",
            processed_files=processed_files,
            total_files=total_files,
            error=message,
            log_message=f"Neologism mining failed: {message}",
        )

    def run_mining_workflow(
        self,
        project_id: str,
        file_paths: List[str],
        api_provider: str,
        source_lang: str = "en",
        target_lang: str = "zh-CN",
        game_name: str = "Paradox Game",
        task_id: Optional[str] = None,
        duplicate_index: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        model_name: Optional[str] = None,
        review_language: str = "en",
    ) -> int:
        total_files = len(file_paths)
        processed_files = 0
        self._set_mining_status(
            project_id,
            status="running",
            processed_files=0,
            total_files=total_files,
            new_terms=0,
            duplicate_terms=0,
            current_file=None,
            error=None,
            task_id=task_id,
        )
        self._push_task_status(
            task_id,
            project_id,
            status="running",
            stage="Mining",
            processed_files=0,
            total_files=total_files,
            new_terms=0,
            duplicate_terms=0,
            log_message="Neologism mining started.",
        )

        try:
            if not file_paths:
                raise ValueError("No supported project files were selected for mining")
            handler = get_handler(api_provider, model_name=model_name)
            miner = NeologismMiner(handler)
            file_texts: Dict[str, List[str]] = {}
            aggregates: Dict[str, Dict[str, Any]] = {}

            for index, file_path in enumerate(file_paths, start=1):
                self._set_mining_status(project_id, processed_files=index - 1, current_file=file_path)
                self._push_task_status(
                    task_id,
                    project_id,
                    stage="Mining",
                    processed_files=index - 1,
                    total_files=total_files,
                    current_file=file_path,
                )
                texts = self._read_translatable_texts(file_path)
                file_texts[file_path] = texts
                for chunk in self._chunk_texts(texts):
                    for item in miner.extract_terms(chunk, game_name=game_name):
                        if item.original.casefold() not in chunk.casefold():
                            self.logger.warning(
                                "Discarded ungrounded neologism candidate %r from %s",
                                item.original,
                                file_path,
                            )
                            continue
                        key = self._normalize_term(item.original)
                        current = aggregates.get(key)
                        if current is None or item.confidence > current["confidence"]:
                            aggregates[key] = {
                                "original": item.original.strip(),
                                "category": item.category,
                                "confidence": item.confidence,
                            }
                processed_files = index
                self._set_mining_status(project_id, processed_files=index)
                self._push_task_status(
                    task_id,
                    project_id,
                    stage="Mining",
                    processed_files=index,
                    total_files=total_files,
                    current_file=file_path,
                )

            existing_candidates = self.load_candidates(project_id)
            existing_terms = {self._normalize_term(candidate.original) for candidate in existing_candidates}
            duplicate_index = duplicate_index or {}
            prepared: List[Dict[str, Any]] = []
            duplicate_count = 0
            for key, aggregate in aggregates.items():
                if key in existing_terms:
                    continue
                evidence = self._collect_evidence(aggregate["original"], file_texts)
                if not evidence["context_snippets"]:
                    continue
                duplicate_matches = duplicate_index.get(key, [])
                if duplicate_matches:
                    duplicate_count += 1
                prepared.append({
                    **aggregate,
                    **evidence,
                    "duplicate_matches": duplicate_matches,
                })

            review_payloads = [
                {
                    "original": item["original"],
                    "category": item["category"],
                    "frequency": item["frequency"],
                    "contexts": item["context_snippets"],
                }
                for item in prepared
                if not self._existing_target_suggestion(item["duplicate_matches"], target_lang)
            ]
            reviews: Dict[str, Any] = {}
            for offset in range(0, len(review_payloads), REVIEW_BATCH_SIZE):
                reviews.update(miner.review_terms(
                    review_payloads[offset:offset + REVIEW_BATCH_SIZE],
                    source_lang=source_lang,
                    target_lang=target_lang,
                    game_name=game_name,
                    review_language=review_language,
                ))

            new_candidates: List[Candidate] = []
            for item in prepared:
                existing_suggestion = self._existing_target_suggestion(item["duplicate_matches"], target_lang)
                review = reviews.get(item["original"])
                suggestion = existing_suggestion or (review.suggestion if review else "")
                reasoning = (
                    "An existing glossary entry matches this source term. Review whether to reuse it, "
                    "create a project override, or mark a new meaning."
                    if existing_suggestion
                    else review.reasoning
                )
                confidence = max(item["confidence"], review.confidence if review else 0.0)
                new_candidates.append(Candidate(
                    id=str(uuid.uuid4()),
                    project_id=project_id,
                    original=item["original"],
                    context_snippets=item["context_snippets"],
                    suggestion=suggestion,
                    reasoning=reasoning,
                    source_file=item["source_files"][0] if item["source_files"] else None,
                    source_files=item["source_files"],
                    context_evidence=item["context_evidence"],
                    source_lang=source_lang,
                    target_lang=target_lang,
                    review_language=review_language,
                    duplicate_matches=item["duplicate_matches"],
                    frequency=item["frequency"],
                    category=item["category"],
                    confidence=confidence,
                ))

            with self._candidate_lock(project_id):
                latest = self._load_candidates_unlocked(project_id)
                latest_terms = {self._normalize_term(candidate.original) for candidate in latest}
                added_candidates = []
                for candidate in new_candidates:
                    key = self._normalize_term(candidate.original)
                    if key in latest_terms:
                        continue
                    latest.append(candidate)
                    added_candidates.append(candidate)
                    latest_terms.add(key)
                self._save_candidates_unlocked(project_id, latest)

            new_count = len(added_candidates)
            self._set_mining_status(
                project_id,
                status="completed",
                processed_files=total_files,
                total_files=total_files,
                new_terms=new_count,
                duplicate_terms=duplicate_count,
                current_file=None,
                error=None,
            )
            self._push_task_status(
                task_id,
                project_id,
                status="completed",
                stage="Completed",
                processed_files=total_files,
                total_files=total_files,
                current_file="",
                new_terms=new_count,
                duplicate_terms=duplicate_count,
                log_message=f"Neologism mining completed. Found {new_count} new candidates.",
            )
            return new_count
        except Exception as exc:
            self.logger.error("Neologism mining failed for project %s: %s", project_id, exc, exc_info=True)
            self._fail_workflow(project_id, task_id, total_files, processed_files, exc)
            raise

    @staticmethod
    def _existing_target_suggestion(matches: List[Dict[str, Any]], target_lang: str) -> str:
        scope_rank = {"project": 3, "game": 2, "main": 1}
        for match in sorted(matches, key=lambda item: scope_rank.get(item.get("scope"), 0), reverse=True):
            translations = match.get("translations") or {}
            suggestion = translations.get(target_lang)
            if suggestion:
                return suggestion
        return ""


neologism_manager = NeologismManager()
