"""Odczyt i zapis konfiguracji z config.json."""

import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"

DEFAULT_CONFIG = {
    "api_key": "",
    "model": "claude-opus-4-6",
    "default_lang": "pl",
    "default_output_dir": "./output",
    "delay_seconds": 5,
    "appearance_mode": "dark",
}


def load_config() -> dict:
    """Wczytuje konfigurację z pliku. Tworzy domyślny jeśli nie istnieje."""
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        # Uzupełnij brakujące klucze domyślnymi wartościami
        for key, value in DEFAULT_CONFIG.items():
            config.setdefault(key, value)
        return config
    except (json.JSONDecodeError, OSError):
        return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    """Zapisuje konfigurację do pliku."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
