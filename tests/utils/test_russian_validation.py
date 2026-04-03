# tests/utils/test_russian_validation.py
import pytest
from scripts.utils.post_process_validator import PostProcessValidator, ValidationLevel

def test_numeric_game_id_4_resolves_to_hoi4():
    validator = PostProcessValidator()
    resolved = validator.get_validator_by_game_id("4")
    assert resolved.game_name == "Hearts of Iron IV"

def test_hoi4_russian_no_false_positive():
    """
    Verifies that HOI4 rules NO LONGER flag Russian characters in text near tags.
    """
    validator = PostProcessValidator()
    game_id = "hoi4" # HOI4
    
    # Text from the user's issue: "у\n$VALUE|H$"
    # The 'у' is outside the tag, so it should be ignored by the technical rules.
    test_text = "у\n$VALUE|H$"
    results = validator.validate_game_text(game_id, test_text, 1, target_lang="ru")
    
    errors = [r for r in results if r.level.value == 'error']
    assert len(errors) == 0, f"False positive detected: {errors[0].details if errors else ''}"


def test_hoi4_russian_inside_tag_fails():
    """
    Verifies that Russian characters INSIDE a tag ARE flagged as errors.
    According to Wiki, these must be ASCII identifiers.
    """
    validator = PostProcessValidator()
    game_id = "hoi4" # HOI4
    
    # Russian 'Д' inside a namespace tag
    test_text = "[Д.GetName]" 
    results = validator.validate_game_text(game_id, test_text, 1, target_lang="zh-CN")
    assert len(results) > 0
    assert "Д" in results[0].details

    # Russian 'П' inside a nested string tag - NOW ALLOWED in HOI4!
    test_text = "$ПЕРЕМЕННАЯ$"
    results = validator.validate_game_text(game_id, test_text, 1, target_lang="zh-CN")
    # Check that there are NO errors for this specific nested string
    nested_errors = [r for r in results if r.level == ValidationLevel.ERROR and "nested_strings" in r.message] # Wait, message might be different
    # Better: just check that it's valid now
    assert len(results) == 0, f"Nested string should be allowed now: {results[0].details if results else ''}"

def test_hoi4_spaces_in_tag_prevents_match():
    """
    Tests that if brackets contain spaces, they are not treated as 
    technical identifiers (thus allowing them to contain Russian).
    In HOI4, identifiers [Root.GetName] don't have spaces.
    """
    validator = PostProcessValidator()
    game_id = "hoi4" # HOI4
    
    # This shouldn't match the namespace rule because of the spaces.
    test_text = "[Это просто текст в скобках]" 
    results = validator.validate_game_text(game_id, test_text, 1, target_lang="ru")
    
    # Should be valid (no technical tag found)
    assert len(results) == 0

if __name__ == "__main__":
    test_hoi4_russian_no_false_positive()
    test_hoi4_russian_inside_tag_fails()
    test_hoi4_spaces_in_tag_prevents_match()
    print("Tests PASSED!")
