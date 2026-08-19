from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QSpinBox, QCheckBox, QPlainTextEdit, QPushButton
)

class RolloverMinuteSpinBox(QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(-1, 60)

    def textFromValue(self, val: int) -> str:
        if val < 0:
            val = 59
        elif val > 59:
            val = 0
        return f"{val:02d}"


class TemporaryStablingDialog(QDialog):
    """一時入庫の設定ダイアログ"""

    def __init__(self, parent=None, event_data: dict = None, default_start_time: str = None, default_end_time: str = None):
        super().__init__(parent)
        self.setWindowTitle("一時入庫の設定")
        self.resize(400, 400)

        self.event_data = event_data

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # 1. 入庫場所名:
        lbl_location = QLabel("入庫場所名:")
        layout.addWidget(lbl_location)
        self.txt_location = QLineEdit()
        layout.addWidget(self.txt_location)

        # 2. 入庫時刻:
        lbl_start_time = QLabel("入庫時刻:")
        layout.addWidget(lbl_start_time)
        start_layout = QHBoxLayout()
        self.spin_start_hour = QSpinBox()
        self.spin_start_hour.setRange(0, 99)
        self.spin_start_min = RolloverMinuteSpinBox()

        lbl_start_h = QLabel("時")
        lbl_start_m = QLabel("分")
        start_layout.addWidget(self.spin_start_hour)
        start_layout.addWidget(lbl_start_h)
        start_layout.addWidget(self.spin_start_min)
        start_layout.addWidget(lbl_start_m)
        start_layout.addStretch()
        layout.addLayout(start_layout)

        # 3. 出庫時刻:
        lbl_end_time = QLabel("出庫時刻:")
        layout.addWidget(lbl_end_time)
        end_layout = QHBoxLayout()
        self.spin_end_hour = QSpinBox()
        self.spin_end_hour.setRange(0, 99)
        self.spin_end_min = RolloverMinuteSpinBox()

        lbl_end_h = QLabel("時")
        lbl_end_m = QLabel("分")
        end_layout.addWidget(self.spin_end_hour)
        end_layout.addWidget(lbl_end_h)
        end_layout.addWidget(self.spin_end_min)
        end_layout.addWidget(lbl_end_m)
        end_layout.addStretch()
        layout.addLayout(end_layout)

        # 4. 編成の差し替えが可能 チェックボックス
        self.chk_formations = QCheckBox("編成の差し替えが可能")
        layout.addWidget(self.chk_formations)

        # 5. 備考:
        lbl_note = QLabel("備考:")
        layout.addWidget(lbl_note)
        self.txt_note = QPlainTextEdit()
        layout.addWidget(self.txt_note)
        
        layout.addStretch()

        # 6. OK / キャンセル ボタン
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_ok = QPushButton("OK")
        self.btn_cancel = QPushButton("キャンセル")
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

        # シグナル設定
        self.spin_start_min.valueChanged.connect(
            lambda v: self._on_minute_changed(self.spin_start_min, self.spin_start_hour, v)
        )
        self.spin_end_min.valueChanged.connect(
            lambda v: self._on_minute_changed(self.spin_end_min, self.spin_end_hour, v)
        )
        self.btn_ok.clicked.connect(self._on_accept)
        self.btn_cancel.clicked.connect(self.reject)

        # ウィジェットの枠線を表示するスタイルシート
        self.setStyleSheet("""
            QLineEdit, QSpinBox, QPlainTextEdit {
                border: 1px solid #aaaaaa;
                border-radius: 3px;
                padding: 3px;
                background-color: #ffffff;
            }
            QLineEdit:focus, QSpinBox:focus, QPlainTextEdit:focus {
                border: 1px solid #3b82f6;
            }
            QPushButton {
                border: 1px solid #aaaaaa;
                border-radius: 3px;
                padding: 5px 15px;
                background-color: #f0f0f0;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """)

        # 初期値のセット
        self._init_values(event_data, default_start_time, default_end_time)

    def _on_accept(self):
        self._set_modified()
        self.accept()

    def _set_modified(self):
        parent = self.parent()
        if parent:
            main_win = parent.window() if hasattr(parent, "window") else parent
            if hasattr(main_win, "set_modified"):
                main_win.set_modified(True)

    def _on_minute_changed(self, min_spin: QSpinBox, hour_spin: QSpinBox, val: int):
        if val == 60:
            min_spin.blockSignals(True)
            min_spin.setValue(0)
            min_spin.blockSignals(False)
            hour_spin.setValue(hour_spin.value() + 1)
        elif val == -1:
            min_spin.blockSignals(True)
            min_spin.setValue(59)
            min_spin.blockSignals(False)
            if hour_spin.value() > 0:
                hour_spin.setValue(hour_spin.value() - 1)

    def _parse_time(self, time_str: str):
        if not time_str:
            return 0, 0
        try:
            parts = time_str.split(":")
            return int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            return 0, 0

    def _init_values(self, event_data: dict, default_start_time: str, default_end_time: str):
        if event_data:
            self.txt_location.setText(event_data.get("stabled_location", ""))
            sh, sm = self._parse_time(event_data.get("start_time"))
            eh, em = self._parse_time(event_data.get("end_time"))
            self.chk_formations.setChecked(event_data.get("formations_can_changed", False))
            self.txt_note.setPlainText(event_data.get("note", ""))
        else:
            self.txt_location.setText("")
            sh, sm = self._parse_time(default_start_time)
            eh, em = self._parse_time(default_end_time)
            self.chk_formations.setChecked(False)
            self.txt_note.setPlainText("")

        self.spin_start_hour.setValue(sh)
        self.spin_start_min.blockSignals(True)
        self.spin_start_min.setValue(sm)
        self.spin_start_min.blockSignals(False)

        self.spin_end_hour.setValue(eh)
        self.spin_end_min.blockSignals(True)
        self.spin_end_min.setValue(em)
        self.spin_end_min.blockSignals(False)

    def get_data(self) -> dict:
        sh = self.spin_start_hour.value()
        sm = self.spin_start_min.value()
        if sm < 0: sm = 59
        elif sm > 59: sm = 0

        eh = self.spin_end_hour.value()
        em = self.spin_end_min.value()
        if em < 0: em = 59
        elif em > 59: em = 0

        return {
            "stabled_location": self.txt_location.text(),
            "start_time": f"{sh:02d}:{sm:02d}:00",
            "end_time": f"{eh:02d}:{em:02d}:00",
            "formations_can_changed": self.chk_formations.isChecked(),
            "note": self.txt_note.toPlainText()
        }
