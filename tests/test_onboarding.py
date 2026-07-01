from unittest.mock import patch

from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QPushButton,
)

from src.auth import REDIRECT_URI
from src.onboarding import DASHBOARD_URL, SpotifyOnboardingDialog


def _label_texts(dialog):
    return [label.text() for label in dialog.findChildren(QLabel)]


def test_dialog_displays_redirect_uri(qtbot):
    dialog = SpotifyOnboardingDialog(REDIRECT_URI)
    qtbot.addWidget(dialog)

    assert any(REDIRECT_URI in text for text in _label_texts(dialog))


def test_dialog_can_start_in_english(qtbot):
    dialog = SpotifyOnboardingDialog(REDIRECT_URI, language="en")
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "Spotify Setup"
    assert any("Create a Spotify Developer App" in text for text in _label_texts(dialog))
    assert dialog.findChild(QPushButton, "open_dashboard_button").text() == "Open Dashboard"


def test_dialog_can_switch_language(qtbot):
    dialog = SpotifyOnboardingDialog(REDIRECT_URI, language="en")
    qtbot.addWidget(dialog)

    combo = dialog.findChild(QComboBox, "language_combo")
    combo.setCurrentIndex(combo.findData("zh_TW"))

    assert dialog.language == "zh_TW"
    assert dialog.windowTitle() == "Spotify 初始設定"
    assert dialog.findChild(QPushButton, "open_dashboard_button").text() == "開啟 Dashboard"


def test_copy_redirect_uri_puts_value_on_clipboard(qtbot):
    dialog = SpotifyOnboardingDialog(REDIRECT_URI)
    qtbot.addWidget(dialog)

    button = dialog.findChild(QPushButton, "copy_redirect_uri_button")
    button.click()

    assert QApplication.clipboard().text() == REDIRECT_URI


def test_open_dashboard_uses_spotify_dashboard_url(qtbot):
    dialog = SpotifyOnboardingDialog(REDIRECT_URI)
    qtbot.addWidget(dialog)

    button = dialog.findChild(QPushButton, "open_dashboard_button")

    with patch("src.onboarding.QDesktopServices.openUrl") as open_url:
        button.click()

    open_url.assert_called_once()
    assert open_url.call_args.args[0].toString() == DASHBOARD_URL


def test_accept_strips_client_id(qtbot):
    dialog = SpotifyOnboardingDialog(REDIRECT_URI, language="en")
    qtbot.addWidget(dialog)
    input_box = dialog.findChild(QLineEdit, "client_id_input")
    input_box.setText("  client-123  ")

    buttons = dialog.findChild(QDialogButtonBox, "dialog_buttons")
    buttons.button(QDialogButtonBox.StandardButton.Ok).click()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.client_id == "client-123"
    assert dialog.language == "en"


def test_empty_client_id_warns_and_stays_open(qtbot):
    dialog = SpotifyOnboardingDialog(REDIRECT_URI)
    qtbot.addWidget(dialog)
    input_box = dialog.findChild(QLineEdit, "client_id_input")
    input_box.setText("   ")

    buttons = dialog.findChild(QDialogButtonBox, "dialog_buttons")

    with patch("src.onboarding.QMessageBox.warning") as warning:
        buttons.button(QDialogButtonBox.StandardButton.Ok).click()

    warning.assert_called_once()
    assert dialog.result() == 0
