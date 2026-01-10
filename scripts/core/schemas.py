from pydantic import BaseModel, Field, BeforeValidator
from typing import List, Annotated, Any

def flatten_nested_list(v: Any) -> Any:
    """
    Validator to handle LLM hallucinations where a string is wrapped in a list.
    Example: ["text"] -> "text"
    """
    if isinstance(v, list) and len(v) == 1 and isinstance(v[0], str):
        return v[0]
    return v

# Define a robust string type that auto-flattens lists
RobustString = Annotated[str, BeforeValidator(flatten_nested_list)]

class TranslationResponse(BaseModel):
    translations: List[RobustString] = Field(description="A list of translated strings. The list must have the same number of elements as the input list.")
