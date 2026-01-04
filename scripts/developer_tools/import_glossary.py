# scripts/developer_tools/import_glossary.py
"""
导入单个词典文件到SQLite数据库（增量导入，不会覆盖现有数据）
用法: python -m scripts.developer_tools.import_glossary <game_id> <json_file>
"""
import sqlite3
import os
import json
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Ensure we can find app_settings
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from scripts import app_settings

# Use the correct database path from app_settings (AppData in dev, bundled in prod)
DB_PATH = app_settings.DATABASE_PATH


def import_glossary_from_json(game_id: str, json_path: str) -> bool:
    """
    将一个JSON词典文件导入到SQLite数据库
    
    Args:
        game_id: 游戏ID (如 'eu5', 'hoi4')
        json_path: JSON文件的绝对路径
    
    Returns:
        bool: 导入成功返回True
    """
    if not os.path.exists(json_path):
        logging.error(f"File not found: {json_path}")
        return False
    
    try:
        with open(json_path, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
    except Exception as e:
        logging.error(f"Failed to read JSON file: {e}")
        return False
    
    metadata = data.get('metadata', {})
    entries = data.get('entries', [])
    
    if not entries:
        logging.warning("No entries found in the JSON file.")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 确定词典名称
        filename = os.path.basename(json_path)
        is_main = 1 if filename == 'glossary.json' else 0
        
        glossary_name = metadata.get('name')
        if not glossary_name:
            if is_main:
                glossary_name = f"{game_id.capitalize()} Main Glossary"
            else:
                glossary_name = filename.replace('.json', '')
        
        # 检查是否已存在
        cursor.execute(
            "SELECT glossary_id FROM glossaries WHERE game_id = ? AND name = ?",
            (game_id, glossary_name)
        )
        existing = cursor.fetchone()
        
        if existing:
            glossary_id = existing[0]
            logging.info(f"Glossary '{glossary_name}' already exists (id: {glossary_id}). Updating entries...")
            # 删除旧条目
            cursor.execute("DELETE FROM entries WHERE glossary_id = ?", (glossary_id,))
        else:
            # 插入新词典
            cursor.execute("""
                INSERT INTO glossaries (game_id, name, description, version, is_main, sources, raw_metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                game_id,
                glossary_name,
                metadata.get('description'),
                metadata.get('version'),
                is_main,
                json.dumps(metadata.get('sources', [])),
                json.dumps(metadata)
            ))
            glossary_id = cursor.lastrowid
            logging.info(f"Created new glossary '{glossary_name}' (id: {glossary_id}) for game '{game_id}'")
        
        # 插入条目
        entries_to_insert = []
        for entry in entries:
            entry_id = entry.get('id')
            if not entry_id:
                logging.warning(f"Skipping entry with no ID: {entry}")
                continue
            
            entries_to_insert.append((
                entry_id,
                glossary_id,
                json.dumps(entry.get('translations', {})),
                json.dumps(entry.get('abbreviations', {})),
                json.dumps(entry.get('variants', {})),
                json.dumps(entry.get('metadata', {}))
            ))
        
        cursor.executemany("""
            INSERT OR REPLACE INTO entries (entry_id, glossary_id, translations, abbreviations, variants, raw_metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, entries_to_insert)
        
        conn.commit()
        logging.info(f"Successfully imported {len(entries_to_insert)} entries to glossary '{glossary_name}'")
        return True
        
    except Exception as e:
        logging.error(f"Database error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def main():
    if len(sys.argv) < 3:
        print("Usage: python -m scripts.developer_tools.import_glossary <game_id> <json_file>")
        print("Example: python -m scripts.developer_tools.import_glossary eu5 data/glossary/eu5/remis_demo_eu5.json")
        sys.exit(1)
    
    game_id = sys.argv[1]
    json_path = sys.argv[2]
    
    # 支持相对路径
    if not os.path.isabs(json_path):
        json_path = os.path.join(app_settings.PROJECT_ROOT, json_path)
    
    success = import_glossary_from_json(game_id, json_path)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
