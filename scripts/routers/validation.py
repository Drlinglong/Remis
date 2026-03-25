import logging
from fastapi import APIRouter, HTTPException
from scripts.utils.post_process_validator import validate_text as validate_text_util
from scripts.schemas.validation import ValidationRequest, ValidateFileRequest

router = APIRouter()

@router.post("/api/validate/localization")
def validate_localization(payload: ValidationRequest):
    try:
        results = validate_text_util(
            game_id=payload.game_id,
            text=payload.content,
            source_lang={"code": payload.source_lang_code},
            target_lang=getattr(payload, 'target_lang', None)
        )
        # Convert ValidationResult objects to dicts
        return [
            {
                "is_valid": r.is_valid,
                "level": r.level.value,
                "message": r.message,
                "details": r.details,
                "line_number": r.line_number,
                "text_sample": r.text_sample
            }
            for r in results
        ]
    except Exception as e:
        logging.error(f"Validation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/validate_file")
def validate_file(payload: ValidateFileRequest):
    try:
        from pathlib import Path
        from scripts.core.loc_parser import parse_loc_file_with_lines
        
        file_path = Path(payload.file_path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
            
        entries = parse_loc_file_with_lines(file_path)
        all_results = []
        
        # Validate each entry
        for key, value, line_number in entries:
            # Validate value
            results = validate_text_util(
                game_id=payload.game_id,
                text=value,
                line_number=line_number,
                target_lang=getattr(payload, 'target_lang', None)
            )
            all_results.extend(results)
            
        return {
            "issues": [
                {
                    "is_valid": r.is_valid,
                    "level": r.level.value,
                    "message": r.message,
                    "details": r.details,
                    "line_number": r.line_number,
                    "text_sample": r.text_sample
                }
                for r in all_results
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"File validation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
