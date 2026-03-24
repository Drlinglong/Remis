# tests/utils/test_russian_validation.py
import pytest
from scripts.utils.post_process_validator import PostProcessValidator, ValidationLevel

def test_hoi4_russian_no_false_positive():
    """
    Verifies that HOI4 rules NO LONGER flag Russian characters in text near tags.
    """
    validator = PostProcessValidator()
    game_id = "4" # HOI4
    
    # Text from the user's issue: "у\n$VALUE|H$"
    # The 'у' is outside the tag, so it should be ignored by the technical rules.
    test_text = "у\n$VALUE|H$"
    results = validator.validate_game_text(game_id, test_text, 1)
    
    errors = [r for r in results if r.level.value == 'error']
    assert len(errors) == 0, f"False positive detected: {errors[0].details if errors else ''}"

def test_hoi4_russian_inside_tag_fails():
    """
    Verifies that Russian characters INSIDE a tag ARE flagged as errors.
    According to Wiki, these must be ASCII identifiers.
    """
    validator = PostProcessValidator()
    game_id = "4" # HOI4
    
    # Russian 'Д' inside a namespace tag
    test_text = "[Д.GetName]" 
    results = validator.validate_game_text(game_id, test_text, 1)
    assert len(results) > 0
    assert "Д" in results[0].details

    # Russian 'П' inside a nested string tag
    test_text = "$ПЕРЕМЕННАЯ$"
    results = validator.validate_game_text(game_id, test_text, 1)
    assert any("П" in r.details for r in results)

def test_hoi4_spaces_in_tag_prevents_match():
    """
    Tests that if brackets contain spaces, they are not treated as 
    technical identifiers (thus allowing them to contain Russian).
    In HOI4, identifiers [Root.GetName] don't have spaces.
    """
    validator = PostProcessValidator()
    game_id = "4" # HOI4
    
    # This shouldn't match the namespace rule because of the spaces.
    test_text = "[Это просто текст в скобках]" 
    results = validator.validate_game_text(game_id, test_text, 1)
    
    # Should be valid (no technical tag found)
    assert len(results) == 0

if __name__ == "__main__":
    test_hoi4_russian_no_false_positive()
    test_hoi4_russian_inside_tag_fails()
    test_hoi4_spaces_in_tag_prevents_match()
    print("Tests PASSED!")
