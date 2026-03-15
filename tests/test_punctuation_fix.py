import os
import shutil
from scripts.core.file_builder import rebuild_and_write_file

# Mock Data with Chinese Punctuation
original_lines = [
    "l_english:\n",
    ' key1:0 "原值1"\n',
]
texts_to_translate = ["原值1"]
translated_texts = ['Hello，world！This is a test：punctuation。'] # Note full-width punctuation
key_map = {
    0: {"line_num": 1, "key_part": "key1"}
}
dest_dir = "test_punct_output"
filename = "test_punct_l_english.yml"
source_lang = {"code": "zh-CN", "key": "l_simp_chinese", "name": "Chinese"}
target_lang = {"code": "en", "key": "l_english", "name": "English"}
game_profile = {"id": "vic3"}

# Setup
if os.path.exists(dest_dir):
    shutil.rmtree(dest_dir)
os.makedirs(dest_dir)

print("--- Starting Punctuation Test ---")

try:
    output_path = rebuild_and_write_file(
        original_lines,
        texts_to_translate,
        translated_texts,
        key_map,
        dest_dir,
        filename,
        source_lang,
        target_lang,
        game_profile
    )
    
    print(f"Success! File written to: {output_path}")
    
    # Verify Content
    with open(output_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
        print("\n--- Generated Content ---")
        print(content)
        
        # Check for English punctuation
        if 'Hello, world! This is a test: punctuation.' not in content:
            print("FAILED: Punctuation not converted correctly")
            print(f"Expected: Hello, world! This is a test: punctuation.")
            actual_content = content.strip().split('"')[1]
            print(f"Actual:   {actual_content}")
            raise Exception("Punctuation conversion failed")
            
    print("\nTest PASSED")

except Exception as e:
    print(f"\nTest FAILED: {e}")
    import traceback
    traceback.print_exc()

finally:
    # Cleanup
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
