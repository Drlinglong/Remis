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
VERSION = "2.0.7"
LAST_UPDATE_DATE = "2026-01-20"
COPYRIGHT = "© 2026 Project Remis Team"

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
GEMINI_CLI_CHUNK_SIZE = 40
GEMINI_CLI_MAX_RETRIES = 3

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
CONFIG_DIR = os.path.join(APP_DATA_DIR, 'config') if getattr(sys, 'frozen', False) else os.path.join(PROJECT_ROOT, 'data', 'config')

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

# API_PROVIDERS definitions have been externalized to data/config/api_providers.json
# They are loaded via ConfigManager below.


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
# --- Game ID Aliases (Normalization) -----------------------------
# Moved before GAME_PROFILES if needed, or after.
# But GAME_PROFILES is now loaded from ConfigManager.

# Initialize ConfigManager
# We use DATA_DIR which is defined above.
# We need to import ConfigManager here.
# Note: config_manager.py imports prompts, so we don't need to pass them.

from scripts.core.config_manager import ConfigManager
config_manager = ConfigManager(CONFIG_DIR)
GAME_PROFILES = config_manager.game_profiles
API_PROVIDERS = config_manager.api_providers

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
