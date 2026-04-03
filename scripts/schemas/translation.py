from typing import List, Optional
from pydantic import BaseModel, field_validator
from scripts.schemas.common import LanguageCode

class CheckpointStatusRequest(BaseModel):
    mod_name: str
    target_lang_codes: List[LanguageCode]

    @field_validator('target_lang_codes', mode='before')
    @classmethod
    def normalize_langs(cls, v):
        if isinstance(v, str):
            return [LanguageCode.from_str(v)]
        if isinstance(v, list):
            return [LanguageCode.from_str(code) if isinstance(code, str) else code for code in v]
        return v

class CustomLangConfig(BaseModel):
    name: str
    code: str
    key: str
    folder_prefix: str


class EmbeddedWorkshopConfig(BaseModel):
    enabled: bool = True
    follow_primary_settings: bool = True
    api_provider: Optional[str] = None
    api_model: Optional[str] = None
    batch_size_limit: Optional[int] = 10
    concurrency_limit: Optional[int] = 1
    rpm_limit: Optional[int] = 40

class InitialTranslationRequest(BaseModel):
    project_id: str
    source_lang_code: LanguageCode
    target_lang_codes: List[LanguageCode] = [LanguageCode.ZH_CN]
    api_provider: str = "gemini"
    model: str = "gemini-pro"
    mod_context: Optional[str] = ""
    selected_glossary_ids: Optional[List[int]] = []
    use_main_glossary: bool = True
    clean_source: bool = False
    use_resume: bool = True
    custom_lang_config: Optional[CustomLangConfig] = None
    embedded_workshop: Optional[EmbeddedWorkshopConfig] = None

    @field_validator('source_lang_code', mode='before')
    @classmethod
    def normalize_source_lang(cls, v):
        if isinstance(v, str):
            return LanguageCode.from_str(v)
        return v

    @field_validator('target_lang_codes', mode='before')
    @classmethod
    def normalize_target_langs(cls, v):
        if isinstance(v, str):
            # Split by comma if it's a comma-separated string, just in case
            if "," in v:
                return [LanguageCode.from_str(code.strip()) for code in v.split(",") if code.strip()]
            return [LanguageCode.from_str(v)]
        if isinstance(v, list):
            return [LanguageCode.from_str(code) if isinstance(code, str) else code for code in v]
        return v

class TranslationRequestV2(BaseModel):
    project_path: str
    game_profile_id: str
    source_lang_code: LanguageCode
    target_lang_codes: List[LanguageCode]
    api_provider: str
    mod_context: Optional[str] = ""
    selected_glossary_ids: Optional[List[int]] = []
    model_name: Optional[str] = None
    use_main_glossary: bool = True
    clean_source: bool = False
    is_existing_source: bool = False
    use_resume: bool = True
    custom_lang_config: Optional[CustomLangConfig] = None
    embedded_workshop: Optional[EmbeddedWorkshopConfig] = None

    @field_validator('source_lang_code', mode='before')
    @classmethod
    def normalize_source_lang(cls, v):
        if isinstance(v, str):
            return LanguageCode.from_str(v)
        return v

    @field_validator('target_lang_codes', mode='before')
    @classmethod
    def normalize_target_langs(cls, v):
        if isinstance(v, str):
            return [LanguageCode.from_str(v)]
        if isinstance(v, list):
            return [LanguageCode.from_str(code) if isinstance(code, str) else code for code in v]
        return v

class IncrementalUpdateConfig(BaseModel):
    project_id: str
    target_lang_codes: List[LanguageCode] = [LanguageCode.ZH_CN]
    api_provider: str = "gemini"
    model: str = "gemini-pro"
    mod_context: Optional[str] = ""
    dry_run: bool = False
    custom_source_path: Optional[str] = None
    use_resume: bool = True

    @field_validator('target_lang_codes', mode='before')
    @classmethod
    def normalize_target_langs(cls, v):
        if isinstance(v, str):
            if "," in v:
                return [LanguageCode.from_str(code.strip()) for code in v.split(",") if code.strip()]
            return [LanguageCode.from_str(v)]
        if isinstance(v, list):
            return [LanguageCode.from_str(code) if isinstance(code, str) else code for code in v]
        return v
