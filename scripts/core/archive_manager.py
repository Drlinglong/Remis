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
        cursor.execute("CREATE TABLE IF NOT EXISTS source_versions (version_id INTEGER PRIMARY KEY AUTOINCREMENT, mod_id INTEGER NOT NULL, snapshot_hash TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (mod_id) REFERENCES mods (mod_id), UNIQUE(mod_id, snapshot_hash))")
        
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
        
        # [MIGRATION] Add indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_versions_mod_id ON source_versions(mod_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entries_version_id ON source_entries(version_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entries_key ON source_entries(entry_key)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trans_source_entry ON translated_entries(source_entry_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trans_lang ON translated_entries(language_code)")
        
        self._migrate_legacy_schema(conn)
        self._normalize_legacy_file_paths(conn)
        conn.commit()

    def _migrate_legacy_schema(self, conn: sqlite3.Connection):
        cursor = conn.cursor()

        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='source_versions'")
        source_versions_sql_row = cursor.fetchone()
        source_versions_sql = source_versions_sql_row[0] if source_versions_sql_row else ""

        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='source_entries'")
        source_entries_sql_row = cursor.fetchone()
        source_entries_sql = source_entries_sql_row[0] if source_entries_sql_row else ""

        needs_source_versions_migration = (
            source_versions_sql
            and "snapshot_hash TEXT NOT NULL UNIQUE" in source_versions_sql
        )
        needs_source_entries_migration = (
            source_entries_sql
            and "UNIQUE(version_id, file_path, entry_key)" not in source_entries_sql
        )

        if not needs_source_versions_migration and not needs_source_entries_migration:
            return

        logging.info("[Archive] Migrating legacy archive schema to incremental-safe constraints.")
        cursor.execute("PRAGMA foreign_keys = OFF")

        try:
            if needs_source_versions_migration:
                cursor.execute("""
                    CREATE TABLE source_versions_migrated (
                        version_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        mod_id INTEGER NOT NULL,
                        snapshot_hash TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (mod_id) REFERENCES mods (mod_id),
                        UNIQUE(mod_id, snapshot_hash)
                    )
                """)
                cursor.execute("""
                    INSERT INTO source_versions_migrated (version_id, mod_id, snapshot_hash, created_at)
                    SELECT version_id, mod_id, snapshot_hash, created_at
                    FROM source_versions
                    ORDER BY version_id
                """)
                cursor.execute("DROP TABLE source_versions")
                cursor.execute("ALTER TABLE source_versions_migrated RENAME TO source_versions")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_versions_mod_id ON source_versions(mod_id)")

            if needs_source_entries_migration:
                cursor.execute("""
                    CREATE TABLE source_entries_migrated (
                        source_entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        version_id INTEGER NOT NULL,
                        entry_key TEXT NOT NULL,
                        source_text TEXT NOT NULL,
                        file_path TEXT DEFAULT '',
                        UNIQUE(version_id, file_path, entry_key),
                        FOREIGN KEY (version_id) REFERENCES source_versions (version_id)
                    )
                """)

                cursor.execute("PRAGMA table_info(source_entries)")
                source_entry_columns = {row["name"] for row in cursor.fetchall()}
                file_path_expr = "COALESCE(file_path, '')" if "file_path" in source_entry_columns else "''"

                cursor.execute(f"""
                    INSERT INTO source_entries_migrated (
                        source_entry_id, version_id, entry_key, source_text, file_path
                    )
                    SELECT
                        source_entry_id,
                        version_id,
                        entry_key,
                        source_text,
                        {file_path_expr}
                    FROM source_entries
                    ORDER BY source_entry_id
                """)
                cursor.execute("DROP TABLE source_entries")
                cursor.execute("ALTER TABLE source_entries_migrated RENAME TO source_entries")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_entries_version_id ON source_entries(version_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_entries_key ON source_entries(entry_key)")

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.execute("PRAGMA foreign_keys = ON")

    def _normalize_legacy_file_paths(self, conn: sqlite3.Connection):
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE source_entries
            SET file_path = TRIM(REPLACE(COALESCE(file_path, ''), '\\', '/'))
            WHERE file_path IS NOT NULL
              AND file_path != TRIM(REPLACE(COALESCE(file_path, ''), '\\', '/'))
            """
        )

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
    def get_mod_id_by_remote_id(self, remote_file_id: str) -> Optional[int]:
        """Looks up a mod_id using the remote_file_id (project_id)."""
        if not self.connection: return None
        cursor = self.connection.cursor()
        cursor.execute("SELECT mod_id FROM mod_identities WHERE remote_file_id = ?", (remote_file_id,))
        result = cursor.fetchone()
        return result['mod_id'] if result else None

    def get_latest_version(
        self,
        mod_name: str = None,
        mod_id: int = None,
        project_id: str = None,
        language: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves the latest version of a mod. 
        Priority: project_id (remote_file_id) > mod_id > mod_name.
        """
        if not self.connection: return None
        cursor = self.connection.cursor()

        # 1. Try by Project ID (remote_file_id)
        if project_id:
            mod_id = self.get_mod_id_by_remote_id(project_id)
            if mod_id:
                logging.info(f"[Archive] Found mod_id {mod_id} by project_id {project_id}")
        
        # 2. Try by Exact Name
        if not mod_id and mod_name:
            cursor.execute("SELECT mod_id FROM mods WHERE name = ?", (mod_name.strip(),))
            row = cursor.fetchone()
            if row:
                mod_id = row['mod_id']
                logging.info(f"[Archive] Found mod_id {mod_id} by exact name: '{mod_name}'")
                
        # 3. Fuzzy match fallback by name (trimmed, case-insensitive)
        if not mod_id and mod_name:
            cursor.execute("SELECT mod_id, name FROM mods WHERE name LIKE ?", (f"%{mod_name.strip()}%",))
            rows = cursor.fetchall()
            if rows:
                mod_id = rows[0]['mod_id']
                logging.warning(f"[Archive] Fuzzy match for '{mod_name}' found mod_id {mod_id} (Actual name in DB: '{rows[0]['name']}')")

        if not mod_id:
            logging.error(f"[Archive] Could not find any archive for project_id={project_id}, mod_name='{mod_name}'")
            return None

        ver_row = self._get_latest_version_row(cursor, mod_id, language=language, require_translations=True)
        if not ver_row:
            ver_row = self._get_latest_version_row(cursor, mod_id, require_translations=False)
        if not ver_row:
            logging.error(f"[Archive] Found mod_id {mod_id} but it has NO source_versions!")
            return None
        
        return {
            "id": ver_row['version_id'],
            "created_at": ver_row['created_at'],
            "last_translation_at": ver_row['last_translation_at'] if 'last_translation_at' in ver_row.keys() else None,
            "translated_count": ver_row['translated_count'] if 'translated_count' in ver_row.keys() else None,
            "language": language,
        }

    def _get_latest_version_row(
        self,
        cursor: sqlite3.Cursor,
        mod_id: int,
        language: Optional[str] = None,
        require_translations: bool = False,
    ):
        if require_translations:
            query = """
                SELECT
                    sv.version_id,
                    sv.created_at,
                    MAX(t.last_translated_at) AS last_translation_at,
                    COUNT(t.translated_entry_id) AS translated_count
                FROM source_versions sv
                JOIN source_entries s ON s.version_id = sv.version_id
                JOIN translated_entries t ON t.source_entry_id = s.source_entry_id
                WHERE sv.mod_id = ?
            """
            params: List[Any] = [mod_id]
            if language:
                query += " AND t.language_code = ?"
                params.append(language)
            query += """
                GROUP BY sv.version_id, sv.created_at
                ORDER BY last_translation_at DESC, sv.created_at DESC, translated_count DESC, sv.version_id DESC
                LIMIT 1
            """
            cursor.execute(query, tuple(params))
            return cursor.fetchone()

        cursor.execute(
            "SELECT version_id, created_at FROM source_versions WHERE mod_id = ? ORDER BY created_at DESC LIMIT 1",
            (mod_id,),
        )
        return cursor.fetchone()

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
            # 2. 检查哈希是否存在 (FOR THIS MOD)
            cursor.execute("SELECT version_id FROM source_versions WHERE mod_id = ? AND snapshot_hash = ?", (mod_id, snapshot_hash))
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
                # key_map is a dict from QuoteExtractor where keys are indices
                # file_data['texts_to_translate'] is a list of same length
                km = file_data.get('key_map', {})
                texts = file_data.get('texts_to_translate', [])
                
                for idx, text in enumerate(texts):
                    if isinstance(km, dict):
                        key_info = km.get(idx)
                    elif isinstance(km, list) and idx < len(km):
                        key_info = km[idx]
                    else:
                        key_info = None
                    
                    if isinstance(key_info, dict):
                        entry_key = key_info.get('key_part', '').strip()
                    else:
                        entry_key = str(key_info) if key_info else str(idx)
                    
                    # Normalize: ensure no trailing colon (consistency)
                    if entry_key.endswith(":"):
                        entry_key = entry_key[:-1].strip()
                    
                    entry_file_path = self._normalize_archive_file_path(
                        file_data.get('file_path') or file_data.get('filename', 'unknown')
                    )
                    source_entries.append((version_id, entry_key, text.rstrip('\r\n'), entry_file_path))

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
                normalized_filename = self._normalize_archive_file_path(filename)
                file_data = next(
                    (
                        fd for fd in all_files_data
                        if self._normalize_archive_file_path(fd.get('file_path') or fd.get('filename')) == normalized_filename
                        or self._normalize_archive_file_path(fd.get('filename')) == normalized_filename
                    ),
                    None
                )
                if not file_data or not translated_texts: continue

                km = file_data.get('key_map', {})
                archive_file_path = self._normalize_archive_file_path(
                    file_data.get('file_path') or file_data.get('filename', '')
                )
                for idx, translated_text in enumerate(translated_texts):
                    if isinstance(km, dict):
                        key_info = km.get(idx)
                    elif isinstance(km, list) and idx < len(km):
                        key_info = km[idx]
                    else:
                        key_info = None
                    
                    # Extract the actual key string
                    entry_key = key_info.get('key_part', '').strip() if isinstance(key_info, dict) else str(key_info if key_info is not None else idx)
                    
                    # Normalize: ensure no trailing colon (consistency)
                    if entry_key.endswith(":"):
                        entry_key = entry_key[:-1].strip()
                
                    # Find source entry
                    file_path_candidates = self._build_file_path_candidates(archive_file_path)
                    row = self._find_source_entry_id(cursor, version_id, entry_key, file_path_candidates)
                    
                    # [FALLBACK] If not found and key has :version, try without version (for legacy compatibility)
                    if not row and ":" in entry_key:
                        pure_key = entry_key.split(':')[0]
                        row = self._find_source_entry_id(cursor, version_id, pure_key, file_path_candidates).fetchone()

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

    def get_all_mod_names(self) -> List[str]:
        """Returns a list of all mod names in the archive."""
        if not self.connection: return []
        cursor = self.connection.cursor()
        try:
            cursor.execute("SELECT name FROM mods")
            return [row['name'] for row in cursor.fetchall()]
        except Exception:
            return []

    def detect_target_language(self, version_id: int) -> Optional[str]:
        """Detects the most common target language for a given version in the archive."""
        if not self.connection: return None
        cursor = self.connection.cursor()
        query = '''
            SELECT t.language_code, COUNT(t.language_code) as count
            FROM translated_entries t
            JOIN source_entries s ON t.source_entry_id = s.source_entry_id
            WHERE s.version_id = ?
            GROUP BY t.language_code
            ORDER BY count DESC LIMIT 1
        '''
        try:
            cursor.execute(query, (version_id,))
            row = cursor.fetchone()
            if row:
                return row['language_code']
            return None
        except Exception as e:
            logging.error(f"Failed to detect target language: {e}")
            return None

    def get_archived_languages(self, version_id: int) -> List[str]:
        """Returns a list of all target languages available for a given version in the archive."""
        if not self.connection: return []
        cursor = self.connection.cursor()
        query = '''
            SELECT DISTINCT t.language_code
            FROM translated_entries t
            JOIN source_entries s ON t.source_entry_id = s.source_entry_id
            WHERE s.version_id = ?
        '''
        try:
            cursor.execute(query, (version_id,))
            rows = cursor.fetchall()
            return [row['language_code'] for row in rows]
        except Exception as e:
            logging.error(f"Failed to get archived languages: {e}")
            return []

    def get_entries(self, mod_name: str = None, project_id: str = None, file_path: str = None, language: str = "zh-CN", limit: int = None) -> List[Dict[str, Any]]:
        """
        Retrieves merged source and translation entries. 
        Priority: project_id > mod_name.
        """
        if not self.connection: return []
        cursor = self.connection.cursor()

        # 1. Get Mod ID
        mod_id = None
        if project_id:
            mod_id = self.get_mod_id_by_remote_id(project_id)
        
        if not mod_id and mod_name:
            cursor.execute("SELECT mod_id FROM mods WHERE name = ?", (mod_name.strip(),))
            mod_row = cursor.fetchone()
            if mod_row:
                mod_id = mod_row['mod_id']
        
        if not mod_id: return []

        # 2. Get Latest Version ID
        ver_row = self._get_latest_version_row(cursor, mod_id, language=language, require_translations=True)
        if not ver_row:
            ver_row = self._get_latest_version_row(cursor, mod_id, require_translations=False)
        if not ver_row: return []
        version_id = ver_row['version_id']

        # 3. Fetch Source Entries for CURRENT Version
        if file_path:
            normalized_file_path = self._normalize_archive_file_path(file_path)
            path_candidates = self._build_file_path_candidates(normalized_file_path)
            query = (
                "SELECT source_entry_id, entry_key, source_text, file_path FROM source_entries "
                f"WHERE version_id = ? AND {self._build_file_path_where_clause(path_candidates)}"
            )
            params = (version_id, *path_candidates)
        else:
            query = "SELECT source_entry_id, entry_key, source_text, file_path FROM source_entries WHERE version_id = ?"
            params = (version_id,)

        if limit:
            query += f" LIMIT {int(limit)}"

        cursor.execute(query, params)
        source_rows = cursor.fetchall()
        
        if not source_rows:
            return []

        # 4. Deep Search for Translations (Optimized: Using version_id directly instead of join mod_id)
        # This is much faster as it uses the index on source_entries(version_id)
        deep_query = '''
            SELECT s.entry_key, t.translated_text
            FROM translated_entries t
            JOIN source_entries s ON t.source_entry_id = s.source_entry_id
            WHERE s.version_id = ? AND t.language_code = ?
        '''
        deep_params = [version_id, language]
        if file_path:
            normalized_file_path = self._normalize_archive_file_path(file_path)
            path_candidates = self._build_file_path_candidates(normalized_file_path)
            deep_query += f" AND {self._build_file_path_where_clause(path_candidates, table_alias='s')}"
            deep_params.extend(path_candidates)
        
        deep_query += " ORDER BY t.last_translated_at ASC"
        
        cursor.execute(deep_query, tuple(deep_params))
        trans_rows = cursor.fetchall()
        
        translation_map = {}
        for row in trans_rows:
            ek = row['entry_key']
            # Normalize for map lookup (strip colon)
            if ek.endswith(":"):
                ek = ek[:-1].strip()
            translation_map[ek] = row['translated_text']

        results = []
        for s_row in source_rows:
            key = s_row['entry_key']
            # Normalize the source key too
            lookup_key = key
            if lookup_key.endswith(":"):
                lookup_key = lookup_key[:-1].strip()
                
            original = s_row['source_text']
            # Try to get translation from the global map using normalized key
            translation = translation_map.get(lookup_key, None)
            
            results.append({
                "key": lookup_key, # Return normalized key
                "original": original.rstrip('\r\n') if original else "",
                "translation": translation,
                "file_path": s_row["file_path"] or ""
            })
            
        return results

    def find_global_translation(self, entry_key: str, source_text: str, language: str) -> Optional[str]:
        """
        Searches for a translation in the entire database (cross-mod) matching exactly the key and source text.
        Returns the most recent translation if found.
        """
        if not self.connection: return None
        cursor = self.connection.cursor()
        query = '''
            SELECT t.translated_text
            FROM translated_entries t
            JOIN source_entries s ON t.source_entry_id = s.source_entry_id
            WHERE s.entry_key = ? AND s.source_text = ? AND t.language_code = ?
            ORDER BY t.last_translated_at DESC LIMIT 1
        '''
        try:
            cursor.execute(query, (entry_key, source_text, language))
            row = cursor.fetchone()
            if row:
                return row['translated_text']
            
            # Fallback: Search by source text only if key doesn't match but text is exactly the same?
            # For now, let's be strict: Key + Text must match for "Smart Reuse".
            return None
        except Exception as e:
            logging.error(f"Global archive lookup failed: {e}")
            return None

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

        normalized_file_path = self._normalize_archive_file_path(file_path)
        file_path_candidates = self._build_file_path_candidates(normalized_file_path)

        for entry in entries:
            key = entry['key']
            translation = entry.get('translation', '')

            # Find source entry ID
            row = self._find_source_entry_id(cursor, version_id, key, file_path_candidates).fetchone()

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

    def _normalize_archive_file_path(self, file_path: str) -> str:
        normalized = (file_path or "").strip().replace("\\", "/")
        while normalized.startswith("./"):
            normalized = normalized[2:]
        normalized = normalized.lstrip("/")
        return normalized

    def _build_file_path_candidates(self, file_path: str) -> List[str]:
        normalized = self._normalize_archive_file_path(file_path)
        return [normalized]

    def _build_file_path_where_clause(self, candidates: List[str], table_alias: str = "") -> str:
        column = f"{table_alias}.file_path" if table_alias else "file_path"
        comparisons = [f"{column} = ?" for _ in candidates]
        comparisons.append(f"{column} IS NULL")
        return "(" + " OR ".join(comparisons) + ")"

    def _find_source_entry_id(
        self,
        cursor: sqlite3.Cursor,
        version_id: int,
        entry_key: str,
        file_path_candidates: List[str],
    ):
        query = (
            "SELECT source_entry_id FROM source_entries "
            f"WHERE version_id = ? AND entry_key = ? AND {self._build_file_path_where_clause(file_path_candidates)}"
        )
        params = (version_id, entry_key, *file_path_candidates)
        cursor.execute(query, params)
        return cursor.fetchone()

    def close(self):
        if self._conn:
            self._conn.close()
            logging.info(i18n.t("log_info_db_connection_closed"))

# 延迟初始化的全局实例
archive_manager = ArchiveManager()
