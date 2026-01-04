# scripts/app_settings.py
# ---------------------------------------------------------------
import os
import sys
import multiprocessing
from scripts.config import prompts
import json

def get_appdata_config_path():
    """Returns the path to the AppData config file."""
    # Use the centralized AppData logic
    config_dir = get_app_data_dir()
    # Note: The original code used "Remis/config.json" inside AppData/Remis
    # But get_app_data_dir uses "RemisModFactory"
    # To maintain backward compatibility if needed, we might want to check.
    # But for a clean break, let's use the new directory.
    # However, the user might have existing config in .remis or AppData/Remis.
    # Let's stick to the new standard: AppData/RemisModFactory/config.json
    return os.path.join(config_dir, "config.json")

def get_api_key(provider_id: str, env_var_name: str) -> str:
    """
    Retrieves the API key for a given provider.
    Priority:
    1. AppData Config (config.json)
    2. Environment Variable (os.environ)
    """
    # 1. Try AppData config
    try:
        config_path = get_appdata_config_path()
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                key = config.get("api_keys", {}).get(provider_id)
                if key:
                    return key
    except Exception:
        pass
    
    # 2. Fallback to environment variable
    return os.environ.get(env_var_name)

def load_api_keys_to_env():
    """
    Loads API keys from AppData config into os.environ.
    This ensures that SDKs and CLI tools that rely on environment variables
    can find the keys.
    """
    try:
        config_path = get_appdata_config_path()
        if not os.path.exists(config_path):
            return

        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            api_keys = config.get("api_keys", {})
            
        for provider_id, key in api_keys.items():
            if provider_id in API_PROVIDERS:
                env_var = API_PROVIDERS[provider_id].get("api_key_env")
                if env_var and key:
                    os.environ[env_var] = key
                    
        # Load RPM limit if present
        rpm_limit = config.get("rpm_limit")
        if rpm_limit:
            from scripts.utils.rate_limiter import rate_limiter
            rate_limiter.update_rpm(int(rpm_limit))
            
    except Exception:
        pass


# Global switch for archiving translation results
ARCHIVE_RESULTS_AFTER_TRANSLATION = True

# --- API Configuration Default ---
DEFAULT_RPM_LIMIT = 40

# --- 项目信息 ----------------------------------------------------
PROJECT_NAME = "Paradox Mod 本地化工厂 - Paradox Mod Localization Factory"
PROJECT_DISPLAY_NAME = "蕾姆丝计划 - Project Remis "
VERSION = "1.2.2"
LAST_UPDATE_DATE = "2025-11-13"
COPYRIGHT = "© 2025 Project Remis Team"

# --- 项目信息显示配置 --------------------------------------------
PROJECT_INFO = {
    "display_name": PROJECT_DISPLAY_NAME,
    "engineering_name": PROJECT_NAME,
    "version": VERSION,
    "last_update": LAST_UPDATE_DATE,
    "copyright": COPYRIGHT
}

# --- 核心配置 ----------------------------------------------------
CHUNK_SIZE = 40
MAX_RETRIES = 2

# --- Gemini CLI 特定配置 -----------------------------------------
GEMINI_CLI_CHUNK_SIZE = 100
GEMINI_CLI_MAX_RETRIES = 2

# --- Ollama 特定配置 ---------------------------------------------
OLLAMA_CHUNK_SIZE = 20
OLLAMA_MAX_RETRIES = 2

# --- 智能线程池配置 ----------------------------------------------------
def get_smart_max_workers():
    cpu_count = multiprocessing.cpu_count() or 1
    return min(32, cpu_count * 2)

RECOMMENDED_MAX_WORKERS = get_smart_max_workers()
BATCH_SIZE = CHUNK_SIZE

