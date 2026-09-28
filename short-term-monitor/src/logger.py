"""日志模块"""
import sys
from pathlib import Path
from loguru import logger
from .config_loader import get_config


class LoggerManager:
    _instance = None
    _configured = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._configured:
            return
        self._configured = True
        config = get_config()
        logger.remove()
        level = config.get("logging.level", "INFO")
        fmt = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
        logger.add(sys.stdout, level=level, format=fmt, colorize=True, enqueue=True)
        log_dir = Path(config.get("system.log_dir", "./logs"))
        log_dir.mkdir(parents=True, exist_ok=True)
        logger.add(str(log_dir / config.get("logging.file", "monitor_{time}.log")),
                   level=level, format=fmt, rotation=config.get("logging.rotation", "00:00"),
                   retention=config.get("logging.retention", "30 days"), encoding="utf-8", enqueue=True)
        logger.add(str(log_dir / "error_{time}.log"), level="ERROR", format=fmt,
                   rotation="00:00", retention="30 days", encoding="utf-8", enqueue=True)

    def get_logger(self, name=None):
        return logger.bind(name=name) if name else logger


def get_logger(name=None):
    return LoggerManager().get_logger(name)
