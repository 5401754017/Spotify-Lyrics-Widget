import json

from src.config import Config


def test_default_config_created_when_missing(tmp_path):
    config = Config(config_dir=tmp_path)
    assert config.client_id is None
    assert config.access_token is None
    assert config.refresh_token is None
    assert config.token_expires_at == 0
    assert config.window_x == 100
    assert config.window_y == 100


def test_save_and_load_config(tmp_path):
    config = Config(config_dir=tmp_path)
    config.client_id = "test_client_id"
    config.access_token = "test_access_token"
    config.refresh_token = "test_refresh_token"
    config.token_expires_at = 1716400000
    config.window_x = 200
    config.window_y = 300
    config.save()

    config2 = Config(config_dir=tmp_path)
    assert config2.client_id == "test_client_id"
    assert config2.access_token == "test_access_token"
    assert config2.refresh_token == "test_refresh_token"
    assert config2.token_expires_at == 1716400000
    assert config2.window_x == 200
    assert config2.window_y == 300


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


def test_default_appdata_path():
    config = Config()
    assert "spotify-lyrics-widget" in str(config._config_dir)