# --- 路径配置 ----------------------------------------------------
# --- 路径配置 ----------------------------------------------------
def get_app_root():
    """Returns the application root directory."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def get_app_data_dir():
    """Returns the user data directory (AppData)."""
    appdata = os.getenv('APPDATA')
    
    # [FIX] Differentiate between Dev and Production to prevent data collision
    # Frozen (EXE/Installer) -> RemisModFactory
    # Not Frozen (python scripts/web_server.py) -> RemisModFactoryDev
    app_folder = "RemisModFactory" if getattr(sys, 'frozen', False) else "RemisModFactoryDev"
    
    if not appdata:
        # Fallback for non-standard environments
        base_dir = os.path.join(os.path.expanduser("~"), f".{app_folder.lower()}")
    else:
        base_dir = os.path.join(appdata, app_folder)
    
    os.makedirs(base_dir, exist_ok=True)
    return base_dir

def get_resource_dir():
    """Returns the directory containing static resources."""
    if getattr(sys, 'frozen', False):
        # Check for PyInstaller temporary directory (onefile)
        if hasattr(sys, '_MEIPASS'):
            return sys._MEIPASS
        # Check for _internal directory (onedir)
        internal = os.path.join(os.path.dirname(sys.executable), '_internal')
        if os.path.exists(internal):
            return internal
        return os.path.dirname(sys.executable)
    return get_app_root()

PROJECT_ROOT = get_app_root().replace("\\", "/")
APP_DATA_DIR = get_app_data_dir().replace("\\", "/")
RESOURCE_DIR = get_resource_dir().replace("\\", "/")

# Data directory for static assets (in dev) or resources (in prod)
# In dev: PROJECT_ROOT/data
# In prod: RESOURCE_DIR/data (if we ship data folder) or just RESOURCE_DIR if flattened
# For now, let's assume we ship a 'data' folder in resources
DATA_DIR = os.path.join(RESOURCE_DIR, 'data') if getattr(sys, 'frozen', False) else os.path.join(PROJECT_ROOT, 'data')

SOURCE_DIR = os.path.join(APP_DATA_DIR, 'source_mod') if getattr(sys, 'frozen', False) else os.path.join(PROJECT_ROOT, 'source_mod')
DEST_DIR = os.path.join(APP_DATA_DIR, 'my_translation') if getattr(sys, 'frozen', False) else os.path.join(PROJECT_ROOT, 'my_translation')

# --- Database Paths ---
# All user databases live in AppData
# [Unified Database] remis.sqlite containing both Glossary and Projects
REMIS_DB_PATH = os.path.join(APP_DATA_DIR, "remis.sqlite")

PROJECTS_DB_PATH = REMIS_DB_PATH
MODS_CACHE_DB_PATH = os.path.join(APP_DATA_DIR, "mods_cache.sqlite") # Keep separate? Yes, cache is cache.
TRANSLATION_PROGRESS_DB_PATH = os.path.join(APP_DATA_DIR, "translation_progress.sqlite")
# The main glossary database
DATABASE_PATH = REMIS_DB_PATH

# --- API Provider Configuration ---
DEFAULT_API_PROVIDER = "gemini"

API_PROVIDERS = {
    "gemini": {
        "api_key_env": "GEMINI_API_KEY",
        "name": "Google Gemini",
        "default_model": "gemini-3-flash-preview",
        "available_models": [
            "gemini-3-flash-preview", 
            "gemini-3-pro-preview"
        ],
        "base_url": "https://generativelanguage.googleapis.com",
        "enable_thinking": False,
        "thinking_budget": 0,
        "description_key": "api_desc_gemini"
    },
    "gemini_cli": {
        "cli_path": "gemini",
        "default_model": "gemini-3-flash-preview",
        "available_models": [
            "gemini-3-flash-preview", 
            "gemini-3-pro-preview"
        ],
        "enable_thinking": True,
        "thinking_budget": -1,
        "chunk_size": GEMINI_CLI_CHUNK_SIZE,
        "max_retries": GEMINI_CLI_MAX_RETRIES,
        "max_daily_calls": 1000,
        "name": "Gemini CLI",
        "description_key": "api_desc_gemini_cli"
    },
    "anthropic": {
        "api_key_env": "ANTHROPIC_API_KEY",
        "base_url": "https://api.anthropic.com/v1",
        "name": "Anthropic Claude",
        "default_model": "claude-4-5-sonnet",
        "available_models": [
            "claude-4-5-sonnet",
            "claude-4-5-haiku",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022"
        ],
        "description_key": "api_desc_anthropic"
    },
    "openai": {
        "api_key_env": "OPENAI_API_KEY",
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-5-mini",
        "available_models": [
            "gpt-5.2",
            "gpt-5-mini",
            "gpt-5-nano"
        ],
        "enable_thinking": False,
        "reasoning_effort": "minimal",
        "description_key": "api_desc_openai"
    },
    "qwen": {
        "api_key_env": "DASHSCOPE_API_KEY",
        "default_model": "qwen-plus",
        "available_models": [
            "qwen-plus",
            "qwen-max",
            "qwen-flash"
        ],
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "region": "beijing",
        "name": "Qwen (通义千问)",
        "enable_thinking": False,
        "description_key": "api_desc_qwen"
    },
    "grok": {
        "api_key_env": "XAI_API_KEY",
        "base_url": "https://api.x.ai/v1",
        "name": "Grok (xAI)",
        "default_model": "grok-4-1-fast-reasoning",
        "available_models": [
            "grok-4-1-fast-reasoning",
            "grok-4-1-fast-non-reasoning"
        ],
        "description_key": "api_desc_grok"
    },
    "deepseek": {
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
        "available_models": [
            "deepseek-chat",
            "deepseek-reasoner",
            "deepseek-v3.2",
            "deepseek-v3.2-speciale",
            "deepseek-r2",
            "deepseek-r1"
        ],
        "name": "DeepSeek (深度求索)",
        "enable_thinking": False,
        "description_key": "api_desc_deepseek"
    },
    "ollama": {
        "base_url_env": "OLLAMA_BASE_URL",
        "base_url": "http://localhost:11434/v1",
        "default_model": "qwen3:4b",
        "available_models": [
            "llama3.2",
            "llama3.1",
            "qwen2.5",
            "qwen3:4b",
            "deepseek-v3",
            "mistral",
            "gemma2"
        ],
        "enable_thinking": False,
        "chunk_size": OLLAMA_CHUNK_SIZE,
        "max_retries": OLLAMA_MAX_RETRIES,
        "name": "Ollama (Local)",
        "description_key": "api_desc_ollama"
    },
    "modelscope": {
        "api_key_env": "MODELSCOPE_API_KEY",
        "base_url": "https://api-inference.modelscope.cn/v1/",
        "default_model": "deepseek-ai/DeepSeek-V3.2-Exp",
        "name": "ModelScope (魔搭)",
        "description_key": "api_desc_modelscope"
    },
    "siliconflow": {
        "api_key_env": "SILICONFLOW_API_KEY",
        "base_url": "https://api.siliconflow.cn/v1",
        "default_model": "DeepSeek-R1",
        "available_models": [
            "DeepSeek-R1",
            "DeepSeek-V3",
            "Qwen2.5-72B-Instruct",
            "Llama-3.3-70B-Instruct"
        ],
        "name": "SiliconFlow (硅基流动)",
        "description_key": "api_desc_siliconflow"
    },
    "lm_studio": {
        "base_url_env": "LM_STUDIO_BASE_URL",
        "default_model": "local-model",
        "base_url": "http://localhost:1234/v1",
        "name": "LM Studio",
        "description_key": "api_desc_lm_studio",
        "chunk_size": OLLAMA_CHUNK_SIZE,
        "max_retries": OLLAMA_MAX_RETRIES
    },
    "vllm": {
        "base_url_env": "VLLM_BASE_URL",
        "default_model": "vllm-model", 
        "base_url": "http://localhost:8000/v1",
        "name": "vLLM",
        "description_key": "api_desc_vllm",
        "chunk_size": OLLAMA_CHUNK_SIZE,
        "max_retries": OLLAMA_MAX_RETRIES
    },
    "koboldcpp": {
        "base_url_env": "KOBOLD_BASE_URL",
        "default_model": "kobold-model",
        "base_url": "http://localhost:5001/v1", 
        "name": "KoboldCPP", 
        "description_key": "api_desc_koboldcpp",
        "chunk_size": OLLAMA_CHUNK_SIZE,
        "max_retries": OLLAMA_MAX_RETRIES
    },
    "oobabooga": {
        "base_url_env": "OOBA_BASE_URL",
        "default_model": "ooba-model",
        "base_url": "http://localhost:5000/v1",
        "name": "Oobabooga (Text Gen WebUI)",
        "description_key": "api_desc_oobabooga",
        "chunk_size": OLLAMA_CHUNK_SIZE,
        "max_retries": OLLAMA_MAX_RETRIES
    },
    "kimi": {
        "api_key_env": "KIMI_API_KEY",
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
        "available_models": [
            "moonshotai/kimi-p1-ultra",
            "deepseek/deepseek-r1",
            "deepseek/deepseek-v3",
            "nvidia/llama-3.1-nemotron-70b-instruct",
            "kimi-k2-turbo"
        ],
        "name": "Kimi (Moonshot AI)",
        "description_key": "api_desc_kimi"
    },
    "minimax": {
        "api_key_env": "MINIMAX_API_KEY",
        "base_url": "https://api.minimaxi.com/v1",
        "default_model": "MiniMax-M2.1",
        "available_models": [
            "MiniMax-M2.1",
            "MiniMax-M2.1-lightning",
            "MiniMax-M2",
            "abab6.5-chat"
        ],
        "name": "Minimax (海螺)",
        "description_key": "api_desc_minimax"
    },
    "zhipu": {
        "api_key_env": "ZHIPU_API_KEY",
        "base_url": "https://open.bigmodel.cn/api/paas/v4/",
        "default_model": "glm-4-plus",
        "available_models": [
            "glm-4.7",
            "glm-4.6",
            "glm-4.5",
            "glm-4.5-air",
            "glm-4.5-flash",
            "glm-4-plus",
            "glm-4-air",
            "glm-4-flash"
        ],
        "name": "ChatGLM (Zhipu AI)",
        "description_key": "api_desc_zhipu"
    },
    "nvidia": {
        "api_key_env": "NVIDIA_API_KEY",
        "name": "NVIDIA NIM",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "default_model": "minimaxai/minimax-m2.1",
        "available_models": [
            "minimaxai/minimax-m2.1"
        ],
        "description_key": "api_desc_nvidia"
    },
    "your_favourite_api": {
        "api_key_env": "YOUR_FAVOURITE_API_KEY",
        "base_url": "YOUR_BASE_URL_HERE",
        "default_model": "YOUR_MODEL_NAME_HERE",
        "name": "Custom (OpenAI Compatible)",
        "description_key": "api_desc_custom"
    },
}

# --- 语言数据库 --------------------------------------------------
LANGUAGES = {
    "1":  {"code": "en",     "key": "l_english",      "name": "English",             "name_en": "English",             "folder_prefix": "en-"},
    "2":  {"code": "zh-CN",  "key": "l_simp_chinese", "name": "简体中文",             "name_en": "Simplified Chinese",  "folder_prefix": "zh-CN-"},
    "3":  {"code": "fr",     "key": "l_french",       "name": "Français",            "name_en": "French",              "folder_prefix": "fr-"},
    "4":  {"code": "de",     "key": "l_german",       "name": "Deutsch",             "name_en": "German",              "folder_prefix": "de-"},
    "5":  {"code": "es",     "key": "l_spanish",      "name": "Español",             "name_en": "Spanish",             "folder_prefix": "es-"},
    "6":  {"code": "ja",     "key": "l_japanese",     "name": "日本語",               "name_en": "Japanese",            "folder_prefix": "ja-"},
    "7":  {"code": "ko",     "key": "l_korean",       "name": "한국어",               "name_en": "Korean",              "folder_prefix": "ko-"},
    "8":  {"code": "pl",     "key": "l_polish",       "name": "Polski",              "name_en": "Polish",              "folder_prefix": "pl-"},
    "9":  {"code": "pt-BR",  "key": "l_braz_por",     "name": "Português do Brasil", "name_en": "Brazilian Portuguese", "folder_prefix": "pt-BR-"},
    "10": {"code": "ru",     "key": "l_russian",      "name": "Русский",             "name_en": "Russian",             "folder_prefix": "ru-"},
    "11": {"code": "tr",     "key": "l_turkish",      "name": "Türkçe",              "name_en": "Turkish",             "folder_prefix": "tr-"}
}

# --- 语言标点符号配置 --------------------------------------------------
LANGUAGE_PUNCTUATION_CONFIG = {
    "zh-CN": {"name": "简体中文", "punctuation": {"，": ", ", "。": ". ", "！": "! ", "？": "? ", "：": ": ", "；": "; ", "（": " (", "）": ") ", "【": "[", "】": "]", "《": "<", "》": ">", "“": "\"", "”": "\"", "‘": "'", "’": "'", "…": "...", "—": "-", "－": "-", "　": " ", "、": ", ", "·": ". ", "～": "~", "％": "%", "＃": "#", "＄": "$", "＆": "&", "＊": "*", "＋": "+", "＝": "=", "／": "/", "＼": "\\", "｜": "|", "＠": "@"}, "examples": ["你好，世界！", "这是一个测试：标点符号。", "（重要）信息"]},
    "ja": {"name": "日本語", "punctuation": {"、": ",", "。": ".", "！": "!", "？": "?", "：": ":", "；": ";", "（": "(", "）": ")", "【": "[", "】": "]", "「": "\"", "」": "\"", "『": "'", "』": "'", "・": "·", "…": "...", "—": "-", "～": "~"}, "examples": ["こんにちは、世界！", "これはテストです：句読点。", "（重要）情報"]},
    "ko": {"name": "한국어", "punctuation": {"，": ",", "。": ".", "！": "!", "？": "?", "：": ":", "；": ";", "（": "(", "）": ")", "［": "[", "］": "]", "｛": "{", "｝": "}", "《": "<", "》": ">", "「": "\"", "」": "\"", "『": "'", "』": "'"}, "examples": ["안녕하세요, 세계!", "이것은 테스트입니다: 문장 부호.", "（중요）정보"]},
    "ru": {"name": "Русский", "punctuation": {"«": "\"", "»": "\"", "—": "-", "…": "...", "№": "#"}, "examples": ["Привет, мир!", "Это тест: пунктуация.", "«Важная» информация"]},
    "fr": {"name": "Français", "punctuation": {"«": "\"", "»": "\"", "‹": "'", "›": "'", "…": "...", "—": "-", "–": "-"}, "examples": ["Bonjour, monde!", "C'est un test: ponctuation.", "«Important» information"]},
    "es": {"name": "Español", "punctuation": {"¿": "?", "¡": "!", "«": "\"", "»": "\"", "…": "...", "—": "-", "–": "-"}, "examples": ["¿Hola, mundo!", "¡Es una prueba: puntuación!", "«Importante» информация"]},
    "tr": {"name": "Türkçe", "punctuation": {"«": "\"", "»": "\"", "…": "...", "—": "-", "–": "-"}, "examples": ["Merhaba, dünya!", "Bu bir test: noktalama.", "«Önemli» bilgi"]},
    "de": {"name": "Deutsch", "punctuation": {"„": "\"", "“": "\"", "‚": "'", "‘": "'", "…": "...", "—": "-", "–": "-"}, "examples": ["Hallo, Welt!", "Das ist ein Test: Interpunktion.", "„Wichtige Informationen"]},
    "pl": {"name": "Polski", "punctuation": {"„": "\"", "”": "\"", "‚": "'", "’": "'", "…": "...", "—": "-", "–": "-"}, "examples": ["Witaj, świecie!", "To jest test: interpunkcja.", "Ważne informacje"]},
    "pt-BR": {"name": "Português do Brasil", "punctuation": {"“": "\"", "”": "\"", "‘": "'", "’": "'", "…": "...", "—": "-", "–": "-"}, "examples": ["Olá, mundo!", "Este é um teste: pontuação.", "Importante informação"]}
}

TARGET_LANGUAGE_PUNCTUATION = {
    "en": {"name": "English", "punctuation": [".", "!", "?", ":", ";", "(", ")", "[", "]", "<", ">", "\"", "'", "...", "-", "~", "#", "$", "%", "&", "*", "+", "=", "/", "\\", "|", "@"]}
}

# --- 游戏档案数据库 ---------------------------------------------
GAME_PROFILES = {
    "1": {
        "id": "victoria3", "name": "Victoria 3 (维多利亚3)",
        "supported_language_keys": ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"],
        "source_localization_folder": "localization",
        "protected_items": {".metadata", "localization", "thumbnail.png"},
        "metadata_file": os.path.join(".metadata", "metadata.json"),
        "encoding": "utf-8-sig", "strip_pl_diacritics": False,
        "prompt_template": prompts.VICTORIA3_PROMPT_TEMPLATE,
        "single_prompt_template": prompts.VICTORIA3_SINGLE_PROMPT_TEMPLATE,
        "format_prompt": prompts.VICTORIA3_FORMAT_PROMPT,
        "official_tags_codex": "scripts/config/validators/vic3_official_tags.json",
    },
    "2": {
        "id": "stellaris", "name": "Stellaris (群星)",
        "supported_language_keys": ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
        "source_localization_folder": "localisation",
        "protected_items": {".descriptor.mod", "localisation", "thumbnail.png"},
        "metadata_file": "descriptor.mod",
        "encoding": "utf-8-sig", "strip_pl_diacritics": False,
        "prompt_template": prompts.STELLARIS_PROMPT_TEMPLATE,
        "single_prompt_template": prompts.STELLARIS_SINGLE_PROMPT_TEMPLATE,
        "format_prompt": prompts.STELLARIS_FORMAT_PROMPT,
        "official_tags_codex": "scripts/config/validators/stellaris_official_tags.json",
    },
    "3": {
        "id": "eu4", "name": "Europa Universalis IV (欧陆风云4)",
        "supported_language_keys": ["1", "3", "4", "5"],
        "source_localization_folder": "localisation",
        "protected_items": {".descriptor.mod", "localisation", "thumbnail.png"},
        "metadata_file": "descriptor.mod",
        "encoding": "cp1252", "strip_pl_diacritics": True,
        "prompt_template": prompts.EU4_PROMPT_TEMPLATE,
        "single_prompt_template": prompts.EU4_SINGLE_PROMPT_TEMPLATE,
        "format_prompt": prompts.EU4_FORMAT_PROMPT,
        "official_tags_codex": "scripts/config/validators/eu4_official_tags.json",
    },
    "4": {
        "id": "hoi4", "name": "Hearts of Iron IV (钢铁雄心4)",
        "supported_language_keys": ["1", "2", "3", "4", "5", "6" , "8", "9", "10"],
        "source_localization_folder": "localisation",
        "protected_items": {'descriptor.mod', 'localisation', 'thumbnail.png'},
        "metadata_file": 'descriptor.mod',
        "encoding": "utf-8-sig", "strip_pl_diacritics": False,
        "prompt_template": prompts.HOI4_PROMPT_TEMPLATE,
        "single_prompt_template": prompts.HOI4_SINGLE_PROMPT_TEMPLATE,
        "format_prompt": prompts.HOI4_FORMAT_PROMPT,
        "official_tags_codex": "scripts/config/validators/hoi4_official_tags.json",
    },
    "5": {
        "id": "ck3", "name": "Crusader Kings III (十字军之王3)",
        "supported_language_keys": ["1", "2", "3", "4", "5", "6" , "8",  "10"],
        "source_localization_folder": "localization",
        "protected_items": {'descriptor.mod', 'localisation', 'thumbnail.png'},
        "metadata_file": 'descriptor.mod',
        "encoding": "utf-8-sig", "strip_pl_diacritics": False,
        "prompt_template": prompts.CK3_PROMPT_TEMPLATE,
        "single_prompt_template": prompts.CK3_SINGLE_PROMPT_TEMPLATE,
        "format_prompt": prompts.CK3_FORMAT_PROMPT,
        "official_tags_codex": "scripts/config/validators/ck3_official_tags.json",
    },
    "6": {
        "id": "eu5", "name": "Europa Universalis V (欧陆风云5)",
        "supported_language_keys": ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"],
        "source_localization_folder": "localization", # Will be searched recursively
        "protected_items": {".metadata", "localization", "thumbnail.png"},
        "metadata_file": os.path.join(".metadata", "metadata.json"),
        "encoding": "utf-8-sig", "strip_pl_diacritics": False,
        "prompt_template": prompts.EU5_PROMPT_TEMPLATE,
        "single_prompt_template": prompts.EU5_SINGLE_PROMPT_TEMPLATE,
        "format_prompt": prompts.EU5_FORMAT_PROMPT,
        "official_tags_codex": "scripts/config/validators/eu5_official_tags.json",
    }
}

# --- Game ID Aliases (Normalization) -----------------------------
GAME_ID_ALIASES = {
    "vic3": "victoria3",
    "victoria 3": "victoria3",
    "stellaris": "stellaris",
    "hoi4": "hoi4",
    "ck3": "ck3",
    "eu4": "eu4",
    "eu5": "eu5"
}

# --- 保底格式提示模板 ---------------------------------------------
FALLBACK_FORMAT_PROMPT = prompts.FALLBACK_FORMAT_PROMPT
