import sqlite3
import json
import logging
import re
import threading
from typing import Dict, List, Any, Optional

from scripts import app_settings
from scripts.utils import i18n
from scripts.utils.phonetics_engine import PhoneticsEngine

# DB_PATH is now accessed dynamically to prevent path leaks in frozen environments

class GlossaryManager:
    """游戏专用词典管理器 (SQLite 版本)"""
    
    def __init__(self):
        self._conn = None
        self._lock = threading.Lock()
        self.current_game_id: Optional[str] = None
        self.in_memory_glossary: Dict[str, Any] = {'entries': []}
        self.fuzzy_matching_mode: str = 'loose'
        self.phonetics_engine = PhoneticsEngine()
        
    @property
    def connection(self):
        """Lazy load database connection."""
        with self._lock:
            if self._conn is None:
                self._conn = self._create_connection()
        return self._conn

    def _create_connection(self):
        """创建并返回一个数据库连接"""
        db_path = app_settings.DATABASE_PATH
        try:
            conn = sqlite3.connect(db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            # Ensure text is returned as str (Unicode) in all environments
            conn.text_factory = str
            logging.info(f"Successfully connected to SQLite database at {db_path}")
            return conn
        except Exception as e:
            logging.error(f"Error connecting to database at {db_path}: {e}")
            return None

    def get_available_glossaries(self, game_id: str) -> List[Dict]:
        """查询并返回指定游戏所有可用的词典元信息"""
        if not self.connection:
            logging.error("Database connection not available.")
            return []
        
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                "SELECT glossary_id, name, description, is_main FROM glossaries WHERE game_id = ?",
                (game_id,)
            )
            glossaries = [dict(row) for row in cursor.fetchall()]
            logging.info(i18n.t("log_found_glossaries_for_game", count=len(glossaries), game_id=game_id))
            return glossaries
        except Exception as e:
            logging.error(f"Failed to get available glossaries for {game_id}: {e}")
            return []

    def get_glossary_tree_data(self) -> List[Dict]:
        """Queries the database to build a tree structure of glossaries grouped by game."""
        if not self.connection:
            logging.error("Database connection not available.")
            return []
        
        try:
            cursor = self.connection.cursor()
            # Fetch all glossaries, ordered by game_id to make grouping easy
            cursor.execute("SELECT glossary_id, name, game_id FROM glossaries ORDER BY game_id, name")
            rows = cursor.fetchall()

            tree_data = []
            current_game_id = None
            game_node = None

            for row in rows:
                if row['game_id'] != current_game_id:
                    # If there's a previous game node, add it to the list
                    if game_node:
                        tree_data.append(game_node)
                    
                    # Start a new game node
                    current_game_id = row['game_id']
                    game_node = {
                        "title": current_game_id,
                        "key": current_game_id,
                        "children": []
                    }
                
                # Add the glossary file to the current game's children
                if game_node:
                    game_node["children"].append({
                        "title": row['name'],
                        # Use a format that can be easily parsed on the frontend
                        "key": f"{row['game_id']}|{row['glossary_id']}|{row['name']}",
                        "isLeaf": True
                    })
            
            # Add the last game node if it exists
            if game_node:
                tree_data.append(game_node)
                
            return tree_data

        except Exception as e:
            logging.error(f"Failed to build glossary tree from database: {e}")
            return []

    def get_glossary_entries_paginated(self, glossary_id: int, page: int, page_size: int) -> Dict:
        """Fetches paginated entries for a given glossary_id."""
        if not self.connection:
            return {"entries": [], "totalCount": 0}

        try:
            cursor = self.connection.cursor()
            
            # Get total count
            cursor.execute("SELECT COUNT(*) FROM entries WHERE glossary_id = ?", (glossary_id,))
            total_count = cursor.fetchone()[0]
            
            # Get paginated entries
            offset = (page - 1) * page_size
            cursor.execute(
                "SELECT * FROM entries WHERE glossary_id = ? LIMIT ? OFFSET ?",
                (glossary_id, page_size, offset)
            )
            rows = cursor.fetchall()
            
            entries = []
            for row in rows:
                entry = dict(row)
                # Deserialize JSON fields
                entry['translations'] = json.loads(entry['translations']) if entry['translations'] else {}
                entry['abbreviations'] = json.loads(entry['abbreviations']) if entry['abbreviations'] else {}
                entry['variants'] = json.loads(entry['variants']) if entry['variants'] else {}
                entry['raw_metadata'] = json.loads(entry['raw_metadata']) if entry['raw_metadata'] else {}
                entries.append(entry)

            return {"entries": entries, "totalCount": total_count}

        except Exception as e:
            logging.error(f"Failed to get paginated entries for glossary {glossary_id}: {e}")
            return {"entries": [], "totalCount": 0}

    def search_glossary_entries_paginated(self, query: str, glossary_ids: List[int], page: int, page_size: int) -> Dict:
        """Searches for entries across a list of glossaries with pagination."""
        if not self.connection or not glossary_ids:
            return {"entries": [], "totalCount": 0}

        try:
            cursor = self.connection.cursor()
            
            search_query = f"%{query.lower()}%"
            placeholders = ','.join('?' for _ in glossary_ids)
            
            # Base query for counting and selecting
            base_sql = f"FROM entries WHERE glossary_id IN ({placeholders}) AND LOWER(translations) LIKE ?"
            
            # Get total count
            count_sql = f"SELECT COUNT(*) {base_sql}"
            cursor.execute(count_sql, glossary_ids + [search_query])
            total_count = cursor.fetchone()[0]
            
            # Get paginated entries
            select_sql = f"SELECT * {base_sql} LIMIT ? OFFSET ?"
            offset = (page - 1) * page_size
            cursor.execute(select_sql, glossary_ids + [search_query, page_size, offset])
            rows = cursor.fetchall()
            
            entries = []
            for row in rows:
                entry = dict(row)
                entry['translations'] = json.loads(entry['translations']) if entry['translations'] else {}
                entry['abbreviations'] = json.loads(entry['abbreviations']) if entry['abbreviations'] else {}
                entry['variants'] = json.loads(entry['variants']) if entry['variants'] else {}
                entry['raw_metadata'] = json.loads(entry['raw_metadata']) if entry['raw_metadata'] else {}
                entries.append(entry)

            return {"entries": entries, "totalCount": total_count}

        except Exception as e:
            logging.error(f"Failed to search entries: {e}")
            return {"entries": [], "totalCount": 0}

    def load_game_glossary(self, game_id: str) -> bool:
        """默认只加载指定游戏的主词典 (is_main = 1)"""
        if not self.connection:
            logging.error("Database connection not available.")
            return False
        self.current_game_id = game_id
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                "SELECT glossary_id FROM glossaries WHERE game_id = ? AND is_main = 1",
                (game_id,)
            )
            main_glossary = cursor.fetchone()

            if main_glossary:
                return self.load_selected_glossaries([main_glossary['glossary_id']])
            else:
                logging.warning(f"No main glossary found for game_id: {game_id}. No glossaries loaded.")
                self.in_memory_glossary = {'entries': []}
                return False
        except Exception as e:
            logging.error(f"Error loading main glossary for {game_id}: {e}")
            return False

    def load_selected_glossaries(self, selected_glossary_ids: List[int]) -> bool:
        """根据选定的glossary_id列表，加载并合并这些词典的条目到内存中"""
        if not self.connection:
            logging.error("Database connection not available.")
            return False
        
        if not selected_glossary_ids:
            logging.warning("No glossary IDs provided. Clearing in-memory glossary.")
            with self._lock:
                self.in_memory_glossary = {'entries': []}
            return True

        try:
            cursor = self.connection.cursor()
            placeholders = ','.join('?' for _ in selected_glossary_ids)
            query = f"SELECT * FROM entries WHERE glossary_id IN ({placeholders})"
            cursor.execute(query, selected_glossary_ids)
            rows = cursor.fetchall()
            
            new_entries = []
            for row in rows:
                entry = dict(row)
                try:
                    # Robust loading if it's already a dict (shouldn't happen with sqlite but safe)
                    if isinstance(entry['translations'], str):
                        entry['translations'] = json.loads(entry['translations'])
                except Exception as je:
                    logging.warning(f"Failed to parse translations JSON for entry {entry.get('entry_id')}: {je}")
                    continue
                
                entry['abbreviations'] = json.loads(entry['abbreviations']) if entry['abbreviations'] and isinstance(entry['abbreviations'], str) else {}
                entry['variants'] = json.loads(entry['variants']) if entry['variants'] and isinstance(entry['variants'], str) else {}
                entry['raw_metadata'] = json.loads(entry['raw_metadata']) if entry['raw_metadata'] and isinstance(entry['raw_metadata'], str) else {}
                new_entries.append(entry)
            
            with self._lock:
                self.in_memory_glossary = {'entries': new_entries}
            
            logging.info(i18n.t("log_glossary_loaded_from_selected", entries_count=len(new_entries), glossaries_count=len(selected_glossary_ids)))
            return True

        except Exception as e:
            logging.error(f"Failed to load selected glossaries: {e}")
            with self._lock:
                self.in_memory_glossary = {'entries': []}
            return False

    def add_entry(self, glossary_id: int, entry_data: Dict) -> bool:
        if not self.connection: return False
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO entries (entry_id, glossary_id, translations, abbreviations, variants, raw_metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (
                entry_data['id'],
                glossary_id,
                json.dumps(entry_data.get('translations', {})),
                json.dumps(entry_data.get('abbreviations', {})),
                json.dumps(entry_data.get('variants', {})),
                json.dumps(entry_data.get('metadata', {}))
            ))
            self.connection.commit()
            logging.info(f"Successfully added/replaced entry with id {entry_data['id']} to glossary {glossary_id}")
            return True
        except Exception as e:
            logging.error(f"Failed to add entry: {e}")
            return False

    def update_entry(self, entry_id: str, entry_data: Dict) -> bool:
        if not self.connection: return False
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
            UPDATE entries
            SET translations = ?, abbreviations = ?, variants = ?, raw_metadata = ?
            WHERE entry_id = ?
            """, (
                json.dumps(entry_data.get('translations', {})),
                json.dumps(entry_data.get('abbreviations', {})),
                json.dumps(entry_data.get('variants', {})),
                json.dumps(entry_data.get('metadata', {})),
                entry_id
            ))
            self.connection.commit()
            logging.info(f"Successfully updated entry with id {entry_id}")
            return True
        except Exception as e:
            logging.error(f"Failed to update entry {entry_id}: {e}")
            return False

    def delete_entry(self, entry_id: str) -> bool:
        if not self.connection: return False
        try:
            cursor = self.connection.cursor()
            cursor.execute("DELETE FROM entries WHERE entry_id = ?", (entry_id,))
            self.connection.commit()
            logging.info(f"Successfully deleted entry with id {entry_id}")
            return True
        except Exception as e:
            logging.error(f"Failed to delete entry {entry_id}: {e}")
            return False

    def get_glossary_for_translation(self) -> Optional[Dict]:
        return self.in_memory_glossary if self.in_memory_glossary.get('entries') else None

    def extract_relevant_terms(self, texts: List[str], source_lang: str, target_lang: str) -> List[Dict]:
        glossary = self.get_glossary_for_translation()
        if not glossary or not glossary.get('entries'):
            # [DEBUG]
            # logging.debug(f"[Glossary] No glossary loaded or empty entries. In-memory keys: {list(glossary.keys()) if glossary else 'None'}")
            return []
        
        # [DEBUG] Log extraction attempt
        logging.info(f"[Glossary] Extracting terms for {len(texts)} texts. Lang: {source_lang}->{target_lang}. Total loaded entries: {len(glossary.get('entries', []))}")

        relevant_terms = []
        all_text = " ".join(texts).lower()
        matches = self._smart_term_matching(all_text, source_lang, target_lang)
        
        # [DEBUG]
        if not matches:
             # Sample checking first entry to see why it didn't match
             first_entry = glossary['entries'][0]
             translations = first_entry.get('translations', {})
             s_term = translations.get(source_lang, "")
             logging.info(f"[Glossary] No matches found. Sample check - Entry: {first_entry.get('entry_id')}, SourceLang '{source_lang}' term: '{s_term}'. Term in Text: {s_term.lower() in all_text if s_term else 'N/A'}")

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
        
        if relevant_terms:
            logging.info(i18n.t("glossary_terms_extracted", count=len(relevant_terms), text_count=len(texts)))
        
        return relevant_terms

    def _smart_term_matching(self, text: str, source_lang: str, target_lang: str) -> List[Dict]:
        matches = []
        glossary = self.get_glossary_for_translation()
        if not glossary:
            return matches
            
        # Pre-compute text fingerprint for CJK languages to optimize loop
        text_fingerprint = ""
        is_cjk = source_lang in ['zh-CN', 'zh-TW', 'ja', 'ko']
        if is_cjk:
            # Map locale to PhoneticsEngine lang code
            pe_lang = 'zh' if 'zh' in source_lang else source_lang
            text_fingerprint = self.phonetics_engine.generate_fingerprint(text, pe_lang)

        logged_sample = False
        for entry in glossary.get('entries', []):
            translations = entry.get('translations', {})
            
            # [DEBUG] Log snippet to diagnose key mismatch
            if not logged_sample:
                 logging.info(f"[DEBUG-GLOSSARY] Matching terms. ReqSource: '{source_lang}', ReqTarget: '{target_lang}'. Entry Keys available: {list(translations.keys())}")
                 logged_sample = True

            source_term = translations.get(source_lang, "")
            target_term = translations.get(target_lang, "")
            if not source_term or not target_term:
                continue
                
            # 1. Exact Match
            if source_term.lower() in text:
                matches.append({
                    'source_term': source_term,
                    'target_term': target_term,
                    'id': entry.get('entry_id', ''),
                    'metadata': entry.get('raw_metadata', {}),
                    'variants': entry.get('variants', {}),
                    'match_type': 'exact',
                    'confidence': 1.0
                })
                continue
                
            # 2. Phonetic Match (New Tier 1 Feature)
            if is_cjk and len(source_term) > 1: # Avoid single character phonetic noise
                term_fingerprint = self.phonetics_engine.generate_fingerprint(source_term, pe_lang)
                if term_fingerprint and term_fingerprint in text_fingerprint:
                    matches.append({
                        'source_term': source_term,
                        'target_term': target_term,
                        'id': entry.get('entry_id', ''),
                        'metadata': entry.get('raw_metadata', {}),
                        'variants': entry.get('variants', {}),
                        'match_type': 'phonetic',
                        'confidence': 0.85 # High confidence for homophone match
                    })
                    # Don't continue, check other match types too? 
                    # Actually if phonetic match is found, we might still want to check variants/abbrs
                    # But usually phonetic match is strong enough to be a candidate.
                    # Let's continue to avoid duplicates if variants also match.
                    continue

            # 3. Variant Match
            variants = entry.get('variants', {}).get(source_lang, [])
            for variant in variants:
                if variant.lower() in text:
                    matches.append({
                        'source_term': source_term,
                        'target_term': target_term,
                        'id': entry.get('entry_id', ''),
                        'metadata': entry.get('raw_metadata', {}),
                        'variants': entry.get('variants', {}),
                        'match_type': 'variant',
                        'confidence': 0.9
                    })
                    break
            
            # 4. Abbreviation Match
            abbreviations = entry.get('abbreviations', {}).get(source_lang, [])
            if abbreviations:
                 for abbreviation in abbreviations:
                    if self._is_abbreviation_in_text(abbreviation, text, source_lang):
                        matches.append({
                            'source_term': source_term,
                            'target_term': target_term,
                            'id': entry.get('entry_id', ''),
                            'metadata': entry.get('raw_metadata', {}),
                            'variants': entry.get('variants', {}),
                            'match_type': 'abbreviation',
                            'confidence': 0.85
                        })
                        break
            
            # 5. Partial Match
            partial_match = self._check_partial_match(source_term, text, source_lang)
            if partial_match:
                matches.append({
                    'source_term': source_term,
                    'target_term': target_term,
                    'id': entry.get('entry_id', ''),
                    'metadata': entry.get('raw_metadata', {}),
                    'variants': entry.get('variants', {}),
                    'match_type': partial_match.get('match_type', 'partial'),
                    'confidence': partial_match['confidence']
                })
        return self._deduplicate_matches(matches)

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
            "Match Type Explanation:",
            "• EXACT: Exact match, highest priority",
            "• PHONETIC: Phonetic/Homophone match (potential typo in source)",
            "• VARIANT: Variant match, such as plural forms, synonyms, abbreviations",
            "• ABBREVIATION: Abbreviation match, such as organization abbreviations, person name abbreviations",
            "• PARTIAL: Smart partial match, automatically identifies abbreviation and full name relationships",
            "• FUZZY: Fuzzy match, tolerates spelling errors and minor differences",
            "",
            "Translation Requirements:",
            "1. The above terms must be translated strictly according to the glossary, no arbitrary changes allowed",
            "2. Variant forms of terms should also be translated to the same target language equivalent",
            "3. For phonetic matches, be aware that the source text might contain a homophone typo; use the glossary term as the correct reference.",
            "4. For abbreviation and partial match terms, choose the most appropriate translation based on context",
            "5. For fuzzy match terms, translate reasonably based on context and glossary",
            "6. Maintain consistency and accuracy of game terminology",
            "7. Term placement in sentences should be natural and appropriate",
            "8. If encountering terms not in the glossary, translate reasonably based on context",
            "",
            "Please ensure strict adherence to the above glossary reference during translation."
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
        else:
            return re.findall(r'\w+', text.lower())

    def _is_similar_word(self, word1: str, word2: str) -> bool:
        if len(word1) < 3 or len(word2) < 3:
            return False
        distance = self._levenshtein_distance(word1, word2)
        max_distance = max(1, len(word1) // 4)
        return distance <= max_distance

    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)
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
        
    def set_fuzzy_matching_mode(self, mode: str):
        if mode in ['strict', 'loose']:
            self.fuzzy_matching_mode = mode
            mode_name = i18n.t("fuzzy_mode_strict") if mode == 'strict' else i18n.t("fuzzy_mode_loose")
            logging.info(i18n.t("fuzzy_mode_set", mode=mode_name))
        else:
            logging.warning(f"Invalid fuzzy matching mode: {mode}. Using default 'loose' mode.")
            self.fuzzy_matching_mode = 'loose'

    def create_glossary_file(self, game_id: str, file_name: str) -> bool:
        """Creates a new glossary file (record) for a game."""
        if not self.connection: return False
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO glossaries (game_id, name, description, is_main)
                VALUES (?, ?, ?, 0)
            """, (game_id, file_name, f"User created glossary for {game_id}"))
            self.connection.commit()
            logging.info(f"Created new glossary file '{file_name}' for game {game_id}")
            return True
        except Exception as e:
            logging.error(f"Failed to create glossary file: {e}")
            return False

    def delete_glossary(self, glossary_id: int) -> bool:
        """Deletes an entire glossary file and all its entries."""
        if not self.connection: return False
        try:
            cursor = self.connection.cursor()
            # First delete all entries belonging to this glossary
            cursor.execute("DELETE FROM entries WHERE glossary_id = ?", (glossary_id,))
            entries_deleted = cursor.rowcount
            # Then delete the glossary itself
            cursor.execute("DELETE FROM glossaries WHERE glossary_id = ?", (glossary_id,))
            self.connection.commit()
            logging.info(f"Successfully deleted glossary {glossary_id} and {entries_deleted} entries")
            return True
        except Exception as e:
            logging.error(f"Failed to delete glossary {glossary_id}: {e}")
            return False

    def get_glossary_stats(self) -> Dict[str, Any]:
        """Returns statistics about the glossary database."""
        if not self.connection:
            return {"total_terms": 0, "game_distribution": []}
        
        try:
            cursor = self.connection.cursor()
            
            # 1. Total terms count
            cursor.execute("SELECT COUNT(*) FROM entries")
            total_terms = cursor.fetchone()[0]
            
            # 2. Distribution by game
            cursor.execute("""
                SELECT g.game_id, COUNT(e.entry_id) as term_count
                FROM glossaries g
                LEFT JOIN entries e ON g.glossary_id = e.glossary_id
                GROUP BY g.game_id
                ORDER BY term_count DESC
            """)
            rows = cursor.fetchall()
            
            game_distribution = [
                {"name": row['game_id'], "terms": row['term_count']} 
                for row in rows if row['term_count'] > 0
            ]
            
            return {
                "total_terms": total_terms,
                "game_distribution": game_distribution
            }
        except Exception as e:
            logging.error(f"Failed to get glossary stats: {e}")
            return {"total_terms": 0, "game_distribution": []}

glossary_manager = GlossaryManager()
