# scripts/translate_i18n.py
import os
import sys
import json
import time

# Add scripts directory to path to allow importing app_settings
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.app_settings import get_api_key, load_api_keys_to_env

TARGET_LANGS = {
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "ja": "Japanese",
    "ko": "Korean",
    "pl": "Polish",
    "pt-BR": "Brazilian Portuguese",
    "tr": "Turkish"
}

def traverse_and_collect(obj, path, collected):
    if isinstance(obj, str):
        collected.append((path, obj))
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            traverse_and_collect(item, path + [idx], collected)
    elif isinstance(obj, dict):
        for key, val in obj.items():
            traverse_and_collect(val, path + [key], collected)

def traverse_and_replace(obj, path, mapping):
    key = tuple(path)
    if key in mapping:
        return mapping[key]
    
    if isinstance(obj, list):
        return [traverse_and_replace(item, path + [idx], mapping) for idx, item in enumerate(obj)]
    elif isinstance(obj, dict):
        return {k: traverse_and_replace(v, path + [k], mapping) for k, v in obj.items()}
    return obj

def translate_batch(client, texts, target_lang_name):
    prompt = f"""You are a professional localization translator. Translate the following list of frontend UI texts from English to {target_lang_name}.
Requirements:
1. Keep the exact order of the elements.
2. Keep any interpolation parameters like {{{{count}}}}, {{{{total_batches}}}}, {{{{model}}}}, etc. exactly as they are.
3. Do not change HTML tags or special formatting.
4. Return the translated texts in a JSON array of strings matching the exact input order.
5. Return ONLY a valid JSON array of strings, with no markdown code blocks or extra text.

Texts to translate:
{json.dumps(texts, ensure_ascii=False)}"""

    for attempt in range(4):
        try:
            response = client.models.generate_content(
                model='gemini-3-flash-preview',
                contents=prompt
            )
            text = response.text.strip()
            # Strip markdown code blocks if any
            if text.startswith("```"):
                lines = text.split("\n")
                if lines[0].startswith("```json") or lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines).strip()
            
            translated = json.loads(text)
            if isinstance(translated, list) and len(translated) == len(texts):
                return [str(t) for t in translated]
            else:
                print(f"Warning: Expected array of length {len(texts)}, got {len(translated) if isinstance(translated, list) else type(translated)}. Retrying...")
        except Exception as e:
            print(f"Error in batch translation attempt {attempt+1}: {e}")
            time.sleep(3)
    raise RuntimeError("Failed to translate batch after 4 attempts")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--langs', type=str, help='Comma-separated target languages')
    args = parser.parse_known_args()[0]
    
    global TARGET_LANGS
    if args.langs:
        selected = [l.strip() for l in args.langs.split(',')]
        TARGET_LANGS = {k: v for k, v in TARGET_LANGS.items() if k in selected}

    load_api_keys_to_env()
    gemini_key = get_api_key('gemini', 'GEMINI_API_KEY')
    if not gemini_key:
        print("Error: GEMINI_API_KEY not found in AppData config or environment variables.")
        sys.exit(1)
        
    from google import genai
    client = genai.Client(api_key=gemini_key)
    print("Successfully initialized Google GenAI Client!")
    
    en_file = os.path.join(os.path.dirname(__file__), 'react-ui', 'src', 'i18n', 'locales', 'en', 'translation.json')
    if not os.path.exists(en_file):
        print(f"Error: English translation file not found at {en_file}")
        sys.exit(1)
        
    with open(en_file, 'r', encoding='utf-8') as f:
        en_data = json.load(f)
        
    # Traverse and collect all strings
    collected = []
    traverse_and_collect(en_data, [], collected)
    total_strings = len(collected)
    print(f"Total strings to translate: {total_strings}")
    
    batch_size = 100
    
    for lang_code, lang_name in TARGET_LANGS.items():
        print(f"\n--- Starting translation for {lang_name} ({lang_code}) ---")
        dest_dir = os.path.join(os.path.dirname(__file__), 'react-ui', 'src', 'i18n', 'locales', game_folder := lang_code)
        os.makedirs(dest_dir, exist_ok=True)
        dest_file = os.path.join(dest_dir, 'translation.json')
        
        # Load existing progress if any
        existing_data = {}
        if os.path.exists(dest_file):
            try:
                with open(dest_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                print(f"Found existing translation file with {len(existing_data)} keys.")
            except Exception:
                pass
                
        mapping = {}
        # Collect existing translated strings to avoid duplicate work
        existing_collected = []
        traverse_and_collect(existing_data, [], existing_collected)
        existing_mapping = {tuple(p): v for p, v in existing_collected}
        
        # We need to translate elements that are NOT in existing_mapping OR are identical to English
        to_translate = []
        for path, val in collected:
            key = tuple(path)
            if key in existing_mapping and existing_mapping[key] != val:
                mapping[key] = existing_mapping[key]
            else:
                to_translate.append((path, val))
                
        print(f"Already translated (non-English value): {len(mapping)} / {total_strings}. Remaining to translate: {len(to_translate)}")
        
        if to_translate:
            for i in range(0, len(to_translate), batch_size):
                chunk = to_translate[i:i+batch_size]
                chunk_texts = [val for path, val in chunk]
                print(f"Translating batch {i//batch_size + 1} / {(len(to_translate)-1)//batch_size + 1} ({len(chunk_texts)} strings)...")
                
                translated_texts = translate_batch(client, chunk_texts, lang_name)
                
                for (path, val), trans in zip(chunk, translated_texts):
                    mapping[tuple(path)] = trans
                    
                # Save partial progress in case of crash
                reconstructed = traverse_and_replace(en_data, [], mapping)
                with open(dest_file, 'w', encoding='utf-8') as f:
                    json.dump(reconstructed, f, ensure_ascii=False, indent=2)
                
                # Sleep briefly to respect API limits
                time.sleep(1)
        else:
            print(f"All strings already translated for {lang_name} ({lang_code})!")
            
        print(f"Translation completed and saved for {lang_name} ({lang_code}) to {dest_file}")

if __name__ == '__main__':
    main()
