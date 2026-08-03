# scripts/utils/logger.py
import logging
import os
import platform
from typing import Mapping, Optional
from logging.handlers import RotatingFileHandler

def get_logs_dir(
    app_data_dir: Optional[str] = None,
    *,
    environ: Optional[Mapping[str, str]] = None,
) -> str:
    """Return a writable user log directory, with test/runtime overrides."""
    environment = environ if environ is not None else os.environ
    override = environment.get("REMIS_LOG_DIR")
    if override:
        return os.path.abspath(os.path.expanduser(override))

    if app_data_dir is None:
        try:
            from scripts import app_settings

            app_data_dir = app_settings.APP_DATA_DIR
        except (ImportError, AttributeError):
            app_data_dir = None
    if app_data_dir:
        return os.path.join(os.path.abspath(app_data_dir), "logs")

    if platform.system() == "Windows":
        base = environment.get("APPDATA")
    else:
        base = os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base or os.path.expanduser("~"), "RemisModFactory", "logs")

LOGS_DIR = get_logs_dir()

def setup_logger(logs_dir: Optional[str] = None):
    """
    Configures the global root logger for the entire project.
    Implements smart path resolution (AppData vs Dev) and log rotation.
    """
    target_dir = os.path.abspath(logs_dir or LOGS_DIR)
    try:
        os.makedirs(target_dir, exist_ok=True)
    except OSError as error:
        print(f"[LOGGER] Failed to create log directory {target_dir}: {error}")
    print(f"[LOGGER] Writing logs to: {target_dir}")

    # 2. 飞行记录仪模式 (Rotating File Handler)
    log_filename = os.path.join(target_dir, "remis_backend.log")

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # 清除旧 Handlers 避免重复
    if logger.hasHandlers():
        logger.handlers.clear()

    # File Handler (Rotating)
    try:
        file_handler = RotatingFileHandler(
            filename=log_filename,
            mode='a',
            maxBytes=5*1024*1024,  # 5MB 单个文件限制
            backupCount=5,         # 保留最近 5 个备份
            encoding='utf-8',
            delay=0
        )
        
        # 3. 增强型格式 (Rich Formatting)
        # 显示文件名和行号，方便定位
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"[LOGGER] Failed to setup file handler: {e}")

    # Console Handler (保留控制台输出，用于黑框调试)
    try:
        stream_handler = logging.StreamHandler()
        # Console output can be simpler
        stream_formatter = logging.Formatter('%(levelname)s: %(message)s')
        stream_handler.setFormatter(stream_formatter)
        stream_handler.setLevel(logging.INFO)
        logger.addHandler(stream_handler)
    except Exception as e:
        print(f"[LOGGER] Safe StreamHandler failed: {e}")

    logging.info(f"Logger initialized. Writing to: {target_dir}")
    
    # Try to log i18n message if available
    try:
        from scripts.utils import i18n
        if getattr(i18n, '_language_loaded', False):
            logging.info(i18n.t("logger_initialized"))
    except ImportError:
        pass
