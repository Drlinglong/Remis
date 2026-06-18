import json
import os
import uuid
import logging
import threading
from typing import List, Dict, Optional, Literal, Any
from pydantic import BaseModel, Field
from scripts.app_settings import PROJECT_ROOT
from scripts.core.api_handler import get_handler
from scripts.core.neologism_miner import NeologismMiner
from scripts.core.glossary_manager import glossary_manager
from scripts.shared import task_state

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(PROJECT_ROOT, "data", "cache", "neologism_candidates")

class Candidate(BaseModel):
    id: str
    project_id: str  # NEW: bind candidate to project
    original: str
    context_snippets: List[str]
    suggestion: str
    reasoning: str
    status: Literal["pending", "approved", "ignored"] = "pending"
    source_file: Optional[str] = None
    source_lang: str = "en"
    target_lang: str = "zh-CN"
    duplicate_matches: List[Dict[str, Any]] = Field(default_factory=list)

class NeologismManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._status_lock = threading.Lock()
        self._mining_status: Dict[str, Dict[str, Any]] = {}

    def _set_mining_status(self, project_id: str, **updates):
        with self._status_lock:
            current = self._mining_status.get(project_id, {
                "status": "idle",
                "processed_files": 0,
                "total_files": 0,
                "new_terms": 0,
                "current_file": None,
                "error": None,
            })
            current.update(updates)
            self._mining_status[project_id] = current

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
    ):
        if not task_id:
            return
        progress = {}
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

        summary = {"project_id": project_id}
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

    def get_mining_status(self, project_id: str) -> Dict[str, Any]:
        with self._status_lock:
            return dict(self._mining_status.get(project_id, {
                "status": "idle",
                "processed_files": 0,
                "total_files": 0,
                "new_terms": 0,
                "current_file": None,
                "error": None,
            }))
    
    def _get_cache_file(self, project_id: str) -> str:
        """Get project-specific cache file path."""
        os.makedirs(CACHE_DIR, exist_ok=True)
        return os.path.join(CACHE_DIR, f"{project_id}.json")

    def load_candidates(self, project_id: str) -> List[Candidate]:
        """Load candidates for a specific project."""
        cache_file = self._get_cache_file(project_id)
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return [Candidate(**item) for item in data]
            except Exception as e:
                self.logger.error(f"Failed to load candidates for {project_id}: {e}", exc_info=True)
                return []
        else:
            return []

    def save_candidates(self, project_id: str, candidates: List[Candidate]):
        """Save candidates for a specific project."""
        cache_file = self._get_cache_file(project_id)
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump([c.model_dump() for c in candidates], f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save candidates for {project_id}: {e}", exc_info=True)

    def get_pending_candidates(self, project_id: Optional[str] = None) -> List[Dict]:
        """Get pending candidates, optionally filtered by project."""
        if project_id:
            candidates = self.load_candidates(project_id)
            return [c.model_dump() for c in candidates if c.status == "pending"]
        else:
            # Return all pending from all projects
            all_pending = []
            if os.path.exists(CACHE_DIR):
                for filename in os.listdir(CACHE_DIR):
                    if filename.endswith('.json'):
                        pid = filename[:-5]  # Remove .json
                        candidates = self.load_candidates(pid)
                        all_pending.extend([c.model_dump() for c in candidates if c.status == "pending"])
            return all_pending

    async def approve_candidate(
        self,
        project_id: str,
        candidate_id: str,
        final_translation: str,
        glossary_id: Optional[int],
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None,
    ) -> bool:
        """Approve a candidate and add it to glossary."""
        candidates = self.load_candidates(project_id)
        candidate = next((c for c in candidates if c.id == candidate_id), None)
        if not candidate:
            return False

        resolved_source_lang = source_lang or candidate.source_lang or "en"
        resolved_target_lang = target_lang or candidate.target_lang or "zh-CN"
        resolved_glossary_id = glossary_id
        if not resolved_glossary_id:
            return False
        
        # Add to glossary
        new_entry_id = str(uuid.uuid4())
        storage_entry = {
            "id": new_entry_id,
            "translations": {
                resolved_source_lang: candidate.original,
                resolved_target_lang: final_translation
            },
            "metadata": {
                "remarks": f"Auto-mined. Reasoning: {candidate.reasoning}",
                "source_file": candidate.source_file,
                "source_lang": resolved_source_lang,
                "target_lang": resolved_target_lang,
            },
            "variants": {},
            "abbreviations": {}
        }
        
        if await glossary_manager.add_entry(resolved_glossary_id, storage_entry):
            candidate.status = "approved"
            self.save_candidates(project_id, candidates)
            self.logger.info(f"Approved candidate {candidate_id} for project {project_id}")
            return True
        return False

    def reject_candidate(self, project_id: str, candidate_id: str) -> bool:
        """Reject a candidate (mark as ignored)."""
        candidates = self.load_candidates(project_id)
        candidate = next((c for c in candidates if c.id == candidate_id), None)
        if candidate:
            candidate.status = "ignored"
            self.save_candidates(project_id, candidates)
            self.logger.info(f"Rejected candidate {candidate_id} for project {project_id}")
            return True
        return False
    
    def update_candidate_suggestion(self, project_id: str, candidate_id: str, suggestion: str) -> bool:
        """Update a candidate's suggestion."""
        candidates = self.load_candidates(project_id)
        candidate = next((c for c in candidates if c.id == candidate_id), None)
        if candidate:
            candidate.suggestion = suggestion
            self.save_candidates(project_id, candidates)
            self.logger.info(f"Updated candidate {candidate_id} suggestion for project {project_id}")
            return True
        return False

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
    ):
        """
        Main workflow:
        1. Initialize Miner with API provider.
        2. Iterate files, extract terms (Stage A).
        3. Deduplicate terms.
        4. For each term, find context (Stage B preparation).
        5. Call LLM for analysis (Stage B).
        6. Save candidates.
        """
        total_files = len(file_paths)
        self.logger.info(f"Starting mining workflow for project {project_id} with {total_files} files.")
        self._set_mining_status(
            project_id,
            status="running",
            processed_files=0,
            total_files=total_files,
            new_terms=0,
            current_file=None,
            error=None,
        )
        self._push_task_status(
            task_id,
            project_id,
            status="running",
            stage="Mining",
            processed_files=0,
            total_files=total_files,
            current_file="",
            new_terms=0,
            duplicate_terms=0,
            log_message="Neologism mining started.",
        )
        try:
            handler = get_handler(api_provider)
        except Exception as e:
            self._set_mining_status(project_id, status="failed", error=str(e), current_file=None)
            self._push_task_status(
                task_id,
                project_id,
                status="failed",
                stage="Failed",
                processed_files=0,
                total_files=total_files,
                error=str(e),
                log_message=f"Neologism mining failed: {e}",
            )
            raise
        miner = NeologismMiner(handler)
        
        all_terms = set()
        term_sources = {} # term -> source_file
        term_data = {} # Store analysis data from miner
        
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
            try:
                with open(file_path, 'r', encoding='utf-8-sig') as f:
                    lines = f.readlines()
                
                # Intelligent line-based chunking
                # ≤50 lines: process entire file
                # >50 lines: chunk by 50 lines with 3-line overlap
                if len(lines) <= 50:
                    chunks = [''.join(lines)]
                else:
                    chunks = []
                    chunk_size = 50
                    overlap = 3
                    step = chunk_size - overlap
                    
                    for i in range(0, len(lines), step):
                        chunk_lines = lines[i:i + chunk_size]
                        chunks.append(''.join(chunk_lines))
                        
                        # Stop if we've covered all lines
                        if i + chunk_size >= len(lines):
                            break
                
                for chunk in chunks:
                    # Pass target language to miner
                    lang_name_map = {
                        "zh": "Chinese", "zh-CN": "Chinese", "zh-TW": "Traditional Chinese",
                        "en": "English",
                        "ja": "Japanese",
                        "ko": "Korean",
                        "fr": "French",
                        "de": "German",
                        "ru": "Russian",
                        "es": "Spanish",
                        "pt": "Portuguese",
                        "pt-BR": "Portuguese",
                        "pl": "Polish"
                    }
                    target_lang_name = lang_name_map.get(target_lang, target_lang)
                    
                    # Miner now returns list of NeologismTerm objects
                    extracted_items = miner.extract_terms(chunk, target_lang=target_lang_name, target_lang_code=target_lang, game_name=game_name)
                    
                    for item in extracted_items:
                        term = item.original
                        if term not in all_terms:
                            all_terms.add(term)
                            term_sources[term] = file_path
                            # Store the initial analysis
                            term_data[term] = item
                            
            except Exception as e:
                self.logger.error(f"Error reading file {file_path}: {e}", exc_info=True)
            finally:
                self._set_mining_status(project_id, processed_files=index)
                self._push_task_status(
                    task_id,
                    project_id,
                    stage="Mining",
                    processed_files=index,
                    total_files=total_files,
                    current_file=file_path,
                )

        # Load existing candidates for this project
        existing_candidates = self.load_candidates(project_id)
        existing_terms = set()
        for c in existing_candidates:
            if c.status in ["approved", "ignored"]:
                existing_terms.add(c.original)
        
        # Filter new terms
        new_terms = [t for t in all_terms if t not in existing_terms and not any(c.original == t for c in existing_candidates)]

        # Create candidates (Single Stage: Analysis already done by Miner)
        new_candidates = []
        duplicate_index = duplicate_index or {}
        duplicate_count = 0
        for term in new_terms:
            source_file = term_sources[term]
            # Still extract context snippets for evidence
            context_snippets = self._find_context_snippets(term, source_file)
            
            # Get analysis from miner output (NeologismTerm object)
            analysis = term_data.get(term)
            
            duplicate_matches = duplicate_index.get(self._normalize_term(term), [])
            if duplicate_matches:
                duplicate_count += 1

            candidate = Candidate(
                id=str(uuid.uuid4()),
                project_id=project_id,
                original=term,
                context_snippets=context_snippets,
                suggestion=analysis.suggestion if analysis else "",
                reasoning=analysis.reasoning if analysis else "",
                status="pending",
                source_file=source_file,
                source_lang=source_lang,
                target_lang=target_lang,
                duplicate_matches=duplicate_matches,
            )
            new_candidates.append(candidate)
        
        # Merge with existing and save
        all_candidates = existing_candidates + new_candidates
        self.save_candidates(project_id, all_candidates)
        self.logger.info(f"Mining complete. Found {len(new_terms)} new terms.")
        self._set_mining_status(
            project_id,
            status="completed",
            processed_files=total_files,
            total_files=total_files,
            new_terms=len(new_terms),
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
            new_terms=len(new_terms),
            duplicate_terms=duplicate_count,
            log_message=f"Neologism mining completed. Found {len(new_terms)} new candidates.",
        )
        return len(new_terms)

    def _normalize_term(self, term: str) -> str:
        return " ".join((term or "").casefold().split())

    def _find_context_snippets(self, term: str, file_path: str, max_snippets: int = 3) -> List[str]:
        snippets = []
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                lines = f.readlines()
            
            for line in lines:
                if term in line:
                    snippets.append(line.strip())
                    if len(snippets) >= max_snippets:
                        break
        except Exception:
            pass
        return snippets

    def _analyze_term(self, term: str, snippets: List[str], handler, source_lang: str, target_lang: str) -> Dict:
        """
        Ask LLM for suggestion and reasoning.
        """
        context_text = "\n".join([f"- {s}" for s in snippets])
        prompt = f"""
        Term: "{term}"
        
        Context Snippets:
        {context_text}
        
        Task:
        1. Analyze the meaning of the term "{term}" based on the provided context.
        2. Suggest a translation for this term from {source_lang} to {target_lang}.
        3. Provide a brief reasoning for your suggestion.
        
        Output JSON:
        {{
            "suggestion": "...",
            "reasoning": "..."
        }}
        """
        
        try:
            # Use _call_api or generate_content
            # We need to handle the response parsing
            response_text = ""
            if hasattr(handler, "generate_content"):
                 response_text = handler.generate_content(prompt)
            else:
                 response_text = handler._call_api(handler.client, prompt)
            
            # Clean and parse JSON
            cleaned = response_text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            
            return json.loads(cleaned)
        except Exception as e:
            self.logger.error(f"Analysis failed for term {term}: {e}", exc_info=True)
            return {"suggestion": "", "reasoning": "Analysis failed"}

neologism_manager = NeologismManager()
