# Temporary script to check glossary status
import sqlite3
from scripts import app_settings
from scripts.core.glossary_manager import glossary_manager

# Connect to database directly
conn = sqlite3.connect(app_settings.DATABASE_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print(f"=== Database Path: {app_settings.DATABASE_PATH} ===")

print("\n=== EU5 Glossaries in Database ===")
cur.execute("SELECT * FROM glossaries WHERE game_id = 'eu5'")
rows = cur.fetchall()
for row in rows:
    print(dict(row))

print("\n=== Entries Count in EU5 Glossaries ===")
for row in rows:
    glossary_id = row['glossary_id']
    cur.execute("SELECT COUNT(*) as count FROM entries WHERE glossary_id = ?", (glossary_id,))
    count = cur.fetchone()['count']
    print(f"Glossary ID {glossary_id} ({row['name']}): {count} entries, is_main={row['is_main']}")

# Test glossary manager loading
print("\n=== Testing Glossary Manager Load ===")
print(f"Current in_memory_glossary before load: {len(glossary_manager.in_memory_glossary.get('entries', []))} entries")

result = glossary_manager.load_game_glossary('eu5')
print(f"load_game_glossary('eu5') returned: {result}")
print(f"Current in_memory_glossary after load: {len(glossary_manager.in_memory_glossary.get('entries', []))} entries")

# Check if get_glossary_for_translation returns anything
translation_glossary = glossary_manager.get_glossary_for_translation()
print(f"\nget_glossary_for_translation() returns: {'Entries available' if translation_glossary else 'None/Empty'}")

# Test term extraction
if glossary_manager.in_memory_glossary.get('entries'):
    print("\n=== Sample entries from loaded glossary ===")
    for entry in glossary_manager.in_memory_glossary['entries'][:5]:
        print(f"  - {entry.get('entry_id')}: {entry.get('translations')}")
    
    # Test term extraction with sample text
    print("\n=== Testing Term Extraction ===")
    test_text = ["This is Aeterna Roma and Solidus Nova for testing"]
    print(f"Test text: {test_text}")
    
    # Debug: Check what source_lang maps to in translations
    print("\n=== Entry details for matching ===")
    for entry in glossary_manager.in_memory_glossary['entries'][:3]:
        translations = entry.get('translations', {})
        source_term = translations.get('en', "")
        target_term = translations.get('zh-CN', "")
        print(f"  Entry: {entry.get('entry_id')}")
        print(f"    translations keys: {list(translations.keys())}")
        print(f"    source_term (en): '{source_term}'")
        print(f"    target_term (zh-CN): '{target_term}'")
        print(f"    source_term.lower() in test_text[0].lower(): {source_term.lower() in test_text[0].lower()}")
    
    terms = glossary_manager.extract_relevant_terms(test_text, 'en', 'zh-CN')
    print(f"\nExtracted {len(terms)} terms from test text")
    for term in terms[:5]:
        print(f"  - {term}")

conn.close()
