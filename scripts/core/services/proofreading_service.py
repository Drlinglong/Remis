import os
import re
import logging
import hashlib
import tempfile
from pathlib import Path
from typing import List, Dict, Any

from scripts.utils.quote_extractor import QuoteExtractor
from scripts.core.file_builder import patch_file_content
from scripts.core.loc_parser import unescape_value
from scripts.utils.i18n_utils import iso_to_paradox
from scripts.schemas.common import LanguageCode

logger = logging.getLogger(__name__)

class ProofreadingDataError(Exception):
    def __init__(self, code: str, message: str, *, status_code: int = 404):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class ProofreadingConflictError(Exception):
    """Raised when the target file changed after the proofreading session loaded."""


def _file_revision(file_path: str) -> str:
    digest = hashlib.sha256()
    with open(file_path, 'rb') as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_lines(file_path: str, lines: List[str]) -> None:
    target_path = Path(file_path)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w',
            delete=False,
            encoding='utf-8-sig',
            newline='',
            dir=target_path.parent,
            prefix=f'.{target_path.name}.',
            suffix='.tmp',
        ) as temp_file:
            temp_path = temp_file.name
            temp_file.writelines(lines)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, target_path)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


class ProofreadingService:
    def __init__(self, project_manager, archive_manager):
        self.project_manager = project_manager
        self.archive_manager = archive_manager

    def _classify_structure_line(self, line: str) -> str:
        stripped = line.strip()
        if not stripped:
            return "blank"
        if stripped.startswith("#"):
            return "comment"
        if re.match(r"^\s*l_[\w-]+:\s*$", line, re.IGNORECASE):
            return "header"
        return "raw"

    @staticmethod
    def _normalize_translation_value(value: Any) -> str:
        if value is None:
            return ""
        return unescape_value(str(value))

    def _collect_structure_blocks(
        self,
        lines: List[str],
        structure_type: str,
    ) -> List[Dict[str, Any]]:
        blocks = []
        start = None
        for line_num, line in enumerate(lines):
            matches = self._classify_structure_line(line) == structure_type
            if matches and start is None:
                start = line_num
            if start is not None and (not matches or line_num == len(lines) - 1):
                end = line_num if matches and line_num == len(lines) - 1 else line_num - 1
                blocks.append({
                    "start": start,
                    "end": end,
                    "lines": lines[start:end + 1],
                })
                start = None
        return blocks

    def _build_proofreading_rows(
        self,
        original_lines: List[str],
        texts_to_translate: List[str],
        key_map: Dict[int, Dict[str, Any]],
        ai_translated_texts: List[str],
        disk_translated_texts: List[str],
        target_lines: List[str] = None,
    ) -> List[Dict[str, Any]]:
        entry_by_line = {}
        for idx, source_value in enumerate(texts_to_translate):
            line_info = key_map[idx]
            line_num = line_info["line_num"]
            entry_by_line[line_num] = {
                "entry_id": f"entry-{idx}",
                "row_type": "translation",
                "line_number": line_num + 1,
                "key": line_info["key_part"].strip(),
                "source_value": self._normalize_translation_value(source_value),
                "ai_value": self._normalize_translation_value(
                    ai_translated_texts[idx] if idx < len(ai_translated_texts) else ""
                ),
                "final_value": self._normalize_translation_value(
                    disk_translated_texts[idx] if idx < len(disk_translated_texts) else ""
                ),
                "editable": True,
                "issues": [],
            }

        target_lines = target_lines or original_lines
        source_comment_blocks = self._collect_structure_blocks(original_lines, "comment")
        target_comment_blocks = self._collect_structure_blocks(target_lines, "comment")
        target_comments_by_source_start = {}
        if len(source_comment_blocks) == len(target_comment_blocks):
            target_comments_by_source_start = {
                source_block["start"]: target_block["lines"]
                for source_block, target_block in zip(source_comment_blocks, target_comment_blocks)
            }
        rows = []
        pending_structure = None

        def structure_value(lines: List[str]) -> str:
            return "\n".join(line.rstrip("\r\n") for line in lines)

        def flush_structure():
            nonlocal pending_structure
            if not pending_structure:
                return

            start = pending_structure["start"]
            end = pending_structure["end"]
            structure_type = pending_structure["structure_type"]
            source_block = original_lines[start:end + 1]
            target_block = target_comments_by_source_start.get(start) if structure_type == "comment" else None
            if target_block is None:
                target_block = []
                for line_num in range(start, end + 1):
                    source_line = original_lines[line_num]
                    target_line = target_lines[line_num] if line_num < len(target_lines) else source_line
                    if self._classify_structure_line(target_line) != self._classify_structure_line(source_line):
                        target_line = source_line
                    target_block.append(target_line)

            source_value = structure_value(source_block)
            final_value = structure_value(target_block)
            rows.append({
                "entry_id": f"structure-{structure_type}-{start}-{end}",
                "row_type": "structure",
                "structure_type": structure_type,
                "line_number": start + 1,
                "line_start": start + 1,
                "line_end": end + 1,
                "raw_source_line": source_value,
                "display_text": source_value,
                "source_value": source_value,
                "final_value": final_value,
                "editable": structure_type == "comment",
            })
            pending_structure = None

        for line_num, line in enumerate(original_lines):
            if line_num in entry_by_line:
                flush_structure()
                row = dict(entry_by_line[line_num])
                row["raw_source_line"] = line.rstrip("\n")
                rows.append(row)
                continue

            structure_type = self._classify_structure_line(line)
            can_group = structure_type in {"comment", "blank"}
            if (
                can_group
                and pending_structure
                and pending_structure["structure_type"] == structure_type
                and pending_structure["end"] == line_num - 1
            ):
                pending_structure["end"] = line_num
                continue

            flush_structure()
            pending_structure = {
                "start": line_num,
                "end": line_num,
                "structure_type": structure_type,
            }

        flush_structure()

        return rows

    def _build_preserved_comment_patches(
        self,
        source_lines: List[str],
        target_lines: List[str],
    ) -> List[Dict[str, Any]]:
        source_blocks = self._collect_structure_blocks(source_lines, "comment")
        target_blocks = self._collect_structure_blocks(target_lines, "comment")
        if len(source_blocks) != len(target_blocks):
            logger.warning(
                "ProofreadingService: Cannot preserve target comments because comment block counts differ (%s source, %s target).",
                len(source_blocks),
                len(target_blocks),
            )
            return []

        return [
            {
                "entry_id": f"preserved-comment-{source_block['start']}-{source_block['end']}",
                "line_start": source_block["start"] + 1,
                "line_end": source_block["end"] + 1,
                "content": "\n".join(line.rstrip("\r\n") for line in target_block["lines"]),
            }
            for source_block, target_block in zip(source_blocks, target_blocks)
        ]

    def _apply_structure_patches(
        self,
        lines: List[str],
        structure_patches: List[Dict[str, Any]],
    ) -> List[str]:
        patched_lines = list(lines)
        ordered_patches = sorted(
            structure_patches or [],
            key=lambda patch: patch["line_start"],
            reverse=True,
        )

        for patch in ordered_patches:
            start = int(patch["line_start"]) - 1
            end = int(patch["line_end"])
            if start < 0 or end <= start or end > len(lines):
                raise ValueError("Comment patch line range is outside the source file.")
            if any(self._classify_structure_line(line) != "comment" for line in lines[start:end]):
                raise ValueError("Only comment rows can be changed from the proofreading table.")

            content = str(patch.get("content", ""))
            if not content.strip():
                raise ValueError("Comment blocks cannot be empty.")
            replacement_lines = [f"{line}\n" for line in content.split("\n")]
            if any(line.strip() and not line.lstrip().startswith("#") for line in replacement_lines):
                raise ValueError("Edited comment lines must remain comments.")

            patched_lines[start:end] = replacement_lines

        return patched_lines

    async def find_source_template(self, target_path: str, source_lang: str, current_lang: str, project_id: str = None) -> str:
        """
        Robustly finds the source template file path given the target file path.
        """
        # --- Strategy 1: Path Manipulation ---
        try:
            path_obj = Path(target_path)
            parts = list(path_obj.parts)
            
            lang_folder_index = -1
            for i, part in enumerate(parts):
                if part.lower() == current_lang.lower():
                    lang_folder_index = i
                    break
            
            if lang_folder_index != -1:
                parts[lang_folder_index] = source_lang 
                filename = parts[-1]
                current_suffix = f"_l_{current_lang}"
                source_suffix = f"_l_{source_lang}"
                
                if current_suffix.lower() in filename.lower():
                    new_filename = re.sub(re.escape(current_suffix), source_suffix, filename, flags=re.IGNORECASE)
                    parts[-1] = new_filename
                    new_path = Path(*parts)
                    if new_path.exists():
                        return str(new_path)

            target_path_str = str(target_path)
            pattern_dir = re.compile(re.escape(os.sep + current_lang + os.sep), re.IGNORECASE)
            replacement_dir = (os.sep + source_lang + os.sep).replace('\\', '\\\\')
            new_path_str = pattern_dir.sub(replacement_dir, target_path_str)
            pattern_suffix = re.compile(re.escape(f"_l_{current_lang}"), re.IGNORECASE)
            new_path_str = pattern_suffix.sub(f"_l_{source_lang}", new_path_str)
            
            if os.path.exists(new_path_str):
                return new_path_str
        except Exception as e:
            logger.warning(f"ProofreadingService: Strategy 1 failed: {e}")

        # --- Strategy 2: Project-wide Search ---
        try:
            if project_id:
                filename = os.path.basename(target_path)
                current_suffix = f"_l_{current_lang}"
                source_suffix = f"_l_{source_lang}"
                
                if current_suffix.lower() in filename.lower():
                    expected_source_filename = re.sub(re.escape(current_suffix), source_suffix, filename, flags=re.IGNORECASE)
                    # [ASYNC CHANGE] Added await
                    files = await self.project_manager.get_project_files(project_id)
                    for f in files:
                        if os.path.basename(f['file_path']).lower() == expected_source_filename.lower():
                            if os.path.exists(f['file_path']):
                                return f['file_path']
        except Exception as e:
            logger.warning(f"ProofreadingService: Strategy 2 failed: {e}")

        # --- Strategy 3: Direct Disk Search ---
        try:
            if project_id:
                filename = os.path.basename(target_path)
                current_suffix = f"_l_{current_lang}"
                source_suffix = f"_l_{source_lang}"
                
                if current_suffix.lower() in filename.lower():
                    expected_source_filename = re.sub(re.escape(current_suffix), source_suffix, filename, flags=re.IGNORECASE)
                    # [ASYNC CHANGE] Added await
                    project = await self.project_manager.get_project(project_id)
                    if project and project.get('source_path') and os.path.exists(project['source_path']):
                        for root, dirs, files in os.walk(project['source_path']):
                            for f in files:
                                if f.lower() == expected_source_filename.lower():
                                    return os.path.join(root, f)
        except Exception as e:
            logger.warning(f"ProofreadingService: Strategy 3 failed: {e}")

        return ""

    async def _resolve_target_file_path(self, project_id: str, file_id: str) -> tuple[Dict[str, Any], str]:
        project = await self.project_manager.get_project(project_id)
        if not project:
            raise ProofreadingDataError(
                "project_not_found",
                "Cannot load proofreading data because the project no longer exists.",
            )

        files = await self.project_manager.get_project_files(project_id)
        target_file = next((item for item in files if item['file_id'] == file_id), None)
        if not target_file:
            raise ProofreadingDataError(
                "file_not_indexed",
                "Cannot load proofreading data because this file is not in the current project file index. Refresh project files and try again.",
            )

        target_file_path = target_file.get('file_path')
        if not target_file_path:
            raise ProofreadingDataError(
                "file_path_missing",
                "Cannot load proofreading data because this project file has no recorded localization path. Refresh or repair the project metadata.",
            )
        if not os.path.exists(target_file_path):
            raise ProofreadingDataError(
                "file_path_not_found",
                f"Cannot load proofreading data because the indexed localization file no longer exists on disk: {target_file_path}",
            )
        return project, target_file_path

    async def get_document_revision(self, project_id: str, file_id: str) -> Dict[str, str]:
        _, target_file_path = await self._resolve_target_file_path(project_id, file_id)
        return {"document_revision": _file_revision(target_file_path)}

    async def get_proofread_data(self, project_id: str, file_id: str) -> Dict[str, Any]:
        project, target_file_path = await self._resolve_target_file_path(project_id, file_id)

        filename = os.path.basename(target_file_path)
        
        # 1. Detect Languages
        current_lang = "english"
        lang_match = re.search(r"_l_(\w+)\.yml$", filename, re.IGNORECASE)
        if lang_match:
            current_lang = lang_match.group(1).lower()
        else:
            try:
                with open(target_file_path, 'r', encoding='utf-8-sig') as f:
                    first_line = f.readline()
                    header_match = re.match(r"^\s*l_(\w+):", first_line, re.IGNORECASE)
                    if header_match:
                        current_lang = header_match.group(1).lower()
            except: pass

        current_lang_key = f"l_{current_lang}"
        iso_source = project.get('source_language', 'en')
        source_lang = iso_to_paradox(iso_source)
        source_lang_key = f"l_{source_lang}"
        
        # 2. Locate Template
        if current_lang.lower() == source_lang.lower():
            template_file_path = target_file_path
        else:
            template_file_path = await self.find_source_template(target_file_path, source_lang, current_lang, project_id)

        if not template_file_path or not os.path.exists(template_file_path):
            template_file_path = target_file_path

        # 3. Parse and Patch
        try:
            original_lines, texts_to_translate, key_map = QuoteExtractor.extract_from_file(template_file_path)
            texts_to_translate = [self._normalize_translation_value(text) for text in texts_to_translate]
            original_content = "".join(original_lines)
            
            # AI Draft
            lang_code = LanguageCode.from_str(current_lang).value
            db_entries = self.archive_manager.get_entries(
                mod_name=project['name'],
                file_path=template_file_path,
                language=lang_code
            )
            if not db_entries:
                folder_mod_name = os.path.basename(project['source_path'])
                db_entries = self.archive_manager.get_entries(
                    mod_name=folder_mod_name,
                    file_path=template_file_path,
                    language=lang_code
                )

            db_translation_map = {
                e['key']: self._normalize_translation_value(e['translation'])
                for e in db_entries
                if e['translation']
            }
            
            # Disk State
            disk_translation_map = {}
            target_lines = original_lines
            if os.path.exists(target_file_path):
                target_lines, target_texts, target_map = QuoteExtractor.extract_from_file(target_file_path)
                for i, text in enumerate(target_texts):
                    if i in target_map:
                        disk_translation_map[target_map[i]['key_part'].strip()] = self._normalize_translation_value(text)

            entries = []
            ai_translated_texts = []
            disk_translated_texts = []
            
            for i, text in enumerate(texts_to_translate):
                key = key_map[i]['key_part'].strip()
                
                # AI Logic
                ai_trans = db_translation_map.get(key)
                if ai_trans is None: ai_trans = db_translation_map.get(str(i))
                if ai_trans is None and ":" in key: ai_trans = db_translation_map.get(key.split(':')[0])
                if ai_trans is None: ai_trans = db_translation_map.get(key + ":")
                
                # [REVERTED] Disk Fallback removed as per user request (DB consistency check)
                
                # If still None, it means DB is missing this key.
                # User requested explicit warning.
                if ai_trans is None: 
                    ai_trans = "⚠️ [DB_MISSING] " + text 

                ai_translated_texts.append(ai_trans)
                
                # Disk Logic
                disk_trans = disk_translation_map.get(key)
                if disk_trans is None and ":" in key: disk_trans = disk_translation_map.get(key.split(':')[0])
                if disk_trans is None: disk_trans = ai_trans
                disk_translated_texts.append(disk_trans)
                
                entries.append({
                    "key": key,
                    "original": text,
                    "translation": disk_trans, 
                    "line_number": key_map[i]['line_num'] 
                })

            ai_lines = patch_file_content(original_lines, texts_to_translate, ai_translated_texts, key_map, source_lang_key, current_lang_key)
            final_lines = patch_file_content(original_lines, texts_to_translate, disk_translated_texts, key_map, source_lang_key, current_lang_key)
            proofreading_rows = self._build_proofreading_rows(
                original_lines,
                texts_to_translate,
                key_map,
                ai_translated_texts,
                disk_translated_texts,
                target_lines,
            )

            return {
                "file_id": file_id,
                "file_path": target_file_path,
                "mod_name": project['name'],
                "entries": entries,
                "rows": proofreading_rows,
                "file_content": original_content,
                "ai_content": "".join(ai_lines),
                "final_content": "".join(final_lines),
                "document_revision": _file_revision(target_file_path),
            }
        except Exception as e:
            logger.error(f"ProofreadingService: Data preparation failed: {e}", exc_info=True)
            raise ProofreadingDataError(
                "data_preparation_failed",
                "Cannot prepare proofreading data for this file. Check that the source and translation files are valid localization files.",
                status_code=500,
            ) from e

    async def save_proofread_data(
        self,
        project_id: str,
        file_id: str,
        entries_list: List[Dict],
        structure_patches: List[Dict[str, Any]] = None,
        base_revision: str = None,
    ) -> Dict[str, Any] | bool:
        """
        Saves user-corrected translations back to the target file.
        """
        try:
            project = await self.project_manager.get_project(project_id)
            files = await self.project_manager.get_project_files(project_id)
            target_file = next((f for f in files if f['file_id'] == file_id), None)

            if not project or not target_file:
                return False

            target_file_path = target_file['file_path']
            if not os.path.exists(target_file_path):
                return False
            current_revision = _file_revision(target_file_path)
            if base_revision and current_revision != base_revision:
                raise ProofreadingConflictError(
                    "The proofreading target changed after it was loaded."
                )
            filename = os.path.basename(target_file_path)

            # 1. Detect Languages
            current_lang = "english"
            lang_match = re.search(r"_l_(\w+)\.yml$", filename, re.IGNORECASE)
            if lang_match:
                current_lang = lang_match.group(1).lower()
            else:
                try:
                    with open(target_file_path, 'r', encoding='utf-8-sig') as f:
                        first_line = f.readline()
                        header_match = re.match(r"^\s*l_(\w+):", first_line, re.IGNORECASE)
                        if header_match:
                            current_lang = header_match.group(1).lower()
                except:
                    pass
            
            current_lang_key = f"l_{current_lang}"
            iso_source = project.get('source_language', 'en')
            disk_source_lang = iso_to_paradox(iso_source)
            source_lang_key = f"l_{disk_source_lang}"

            # 2. Locate Template
            if current_lang == disk_source_lang:
                template_file_path = target_file_path
            else:
                template_file_path = await self.find_source_template(target_file_path, disk_source_lang, current_lang, project_id)
            
            if not template_file_path or not os.path.exists(template_file_path):
                template_file_path = target_file_path

            # 3. Read Template and Prepare Data
            original_lines, texts_to_translate, key_map = QuoteExtractor.extract_from_file(template_file_path)
            texts_to_translate = [self._normalize_translation_value(text) for text in texts_to_translate]
            target_lines, _, _ = QuoteExtractor.extract_from_file(target_file_path)
            user_translation_map = {
                e['key']: self._normalize_translation_value(e['translation'])
                for e in entries_list
            }
            
            translated_texts = []
            for i, text in enumerate(texts_to_translate):
                key = key_map[i]['key_part'].strip()
                translated_texts.append(user_translation_map.get(key, text))
                
            # 4. Patch and Write
            patched_lines = patch_file_content(original_lines, texts_to_translate, translated_texts, key_map, source_lang_key, current_lang_key)
            preserved_patches = self._build_preserved_comment_patches(original_lines, target_lines)
            merged_patches = {
                (patch["line_start"], patch["line_end"]): patch
                for patch in preserved_patches
            }
            merged_patches.update({
                (patch["line_start"], patch["line_end"]): patch
                for patch in (structure_patches or [])
            })
            patched_lines = self._apply_structure_patches(patched_lines, list(merged_patches.values()))
            
            _atomic_write_lines(target_file_path, patched_lines)

            # 5. Update project-local workflow state
            await self.project_manager.update_file_status_with_kanban_sync(
                project_id,
                file_id,
                "done",
            )
            return {
                "status": "success",
                "document_revision": _file_revision(target_file_path),
            }

        except ProofreadingConflictError:
            raise
        except Exception as e:
            logger.error(f"ProofreadingService: Save failed: {e}", exc_info=True)
            return False
