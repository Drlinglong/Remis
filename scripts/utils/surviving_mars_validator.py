"""Validation factory for Surviving Mars localization-table values."""

from __future__ import annotations

from scripts.core.surviving_mars_csv import compare_tags


def build_validator():
    """Create a validator without importing the main validator module eagerly."""

    from scripts.utils.post_process_validator import BaseGameValidator
    from scripts.utils.validation_results import ValidationLevel, ValidationResult

    class SurvivingMarsValidator(BaseGameValidator):
        def __init__(self):
            super().__init__({
                "game_id": "surviving_mars",
                "game_name": "Surviving Mars / Relaunched",
                "rules": [],
            })

        def validate_text(
            self,
            text: str,
            line_number=None,
            source_lang=None,
            source_text=None,
            target_lang=None,
            **kwargs,
        ):
            if source_text is None:
                return []
            mismatch = compare_tags(source_text, text)
            if not mismatch.is_mismatch:
                return []
            missing = ", ".join(mismatch.missing) or "none"
            unexpected = ", ".join(mismatch.unexpected) or "none"
            return [ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message="Surviving Mars localization tags do not match",
                code="validation_surviving_mars_tag_mismatch",
                details=f"Missing: {missing}; unexpected: {unexpected}",
                details_code="validation_surviving_mars_tag_mismatch",
                details_params={
                    "missing": list(mismatch.missing),
                    "unexpected": list(mismatch.unexpected),
                },
                line_number=line_number,
                text_sample=text[:100],
            )]

    return SurvivingMarsValidator()
