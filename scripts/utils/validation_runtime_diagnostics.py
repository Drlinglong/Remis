from typing import Optional

from scripts.utils.validation_results import ValidationLevel, ValidationResult


def validation_runtime_error(
    *,
    code: str,
    message: str,
    details: str,
    text: str,
    line_number: Optional[int],
) -> ValidationResult:
    """Build a blocking result when validation infrastructure cannot run."""

    return ValidationResult(
        is_valid=False,
        level=ValidationLevel.ERROR,
        message=message,
        code=code,
        details=details,
        line_number=line_number,
        text_sample=text,
    )
