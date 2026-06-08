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

        dashboard_row = QHBoxLayout()
        dashboard_text = QLabel("1. 開啟 Spotify Developer Dashboard")
        dashboard_button = QPushButton("開啟 Dashboard")
        dashboard_button.setObjectName("open_dashboard_button")
        dashboard_button.clicked.connect(self._open_dashboard)
        dashboard_row.addWidget(dashboard_text, 1)
        dashboard_row.addWidget(dashboard_button)
        layout.addLayout(dashboard_row)

        redirect_label = QLabel("2. 把這個 Redirect URI 加到你的 Spotify app")
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

        client_label = QLabel("3. 貼上你的 Client ID")
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
