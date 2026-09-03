from pathlib import Path

from scripts.core.file_builder import rebuild_and_write_file

def test_rebuild_converts_full_width_punctuation(tmp_path):
    original_lines = [
        "l_english:\n",
        ' key1:0 "原值1"\n',
    ]
    texts_to_translate = ["原值1"]
    translated_texts = ["Hello，world！This is a test：punctuation。"]
    key_map = {0: {"line_num": 1, "key_part": "key1"}}
    source_lang = {"code": "zh-CN", "key": "l_simp_chinese", "name": "Chinese"}
    target_lang = {"code": "en", "key": "l_english", "name": "English"}
    game_profile = {"id": "vic3"}

    output_path = rebuild_and_write_file(
        original_lines,
        texts_to_translate,
        translated_texts,
        key_map,
        str(tmp_path),
        "test_punct_l_english.yml",
        source_lang,
        target_lang,
        game_profile,
    )

    content = Path(output_path).read_text(encoding="utf-8-sig")

    assert "Hello, world! This is a test: punctuation." in content
