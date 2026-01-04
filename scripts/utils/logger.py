# scripts/utils/logger.py
import os
import sys
import logging
import platform
from logging.handlers import RotatingFileHandler

def get_logs_dir():
    """Returns the absolute path to the logs directory."""
    if getattr(sys, 'frozen', False):
        if platform.system() == "Windows":
            base = os.getenv('APPDATA')
        else:
            base = os.path.expanduser("~/.local/share")
        if not base:
            base = os.path.expanduser("~")
        return os.path.join(base, "RemisModFactory", "logs")
    else:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
        return os.path.join(project_root, "logs")

LOGS_DIR = get_logs_dir()

def setup_logger():
    """
    Configures the global root logger for the entire project.
    Implements smart path resolution (AppData vs Dev) and log rotation.
    """
    os.makedirs(LOGS_DIR, exist_ok=True)
    print(f"[LOGGER] Writing logs to: {LOGS_DIR}")

    # 2. 飞行记录仪模式 (Rotating File Handler)
    log_filename = os.path.join(LOGS_DIR, "remis_backend.log")

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

    logging.info(f"Logger initialized. Writing to: {LOGS_DIR}")
    
    # Try to log i18n message if available
    try:
        from scripts.utils import i18n
        if getattr(i18n, '_language_loaded', False):
            logging.info(i18n.t("logger_initialized"))
    except ImportError:
        pass