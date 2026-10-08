import re
import zoneinfo
from PySide6.QtCore import Qt, QDate, QEvent
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QPushButton, QTabWidget, QWidget, QDateEdit, QComboBox,
    QListWidget, QListWidgetItem, QGroupBox, QFormLayout, QAbstractItemView
)
from core.project import OptDiaProject


class RevisionDateEdit(QDateEdit):
    """
    ダイヤ改正日編集用 QDateEdit
    1901年1月1日〜2200年12月31日の範囲を扱い、
    1901年1月1日のときは「未設定」と表示し、カレンダー表示時に現在日付を開く。
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCalendarPopup(True)
        self.setDisplayFormat("yyyy-MM-dd")
        self.setMinimumDate(QDate(1901, 1, 1))
        self.setMaximumDate(QDate(2200, 12, 31))
        self.setSpecialValueText("未設定")

        cal = self.calendarWidget()
        if cal:
            cal.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj == self.calendarWidget() and event.type() == QEvent.Show:
            if self.date() == self.minimumDate():
                today = QDate.currentDate()
                self.calendarWidget().setCurrentPage(today.year(), today.month())
                self.calendarWidget().setSelectedDate(today)
        return super().eventFilter(obj, event)


class PublisherItemWidget(QGroupBox):
    """
    作成者情報の1件を表示・編集するグループボックスウィジェット
    """
    def __init__(self, index: int, name: str = "", url: str = "", on_delete=None, parent=None):
        super().__init__(f"作成者{index}", parent)
        self.on_delete_callback = on_delete

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(6)

        self.name_edit = QLineEdit(name)
        form_layout.addRow("作成者名:", self.name_edit)

        self.url_edit = QLineEdit(url)
        form_layout.addRow("作成者URL:", self.url_edit)

        layout.addLayout(form_layout)

        # 「この作成者を削除」ボタン
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addStretch()
        self.delete_btn = QPushButton("この作成者を削除")
        self.delete_btn.setProperty("class", "delete_button")
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        btn_layout.addWidget(self.delete_btn)

        layout.addLayout(btn_layout)

    def update_index(self, index: int):
        self.setTitle(f"作成者{index}")

    def get_publisher_data(self) -> dict:
        url_text = self.url_edit.text().strip()
        return {
            "publisher_name": self.name_edit.text(),
            "publisher_url": url_text if url_text else None
        }

    def _on_delete_clicked(self):
        if self.on_delete_callback:
            self.on_delete_callback(self)


# プロジェクトのプロパティダイアログ
class ProjectPropertiesDialog(QDialog):
    def __init__(self, parent, project: OptDiaProject):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("プロジェクトのプロパティ")
        self.resize(480, 640)

        main_layout = QVBoxLayout(self)

        # タブウィジェット
        self.tab_widget = QTabWidget()
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        self._current_tab_index = 0
        main_layout.addWidget(self.tab_widget)

        # 基本情報タブ
        self._init_basic_info_tab()

        # 作成者情報タブ
        self._init_publishers_tab()

        # タブウィジェットの外に横並びの「OK」「キャンセル」ボタン
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.ok_button = QPushButton("OK")
        self.ok_button.setProperty("class", "ok_button")
        self.cancel_button = QPushButton("キャンセル")

        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        main_layout.addLayout(button_layout)

        self.ok_button.clicked.connect(self._on_ok_clicked)
        self.cancel_button.clicked.connect(self.reject)

    def _init_basic_info_tab(self):
        basic_tab = QWidget()
        layout = QVBoxLayout(basic_tab)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(6)

        # 路線系統ID
        layout.addWidget(QLabel("路線系統ID:"))
        self.id_edit = QLineEdit(self.project.metadata.get("railroad_id") or "")
        self.id_edit.setPlaceholderText("例) nankai_nankai")
        self.id_edit.textChanged.connect(self._clear_id_warning)
        layout.addWidget(self.id_edit)

        # 警告表示用ラベル
        self.warning_label = QLabel("")
        self.warning_label.setStyleSheet("color: #cc3333; padding-left: 5px;")
        layout.addWidget(self.warning_label)

        # 路線系統名
        layout.addWidget(QLabel("路線系統名:"))
        self.name_edit = QLineEdit(self.project.metadata.get("railroad_name", ""))
        self.name_edit.setPlaceholderText("例) 南海電鉄 南海本線・空港線")
        layout.addWidget(self.name_edit)
        layout.addSpacing(10)

        # ダイヤ改正日
        layout.addWidget(QLabel("ダイヤ改正日:"))
        date_layout = QHBoxLayout()
        date_layout.setContentsMargins(0, 0, 0, 0)
        date_layout.setSpacing(5)

        self.date_edit = RevisionDateEdit()
        rev_date_str = self.project.metadata.get("timetable_revision_date")
        if rev_date_str:
            qdate = QDate.fromString(rev_date_str, "yyyy-MM-dd")
            if qdate.isValid():
                self.date_edit.setDate(qdate)
            else:
                self.date_edit.setDate(QDate(1901, 1, 1))
        else:
            self.date_edit.setDate(QDate(1901, 1, 1))
        date_layout.addWidget(self.date_edit, stretch=1)

        self.delete_date_btn = QPushButton("削除")
        self.delete_date_btn.setFixedWidth(60)
        self.delete_date_btn.clicked.connect(self._on_clear_date_clicked)
        date_layout.addWidget(self.delete_date_btn)

        layout.addLayout(date_layout)
        layout.addSpacing(10)

        # タイムゾーン
        layout.addWidget(QLabel("タイムゾーン:"))
        self.timezone_combo = QComboBox()
        self._populate_timezones()
        current_tz = self.project.metadata.get("timezone", "Asia/Tokyo")
        idx = self.timezone_combo.findText(current_tz)
        if idx >= 0:
            self.timezone_combo.setCurrentIndex(idx)
        else:
            # 見つからない場合は追加して選択
            self.timezone_combo.addItem(current_tz)
            self.timezone_combo.setCurrentIndex(self.timezone_combo.count() - 1)
        layout.addWidget(self.timezone_combo)
        layout.addSpacing(10)

        # 説明
        layout.addWidget(QLabel("説明:"))
        self.description_edit = QTextEdit(self.project.metadata.get("description", ""))
        layout.addWidget(self.description_edit)
        layout.addSpacing(10)

        # ライセンス
        layout.addWidget(QLabel("ライセンス:"))
        self.license_edit = QTextEdit(self.project.metadata.get("license_text", ""))
        layout.addWidget(self.license_edit)

        self.tab_widget.addTab(basic_tab, "基本情報")

    def _populate_timezones(self):
        """標準ライブラリのzoneinfoから取得した「<地域>/<地名>」形式のタイムゾーン一覧を設定"""
        try:
            available = zoneinfo.available_timezones()
        except Exception:
            available = set()

        if not available:
            from PySide6.QtCore import QTimeZone
            available = {bytes(b).decode("utf-8") for b in QTimeZone.availableTimeZoneIds()}

        tz_list = sorted([
            tz for tz in available
            if "/" in tz and not tz.startswith("SystemV/") and not tz.startswith("Etc/")
        ])

        self.timezone_combo.clear()
        self.timezone_combo.addItems(tz_list)

    def _init_publishers_tab(self):
        pub_tab = QWidget()
        layout = QVBoxLayout(pub_tab)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # 作成者リストウィジェット (並び替え可能)
        self.publisher_list_widget = QListWidget()
        self.publisher_list_widget.setDragDropMode(QListWidget.InternalMove)
        self.publisher_list_widget.setFocusPolicy(Qt.NoFocus)
        self.publisher_list_widget.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.publisher_list_widget.setStyleSheet(
            "QListWidget { border: none; background-color: transparent; }"
            "QListWidget::item:hover, QListWidget::item:selected:hover { background-color: transparent; }"
            "QListWidget::item:selected { background-color: transparent; }"
        )
        self.publisher_list_widget.model().rowsMoved.connect(self._on_publishers_reordered)
        layout.addWidget(self.publisher_list_widget)

        # 「作成者の追加」ボタン
        self.add_publisher_button = QPushButton("作成者の追加")
        self.add_publisher_button.clicked.connect(self._on_add_publisher)
        layout.addWidget(self.add_publisher_button)

        # 既存の作成者情報を投入
        publishers = self.project.metadata.get("publishers", [])
        for pub in publishers:
            self._add_publisher_item(pub.get("publisher_name", ""), pub.get("publisher_url") or "")

        self.tab_widget.addTab(pub_tab, "作成者情報")

    def _on_clear_date_clicked(self):
        self.date_edit.setDate(self.date_edit.minimumDate())

    def _clear_id_warning(self):
        self.warning_label.setText("")
        self.id_edit.setStyleSheet("")

    def _validate_railroad_id(self) -> bool:
        """路線系統IDのバリデーション (空欄可、入力がある場合は半角英数字とアンダーバーのみ)"""
        railroad_id = self.id_edit.text().strip()
        if railroad_id:
            if not re.match(r"^[a-zA-Z0-9_]+$", railroad_id):
                self.warning_label.setText("IDには半角英数字とアンダーバーのみが使用可能です")
                self.id_edit.setStyleSheet("background-color: #ffeeee;")
                return False
        self._clear_id_warning()
        return True

    def _on_tab_changed(self, new_index: int):
        # 基本情報タブから離れようとした時にバリデーション
        if self._current_tab_index == 0 and new_index != 0:
            if not self._validate_railroad_id():
                self.tab_widget.blockSignals(True)
                self.tab_widget.setCurrentIndex(0)
                self.tab_widget.blockSignals(False)
                return
        self._current_tab_index = new_index

    def _add_publisher_item(self, name: str = "", url: str = ""):
        index = self.publisher_list_widget.count() + 1
        item_widget = PublisherItemWidget(index, name, url, on_delete=self._on_delete_publisher)

        list_item = QListWidgetItem()
        list_item.setSizeHint(item_widget.sizeHint())
        self.publisher_list_widget.addItem(list_item)
        self.publisher_list_widget.setItemWidget(list_item, item_widget)

    def _on_add_publisher(self):
        self._add_publisher_item("", "")
        self.publisher_list_widget.scrollToBottom()

    def _on_delete_publisher(self, widget: PublisherItemWidget):
        for i in range(self.publisher_list_widget.count()):
            item = self.publisher_list_widget.item(i)
            if self.publisher_list_widget.itemWidget(item) == widget:
                self.publisher_list_widget.takeItem(i)
                break
        self._update_all_publisher_titles()

    def _on_publishers_reordered(self, parent, start, end, destination, row):
        self._update_all_publisher_titles()

    def _update_all_publisher_titles(self):
        for i in range(self.publisher_list_widget.count()):
            item = self.publisher_list_widget.item(i)
            widget = self.publisher_list_widget.itemWidget(item)
            if isinstance(widget, PublisherItemWidget):
                widget.update_index(i + 1)

    def _on_ok_clicked(self):
        if not self._validate_railroad_id():
            self.tab_widget.setCurrentIndex(0)
            return

        # メタデータを更新
        railroad_id = self.id_edit.text().strip()
        self.project.metadata["railroad_id"] = railroad_id if railroad_id else None
        self.project.metadata["railroad_name"] = self.name_edit.text()

        # ダイヤ改正日
        if self.date_edit.date() == self.date_edit.minimumDate():
            self.project.metadata["timetable_revision_date"] = None
        else:
            self.project.metadata["timetable_revision_date"] = self.date_edit.date().toString("yyyy-MM-dd")

        self.project.metadata["timezone"] = self.timezone_combo.currentText()
        self.project.metadata["description"] = self.description_edit.toPlainText()
        self.project.metadata["license_text"] = self.license_edit.toPlainText()

        # 作成者情報
        publishers = []
        for i in range(self.publisher_list_widget.count()):
            item = self.publisher_list_widget.item(i)
            widget = self.publisher_list_widget.itemWidget(item)
            if isinstance(widget, PublisherItemWidget):
                publishers.append(widget.get_publisher_data())
        self.project.metadata["publishers"] = publishers

        self.accept()