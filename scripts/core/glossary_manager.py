import logging
import json
import re
import threading
import asyncio
from typing import Dict, List, Any, Optional

from sqlalchemy.future import select
from sqlalchemy import func
from sqlmodel.ext.asyncio.session import AsyncSession

from scripts import app_settings
from scripts.utils import i18n
from scripts.utils.phonetics_engine import PhoneticsEngine
from scripts.core.db_manager import DatabaseConnectionManager
from scripts.core.db_models import Glossary, GlossaryEntry

logger = logging.getLogger(__name__)

class GlossaryManager:
    """Async Glossary Manager using SQLModel."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self.current_game_id: Optional[str] = None
        self.in_memory_glossary: Dict[str, Any] = {'entries': []}
        self.fuzzy_matching_mode: str = 'loose'
        self.phonetics_engine = PhoneticsEngine()
        self.db_manager = DatabaseConnectionManager()

    async def get_available_glossaries(self, game_id: str) -> List[Dict]:
        """Async: Query available glossaries for a game."""
        try:
            async for session in self.db_manager.get_async_session():
                statement = select(Glossary).where(Glossary.game_id == game_id)
                results = await session.execute(statement)
                glossaries = results.scalars().all()
                return [g.model_dump() for g in glossaries]
        except Exception as e:
            logger.error(f"Failed to get available glossaries for {game_id}: {e}")
            return []
        return []

    async def get_glossary_tree_data(self) -> List[Dict]:
        """Async: Build glossary tree data."""
        try:
            async for session in self.db_manager.get_async_session():
                statement = select(Glossary).order_by(Glossary.game_id, Glossary.name)
                results = await session.execute(statement)
                glossaries = results.scalars().all()

                tree_data = []
                current_game_id = None
                game_node = None

                for g in glossaries:
                    if g.game_id != current_game_id:
                        if game_node:
                            tree_data.append(game_node)
                        current_game_id = g.game_id
                        game_node = {
                            "title": current_game_id,
                            "key": current_game_id,
                            "children": []
                        }
                    
                    if game_node:
                        game_node["children"].append({
                            "title": g.name,
                            "key": f"{g.game_id}|{g.glossary_id}|{g.name}",
                            "isLeaf": True
                        })
                
                if game_node:
                    tree_data.append(game_node)
                    
                return tree_data
        except Exception as e:
            logger.error(f"Failed to build glossary tree: {e}")
            return []
        return []

    async def get_glossary_entries_paginated(self, glossary_id: int, page: int, page_size: int) -> Dict:
        """Async: Get paginated entries."""
        try:
            async for session in self.db_manager.get_async_session():
                # Count
                count_stmt = select(func.count()).select_from(GlossaryEntry).where(GlossaryEntry.glossary_id == glossary_id)
                total_count = (await session.execute(count_stmt)).scalar_one()

                # Select
                offset = (page - 1) * page_size
                stmt = select(GlossaryEntry).where(GlossaryEntry.glossary_id == glossary_id).limit(page_size).offset(offset)
                results = await session.execute(stmt)
                entries = results.scalars().all()
                
                return {
                    "entries": [e.model_dump() for e in entries],
                    "totalCount": total_count
                }
        except Exception as e:
            logger.error(f"Failed to get entries for {glossary_id}: {e}")
            return {"entries": [], "totalCount": 0}
        return {"entries": [], "totalCount": 0}

    async def search_glossary_entries_paginated(self, query: str, glossary_ids: List[int], page: int, page_size: int) -> Dict:
        """Async: Search entries."""
        if not glossary_ids:
            return {"entries": [], "totalCount": 0}

        try:
            async for session in self.db_manager.get_async_session():
                # Search using JSON casting or text text query is tricky in SQLModel + SQLite JSON
                # But here we search in 'translations' column which is JSON type.
                # In SQLite, we can use LIKE on the text representation of JSON?
                # SQLAlchemy JSON type handles serialization. In SQLite it's TEXT.
                # So `cast(GlossaryEntry.translations, String).ilike(f"%{query}%")` might work.
                # However, cleaner is just `GlossaryEntry.translations.ilike(...)`? No.
                
                from sqlalchemy import cast, String
                
                search_term = f"%{query.lower()}%"
                
                # Base condition
                # Note: This crude casting relies on backend storing JSON as string.
                condition = (GlossaryEntry.glossary_id.in_(glossary_ids)) & \
                            (cast(GlossaryEntry.translations, String).ilike(search_term))

                # Count
                count_stmt = select(func.count()).select_from(GlossaryEntry).where(condition)
                total_count = (await session.execute(count_stmt)).scalar_one()

                # Select
                offset = (page - 1) * page_size
                stmt = select(GlossaryEntry).where(condition).limit(page_size).offset(offset)
                results = await session.execute(stmt)
                entries = results.scalars().all()

                return {
                    "entries": [e.model_dump() for e in entries],
                    "totalCount": total_count
                }
        except Exception as e:
            logger.error(f"Failed to search entries: {e}")
            return {"entries": [], "totalCount": 0}
        return {"entries": [], "totalCount": 0}

    async def load_game_glossary(self, game_id: str) -> bool:
        """Async: Load main glossary for a game into memory."""
        self.current_game_id = game_id
        try:
            async for session in self.db_manager.get_async_session():
                # Find main glossary
                stmt = select(Glossary).where(Glossary.game_id == game_id, Glossary.is_main == True)
                result = await session.execute(stmt)
                main_glossary = result.scalar_one_or_none()

                if main_glossary and main_glossary.glossary_id:
                     return await self.load_selected_glossaries([main_glossary.glossary_id])
                else:
                    logger.warning(f"No main glossary found for {game_id}")
                    with self._lock:
                        self.in_memory_glossary = {'entries': []}
                    return False
        except Exception as e:
            logger.error(f"Error loading main glossary for {game_id}: {e}")
            return False
        return False

    async def load_selected_glossaries(self, selected_glossary_ids: List[int]) -> bool:
        """Async: Load selected glossaries into memory."""
        if not selected_glossary_ids:
            with self._lock:
                self.in_memory_glossary = {'entries': []}
            return True

        try:
            async for session in self.db_manager.get_async_session():
                stmt = select(GlossaryEntry).where(GlossaryEntry.glossary_id.in_(selected_glossary_ids))
                results = await session.execute(stmt)
                entries = results.scalars().all()
                
                # Convert to dicts
                entries_data = [e.model_dump() for e in entries]
                
                with self._lock:
                    self.in_memory_glossary = {'entries': entries_data}
                
                logger.info(i18n.t("log_glossary_loaded_from_selected", entries_count=len(entries_data), glossaries_count=len(selected_glossary_ids)))
                return True
        except Exception as e:
            logger.error(f"Failed to load selected glossaries: {e}")
            with self._lock:
                 self.in_memory_glossary = {'entries': []}
            return False
        return False

    async def add_entry(self, glossary_id: int, entry_data: Dict) -> bool:
        """Async: Add or Replace entry."""
        try:
            async for session in self.db_manager.get_async_session():
                # Check directly merging?
                # entry_data has 'id' which maps to 'entry_id'
                # But model expects 'entry_id'.
                
                # Transform data to model
                entry = GlossaryEntry(
                    entry_id=entry_data['id'],
                    glossary_id=glossary_id,
                    translations=entry_data.get('translations', {}),
                    abbreviations=entry_data.get('abbreviations', {}),
                    variants=entry_data.get('variants', {}),
                    raw_metadata=entry_data.get('metadata', {})
                )
                
                merged_entry = await session.merge(entry)
                await session.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to add entry: {e}")
            return False
        return False

    async def update_entry(self, entry_id: str, entry_data: Dict) -> bool:
        """Async: Update entry."""
        try:
            async for session in self.db_manager.get_async_session():
                stmt = select(GlossaryEntry).where(GlossaryEntry.entry_id == entry_id)
                result = await session.execute(stmt)
                entry = result.scalar_one_or_none()
                
                if entry:
                    entry.translations = entry_data.get('translations', {})
                    entry.abbreviations = entry_data.get('abbreviations', {})
                    entry.variants = entry_data.get('variants', {})
                    entry.raw_metadata = entry_data.get('metadata', {})
                    
                    session.add(entry)
                    await session.commit()
                    return True
                else:
                    logger.error(f"Entry {entry_id} not found for update")
                    return False
        except Exception as e:
            logger.error(f"Failed to update entry {entry_id}: {e}")
            return False
        return False

    async def delete_entry(self, entry_id: str) -> bool:
        """Async: Delete entry."""
        try:
            async for session in self.db_manager.get_async_session():
                stmt = select(GlossaryEntry).where(GlossaryEntry.entry_id == entry_id)
                result = await session.execute(stmt)
                entry = result.scalar_one_or_none()
                if entry:
                    await session.delete(entry)
                    await session.commit()
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to delete entry {entry_id}: {e}")
            return False

    async def create_glossary_file(self, game_id: str, file_name: str) -> bool:
        """Async: Create new glossary."""
        try:
            async for session in self.db_manager.get_async_session():
                glossary = Glossary(
                    game_id=game_id,
                    name=file_name,
                    description=f"User created glossary for {game_id}",
                    is_main=False
                )
                session.add(glossary)
                await session.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to create glossary file: {e}")
            return False

    async def delete_glossary(self, glossary_id: int) -> bool:
        """Async: Delete glossary and entries."""
        try:
            async for session in self.db_manager.get_async_session():
                # Delete entries first (cascade manual if not set in DB)
                from sqlalchemy import delete as sa_delete
                await session.execute(sa_delete(GlossaryEntry).where(GlossaryEntry.glossary_id == glossary_id))
                await session.execute(sa_delete(Glossary).where(Glossary.glossary_id == glossary_id))
                await session.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to delete glossary {glossary_id}: {e}")
            return False

    def get_glossary_for_translation(self) -> Optional[Dict]:
        """SYNC: Returns the in-memory glossary."""
        return self.in_memory_glossary if self.in_memory_glossary.get('entries') else None

    # --- Sync Business Logic (In-Memory) ---
    def extract_relevant_terms(self, texts: List[str], source_lang: str, target_lang: str) -> List[Dict]:
        glossary = self.get_glossary_for_translation()
        if not glossary or not glossary.get('entries'):
            return []
        
        logging.info(f"[Glossary] Extracting terms for {len(texts)} texts. Lang: {source_lang}->{target_lang}.")

        relevant_terms = []
        all_text = " ".join(texts).lower()
        matches = self._smart_term_matching(all_text, source_lang, target_lang)
        
        for match in matches:
            relevant_terms.append({
                'translations': {
                    source_lang: match['source_term'],
                    target_lang: match['target_term']
                },
                'id': match['id'],
                'metadata': match.get('metadata', match.get('raw_metadata', {})),
                'variants': match.get('variants', {}),
                'match_type': match['match_type'],
                'confidence': match['confidence']
            })
        relevant_terms.sort(key=lambda x: (x['confidence'], len(x['translations'][source_lang])), reverse=True)
        return relevant_terms

    def _smart_term_matching(self, text: str, source_lang: str, target_lang: str) -> List[Dict]:
        matches = []
        glossary = self.get_glossary_for_translation()
        if not glossary:
            return matches
            
        text_fingerprint = ""
        is_cjk = source_lang in ['zh-CN', 'zh-TW', 'ja', 'ko']
        if is_cjk:
            pe_lang = 'zh' if 'zh' in source_lang else source_lang
            text_fingerprint = self.phonetics_engine.generate_fingerprint(text, pe_lang)

        for entry in glossary.get('entries', []):
            translations = entry.get('translations', {})
            source_term = translations.get(source_lang, "")
            target_term = translations.get(target_lang, "")
            if not source_term or not target_term:
                continue
                
            # 1. Exact Match
            if source_term.lower() in text:
                matches.append(self._make_match(entry, source_term, target_term, 'exact', 1.0))
                continue
                
            # 2. Phonetic Match
            if is_cjk and len(source_term) > 1:
                term_fingerprint = self.phonetics_engine.generate_fingerprint(source_term, pe_lang)
                if term_fingerprint and term_fingerprint in text_fingerprint:
                    matches.append(self._make_match(entry, source_term, target_term, 'phonetic', 0.85))
                    continue

            # 3. Variant Match
            variants = entry.get('variants', {}).get(source_lang, [])
            found_variant = False
            for variant in variants:
                if variant.lower() in text:
                    matches.append(self._make_match(entry, source_term, target_term, 'variant', 0.9))
                    found_variant = True
                    break
            if found_variant: continue
            
            # 4. Abbreviation Match
            abbreviations = entry.get('abbreviations', {}).get(source_lang, [])
            if abbreviations:
                 for abbreviation in abbreviations:
                    if self._is_abbreviation_in_text(abbreviation, text, source_lang):
                         matches.append(self._make_match(entry, source_term, target_term, 'abbreviation', 0.85))
                         break
            
            # 5. Partial Match
            partial_match = self._check_partial_match(source_term, text, source_lang)
            if partial_match:
                 matches.append(self._make_match(entry, source_term, target_term, partial_match.get('match_type', 'partial'), partial_match['confidence']))

        return self._deduplicate_matches(matches)

    def _make_match(self, entry, source, target, mtype, conf):
        return {
            'source_term': source,
            'target_term': target,
            'id': entry.get('entry_id', ''),
            'metadata': entry.get('raw_metadata', {}),
            'variants': entry.get('variants', {}),
            'match_type': mtype,
            'confidence': conf
        }

    def create_dynamic_glossary_prompt(self, relevant_terms: List[Dict], source_lang: str, target_lang: str) -> str:
        if not relevant_terms:
            return ""
        prompt_lines = [
            "🔍 CRITICAL GLOSSARY INSTRUCTIONS - HIGH PRIORITY 🔍",
            f"The following terms must be translated strictly according to the glossary to maintain consistency:",
            "",
            "Glossary Reference:"
        ]
        for term in relevant_terms:
            source = term['translations'][source_lang]
            target = term['translations'][target_lang]
            metadata = term.get('metadata', {})
            remarks = metadata.get('remarks', '')
            variants = term.get('variants', {}).get(source_lang, [])
            match_type = term.get('match_type', 'unknown')
            confidence = term.get('confidence', 1.0)
            
            match_info = f"[{match_type.upper()}]"
            if confidence < 1.0:
                 match_info += f" (confidence: {confidence:.1f})"
            
            prompt_lines.append(f"• {match_info} '{source}' → '{target}'")
            if variants:
                variant_list = ", ".join([f"'{v}'" for v in variants])
                prompt_lines.append(f"  Variants: {variant_list}")
            if remarks:
                 prompt_lines.append(f"  Remarks: {remarks}")
                 
        prompt_lines.extend([
            "",
            "Translation Requirements:",
            "1. The above terms must be translated strictly according to the glossary.",
            "2. For phonetic matches, use the glossary term as reference.",
            "3. Maintain consistency."
        ])
        return "\n".join(prompt_lines)

    def _check_partial_match(self, source_term: str, text: str, source_lang: str) -> Optional[Dict]:
        if len(source_term) > 3 and source_term.lower() in text:
            match_ratio = len(source_term) / len(text)
            if match_ratio > 0.3:
                return {'confidence': 0.7 + (match_ratio * 0.2)}
        fuzzy_match = self._check_fuzzy_match(source_term, text, source_lang)
        if fuzzy_match:
            return fuzzy_match
        return None

    def _check_fuzzy_match(self, source_term: str, text: str, source_lang: str) -> Optional[Dict]:
        if self.fuzzy_matching_mode == 'strict':
            return None
        text_tokens = self._tokenize_text(text, source_lang)
        source_tokens = self._tokenize_text(source_term, source_lang)
        if len(source_tokens) == 1:
            return self._check_single_word_fuzzy_match(source_term, text, source_lang)
        return self._check_multi_word_fuzzy_match(source_tokens, text_tokens, source_lang)

    def _check_single_word_fuzzy_match(self, source_term: str, text: str, source_lang: str) -> Optional[Dict]:
        if self._is_similar_word(source_term, text):
            distance = self._levenshtein_distance(source_term, text)
            max_distance = max(1, len(source_term) // 4)
            confidence = 0.6 - (distance / max_distance) * 0.3
            return {'confidence': confidence, 'match_type': 'fuzzy'}
        return None

    def _check_multi_word_fuzzy_match(self, source_tokens: List[str], text_tokens: List[str], source_lang: str) -> Optional[Dict]:
        matched_tokens = 0
        total_source_tokens = len(source_tokens)
        for source_token in source_tokens:
            if len(source_token) < 2: continue
            for text_token in text_tokens:
                if len(text_token) < 2: continue
                if source_token == text_token or self._is_similar_word(source_token, text_token):
                    matched_tokens += 1
                    break
        if matched_tokens > 0:
            match_ratio = matched_tokens / total_source_tokens
            if match_ratio > 0.5:
                confidence = 0.3 + (match_ratio * 0.3)
                return {'confidence': confidence, 'match_type': 'fuzzy'}
        return None

    def _tokenize_text(self, text: str, lang: str) -> List[str]:
        if lang in ['zh-CN', 'zh-TW', 'ja', 'ko']:
            return list(text)
        return re.findall(r'\w+', text.lower())

    def _is_similar_word(self, word1: str, word2: str) -> bool:
        if len(word1) < 3 or len(word2) < 3: return False
        distance = self._levenshtein_distance(word1, word2)
        max_distance = max(1, len(word1) // 4)
        return distance <= max_distance

    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        if len(s1) < len(s2): return self._levenshtein_distance(s2, s1)
        if len(s2) == 0: return len(s1)
        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        return previous_row[-1]

    def _is_abbreviation_in_text(self, abbreviation: str, text: str, source_lang: str) -> bool:
        if source_lang in ['en', 'fr', 'de', 'es']:
            pattern = r'\b' + re.escape(abbreviation.lower()) + r'\b'
            return bool(re.search(pattern, text.lower()))
        else:
            text_words = text.split()
            return abbreviation.lower() in [word.lower() for word in text_words]

    def _deduplicate_matches(self, matches: List[Dict]) -> List[Dict]:
        unique_matches = {}
        for match in matches:
            match_id = match['id']
            if match_id not in unique_matches or match['confidence'] > unique_matches[match_id]['confidence']:
                unique_matches[match_id] = match
        return list(unique_matches.values())
        
    async def get_glossary_stats(self) -> Dict[str, Any]:
        """Async: Get glossary statistics for dashboard."""
        try:
            async for session in self.db_manager.get_async_session():
                # select game_id, count(*) from glossary group by game_id
                stmt = select(Glossary.game_id, func.count(Glossary.glossary_id).label('count')).group_by(Glossary.game_id)
                results = await session.execute(stmt)
                rows = results.all()
                
                game_distribution = [{"name": row[0], "value": row[1]} for row in rows]
                
                return {
                    "game_distribution": game_distribution
                }
        except Exception as e:
            logger.error(f"Failed to get glossary stats: {e}")
            return {"game_distribution": []}

    def set_fuzzy_matching_mode(self, mode: str):
        if mode in ['strict', 'loose']:
            self.fuzzy_matching_mode = mode
            logger.info(f"Fuzzy matching mode set to {mode}")
        else:
            self.fuzzy_matching_mode = 'loose'

glossary_manager = GlossaryManager()
