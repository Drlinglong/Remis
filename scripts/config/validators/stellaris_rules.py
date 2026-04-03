# scripts/config/validators/stellaris_rules.py

RULES = {
  "game_id": "2",
  "game_name": "Stellaris",
  "rules": [
    {
      "name": "non_ascii_in_bracket_commands",
      "check_function": "banned_chars",
      "pattern": r"\[([^\]]+)\]",
      "level": "error",
      "message_key": "validation_stellaris_bracket_command_non_ascii",
      "params": {
        "capture_group": 1
      }
    },
    # {
    #   "name": "non_ascii_in_dollar_var_key",
    #   "check_function": "banned_chars",
    #   "pattern": r"\$([^$\s]+)\$",
    #   "level": "error",
    #   "message_key": "validation_stellaris_dollar_var_key_non_ascii",
    #   "params": {
    #     "capture_group": 1
    #   }
    # },
    {
      "name": "non_ascii_in_icon_tag_key",
      "check_function": "banned_chars",
      "pattern": r"£([^£\s]+)£",
      "level": "error",
      "message_key": "validation_stellaris_icon_tag_key_non_ascii",
      "params": {
        "capture_group": 1
      }
    },
    {
      "name": "mismatched_color_tags",
      "check_function": "mismatched_tags",
      "level": "warning",
      "message_key": "validation_stellaris_color_tags_mismatch",
      "params": {
        "start_tag_pattern": r"§[a-zA-Z0-9]",
        "end_tag_string": "§!",
        "details_key": "validation_stellaris_color_tags_count"
      }
    }
  ]
}
