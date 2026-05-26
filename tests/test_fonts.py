from src import fonts


def test_app_font_family_defaults_to_fallback():
    fonts._loaded_family = None
    assert fonts.app_font_family() == "Segoe UI"


def test_load_app_font_falls_back_when_files_missing(qtbot, monkeypatch, tmp_path):
    fonts._loaded_family = None
    monkeypatch.setattr(fonts, "_FONT_DIR", tmp_path)
    assert fonts.load_app_font() == "Segoe UI"


def test_load_app_font_loads_bundled_noto(qtbot):
    fonts._loaded_family = None
    family = fonts.load_app_font()
    assert "Noto" in family
    assert fonts.app_font_family() == family
