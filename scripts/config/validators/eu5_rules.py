# scripts/config/validators/eu5_rules.py

RULES = {
  "game_id": "6",
  "game_name": "Europa Universalis V",
  "rules": [
    {
      "name": "non_ascii_in_data_function_identifier",
      "check_function": "banned_chars",
      "pattern": r"\[([^\]]+)\]",
      "level": "error",
      "message_key": "validation_eu5_data_function_identifier_non_ascii",
      "params": {
        "capture_group": 1,
        "details_key": "validation_eu5_data_function_details"
      }
    },
    {
      "name": "non_ascii_in_variable_key",
      "check_function": "banned_chars",
      "pattern": r"\$([^\$]+)\$",
      "level": "error",
      "message_key": "validation_eu5_variable_key_non_ascii",
      "params": {
        "capture_group": 1,
        "details_key": "validation_eu5_variable_details"
      }
    },
    {
      "name": "non_ascii_in_icon_tag_key",
      "check_function": "banned_chars",
      "pattern": r"@([^!]+)!",
      "level": "error",
      "message_key": "validation_eu5_icon_tag_key_non_ascii",
      "params": {
        "capture_group": 1,
        "details_key": "validation_eu5_icon_details"
      }
    },
    {
      "name": "formatting_tags",
      "check_function": "formatting_tags",
      "pattern": r"#([a-zA-Z_][a-zA-Z0-9_]*)",
      "level": "warning",
      "message_key": "validation_eu5_formatting_missing_space",
      "params": {
        "no_space_required_tags": [],
        "unknown_tag_error_key": "validation_eu5_unknown_formatting",
        "unsupported_formatting_details_key": "validation_eu5_unsupported_formatting",
        "missing_space_details_key": "validation_eu5_missing_space_details"
      }
    },
    {
      "name": "non_ascii_in_formatting_tag_key",
      "check_function": "banned_chars",
      "pattern": r'#([^\s!#;]+)',
      "level": "warning",
      "message_key": "validation_eu5_formatting_tag_key_non_ascii",
      "params": {
        "capture_group": 1,
        "details_key": "validation_eu5_unsupported_formatting"
      }
    },
    {
      "name": "mismatched_formatting_tags",
      "check_function": "mismatched_tags",
      "pattern": r"",
      "level": "warning",
      "message_key": "validation_eu5_mismatched_tags",
      "params": {
        "start_tag_pattern": r"#[a-zA-Z_][a-zA-Z0-9_]*\s",
        "end_tag_string": "#!",
        "details_key": "validation_eu5_mismatched_tags_details"
      }
    }
  ]
}
