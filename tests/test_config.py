import json

import pytest

from src.config import Config


def test_default_config_created_when_missing(tmp_path):
    config = Config(config_dir=tmp_path)
    assert config.client_id is None
    assert config.access_token is None
    assert config.refresh_token is None
    assert config.token_expires_at == 0
    assert config.window_x == 100
    assert config.window_y == 100
    assert config.language in {"en", "zh_TW"}


def test_save_and_load_config(tmp_path):
    config = Config(config_dir=tmp_path)
    config.client_id = "test_client_id"
    config.access_token = "test_access_token"
    config.refresh_token = "test_refresh_token"
    config.token_expires_at = 1716400000
    config.window_x = 200
    config.window_y = 300
    config.language = "zh_TW"
    config.save()

    config2 = Config(config_dir=tmp_path)
    assert config2.client_id == "test_client_id"
    assert config2.access_token == "test_access_token"
    assert config2.refresh_token == "test_refresh_token"
    assert config2.token_expires_at == 1716400000
    assert config2.window_x == 200
    assert config2.window_y == 300
    assert config2.language == "zh_TW"


def test_save_creates_directory(tmp_path):
    nested = tmp_path / "sub" / "dir"
    config = Config(config_dir=nested)
    config.client_id = "abc"
    config.save()
    assert (nested / "config.json").exists()


def test_partial_config_preserves_defaults(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"client_id": "partial"}))

    config = Config(config_dir=tmp_path)
    assert config.client_id == "partial"
    assert config.window_x == 100


def test_config_loads_utf8_bom_file(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_bytes(
        b"\xef\xbb\xbf" + json.dumps({"client_id": "bom-client"}).encode("utf-8")
    )

    config = Config(config_dir=tmp_path)

    assert config.client_id == "bom-client"


def test_config_uses_installer_language_when_config_has_no_language(tmp_path):
    install_ini = tmp_path / "install.ini"
    install_ini.write_text("[Install]\nLanguage=english\n", encoding="utf-8")

    config = Config(config_dir=tmp_path)

    assert config.language == "en"


def test_config_saved_language_overrides_installer_language(tmp_path):
    (tmp_path / "install.ini").write_text(
        "[Install]\nLanguage=english\n", encoding="utf-8"
    )
    (tmp_path / "config.json").write_text(
        json.dumps({"language": "zh_TW"}), encoding="utf-8"
    )

    config = Config(config_dir=tmp_path)

    assert config.language == "zh_TW"


def test_default_appdata_path():
    config = Config()
    assert "spotify-lyrics-widget" in str(config._config_dir)


def test_netease_fallback_defaults_to_true(tmp_path):
    from src.config import Config
    assert Config(config_dir=tmp_path).netease_fallback is True


def test_granted_scope_defaults_to_empty_string(tmp_path):
    from src.config import Config

    config = Config(tmp_path)

    assert config.granted_scope == ""


def test_size_preset_defaults_to_large(tmp_path):
    config = Config(config_dir=tmp_path)

    assert config.size_preset == "large"


def test_size_preset_persists_new_small_value(tmp_path):
    config = Config(config_dir=tmp_path)
    config.size_preset = "small"
    config.save()

    config2 = Config(config_dir=tmp_path)

    assert config2.size_preset == "small"


@pytest.mark.parametrize(
    ("removed_value", "expected"),
    [
        ("mini", "small"),
        ("compact", "medium"),
        ("current", "large"),
    ],
)
def test_removed_size_preset_values_use_simple_alias(tmp_path, removed_value, expected):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"size_preset": removed_value}))

    config = Config(config_dir=tmp_path)

    assert config.size_preset == expected


def test_existing_small_value_is_treated_as_new_small(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"size_preset": "small"}))

    config = Config(config_dir=tmp_path)

    assert config.size_preset == "small"
