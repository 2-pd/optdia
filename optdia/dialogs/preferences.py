from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QSpinBox,
    QPushButton, QWidget
)
from core.settings import AppSettings


class PreferencesDialog(QDialog):
    """
    環境設定ダイアログ
    """
    def __init__(self, parent=None, app_settings: AppSettings = None):
        super().__init__(parent)
        self.app_settings = app_settings if app_settings is not None else AppSettings()
        self.setWindowTitle("環境設定")
        self.setFixedSize(640, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # 「編集中のファイルを自動でバックアップする」チェックボックス
        self.backup_checkbox = QCheckBox("編集中のファイルを自動でバックアップする")
        layout.addWidget(self.backup_checkbox)

        # 「自動バックアップの間隔」ラベルとスピンボックス
        interval_layout = QHBoxLayout()
        interval_layout.setContentsMargins(20, 0, 0, 0)
        interval_layout.setSpacing(8)

        lbl_interval = QLabel("自動バックアップの間隔:")
        interval_layout.addWidget(lbl_interval)

        self.interval_spinbox = QSpinBox()
        self.interval_spinbox.setRange(1, 60)
        self.interval_spinbox.setSuffix(" 分")
        self.interval_spinbox.setFixedWidth(80)
        interval_layout.addWidget(self.interval_spinbox)
        interval_layout.addStretch()

        layout.addLayout(interval_layout)

        # チェック状態に応じてスピンボックスを有効化/無効化
        self.backup_checkbox.toggled.connect(self.interval_spinbox.setEnabled)

        layout.addStretch()

        # 「OK」「キャンセル」ボタン
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.ok_button = QPushButton("OK")
        self.ok_button.setProperty("class", "ok_button")
        self.cancel_button = QPushButton("キャンセル")

        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.ok_button.clicked.connect(self._on_ok_clicked)
        self.cancel_button.clicked.connect(self.reject)

        # 初期値の読み込み
        self._load_preferences()

    def _load_preferences(self):
        """設定値を読み込んでUIに反映する"""
        interval = self.app_settings.load_autobackup_interval()
        if interval is not None:
            self.backup_checkbox.setChecked(True)
            self.interval_spinbox.setValue(interval)
            self.interval_spinbox.setEnabled(True)
        else:
            self.backup_checkbox.setChecked(False)
            self.interval_spinbox.setValue(5)
            self.interval_spinbox.setEnabled(False)

    def _on_ok_clicked(self):
        """OKボタン押下時に設定をAppSettings経由でQSettingsに保存して閉じる"""
        if self.backup_checkbox.isChecked():
            interval = self.interval_spinbox.value()
            self.app_settings.save_autobackup_interval(interval)
        else:
            self.app_settings.save_autobackup_interval(None)
        self.accept()
