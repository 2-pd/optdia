import sys
import importlib.metadata as metadata
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QLabel, QPushButton, QApplication, QMessageBox,
)
import assets_rc
from version import APP_NAME, __version__

# アプリケーション情報ダイアログ
class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} について")
        self.setFixedSize(540, 360)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)

        # ----- 概要 タブ -----
        overview_tab = QWidget()
        tab_widget.addTab(overview_tab, "概要")
        ov_layout = QVBoxLayout(overview_tab)
        ov_layout.setContentsMargins(40, 40, 40, 20)

        # アイコン
        icon_label = QLabel()
        icon_label.setPixmap(QIcon(":/assets/app_icon.ico").pixmap(128, 128))
        icon_label.setAlignment(Qt.AlignCenter)
        ov_layout.addWidget(icon_label)

        # アプリケーション名
        name_label = QLabel(APP_NAME)
        name_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        name_label.setAlignment(Qt.AlignCenter)
        ov_layout.addWidget(name_label)

        # バージョン番号
        version_label = QLabel(f"Version {__version__}")
        version_label.setStyleSheet("font-size: 16px; color: #555555;")
        version_label.setAlignment(Qt.AlignCenter)
        ov_layout.addWidget(version_label)

        ov_layout.addStretch()

        # ボタンエリア (情報のコピー / OK)
        button_layout = QHBoxLayout()
        copy_btn = QPushButton("コピー(&C)")
        copy_btn.clicked.connect(self._copy_to_clipboard)
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        button_layout.addStretch()
        button_layout.addWidget(copy_btn)
        button_layout.addWidget(ok_btn)
        ov_layout.addLayout(button_layout)

        # ----- ライブラリ タブ -----
        lib_tab = QWidget()
        tab_widget.addTab(lib_tab, "ライブラリ")
        lib_layout = QVBoxLayout(lib_tab)
        lib_layout.setContentsMargins(10, 10, 10, 10)

        lib_label = QLabel(
            "このアプリケーションは以下のサードパーティライブラリを使用して動作しています。\n"
            "これらのライブラリはアプリケーション本体とは独立したライセンスの条件下で利用可能です。"
        )
        lib_label.setWordWrap(True)
        lib_layout.addWidget(lib_label)

        lib_layout.addSpacing(20)

        # ボタンエリア (Python 3, Qt 6, PySide 6)
        lib_button_layout = QHBoxLayout()

        def make_button(text, callback):
            btn = QPushButton(text)
            btn.setFlat(True)
            btn.setStyleSheet("text-decoration: underline; color: #0066CC;")
            btn.clicked.connect(callback)
            return btn

        python_btn = make_button("Python 3", self._show_python_info)
        qt_btn = make_button("Qt 6", self._show_qt_info)
        pyside_btn = make_button("PySide 6", self._show_pyside_info)

        lib_button_layout.addStretch()
        lib_button_layout.addWidget(python_btn)
        lib_button_layout.addWidget(qt_btn)
        lib_button_layout.addWidget(pyside_btn)
        lib_button_layout.addStretch()
        lib_layout.addLayout(lib_button_layout)

        lib_layout.addStretch()

    def _copy_to_clipboard(self):
        """アプリ名とバージョン番号をクリップボードにコピーする"""
        clipboard = QApplication.clipboard()
        clipboard.setText(f"{APP_NAME} v{__version__}")

    def _show_python_info(self):
        """Pythonのバージョンとライセンスを表示する"""
        copyright_text = sys.copyright if getattr(sys, "copyright", None) else ""
        license_text = sys.license if getattr(sys, "license", None) else ""
        info = f"Python {sys.version}\n\n{copyright_text}\n\nライセンス:\n{license_text}"

        # ダイアログの作成
        dialog = QDialog(self)
        dialog.setWindowTitle("Pythonについて")
        dialog.setFixedSize(480, 480)
        main_layout = QVBoxLayout(dialog)

        # スクロールエリア(枠線なし)
        scroll = QScrollArea(dialog)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        # ラベルの設定
        label = QLabel(info)
        label.setWordWrap(True)

        scroll.setWidget(label)
        main_layout.addWidget(scroll)

        # OKボタン
        ok_btn = QPushButton("OK")
        ok_btn.setFixedWidth(100)
        ok_btn.clicked.connect(dialog.accept)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(ok_btn)
        main_layout.addLayout(button_layout)
        dialog.exec()

    def _show_qt_info(self):
        """組み込みダイアログでQtのライセンスを表示する"""
        QMessageBox.aboutQt(self.parent(), "Qtについて")

    def _show_pyside_info(self):
        """PySide6のライセンス情報を表示する"""
        try:
            dist_meta = metadata.metadata("PySide6")
            license_str = dist_meta.get("License", "")
        except Exception:
            license_str = ""
        info = f"ライセンス: {license_str}"
        dialog = QDialog(self)
        dialog.setWindowTitle("PySideについて")
        dialog.setFixedSize(480, 240)
        main_layout = QVBoxLayout(dialog)
        label = QLabel(info)
        label.setWordWrap(True)
        main_layout.addWidget(label)
        ok_btn = QPushButton("OK")
        ok_btn.setFixedWidth(100)
        ok_btn.clicked.connect(dialog.accept)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(ok_btn)
        main_layout.addLayout(button_layout)
        dialog.exec()