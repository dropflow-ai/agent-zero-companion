"""Configuration management for Agent Zero Companion."""
import json
import os
from pathlib import Path
from typing import Any

# Default configuration
DEFAULT_CONFIG = {
    "agent_zero_url": "http://localhost:80",
    "api_key": "",
    "hotkey": "<ctrl>+<space>",
    "screenshot_enabled": True,
    "voice_input_enabled": True,
    "voice_output_enabled": True,
    "voice_output_speed": 1.0,
    "voice_output_voice": "de-DE-KatjaNeural",
    "whisper_model": "base",
    "overlay_opacity": 0.95,
    "overlay_width": 480,
    "overlay_max_height": 600,
    "theme": "dark",
    "context_id": "",
    "keep_context": True,
    "auto_screenshot": False,
    "language": "de",
}

# Config file location
CONFIG_DIR = Path.home() / ".agent-zero-companion"
CONFIG_FILE = CONFIG_DIR / "config.json"


class Config:
    """Manages persistent configuration for Agent Zero Companion."""

    def __init__(self):
        self._data: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Load configuration from disk, merging with defaults."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self._data = {**DEFAULT_CONFIG, **saved}
            except (json.JSONDecodeError, OSError):
                self._data = dict(DEFAULT_CONFIG)
        else:
            self._data = dict(DEFAULT_CONFIG)
            self.save()

    def save(self) -> None:
        """Persist configuration to disk."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value and save."""
        self._data[key] = value
        self.save()

    def update(self, updates: dict[str, Any]) -> None:
        """Update multiple configuration values at once."""
        self._data.update(updates)
        self.save()

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)

    def __contains__(self, key: str) -> bool:
        return key in self._data


# Global config instance
config = Config()
