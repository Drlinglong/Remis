from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class ValidationLevel(Enum):
    """Severity emitted by the post-processing validator."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ValidationResult:
    """One structured post-processing validation result."""

    is_valid: bool
    level: ValidationLevel
    message: str
    code: Optional[str] = None
    details: Optional[str] = None
    details_code: Optional[str] = None
    details_params: Optional[Dict[str, Any]] = None
    line_number: Optional[int] = None
    text_sample: Optional[str] = None
    key: Optional[str] = None
