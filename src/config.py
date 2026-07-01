import configparser
import json
import locale
import os
from pathlib import Path

from src.language import language_from_locale, normalize_language


SIZE_PRESET_VALUES = {"small", "medium", "large"}
SIZE_PRESET_ALIASES = {
    "mini": "small",
    "compact": "medium",
    "current": "large",
}


class Config:
    """Manages persistent config in %APPDATA%/spotify-lyrics-widget/config.json."""

    _DEFAULTS = {
        "client_id": None,
        "access_token": None,
        "refresh_token": None,
        "token_expires_at": 0,
        "granted_scope": "",
        "window_x": 100,
        "window_y": 100,
        "netease_fallback": True,
        "size_preset": "large",
        "language": None,
    }

    def __init__(self, config_dir: Path | None = None):
        if config_dir is None:
            appdata = os.environ.get("APPDATA", str(Path.home()))
            config_dir = Path(appdata) / "spotify-lyrics-widget"
        self._config_dir = Path(config_dir)
        self._config_file = self._config_dir / "config.json"
        self._load()

    @property
    def config_dir(self) -> Path:
        return self._config_dir

    def _load(self):
        data = {}
        if self._config_file.exists():
            with open(self._config_file, "r", encoding="utf-8-sig") as file:
                data = json.load(file)

        for key, default in self._DEFAULTS.items():
            setattr(self, key, data.get(key, default))
        self.size_preset = self._normalize_size_preset(data)
        self.language = self._resolve_language(data.get("language"))

    def _normalize_size_preset(self, data: dict) -> str:
        raw_value = data.get("size_preset", self._DEFAULTS["size_preset"])
        if raw_value in SIZE_PRESET_VALUES:
            return raw_value
        return SIZE_PRESET_ALIASES.get(raw_value, "large")

    def _resolve_language(self, saved_language: str | None) -> str:
        language = normalize_language(saved_language, default=None)
        if language:
            return language

        language = normalize_language(self._load_installer_language(), default=None)
        if language:
            return language

        return language_from_locale(locale.getlocale()[0])

    def _load_installer_language(self) -> str | None:
        install_ini = self._config_dir / "install.ini"
        if not install_ini.exists():
            return None

        parser = configparser.ConfigParser()
        parser.read(install_ini, encoding="utf-8-sig")
        return parser.get("Install", "Language", fallback=None)

    def save(self):
        self._config_dir.mkdir(parents=True, exist_ok=True)
        data = {key: getattr(self, key) for key in self._DEFAULTS}
        with open(self._config_file, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)
