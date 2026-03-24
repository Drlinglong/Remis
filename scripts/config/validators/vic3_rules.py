# scripts/config/validators/vic3_rules.py

RULES = {
  "game_id": "1",
  "game_name": "Victoria 3",
  "rules": [
    {
      "name": "non_ascii_in_simple_concept",
      "check_function": "banned_chars",
      "pattern": r"\[([^\]]+)\]",
      "level": "error",
      "message_key": "validation_vic3_simple_concept_chinese",
      "params": {
        "capture_group": 1
      }
    },
    {
      "name": "non_ascii_in_concept_key",
      "check_function": "banned_chars",
      "pattern": r"\[Concept\('([^']*)',.*\)\]",
      "level": "error",
      "message_key": "validation_vic3_concept_key_chinese",
      "params": {
        "capture_group": 1
      }
    },
    {
      "name": "non_ascii_in_scope_key",
      "check_function": "banned_chars",
      "pattern": r"\[SCOPE\.[a-zA-Z]+\('([^']*)'\)\]",
      "level": "error",
      "message_key": "validation_vic3_scope_key_chinese",
      "params": {
        "capture_group": 1
      }
    },
    {
      "name": "non_ascii_in_icon_key",
      "check_function": "banned_chars",
      "pattern": r"@([^!]+)!",
      "level": "error",
      "message_key": "validation_vic3_icon_key_chinese",
      "params": {
        "capture_group": 1
      }
    },
    {
      "name": "formatting_tags",
      "check_function": "formatting_tags",
      "pattern": r"#([a-zA-Z_][a-zA-Z0-9_]*)",
      "level": "warning",
      "message_key": "validation_vic3_formatting_missing_space",
      "params": {
        
        "no_space_required_tags": ["tooltippable", "tooltip"],
        "unknown_tag_error_key": "validation_vic3_unknown_formatting",
        "unsupported_formatting_details_key": "validation_vic3_unsupported_formatting",
      }
    },
    {
      "name": "non_ascii_in_formatting_tag_key",
      "check_function": "banned_chars",
      "pattern": r'#([^\s!#;]+)',
      "level": "warning",
      "message_key": "validation_vic3_tag_key_chinese",
      "params": {
        "capture_group": 1,
        "details_key": "validation_vic3_unsupported_formatting"
      }
    },
    {
      "name": "non_ascii_in_tooltippable_key",
      "check_function": "banned_chars",
      "pattern": r"#tooltippable;tooltip:<([^>]+)>",
      "level": "error",
      "message_key": "validation_vic3_tooltippable_chinese",
      "params": {
        "capture_group": 1,
        "details_key": "validation_vic3_tooltippable_found_in"
      }
    },
    {
      "name": "non_ascii_in_nested_strings",
      "check_function": "banned_chars",
      "pattern": r"\$([^$\s|]+)\$",
      "level": "error",
      "message_key": "validation_vic3_nested_strings_chinese",
      "params": {
        "capture_group": 1
      }
    },
    {
      "name": "mismatched_color_tags",
      "check_function": "mismatched_tags",
      "level": "warning",
      "message_key": "validation_vic3_color_tags_mismatch",
      "params": {
        "start_tag_pattern": r"#[a-zA-Z0-9_]+",
        "end_tag_string": "#!",
        "details_key": "validation_generic_color_tags_count"
      }
    },
    {
      "name": "variable_parity",
      "check_function": "variable_parity",
      "level": "error",
      "message_key": "validation_vic3_variable_parity_mismatch",
      "params": {
        "patterns": [r"\$[^$\s|]+\$", r"\[[^\]]+\]"],
        "details_key": "validation_generic_variable_parity_details"
      }
    },
    {
      "name": "incorrect_color_symbol_vic3",
      "check_function": "formatting_tags",
      "pattern": r"(§[a-zA-Z0-9_]+)",
      "level": "warning",
      "message_key": "validation_vic3_incorrect_symbol_warning",
      "params": {
        "valid_tags": [],
        "unknown_tag_error_key": "validation_vic3_incorrect_symbol_warning",
        "unsupported_formatting_details_key": "validation_vic3_unsupported_formatting",
        "missing_space_details_key": "validation_vic3_formatting_found_at"
      }
    }
  ]
}
