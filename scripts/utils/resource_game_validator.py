"""Expose adapter token checks through the established validator interface."""
from scripts.core.game_adapters.registry import resource_adapter


def build_validator(game_id):
    from scripts.utils.post_process_validator import BaseGameValidator
    from scripts.utils.validation_results import ValidationLevel, ValidationResult

    class ResourceGameValidator(BaseGameValidator):
        def __init__(self):
            super().__init__({"game_id": game_id, "game_name": game_id, "rules": []})

        def validate_text(self, text, line_number=None, source_lang=None,
                          source_text=None, target_lang=None, **kwargs):
            if source_text is None:
                return []
            return [ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR if issue.severity == "error" else ValidationLevel.WARNING,
                message=issue.message, code=issue.code, details=issue.message,
                line_number=line_number, text_sample=text[:100],
            ) for issue in resource_adapter(game_id).validate(source_text, text)]

        def validate_entry(self, key, value, line_number=None, source_lang=None,
                           source_value=None, target_lang=None, **kwargs):
            results = self.validate_text(value, line_number, source_lang,
                                         source_value, target_lang, **kwargs)
            for result in results:
                result.key = key
            return results

    return ResourceGameValidator()
