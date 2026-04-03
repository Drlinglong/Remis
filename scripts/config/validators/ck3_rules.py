# scripts/config/validators/ck3_rules.py

RULES = {
  "game_id": "5",
  "game_name": "Crusader Kings III",
  "rules": [
    {
      "name": "non_ascii_in_bracket_commands",
      "check_function": "banned_chars",
      "pattern": r"\[(?!Concept)([^\]]+)\]",
      "level": "error",
      "message_key": "validation_ck3_bracket_command_non_ascii",
      "params": {
        "capture_group": 1
      }
    },
    {
      "name": "non_ascii_in_concept_function_key",
      "check_function": "banned_chars",
      "pattern": r"\[Concept\('([^']*)',",
      "level": "error",
      "message_key": "validation_ck3_concept_function_key_non_ascii",
      "params": {
        "capture_group": 1
      }
    },
    {
      "name": "non_ascii_in_trait_or_title_key",
      "check_function": "banned_chars",
      "pattern": r"\[(?:GetTrait|GetTitleByKey)'([^']*)'\]",
      "level": "error",
      "message_key": "validation_ck3_trait_or_title_key_non_ascii",
      "params": {
        "capture_group": 1
      }
    },
    {
      "name": "non_ascii_in_dollar_var_key",
      "check_function": "banned_chars",
      "pattern": r"\$([^$\s]+)\$",
      "level": "error",
      "message_key": "validation_ck3_dollar_var_key_non_ascii",
      "params": {
        "capture_group": 1
      }
    },
    {
      "name": "non_ascii_in_icon_tag_key",
      "check_function": "banned_chars",
      "pattern": r"@([^!]+)!",
      "level": "error",
      "message_key": "validation_ck3_icon_tag_key_non_ascii",
      "params": {
        "capture_group": 1
      }
    },
    {
      "name": "mismatched_formatting_tags",
      "check_function": "mismatched_tags",
      "level": "warning",
      "message_key": "validation_ck3_formatting_tags_mismatch",
      "params": {
        "start_tag_pattern": r"#[a-zA-Z0-9_;]+",
        "end_tag_string": "#!",
        "details_key": "validation_generic_color_tags_count"
      }
    },
    {
      "name": "formatting_tags",
      "check_function": "formatting_tags",
      "pattern": r"#([a-zA-Z0-9_]+)",
      "level": "warning",
      "message_key": "validation_ck3_unknown_formatting",
      "params": {
        
        "no_space_required_tags": [],
        "unknown_tag_error_key": "validation_ck3_unknown_formatting",
        "unsupported_formatting_details_key": "validation_ck3_unsupported_formatting",
        "missing_space_details_key": "validation_ck3_formatting_found_at"
      }
    }
  ]
}
