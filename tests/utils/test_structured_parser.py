# tests/utils/test_structured_parser.py
import pytest
from pydantic import BaseModel, Field
from typing import List, Dict

from scripts.utils.structured_parser import parse_response
from scripts.core.schemas import TranslationResponse

# --- Test Fixtures ---

class SimpleModel(BaseModel):
    """A simple Pydantic model for testing."""
    name: str
    value: int

class WrongKeyModel(BaseModel):
    """A model with a different key for testing validation errors."""
    description: str
    amount: int

# --- Test Cases ---

def test_parse_valid_json():
    """Tests parsing a perfectly valid JSON string."""
    json_string = '{"translations": ["hello", "world"]}'
    result = parse_response(json_string, TranslationResponse)
    assert result is not None
    assert isinstance(result, TranslationResponse)
    assert result.translations == ["hello", "world"]

def test_parse_with_missing_comma():
    """Tests if json_repair can fix a missing comma."""
    json_string = '{"translations": ["hello" "world"]}'
    result = parse_response(json_string, TranslationResponse)
    assert result is not None
    assert result.translations == ["hello", "world"]

def test_parse_with_trailing_comma_in_list():
    """Tests if json_repair can handle a trailing comma in a list."""
    json_string = '{"translations": ["hello", "world",]}'
    result = parse_response(json_string, TranslationResponse)
    assert result is not None
    assert result.translations == ["hello", "world"]

def test_parse_with_trailing_comma_in_object():
    """Tests if json_repair can handle a trailing comma in an object."""
    json_string = '{"translations": ["hello", "world"],}'
    result = parse_response(json_string, TranslationResponse)
    assert result is not None
    assert result.translations == ["hello", "world"]

def test_parse_with_single_quotes():
    """Tests if json_repair can handle single quotes."""
    json_string = "{'translations': ['hello', 'world']}"
    result = parse_response(json_string, TranslationResponse)
    assert result is not None
    assert result.translations == ["hello", "world"]

def test_parse_unrecoverable_json():
    """Tests with a completely broken string that cannot be parsed."""
    json_string = 'this is not json at all'
    result = parse_response(json_string, TranslationResponse)
    assert result is None

def test_parse_empty_string():
    """Tests with an empty string input."""
    json_string = ''
    result = parse_response(json_string, TranslationResponse)
    assert result is None

def test_pydantic_validation_error_wrong_key():
    """
    Tests a scenario where the JSON is valid but does not match the Pydantic schema
    (e.g., wrong key name).
    """
    # This JSON is valid, but the key 'translation' does not match 'translations'
    json_string = '{"translation": ["hello", "world"]}'
    result = parse_response(json_string, TranslationResponse)
    assert result is None

def test_pydantic_validation_error_wrong_type():
    """
    Tests a scenario where the JSON is valid, but a value has the wrong type.
    """
    # The value for 'translations' should be a list of strings, not a single string.
    json_string = '{"translations": "hello, world"}'
    result = parse_response(json_string, TranslationResponse)
    assert result is None

def test_with_different_pydantic_model():
    """Tests the function's ability to use a different, provided Pydantic model."""
    json_string = '{"name": "test", "value": 123}'
    result = parse_response(json_string, SimpleModel)
    assert result is not None
    assert isinstance(result, SimpleModel)
    assert result.name == "test"
    assert result.value == 123

def test_validation_error_with_different_model():
    """
    Tests a validation error against a different, provided Pydantic model.
    """
    json_string = '{"name": "test", "value": 123}'
    # We pass the wrong model, so validation should fail.
    result = parse_response(json_string, WrongKeyModel)
    assert result is None

def test_json_with_nested_structures_and_newlines():
    """
    Stress test with newlines and complex structures that the old parser failed on.
    """
    json_string = '''
    {
        "translations": [
            "第一行翻译",
            "第二行翻译，包含一个逗号。",
            "第三行\\n带有一个转义换行符。"
        ]
    }
    '''
    result = parse_response(json_string, TranslationResponse)
    assert result is not None
    assert result.translations == [
        "第一行翻译",
        "第二行翻译，包含一个逗号。",
        "第三行\\n带有一个转义换行符。"
    ]

def test_parse_nested_response_payload_format():
    """
    Tests the parser's ability to handle the specific nested JSON format
    returned by providers that wrap JSON in a response field: {"response": "[...]"}.
    """
    nested_json_string = '{"response": "[\\"你好\\", \\"世界\\"]"}'
    result = parse_response(nested_json_string, TranslationResponse)
    assert result is not None
    assert isinstance(result, TranslationResponse)
    assert result.translations == ["你好", "世界"]

def test_parse_composite_pollution_format():
    """
    Tests the parser's ability to handle composite wrapped JSON:
    A nested JSON object whose string payload is wrapped in a markdown code block.
    e.g., {"response": "```json\n[...]\n```"}
    """
    composite_string = '{"response": "```json\\n[\\"Final\\", \\"Test\\"]\\n```"}'
    result = parse_response(composite_string, TranslationResponse)
    assert result is not None
    assert isinstance(result, TranslationResponse)
    assert result.translations == ["Final", "Test"]

def test_parse_deeply_wrapped_translation_items():
    """
    Local OpenAI-compatible models sometimes wrap one translation item in
    multiple single-element arrays. This should be normalized before the
    batch-length contract is checked.
    """
    json_string = '{"translations": ["hello", [["[[ _QT_ ]]"]], [["QT_"]]]}'
    result = parse_response(json_string, TranslationResponse)
    assert result is not None
    assert result.translations == ["hello", "“", "“"]
