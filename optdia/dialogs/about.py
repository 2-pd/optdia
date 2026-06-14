from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QApplication
import assets_rc
from version import APP_NAME, __version__

# アプリケーション情報ダイアログ
class AboutDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} について")
        self.setFixedSize(480, 320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 20)

        # アイコン
        icon_label = QLabel()
        icon_label.setPixmap(QIcon(":/assets/app_icon.ico").pixmap(128, 128))
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        # アプリケーション名
        name_label = QLabel(APP_NAME)
        name_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        name_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(name_label)

        # バージョン番号
        version_label = QLabel(f"Version {__version__}")
        version_label.setStyleSheet("font-size: 16px; color: #555555;")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)

        # 将来的な拡張用のスペース
        layout.addStretch()

        # ボタンエリア (情報のコピー / OK)
        button_layout = QHBoxLayout()
        copy_btn = QPushButton("コピー(&C)")
        copy_btn.clicked.connect(self._copy_to_clipboard)
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)

        button_layout.addStretch()
        button_layout.addWidget(copy_btn)
        button_layout.addWidget(ok_btn)
        layout.addLayout(button_layout)

    def _copy_to_clipboard(self):
        """アプリ名とバージョン番号をクリップボードにコピーする"""
        clipboard = QApplication.clipboard()
        clipboard.setText(f"{APP_NAME} v{__version__}")