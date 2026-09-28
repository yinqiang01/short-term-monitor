"""配置加载器"""
import os
import re
from pathlib import Path
from typing import Any, Dict
import yaml
from dotenv import load_dotenv


class ConfigLoader:
    _instance = None
    _config = None

    def __new__(cls, config_path=None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path=None):
        if self._initialized:
            return
        self._initialized = True
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "config.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        self._config = self._replace_env(raw)

    def _replace_env(self, obj):
        if isinstance(obj, dict):
            return {k: self._replace_env(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._replace_env(i) for i in obj]
        elif isinstance(obj, str):
            for var in re.findall(r'\$\{([^}]+)\}', obj):
                val = os.environ.get(var, "")
                if val:
                    obj = obj.replace(f"${{{var}}}", val)
            return obj
        return obj

    def get(self, key_path, default=None):
        keys = key_path.split(".")
        val = self._config
        try:
            for k in keys:
                val = val[k]
            return val
        except (KeyError, TypeError):
            return default

    @property
    def config(self):
        return self._config


def get_config(config_path=None):
    return ConfigLoader(config_path)
