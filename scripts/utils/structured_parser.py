# scripts/utils/structured_parser.py
import json
import logging
from json_repair import repair_json
from pydantic import ValidationError, BaseModel
from typing import Type, TypeVar

from scripts.core.schemas import TranslationResponse

logger = logging.getLogger(__name__)

# Define a TypeVar for Pydantic models to ensure type safety
T = TypeVar('T', bound=BaseModel)

from scripts.utils.text_clean import restore_special_tokens

def parse_response(response_text: str, pydantic_model: Type[T] = TranslationResponse, target_lang: str = "en") -> T | None:
    """
    Parses an LLM response string into a Pydantic model using a robust,
    layered approach that handles both direct JSON arrays (for TranslationResponse)
    and nested JSON objects with a stringified ``response`` payload.
    
    Args:
        response_text: The raw text response from the LLM.
        pydantic_model: The Pydantic model class to validate against.
        target_lang: The target language code (e.g., "zh", "de") for token restoration.
    """
    try:
        # First defense: Repair the raw string to ensure it's valid JSON.
        repaired_json_str = repair_json(response_text)
        payload_to_validate = repaired_json_str

        # Unpacking procedure: handle nested provider responses.
        try:
            data = json.loads(repaired_json_str)
            if isinstance(data, dict) and 'response' in data and isinstance(data['response'], str):
                # It's a nested structure. Extract the real payload.
                # The payload itself might be a JSON string, so repair it again just in case.
                payload_to_validate = repair_json(data['response'])
                logger.debug("Unwrapped nested JSON response payload.")
        except (json.JSONDecodeError, TypeError):
            # If it fails to load as a dict, it's likely not a nested object.
            # Proceed with the repaired string directly.
            pass

        # Purification procedure: Strip markdown code block fences if they exist.
        if payload_to_validate.strip().startswith("```json"):
            payload_to_validate = payload_to_validate.strip()[7:-3].strip()
            logger.debug("Stripped markdown JSON code block.")
        elif payload_to_validate.strip().startswith("```"):
            payload_to_validate = payload_to_validate.strip()[3:-3].strip()
            logger.debug("Stripped markdown generic code block.")

        # Second defense: Pydantic Validation with conditional wrapping.
        # The payload might be a JSON array string '["..."]' or a JSON object string '{"key": ...}'.

        # If payload is a list AND the target is TranslationResponse, wrap it to match the schema.
        if payload_to_validate.strip().startswith('[') and pydantic_model is TranslationResponse:
             final_input_for_pydantic = f'{{"translations": {payload_to_validate}}}'
             model_instance = pydantic_model.model_validate_json(final_input_for_pydantic)
        else:
            # Otherwise, assume the payload is a complete object string for the target model.
            # This handles the 'SimpleModel' test case and direct '{"translations": ...}' cases.
            model_instance = pydantic_model.model_validate_json(payload_to_validate)

        # Post-processing: Restore special tokens (Newlines and Quotes)
        if pydantic_model is TranslationResponse and hasattr(model_instance, 'translations'):
            model_instance.translations = [
                restore_special_tokens(t, target_lang) for t in model_instance.translations
            ]

        return model_instance

    except (ValidationError, json.JSONDecodeError) as e:
        logger.error(f"Pydantic validation failed after all parsing attempts. Error: {e}", exc_info=False)
        logger.debug(f"Failed to parse input (first 100 chars): {response_text[:100]}...")
        return None
    except Exception as e:
        logger.critical(f"An unexpected critical error occurred during parsing. Error: {e}", exc_info=True)
        logger.debug(f"Failed to parse input (first 100 chars): {response_text[:100]}...")
        return None
