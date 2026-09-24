"""Manual validator examples, outside the production validator implementation."""
import logging
from scripts.utils.post_process_validator import PostProcessValidator

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    try:
        main_validator = PostProcessValidator()
        print("\n--- Testing Stellaris Validator ---")
        main_validator.validate_game_text("2", "This has mismatched §Ycolor§!", 2)
        main_validator.validate_game_text("2", "This has a bad variable $中文变量$ inside.", 3)
        print("\n--- Testing Victoria 3 Validator ---")
        # Test with dynamic tags
        main_validator.validate_game_text("1", "This has #custom_tag now.", 4, dynamic_valid_tags=["custom_tag"])
        main_validator.validate_game_text("1", "This has a [中文概念].", 5)
        # Test Parity Match Check
        res = main_validator.validate_game_text("1", "Translation without variable.", source_text="This has a $pop$ variable.", line_number=6)
        print(f"Parity Check (expected fail): {res[0].message if res else 'Passed (error!)'} - {res[0].details if res else ''}")
        res2 = main_validator.validate_game_text("1", "Translation with $pop$ extra $pop$.", source_text="This has a $pop$ variable.", line_number=7)
        print(f"Parity Check (extra var): {res2[0].message if res2 else 'Passed (error!)'} - {res2[0].details if res2 else ''}")

        print("\n--- Testing CK3 Validator (New Rule) ---")
        main_validator.validate_game_text("5", "This contains a #totally_fake_command that should be caught.", 6)
        # Test dynamic tag override for CK3
        main_validator.validate_game_text("5", "This #totally_fake_command is now valid.", 7, dynamic_valid_tags=["totally_fake_command"])

        print("\n--- Testing Key Validation ---")
        main_validator.validate_entry("1", "valid_key", "Valid value")
        main_validator.validate_entry("1", "invalid key with spaces", "Value")

    except Exception as e:
        print(f"An error occurred during testing: {e}")
        print("Please ensure all Python rule files are present and correctly formatted.")
