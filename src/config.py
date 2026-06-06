import json
import os
from pathlib import Path


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

    def _normalize_size_preset(self, data: dict) -> str:
        raw_value = data.get("size_preset", self._DEFAULTS["size_preset"])
        if raw_value in SIZE_PRESET_VALUES:
            return raw_value
        return SIZE_PRESET_ALIASES.get(raw_value, "large")

    def save(self):
        self._config_dir.mkdir(parents=True, exist_ok=True)
        data = {key: getattr(self, key) for key in self._DEFAULTS}
        with open(self._config_file, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)
