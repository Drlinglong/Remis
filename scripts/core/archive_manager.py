# scripts/core/archive_manager.py
import sqlite3
import os
import logging
import hashlib
from typing import Dict, List, Optional, Tuple, Any
import json

from scripts.utils import i18n
from scripts.app_settings import PROJECT_ROOT, MODS_CACHE_DB_PATH

class ArchiveManager:
    """
    管理模组翻译结果的归档，与 mods_cache.sqlite 数据库交互。
    """
    def __init__(self):
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def connection(self) -> Optional[sqlite3.Connection]:
        """Lazy load database connection."""
        if self._conn is None:
            self.initialize_database()
        return self._conn

    def initialize_database(self) -> bool:
        """Initializes the database connection. Returns True on success, False on failure."""
        if self._conn:
            return True
        try:
            os.makedirs(os.path.dirname(MODS_CACHE_DB_PATH), exist_ok=True)
            self._conn = sqlite3.connect(MODS_CACHE_DB_PATH, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._create_tables(self._conn)
            logging.info(i18n.t("log_info_db_connected", path=MODS_CACHE_DB_PATH))
            return True
        except Exception as e:
            logging.error(i18n.t("log_error_db_connect", error=e))
            self._conn = None
            return False

    def _create_tables(self, conn: sqlite3.Connection):
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS mods (mod_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        cursor.execute("CREATE TABLE IF NOT EXISTS mod_identities (identity_id INTEGER PRIMARY KEY AUTOINCREMENT, mod_id INTEGER NOT NULL, remote_file_id TEXT NOT NULL UNIQUE, FOREIGN KEY (mod_id) REFERENCES mods (mod_id))")
        cursor.execute("CREATE TABLE IF NOT EXISTS source_versions (version_id INTEGER PRIMARY KEY AUTOINCREMENT, mod_id INTEGER NOT NULL, snapshot_hash TEXT NOT NULL UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (mod_id) REFERENCES mods (mod_id))")
        
        # [MODIFIED] Unique constraint includes file_path to support duplicate keys in different files
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS source_entries (
                source_entry_id INTEGER PRIMARY KEY AUTOINCREMENT, 
                version_id INTEGER NOT NULL, 
                entry_key TEXT NOT NULL, 
                source_text TEXT NOT NULL, 
                file_path TEXT DEFAULT '',
                UNIQUE(version_id, file_path, entry_key), 
                FOREIGN KEY (version_id) REFERENCES source_versions (version_id)
            )
        """)
        cursor.execute("CREATE TABLE IF NOT EXISTS translated_entries (translated_entry_id INTEGER PRIMARY KEY AUTOINCREMENT, source_entry_id INTEGER NOT NULL, language_code TEXT NOT NULL, translated_text TEXT NOT NULL, last_translated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(source_entry_id, language_code), FOREIGN KEY (source_entry_id) REFERENCES source_entries (source_entry_id))")
        
        # [MIGRATION] If old unique constraint exists without file_path, we might need to recreate it
        # But for this local cache, we'll just check if the column exists (handled in create_source_version)
        conn.commit()

    def get_or_create_mod_entry(self, mod_name: str, remote_file_id: str) -> Optional[int]:
        """阶段一: 根据 remote_file_id 查询或创建 mod 记录，返回内部 mod_id"""
        if not self.connection: return None

        cursor = self.connection.cursor()
        try:
            # Check by name first to avoid duplicates if remote_id changes or isn't used consistently
            cursor.execute("SELECT mod_id FROM mods WHERE name = ?", (mod_name,))
            result = cursor.fetchone()
            if result:
                return result['mod_id']

            cursor.execute("INSERT OR IGNORE INTO mods (name) VALUES (?)", (mod_name,))
            cursor.execute("SELECT mod_id FROM mods WHERE name = ?", (mod_name,))
            mod_id_result = cursor.fetchone()
            if not mod_id_result:
                 raise Exception("Failed to retrieve mod_id after insertion.")
            mod_id = mod_id_result['mod_id']

            # Optional: Link remote_file_id if provided
            if remote_file_id:
                cursor.execute("INSERT OR IGNORE INTO mod_identities (mod_id, remote_file_id) VALUES (?, ?)", (mod_id, remote_file_id))

            self.connection.commit()
            return mod_id
        except Exception as e:
            logging.error(i18n.t("log_error_db_get_create_mod_id", error=e))
            self.connection.rollback()
            return None

    def create_source_version(self, mod_id: int, all_files_data: List[Dict]) -> Optional[int]:
        """阶段二: 计算哈希，如果不存在则创建源版本快照"""
        if not self.connection: return None

        # 1. 计算总哈希
        hasher = hashlib.sha256()
        # Sort by filename to ensure consistent hash
        sorted_files = sorted(all_files_data, key=lambda x: x['filename'])
        for file_data in sorted_files:
            # Use texts_to_translate for hash
            for text in file_data.get('texts_to_translate', []):
                hasher.update(text.encode('utf-8'))
        snapshot_hash = hasher.hexdigest()

        cursor = self.connection.cursor()
        try:
            # 2. 检查哈希是否存在
            cursor.execute("SELECT version_id FROM source_versions WHERE snapshot_hash = ?", (snapshot_hash,))
            result = cursor.fetchone()
            if result:
                logging.info(i18n.t("log_info_source_version_exists", hash=snapshot_hash[:7], version_id=result['version_id']))
                return result['version_id']

            # 3. 创建新版本
            cursor.execute("INSERT INTO source_versions (mod_id, snapshot_hash) VALUES (?, ?)", (mod_id, snapshot_hash))
            version_id = cursor.lastrowid
            logging.info(i18n.t("log_info_created_source_version", version_id=version_id, mod_id=mod_id, hash=snapshot_hash[:7]))

            # 4. 插入所有源条目
            source_entries = []
            for file_data in all_files_data:
                # We need to store the file path somehow? The original schema didn't have file_path in source_entries.
                # It seems the original schema was key-centric, assuming unique keys across the mod version.
                # However, for the "Project" flow, we need file-based retrieval.
                # I will ADD a 'file_path' column to source_entries if it doesn't exist?
                # Or simpler: For now, I will assume keys are unique enough or I will rely on the structure.
                # Wait, the key map is needed.
                # The previous code: zip(file_data['key_map'], file_data['texts_to_translate'])
                for key_info, text in zip(file_data['key_map'], file_data['texts_to_translate']):
                    # Use full key-header block (e.g. 'key:0') as entry_key
                    if isinstance(key_info, dict):
                        # Combine key_part and potential colon part if we update QuoteExtractor
                        # For now, QuoteExtractor will be updated to include :0 in key_part
                        entry_key = key_info['key_part'].strip()
                    else:
                        entry_key = str(key_info)
                    
                    source_entries.append((version_id, entry_key, text, file_data.get('filename', 'unknown')))

            # Ensure file_path column exists
            cursor.execute("PRAGMA table_info(source_entries)")
            columns = [col['name'] for col in cursor.fetchall()]
            if 'file_path' not in columns:
                cursor.execute("ALTER TABLE source_entries ADD COLUMN file_path TEXT DEFAULT ''")

            cursor.executemany("INSERT OR IGNORE INTO source_entries (version_id, entry_key, source_text, file_path) VALUES (?, ?, ?, ?)", source_entries)
            self.connection.commit()
            logging.info(i18n.t("log_info_archived_source_entries", count=len(source_entries), version_id=version_id))
            return version_id
        except Exception as e:
            logging.error(i18n.t("log_error_db_create_source_version", error=e))
            self.connection.rollback()
            return None

    def archive_translated_results(self, version_id: int, file_results: Dict[str, Any], all_files_data: List[Dict], target_lang_code: str):
        """阶段三: 将指定语言的翻译结果存入或更新到数据库"""
        if not self.connection or not version_id: return

        cursor = self.connection.cursor()
        try:
            upsert_data = []

            for filename, translated_texts in file_results.items():
                file_data = next((fd for fd in all_files_data if fd['filename'] == filename), None)
                if not file_data or not translated_texts: continue

                for key_info, translated_text in zip(file_data['key_map'], translated_texts):
                    # Fix: key_map is a list of dicts like {'key_part': 'remis.1.t', 'line_num': 5}
                    # We need to extract the actual key string
                    entry_key = key_info['key_part'].strip() if isinstance(key_info, dict) else str(key_info)
                    
                    # Normalize: ensure no trailing colon (legacy consistency)
                    if entry_key.endswith(":"):
                        entry_key = entry_key[:-1].strip()
                
                    # Find source entry
                    # [FIX] Relax query to handle legacy entries where file_path might be empty
                    cursor.execute(
                        "SELECT source_entry_id FROM source_entries WHERE version_id = ? AND entry_key = ? AND (file_path = ? OR file_path = '' OR file_path IS NULL)",
                        (version_id, entry_key, filename)
                    )
                    row = cursor.fetchone()
                    
                    # [FALLBACK] If not found and key has :version, try without version (for legacy compatibility)
                    if not row and ":" in entry_key:
                        pure_key = entry_key.split(':')[0]
                        cursor.execute(
                            "SELECT source_entry_id FROM source_entries WHERE version_id = ? AND entry_key = ? AND (file_path = ? OR file_path = '' OR file_path IS NULL)",
                            (version_id, pure_key, filename)
                        )
                        row = cursor.fetchone()

                    if row:
                        source_entry_id = row['source_entry_id']
                        upsert_data.append((source_entry_id, target_lang_code, translated_text))

            if not upsert_data:
                return

            cursor.executemany("""
                INSERT INTO translated_entries (source_entry_id, language_code, translated_text)
                VALUES (?, ?, ?)
                ON CONFLICT(source_entry_id, language_code) DO UPDATE SET
                translated_text = excluded.translated_text,
                last_translated_at = CURRENT_TIMESTAMP
            """, upsert_data)

            self.connection.commit()
            logging.info(i18n.t("log_info_archived_updated_translations", count=len(upsert_data), lang_code=target_lang_code))

        except Exception as e:
            logging.error(i18n.t("log_error_db_archive_results", lang_code=target_lang_code, error=e))
            self.connection.rollback()

    # --- New Methods for Project/Proofreading Flow ---

    def get_entries(self, mod_name: str, file_path: str, language: str = "zh-CN") -> List[Dict[str, Any]]:
        """
        Retrieves merged source and translation entries for a specific file in the latest version of a mod.
        Includes a 'Deep Search' fallback to find translations from previous versions if the current version lacks them.
        """
        if not self.connection: return []
        cursor = self.connection.cursor()

        # 1. Get Mod ID
        cursor.execute("SELECT mod_id FROM mods WHERE name = ?", (mod_name,))
        mod_row = cursor.fetchone()
        if not mod_row: return []
        mod_id = mod_row['mod_id']

        # 2. Get Latest Version ID
        cursor.execute("SELECT version_id FROM source_versions WHERE mod_id = ? ORDER BY created_at DESC LIMIT 1", (mod_id,))
        ver_row = cursor.fetchone()
        if not ver_row: return []
        version_id = ver_row['version_id']

        # 3. Fetch Source Entries for CURRENT Version
        filename = os.path.basename(file_path)
        
        # We fetch source entries first. 
        # Note: We select entry_key to map them later.
        cursor.execute("SELECT source_entry_id, entry_key, source_text FROM source_entries WHERE version_id = ? AND file_path = ?", (version_id, filename))
        source_rows = cursor.fetchall()
        
        if not source_rows:
            return []

        # 4. Deep Search for Translations
        # Instead of a simple JOIN which only checks the current source_entry_id,
        # we want to match valid translations for these Keys and FilePath from ANY source_entry_id (previous versions included).
        
        # Optimize: Get all translations for this file_path and language from the DB derived from ANY version of this mod
        # We can filter by file_path and language.
        
        # Get mapping: entry_key -> translated_text (latest by timestamp)
        # We join back to source_entries to get the key.
        # We filter source_entries by file_path and mod_id (implicit via keys unique to files? No, file_path is safer)
        # Wait, source_entries link to version, version links to mod.
        
        deep_query = '''
            SELECT s.entry_key, t.translated_text
            FROM translated_entries t
            JOIN source_entries s ON t.source_entry_id = s.source_entry_id
            JOIN source_versions v ON s.version_id = v.version_id
            WHERE v.mod_id = ? AND s.file_path = ? AND t.language_code = ?
            ORDER BY t.last_translated_at ASC
        '''
        # We convert to dict, keeping the LAST one (latest date due to ASC order, or we can use DESC and ignore subsequent)
        # Actually ORDER BY ASC means the last one in the loop is the latest one.
        
        cursor.execute(deep_query, (mod_id, filename, language))
        trans_rows = cursor.fetchall()
        
        translation_map = {row['entry_key']: row['translated_text'] for row in trans_rows}

        results = []
        for s_row in source_rows:
            key = s_row['entry_key']
            original = s_row['source_text']
            # Try to get translation from the global map
            translation = translation_map.get(key, None)
            
            results.append({
                "key": key,
                "original": original,
                "translation": translation
            })
            
        return results

    def update_translations(self, mod_name: str, file_path: str, entries: List[Dict[str, Any]], language: str = "zh-CN"):
        """
        Updates translations for specific keys.
        """
        if not self.connection: return
        cursor = self.connection.cursor()

        # Get Mod/Version (Similar to get_entries)
        cursor.execute("SELECT mod_id FROM mods WHERE name = ?", (mod_name,))
        mod_row = cursor.fetchone()
        if not mod_row: return
        mod_id = mod_row['mod_id']

        cursor.execute("SELECT version_id FROM source_versions WHERE mod_id = ? ORDER BY created_at DESC LIMIT 1", (mod_id,))
        ver_row = cursor.fetchone()
        if not ver_row: return
        version_id = ver_row['version_id']

        filename = os.path.basename(file_path)

        for entry in entries:
            key = entry['key']
            translation = entry.get('translation', '')

            # Find source entry ID
            cursor.execute("SELECT source_entry_id FROM source_entries WHERE version_id=? AND file_path=? AND entry_key=?",
                           (version_id, filename, key))
            row = cursor.fetchone()

            if row:
                source_entry_id = row['source_entry_id']
                # Upsert translation
                cursor.execute('''
                    INSERT INTO translated_entries (source_entry_id, language_code, translated_text)
                    VALUES (?, ?, ?)
                    ON CONFLICT(source_entry_id, language_code) DO UPDATE SET
                    translated_text=excluded.translated_text,
                    last_translated_at=CURRENT_TIMESTAMP
                ''', (source_entry_id, language, translation))

        self.connection.commit()

    def close(self):
        if self._conn:
            self._conn.close()
            logging.info(i18n.t("log_info_db_connection_closed"))

# 延迟初始化的全局实例
archive_manager = ArchiveManager()
