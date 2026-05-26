from src import fonts


def test_app_font_family_defaults_to_fallback():
    fonts._loaded_family = None
    assert fonts.app_font_family() == fonts.FALLBACK_FAMILY


def test_load_app_font_picks_system_font(qtbot):
    fonts._loaded_family = None
    family = fonts.load_app_font()
    assert family
    assert fonts.app_font_family() == family
