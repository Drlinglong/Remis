"""Validation factory for Surviving Mars localization-table values."""

from __future__ import annotations

from scripts.core.surviving_mars_csv import compare_newlines, compare_tags


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
            issues = []
            newlines = compare_newlines(source_text, text)
            if newlines.is_mismatch:
                issues.append(ValidationResult(
                    is_valid=False, level=ValidationLevel.ERROR,
                    message="Surviving Mars CSV line breaks do not match the source",
                    code="validation_surviving_mars_newline_mismatch",
                    details=(f"Expected newline runs: {newlines.source_runs}; actual: "
                             f"{newlines.translation_runs}; unexpected literal escapes: {newlines.unexpected_escaped}"),
                    line_number=line_number, text_sample=text[:100],
                ))
            mismatch = compare_tags(source_text, text)
            if not mismatch.is_mismatch:
                return issues
            missing = ", ".join(mismatch.missing) or "none"
            unexpected = ", ".join(mismatch.unexpected) or "none"
            issues.append(ValidationResult(
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
            ))
            return issues

    return SurvivingMarsValidator()
