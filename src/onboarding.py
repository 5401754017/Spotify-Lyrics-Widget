from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.language import normalize_language


DASHBOARD_URL = "https://developer.spotify.com/dashboard"

ONBOARDING_TEXT = {
    "en": {
        "window_title": "Spotify Setup",
        "language_label": "Language",
        "intro": (
            "Create a Spotify Developer App before using this widget, "
            "then paste the Client ID here."
        ),
        "dashboard_step": "1. Open Spotify Developer Dashboard, then choose Create App",
        "dashboard_button": "Open Dashboard",
        "create_hint": "2. Fill in any app name and description, then select Web API",
        "redirect_label": "3. Paste this Redirect URI, accept the terms, then click Save",
        "copy_redirect_button": "Copy Redirect URI",
        "client_label": (
            "4. After the app is created, open Settings, copy Client ID, "
            "and paste it below"
        ),
        "ok_button": "Connect Spotify",
        "cancel_button": "Cancel",
        "warning_title": "Client ID required",
        "warning_message": "Paste your Spotify App Client ID.",
    },
    "zh_TW": {
        "window_title": "Spotify 初始設定",
        "language_label": "語言",
        "intro": (
            "第一次使用前，需要建立一個 Spotify Developer App，"
            "然後把 Client ID 貼回這裡。"
        ),
        "dashboard_step": "1. 開啟 Spotify Developer Dashboard，按 Create App",
        "dashboard_button": "開啟 Dashboard",
        "create_hint": "2. App name 和 Description 隨便填，API 選 Web API",
        "redirect_label": "3. 在 Redirect URI 欄位貼上下面這串，然後勾選同意條款，按 Save",
        "copy_redirect_button": "複製 Redirect URI",
        "client_label": "4. App 建好後，到 Settings 複製 Client ID，貼到下面",
        "ok_button": "連接 Spotify",
        "cancel_button": "取消",
        "warning_title": "Client ID required",
        "warning_message": "請貼上 Spotify App Client ID。",
    },
}

LANGUAGE_NAMES = {
    "en": "English",
    "zh_TW": "繁體中文",
}


class SpotifyOnboardingDialog(QDialog):
    def __init__(
        self,
        redirect_uri: str,
        parent: QWidget | None = None,
        language: str = "zh_TW",
    ):
        super().__init__(parent)
        self._redirect_uri = redirect_uri
        self._client_id = ""
        self._language = normalize_language(language)

        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)

        language_row = QHBoxLayout()
        self._language_label = QLabel()
        self._language_combo = QComboBox()
        self._language_combo.setObjectName("language_combo")
        for code, name in LANGUAGE_NAMES.items():
            self._language_combo.addItem(name, code)
        self._language_combo.setCurrentIndex(self._language_combo.findData(self._language))
        self._language_combo.currentIndexChanged.connect(self._on_language_changed)
        language_row.addWidget(self._language_label, 1)
        language_row.addWidget(self._language_combo)
        layout.addLayout(language_row)

        self._intro_label = QLabel()
        self._intro_label.setWordWrap(True)
        layout.addWidget(self._intro_label)

        # Step 1: Open Dashboard
        dashboard_row = QHBoxLayout()
        self._dashboard_label = QLabel()
        self._dashboard_button = QPushButton()
        self._dashboard_button.setObjectName("open_dashboard_button")
        self._dashboard_button.clicked.connect(self._open_dashboard)
        dashboard_row.addWidget(self._dashboard_label, 1)
        dashboard_row.addWidget(self._dashboard_button)
        layout.addLayout(dashboard_row)

        # Step 2: Fill in app details
        self._create_hint_label = QLabel()
        self._create_hint_label.setWordWrap(True)
        layout.addWidget(self._create_hint_label)

        # Step 3: Add Redirect URI
        self._redirect_label = QLabel()
        self._redirect_label.setWordWrap(True)
        layout.addWidget(self._redirect_label)

        redirect_row = QHBoxLayout()
        redirect_value = QLabel(self._redirect_uri)
        redirect_value.setObjectName("redirect_uri_label")
        redirect_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._copy_button = QPushButton()
        self._copy_button.setObjectName("copy_redirect_uri_button")
        self._copy_button.clicked.connect(self._copy_redirect_uri)
        redirect_row.addWidget(redirect_value, 1)
        redirect_row.addWidget(self._copy_button)
        layout.addLayout(redirect_row)

        # Step 4: Copy Client ID
        self._client_label = QLabel()
        self._client_label.setWordWrap(True)
        layout.addWidget(self._client_label)

        self._client_id_input = QLineEdit()
        self._client_id_input.setObjectName("client_id_input")
        self._client_id_input.setPlaceholderText("Spotify App Client ID")
        layout.addWidget(self._client_id_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Ok
        )
        buttons.setObjectName("dialog_buttons")
        buttons.accepted.connect(self._try_accept)
        buttons.rejected.connect(self.reject)
        self._buttons = buttons
        layout.addWidget(buttons)

        self._apply_language()

    @property
    def client_id(self) -> str:
        return self._client_id

    @property
    def language(self) -> str:
        return self._language

    def _on_language_changed(self, _index: int):
        self._language = normalize_language(self._language_combo.currentData())
        self._apply_language()

    def _apply_language(self):
        text = ONBOARDING_TEXT[self._language]
        self.setWindowTitle(text["window_title"])
        self._language_label.setText(text["language_label"])
        self._intro_label.setText(text["intro"])
        self._dashboard_label.setText(text["dashboard_step"])
        self._dashboard_button.setText(text["dashboard_button"])
        self._create_hint_label.setText(text["create_hint"])
        self._redirect_label.setText(text["redirect_label"])
        self._copy_button.setText(text["copy_redirect_button"])
        self._client_label.setText(text["client_label"])
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            text["ok_button"]
        )
        self._buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            text["cancel_button"]
        )

    def _open_dashboard(self):
        QDesktopServices.openUrl(QUrl(DASHBOARD_URL))

    def _copy_redirect_uri(self):
        QApplication.clipboard().setText(self._redirect_uri)

    def _try_accept(self):
        client_id = self._client_id_input.text().strip()
        if not client_id:
            text = ONBOARDING_TEXT[self._language]
            QMessageBox.warning(self, text["warning_title"], text["warning_message"])
            return
        self._client_id = client_id
        self.accept()
