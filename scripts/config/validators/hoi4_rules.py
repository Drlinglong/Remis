# scripts/config/validators/hoi4_rules.py

RULES = {
  "game_id": "4",
  "game_name": "Hearts of Iron IV",
  "rules": [
    {
      "name": "non_ascii_in_namespaces",
      "check_function": "banned_chars",
      "pattern": r"\[(?!\?)([^\]\s|]+)\]",
      "level": "error",
      "message_key": "validation_hoi4_namespaces_chinese",
      "params": {
        "capture_group": 1
      }
    },
    {
      "name": "non_ascii_in_formatting_vars",
      "check_function": "banned_chars",
      "pattern": r"\[\?([^|\]\s]+)\|[^\]]*\]",
      "level": "error",
      "message_key": "validation_hoi4_formatting_vars_chinese",
      "params": {
        "capture_group": 1
      }
    },
    {
      "name": "non_ascii_in_nested_strings",
      "check_function": "banned_chars",
      "pattern": r"\$([^$\s|]+)\$",
      "level": "error",
      "message_key": "validation_hoi4_nested_strings_chinese",
      "params": {
        "capture_group": 1
      }
    },
    {
      "name": "non_ascii_in_icon_tags",
      "check_function": "banned_chars",
      "pattern": r"£([^£\s|]+)",
      "level": "error",
      "message_key": "validation_hoi4_icon_tags_chinese",
      "params": {
        "capture_group": 1
      }
    },
    {
      "name": "non_ascii_in_country_flags",
      "check_function": "banned_chars",
      "pattern": r"@([A-Z0-9]{3})",
      "level": "error",
      "message_key": "validation_hoi4_country_flags_chinese",
      "params": {
        "capture_group": 1
      }
    },
    {
      "name": "non_ascii_in_localization_formatters",
      "check_function": "banned_chars",
      "pattern": r"(\[[^|\]\s]+\|[^|\]\s]+\]|\$[^|$\s]+\|[^|$\s]+\$)",
      "level": "error",
      "message_key": "validation_hoi4_localization_formatters_chinese",
      "params": {
        "capture_group": 1
      }
    },
    {
      "name": "mismatched_color_tags",
      "check_function": "mismatched_tags",
      "level": "warning",
      "message_key": "validation_hoi4_color_tags_mismatch",
      "params": {
        "start_tag_pattern": r"§[a-zA-Z0-9]",
        "end_tag_string": "§!",
        "details_key": "validation_generic_color_tags_count"
      }
    }
  ]
}
