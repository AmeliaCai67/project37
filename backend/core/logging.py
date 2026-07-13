import logging
import sys
from pathlib import Path

from config import settings
from core import paths


def setup_logging():
    """配置日志"""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # 格式
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # 根日志配置
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 控制台处理器（开发环境或存在终端时）
    if not paths.is_frozen():
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # 文件日志（生产环境或打包环境）
    if settings.ENV == "prod" or paths.is_frozen():
        log_dir = paths.get_app_data_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_dir / "app.log", encoding="utf-8")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """获取日志记录器"""
    return logging.getLogger(name)
