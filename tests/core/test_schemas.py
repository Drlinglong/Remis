import pytest
from pydantic import ValidationError
from scripts.core.schemas import TranslationResponse

def test_robust_string_flattening():
    """Test that lists wrapped in single-element lists are flattened."""
    # Normal case
    data = {"translations": ["Hello", "World"]}
    model = TranslationResponse(**data)
    assert model.translations == ["Hello", "World"]

    # Hallucinated case (single element list)
    data = {"translations": ["Hello", ["World"]]}
    model = TranslationResponse(**data)
    assert model.translations == ["Hello", "World"]

    # Mixed case
    data = {"translations": [["Start"], "Middle", ["End"]]}
    model = TranslationResponse(**data)
    assert model.translations == ["Start", "Middle", "End"]

def test_robust_string_invalid():
    """Test that other invalid types still fail validation."""
    # Invalid case (list len > 1) - should fail because it can't be flattened to a string
    data = {"translations": ["Hello", ["World", "People"]]}
    with pytest.raises(ValidationError):
        TranslationResponse(**data)

    # Invalid case (not a list or string)
    data = {"translations": ["Hello", 123]}
    with pytest.raises(ValidationError) as excinfo:
        TranslationResponse(**data)
    # Check that it failed specifically on the 2nd item (index 1)
    assert "input_value=123" in str(excinfo.value) or "Input should be a valid string" in str(excinfo.value)
