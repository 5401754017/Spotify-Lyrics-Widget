from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QApplication,
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


DASHBOARD_URL = "https://developer.spotify.com/dashboard"


class SpotifyOnboardingDialog(QDialog):
    def __init__(self, redirect_uri: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._redirect_uri = redirect_uri
        self._client_id = ""

        self.setWindowTitle("Spotify 初始設定")
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)

        intro = QLabel(
            "第一次使用前，需要建立一個 Spotify Developer App，"
            "然後把 Client ID 貼回這裡。"
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        # Step 1: Open Dashboard
        dashboard_row = QHBoxLayout()
        dashboard_text = QLabel("1. 開啟 Spotify Developer Dashboard，按 Create App")
        dashboard_button = QPushButton("開啟 Dashboard")
        dashboard_button.setObjectName("open_dashboard_button")
        dashboard_button.clicked.connect(self._open_dashboard)
        dashboard_row.addWidget(dashboard_text, 1)
        dashboard_row.addWidget(dashboard_button)
        layout.addLayout(dashboard_row)

        # Step 2: Fill in app details
        create_hint = QLabel(
            "2. App name 和 Description 隨便填，API 選 Web API"
        )
        create_hint.setWordWrap(True)
        layout.addWidget(create_hint)

        # Step 3: Add Redirect URI
        redirect_label = QLabel(
            "3. 在 Redirect URI 欄位貼上下面這串，然後勾選同意條款，按 Save"
        )
        redirect_label.setWordWrap(True)
        layout.addWidget(redirect_label)

        redirect_row = QHBoxLayout()
        redirect_value = QLabel(self._redirect_uri)
        redirect_value.setObjectName("redirect_uri_label")
        redirect_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        copy_button = QPushButton("複製 Redirect URI")
        copy_button.setObjectName("copy_redirect_uri_button")
        copy_button.clicked.connect(self._copy_redirect_uri)
        redirect_row.addWidget(redirect_value, 1)
        redirect_row.addWidget(copy_button)
        layout.addLayout(redirect_row)

        # Step 4: Copy Client ID
        client_label = QLabel(
            "4. App 建好後，到 Settings 複製 Client ID，貼到下面"
        )
        client_label.setWordWrap(True)
        layout.addWidget(client_label)

        self._client_id_input = QLineEdit()
        self._client_id_input.setObjectName("client_id_input")
        self._client_id_input.setPlaceholderText("Spotify App Client ID")
        layout.addWidget(self._client_id_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Ok
        )
        buttons.setObjectName("dialog_buttons")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("連接 Spotify")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self._try_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def client_id(self) -> str:
        return self._client_id

    def _open_dashboard(self):
        QDesktopServices.openUrl(QUrl(DASHBOARD_URL))

    def _copy_redirect_uri(self):
        QApplication.clipboard().setText(self._redirect_uri)

    def _try_accept(self):
        client_id = self._client_id_input.text().strip()
        if not client_id:
            QMessageBox.warning(self, "Client ID required", "請貼上 Spotify App Client ID。")
            return
        self._client_id = client_id
        self.accept()
