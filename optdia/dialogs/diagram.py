import re
import copy
import datetime
from PySide6.QtCore import Qt, QDate, QRect, QEvent, Signal, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QWidget, QListWidget, QListWidgetItem,
    QStackedWidget, QColorDialog, QMessageBox, QTabWidget,
    QScrollArea, QCalendarWidget, QDateEdit, QComboBox,
    QGridLayout, QFrame, QTableView
)
from project import OptDiaProject
from common.gui_utils import create_color_square_pixmap
from common.widgets import ColorPickerWidget, AccordionWidget

# 曜日名とキーの対応定義 (日曜始まり)
DAYS_OF_WEEK = [
    ("日", "sunday"),
    ("月", "monday"),
    ("火", "tuesday"),
    ("水", "wednesday"),
    ("木", "thursday"),
    ("金", "friday"),
    ("土", "saturday"),
]

# weekday (0: 月, ..., 6: 日) からキーへの変換
WEEKDAY_TO_KEY = {
    0: "monday",
    1: "tuesday",
    2: "wednesday",
    3: "thursday",
    4: "friday",
    5: "saturday",
    6: "sunday",
}


def get_diagram_for_date(project: OptDiaProject, date_str: str, ignore_date_exceptions: bool = False) -> str | None:
    """
    YYYY-MM-DD形式の日付からその日の運転ダイヤIDを特定する関数。
    ignore_date_exceptions が False の場合、date_exceptions に日付のキーがあればその値を返す。
    なければ calendar_periods の運行区分情報を順に走査し、与えられた日付を期間に含む最初の運行区分情報から
    該当曜日のダイヤIDを返す。該当がなければ None を返す。
    """
    if not ignore_date_exceptions and hasattr(project, "date_exceptions") and project.date_exceptions:
        if date_str in project.date_exceptions:
            return project.date_exceptions[date_str]

    if not hasattr(project, "calendar_periods") or not project.calendar_periods:
        return None

    try:
        dt = datetime.date.fromisoformat(date_str)
        weekday_key = WEEKDAY_TO_KEY[dt.weekday()]
    except (ValueError, KeyError):
        return None

    for period in project.calendar_periods:
        start_date = period.get("start_date")
        end_date = period.get("end_date")

        # 期間の判定 (None の場合は制限なし)
        if start_date and date_str < start_date:
            continue
        if end_date and date_str > end_date:
            continue

        return period.get(weekday_key)

    return None


# 運転ダイヤの追加ダイアログ
class AddDiagramDialog(QDialog):
    def __init__(self, parent, project: OptDiaProject):
        super().__init__(parent)
        self.project = project
        self._is_initial_manually_edited = False
        self.setWindowTitle("運転ダイヤの追加")
        self.setFixedSize(480, 320)

        layout = QVBoxLayout(self)

        # ダイヤID
        layout.addWidget(QLabel("ダイヤID:"))
        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("例) weekday")
        self.id_edit.textChanged.connect(self._clear_id_error)
        layout.addWidget(self.id_edit)

        # 警告表示スペース
        self.warning_label = QLabel("")
        self.warning_label.setStyleSheet("color: red; padding-left: 5px;")
        layout.addWidget(self.warning_label)

        # ダイヤ名
        layout.addWidget(QLabel("ダイヤ名:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例) 平日ダイヤ")
        self.name_edit.textChanged.connect(self._on_name_changed)
        layout.addWidget(self.name_edit)

        # ダイヤ名の1文字表記
        layout.addWidget(QLabel("ダイヤ名の1文字表記:"))
        self.initial_edit = QLineEdit()
        self.initial_edit.setPlaceholderText("例) 平")
        self.initial_edit.setFixedWidth(80)
        self.initial_edit.textEdited.connect(self._on_initial_edited)
        self.initial_edit.editingFinished.connect(self._on_initial_editing_finished)
        layout.addWidget(self.initial_edit)

        layout.addStretch()

        # ボタンエリア (追加 / キャンセル)
        button_layout = QHBoxLayout()
        self.add_button = QPushButton("追加")
        self.cancel_button = QPushButton("キャンセル")

        button_layout.addStretch()
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.add_button.clicked.connect(self._on_add_clicked)
        self.cancel_button.clicked.connect(self.reject)

    def _clear_id_error(self):
        """ID入力欄のエラー表示状態をクリアする"""
        self.id_edit.setStyleSheet("")
        self.warning_label.setText("")

    def _on_name_changed(self, text: str):
        """ダイヤ名が変更されたとき、未編集なら1文字表記を自動更新する"""
        if not self._is_initial_manually_edited:
            if text:
                self.initial_edit.setText(text[0])
            else:
                self.initial_edit.clear()

    def _on_initial_edited(self):
        """ユーザーが手動で1文字表記を編集したことを記録する"""
        self._is_initial_manually_edited = True

    def _on_initial_editing_finished(self):
        """1文字表記の入力欄のフォーカスが外れたときに、2文字目以降を削除する"""
        text = self.initial_edit.text()
        if len(text) > 1:
            self.initial_edit.setText(text[0])

    def _on_add_clicked(self):
        """入力内容を検証し、問題なければ accept する"""
        diagram_id = self.id_edit.text().strip()
        diagram_initial = self.initial_edit.text().strip()

        self.id_edit.setStyleSheet("")

        if not diagram_id:
            self.warning_label.setText("IDを指定してください")
            self.id_edit.setStyleSheet("background-color: #ffeeee;")
            return
        if not re.match(r"^[a-zA-Z0-9_]+$", diagram_id):
            self.warning_label.setText("IDには半角英数字とアンダーバーのみが使用可能です")
            self.id_edit.setStyleSheet("background-color: #ffeeee;")
            return
        if diagram_id in self.project.diagrams:
            self.warning_label.setText("既に使用されているIDです")
            self.id_edit.setStyleSheet("background-color: #ffeeee;")
            return

        if not diagram_initial:
            self.warning_label.setText("1文字表記を指定してください")
            self.initial_edit.setStyleSheet("background-color: #ffeeee;")
            return

        self.accept()


# ダイヤの複製ダイアログ
class DuplicateDiagramDialog(QDialog):
    def __init__(self, parent, project: OptDiaProject, source_diagram_id: str):
        super().__init__(parent)
        self.project = project
        self.source_diagram_id = source_diagram_id
        self.setWindowTitle("ダイヤの複製")
        self.setFixedSize(480, 320)

        source_diag = project.diagrams.get(source_diagram_id, {})
        default_id = source_diagram_id + "_copy"
        default_name = source_diag.get("diagram_name", "") + "のコピー"

        layout = QVBoxLayout(self)

        # 新しいダイヤのID
        layout.addWidget(QLabel("新しいダイヤのID:"))
        self.id_edit = QLineEdit(default_id)
        self.id_edit.setPlaceholderText("例) weekday")
        self.id_edit.textChanged.connect(self._clear_id_error)
        layout.addWidget(self.id_edit)

        # 警告表示スペース
        self.warning_label = QLabel("")
        self.warning_label.setStyleSheet("color: red; padding-left: 5px;")
        layout.addWidget(self.warning_label)

        # 新しいダイヤ名
        layout.addWidget(QLabel("新しいダイヤ名:"))
        self.name_edit = QLineEdit(default_name)
        self.name_edit.setPlaceholderText("例) 平日ダイヤ")
        layout.addWidget(self.name_edit)

        # ダイヤ名の1文字表記
        layout.addWidget(QLabel("ダイヤ名の1文字表記:"))
        self.initial_edit = QLineEdit()
        self.initial_edit.setPlaceholderText("例) 平")
        self.initial_edit.setFixedWidth(80)
        self.initial_edit.editingFinished.connect(self._on_initial_editing_finished)
        layout.addWidget(self.initial_edit)

        layout.addStretch()

        # ボタンエリア (OK / キャンセル)
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("キャンセル")

        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.ok_button.clicked.connect(self._on_ok_clicked)
        self.cancel_button.clicked.connect(self.reject)

    def _clear_id_error(self):
        """ID入力欄のエラー表示状態をクリアする"""
        self.id_edit.setStyleSheet("")
        self.warning_label.setText("")

    def _on_initial_editing_finished(self):
        """1文字表記の入力欄のフォーカスが外れたときに、2文字目以降を削除する"""
        text = self.initial_edit.text()
        if len(text) > 1:
            self.initial_edit.setText(text[0])

    def _on_ok_clicked(self):
        """入力内容を検証し、問題なければ accept する"""
        diagram_id = self.id_edit.text().strip()
        diagram_initial = self.initial_edit.text().strip()

        self.id_edit.setStyleSheet("")
        self.initial_edit.setStyleSheet("")

        if not diagram_id:
            self.warning_label.setText("IDを指定してください")
            self.id_edit.setStyleSheet("background-color: #ffeeee;")
            return
        if not re.match(r"^[a-zA-Z0-9_]+$", diagram_id):
            self.warning_label.setText("IDには半角英数字とアンダーバーのみが使用可能です")
            self.id_edit.setStyleSheet("background-color: #ffeeee;")
            return
        if diagram_id in self.project.diagrams:
            self.warning_label.setText("既に使用されているIDです")
            self.id_edit.setStyleSheet("background-color: #ffeeee;")
            return

        if not diagram_initial:
            self.warning_label.setText("1文字表記を指定してください")
            self.initial_edit.setStyleSheet("background-color: #ffeeee;")
            return

        self.accept()


# カスタムカレンダーウィジェット (日付セルのダイヤ色塗りつぶし・複数日選択に対応)
class DiagramCalendarWidget(QCalendarWidget):
    dates_selection_changed = Signal()

    def __init__(self, project: OptDiaProject, parent=None):
        super().__init__(parent)
        self.project = project
        self.selected_dates = {self.selectedDate()}
        self._anchor_date = self.selectedDate()
        self._is_mouse_down = False

        self.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self.setGridVisible(True)

        self._table_view = self.findChild(QTableView)
        if self._table_view:
            self._table_view.viewport().installEventFilter(self)

        self.currentPageChanged.connect(lambda y, m: self.updateCells())

    def _get_date_from_index(self, row: int, col: int) -> QDate:
        first_of_month = QDate(self.yearShown(), self.monthShown(), 1)
        fdow = self.firstDayOfWeek().value
        first_day_shown = first_of_month.addDays(-((first_of_month.dayOfWeek() - fdow) % 7))
        return first_day_shown.addDays((row - 1) * 7 + col)

    def eventFilter(self, obj, event):
        if self._table_view and obj == self._table_view.viewport():
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                idx = self._table_view.indexAt(event.position().toPoint())
                if idx.isValid() and idx.row() >= 1:
                    date = self._get_date_from_index(idx.row(), idx.column())
                    if event.modifiers() & Qt.ControlModifier:
                        if date in self.selected_dates and len(self.selected_dates) > 1:
                            self.selected_dates.remove(date)
                        else:
                            self.selected_dates.add(date)
                        self._anchor_date = date
                    elif event.modifiers() & Qt.ShiftModifier:
                        d1 = min(self._anchor_date, date)
                        d2 = max(self._anchor_date, date)
                        curr = d1
                        dates = set()
                        while curr <= d2:
                            dates.add(curr)
                            curr = curr.addDays(1)
                        self.selected_dates = dates
                    else:
                        self.selected_dates = {date}
                        self._anchor_date = date
                    self._is_mouse_down = True
                    self.setSelectedDate(date)
                    self.dates_selection_changed.emit()
                    self.updateCells()
                    return True
            elif event.type() == QEvent.MouseMove:
                if self._is_mouse_down and (event.buttons() & Qt.LeftButton):
                    idx = self._table_view.indexAt(event.position().toPoint())
                    if idx.isValid() and idx.row() >= 1:
                        date = self._get_date_from_index(idx.row(), idx.column())
                        d1 = min(self._anchor_date, date)
                        d2 = max(self._anchor_date, date)
                        curr = d1
                        dates = set()
                        while curr <= d2:
                            dates.add(curr)
                            curr = curr.addDays(1)
                        self.selected_dates = dates
                        self.setSelectedDate(date)
                        self.dates_selection_changed.emit()
                        self.updateCells()
                    return True
            elif event.type() == QEvent.MouseButtonRelease:
                self._is_mouse_down = False
                return True
        return super().eventFilter(obj, event)

    def paintCell(self, painter: QPainter, rect: QRect, date: QDate):
        iso_date = date.toString("yyyy-MM-dd")
        diag_id = get_diagram_for_date(self.project, iso_date, ignore_date_exceptions=False)

        bg_color = None
        if diag_id and diag_id in self.project.diagrams:
            bg_hex = self.project.diagrams[diag_id].get("background_color")
            if bg_hex:
                bg_color = QColor(bg_hex)

        painter.save()
        is_current_month = (date.month() == self.monthShown() and date.year() == self.yearShown())

        if bg_color and bg_color.isValid():
            painter.fillRect(rect, bg_color)
            lum = (bg_color.red() * 299 + bg_color.green() * 587 + bg_color.blue() * 114) / 1000
            text_color = Qt.black if lum > 128 else Qt.white
        else:
            painter.fillRect(rect, Qt.white if is_current_month else QColor("#f7f7f7"))
            text_color = Qt.black if is_current_month else QColor("#aaaaaa")

        if date in self.selected_dates:
            pen = QPen(QColor("#0066cc"), 2)
            painter.setPen(pen)
            painter.drawRect(rect.adjusted(1, 1, -1, -1))
            painter.fillRect(rect, QColor(0, 102, 204, 50))

        painter.setPen(text_color)
        painter.drawText(rect, Qt.AlignCenter, str(date.day()))
        painter.restore()


# 運行区分用の日付選択ウィジェット
class PeriodDateEdit(QDateEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDisplayFormat("yyyy-MM-dd")
        self.setCalendarPopup(True)
        self.setMinimumDate(QDate(1901, 1, 1))
        self.setMaximumDate(QDate(2200, 12, 31))
        self.setSpecialValueText("未定義")
        cw = self.calendarWidget()
        if cw:
            cw.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj == self.calendarWidget() and event.type() in (QEvent.Show, QEvent.ShowToParent):
            if self.date() == QDate(1901, 1, 1):
                today = QDate.currentDate()
                self.calendarWidget().setCurrentPage(today.year(), today.month())
                QTimer.singleShot(0, self._set_calendar_to_current_month)
        return super().eventFilter(obj, event)

    def _set_calendar_to_current_month(self):
        cw = self.calendarWidget()
        if cw and self.date() == QDate(1901, 1, 1):
            today = QDate.currentDate()
            cw.setCurrentPage(today.year(), today.month())


# 運行区分情報に対応するアコーディオンウィジェット
class CalendarPeriodAccordion(AccordionWidget):
    def __init__(self, dialog: "DiagramEditorDialog", period: dict, parent=None):
        start_str = period.get("start_date") or "未定義"
        end_str = period.get("end_date") or "未定義"
        super().__init__(f"{start_str} 〜 {end_str}", parent)
        self.dialog = dialog
        self.period = period
        self.combo_boxes = {}

        self._init_content()

    def _init_content(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # 期間の開始日・終了日行
        period_row = QHBoxLayout()
        period_row.setSpacing(8)
        period_row.addWidget(QLabel("期間:"))

        # 開始日選択欄
        self.start_date_edit = PeriodDateEdit()
        if self.period.get("start_date"):
            self.start_date_edit.setDate(QDate.fromString(self.period["start_date"], "yyyy-MM-dd"))
        else:
            self.start_date_edit.setDate(QDate(1901, 1, 1))
            self.period["start_date"] = None
        self.start_date_edit.dateChanged.connect(self._on_start_date_changed)
        period_row.addWidget(self.start_date_edit)

        # 開始日クリアボタン
        self.clear_start_button = QPushButton("クリア")
        self.clear_start_button.setStyleSheet("border: none; font-size: 12px; text-decoration: underline; background-color: transparent;")
        self.clear_start_button.clicked.connect(self._on_clear_start_date)
        period_row.addWidget(self.clear_start_button)

        period_row.addWidget(QLabel(" 〜 "))

        # 終了日選択欄
        self.end_date_edit = PeriodDateEdit()
        if self.period.get("end_date"):
            self.end_date_edit.setDate(QDate.fromString(self.period["end_date"], "yyyy-MM-dd"))
        else:
            self.end_date_edit.setDate(QDate(1901, 1, 1))
            self.period["end_date"] = None
        self.end_date_edit.dateChanged.connect(self._on_end_date_changed)
        period_row.addWidget(self.end_date_edit)

        # 終了日クリアボタン
        self.clear_end_button = QPushButton("クリア")
        self.clear_end_button.setStyleSheet("border: none; font-size: 12px; text-decoration: underline; background-color: transparent;")
        self.clear_end_button.clicked.connect(self._on_clear_end_date)
        period_row.addWidget(self.clear_end_button)

        period_row.addStretch()
        layout.addLayout(period_row)

        # 重複警告ラベル
        self.warning_label = QLabel("")
        self.warning_label.setStyleSheet("color: red; font-size: 12px;")
        layout.addWidget(self.warning_label)

        # 日曜〜土曜の各曜日ダイヤ選択コンボボックス
        grid = QGridLayout()
        grid.setSpacing(6)
        for i, (day_name, day_key) in enumerate(DAYS_OF_WEEK):
            grid.addWidget(QLabel(f"{day_name}曜日のダイヤ:"), i // 4 * 2, i % 4)
            combo = QComboBox()
            self.combo_boxes[day_key] = combo
            self._populate_combo(combo, self.period.get(day_key))
            combo.currentIndexChanged.connect(lambda idx, k=day_key: self._on_combo_changed(k))
            grid.addWidget(combo, i // 4 * 2 + 1, i % 4)
        layout.addLayout(grid)

        # 「この運行区分を削除」ボタン
        delete_row = QHBoxLayout()
        delete_row.addStretch()
        self.delete_button = QPushButton("この運行区分を削除")
        self.delete_button.setStyleSheet(
            "QPushButton { color: #cc3333; border: none; text-decoration: underline; background-color: transparent; font-size: 12px; }"
        )
        self.delete_button.setCursor(Qt.PointingHandCursor)
        self.delete_button.clicked.connect(self._on_delete_clicked)
        delete_row.addWidget(self.delete_button)
        layout.addLayout(delete_row)

        self.set_content_widget(content)
        self._update_title()

    def _populate_combo(self, combo: QComboBox, current_diag_id: str | None):
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("未設定", None)
        selected_idx = 0
        for i, did in enumerate(self.dialog.project.diagrams_order):
            diag = self.dialog.project.diagrams.get(did, {})
            name = diag.get("diagram_name", did)
            combo.addItem(name, did)
            if did == current_diag_id:
                selected_idx = i + 1
        combo.setCurrentIndex(selected_idx)
        combo.blockSignals(False)

    def refresh_combos(self):
        """ダイヤ一覧の更新に合わせて各曜日コンボボックスの選択肢を更新する"""
        for day_key, combo in self.combo_boxes.items():
            self._populate_combo(combo, self.period.get(day_key))

    def _update_title(self):
        start_str = self.period.get("start_date") or "未定義"
        end_str = self.period.get("end_date") or "未定義"
        self.set_title(f"{start_str} 〜 {end_str}")

    def _on_start_date_changed(self, new_date: QDate):
        if new_date == QDate(1901, 1, 1):
            self.period["start_date"] = None
        else:
            self.period["start_date"] = new_date.toString("yyyy-MM-dd")
        self._update_title()
        self.dialog._on_period_start_date_modified()

    def _on_end_date_changed(self, new_date: QDate):
        if new_date == QDate(1901, 1, 1):
            self.period["end_date"] = None
        else:
            self.period["end_date"] = new_date.toString("yyyy-MM-dd")
        self._update_title()
        self.dialog._check_period_overlaps()
        self.dialog.calendar_widget.updateCells()
        self.dialog._update_calendar_details()
        if hasattr(self.dialog.parent(), "set_modified"):
            self.dialog.parent().set_modified(True)

    def _on_clear_start_date(self):
        self.start_date_edit.setDate(QDate(1901, 1, 1))

    def _on_clear_end_date(self):
        self.end_date_edit.setDate(QDate(1901, 1, 1))

    def _on_combo_changed(self, day_key: str):
        combo = self.combo_boxes.get(day_key)
        if combo:
            self.period[day_key] = combo.currentData()
            self.dialog.calendar_widget.updateCells()
            self.dialog._update_calendar_details()
            if hasattr(self.dialog.parent(), "set_modified"):
                self.dialog.parent().set_modified(True)

    def _on_delete_clicked(self):
        if self.period in self.dialog.project.calendar_periods:
            self.dialog.project.calendar_periods.remove(self.period)
        self.dialog._remove_period_accordion(self)
        self.dialog._check_period_overlaps()
        self.dialog.calendar_widget.updateCells()
        self.dialog._update_calendar_details()
        if hasattr(self.dialog.parent(), "set_modified"):
            self.dialog.parent().set_modified(True)


# 運転ダイヤ情報編集ダイアログ
class DiagramEditorDialog(QDialog):
    def __init__(self, parent, project: OptDiaProject, initial_diagram_id=None):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("運転ダイヤ情報")
        self.setFixedSize(800, 640)
        self.initial_diagram_id = initial_diagram_id
        self.period_widgets: list[CalendarPeriodAccordion] = []

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # タブウィジェット
        self.tab_widget = QTabWidget()
        root_layout.addWidget(self.tab_widget)

        # ==========================================
        # 1. 「ダイヤ情報」タブ
        # ==========================================
        self.diagram_tab = QWidget()
        diagram_tab_layout = QHBoxLayout(self.diagram_tab)
        diagram_tab_layout.setContentsMargins(0, 0, 0, 0)
        diagram_tab_layout.setSpacing(0)

        # 左側のサイドバー (幅220px固定)
        sidebar = QWidget()
        sidebar.setObjectName("diagram_editor_sidebar")
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet("#diagram_editor_sidebar { background-color: #f7f7f7; border-right: 1px solid #dddddd; }")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        sidebar_layout.setSpacing(5)

        sidebar_layout.addWidget(QLabel("<b>ダイヤの一覧</b>"))

        # ダイヤリスト
        self.diagram_list_widget = QListWidget()
        self.diagram_list_widget.setDragDropMode(QListWidget.InternalMove)
        self.diagram_list_widget.model().rowsMoved.connect(self._on_diagrams_reordered)
        self.diagram_list_widget.itemSelectionChanged.connect(self._on_diagram_selected)
        sidebar_layout.addWidget(self.diagram_list_widget)

        # ダイヤ追加ボタン
        self.add_diagram_button = QPushButton("ダイヤの追加")
        self.add_diagram_button.clicked.connect(self._on_add_diagram)
        sidebar_layout.addWidget(self.add_diagram_button)

        diagram_tab_layout.addWidget(sidebar)

        # 右側のスタックドウィジェット
        self.right_stack = QStackedWidget()
        diagram_tab_layout.addWidget(self.right_stack, stretch=1)

        # 1-1. プレースホルダーページ (データなし)
        self.placeholder_page = QWidget()
        placeholder_layout = QVBoxLayout(self.placeholder_page)
        placeholder_label = QLabel("ダイヤを追加してください")
        placeholder_label.setAlignment(Qt.AlignCenter)
        placeholder_label.setStyleSheet("color: #888888; font-size: 18px;")
        placeholder_layout.addWidget(placeholder_label)
        self.right_stack.addWidget(self.placeholder_page)

        # 1-2. ダイヤ編集フォームページ
        self.edit_form_page = QWidget()
        edit_form_layout = QVBoxLayout(self.edit_form_page)
        edit_form_layout.setContentsMargins(20, 20, 20, 20)
        edit_form_layout.setSpacing(10)

        # ダイヤID (変更不可)
        edit_form_layout.addWidget(QLabel("ダイヤID(変更不可):"))
        self.diagram_id_display = QLineEdit()
        self.diagram_id_display.setReadOnly(True)
        self.diagram_id_display.setStyleSheet("background-color: #eeeeee; color: #888888;")
        edit_form_layout.addWidget(self.diagram_id_display)

        # ダイヤ名
        edit_form_layout.addWidget(QLabel("ダイヤ名:"))
        self.diagram_name_edit = QLineEdit()
        self.diagram_name_edit.textChanged.connect(self._on_diagram_name_changed)
        edit_form_layout.addWidget(self.diagram_name_edit)

        # ダイヤ名の1文字表記
        edit_form_layout.addWidget(QLabel("ダイヤ名の1文字表記:"))
        self.diagram_initial_edit = QLineEdit()
        self.diagram_initial_edit.setFixedWidth(80)
        self.diagram_initial_edit.textChanged.connect(self._on_diagram_initial_changed)
        self.diagram_initial_edit.editingFinished.connect(self._on_diagram_initial_editing_finished)
        edit_form_layout.addWidget(self.diagram_initial_edit)

        # 背景色
        edit_form_layout.addSpacing(10)
        edit_form_layout.addWidget(QLabel("背景色:"))
        self.background_color_picker = ColorPickerWidget("#cccccc")
        self.background_color_picker.colorChanged.connect(self._on_background_color_changed)
        edit_form_layout.addWidget(self.background_color_picker)

        edit_form_layout.addStretch()

        # ダイヤ複製・削除ボタン行
        diagram_action_row = QHBoxLayout()
        diagram_action_row.addStretch()

        self.duplicate_diagram_button = QPushButton("このダイヤを複製")
        self.duplicate_diagram_button.setStyleSheet("QPushButton { border: none; text-decoration: underline; background-color: transparent; }")
        self.duplicate_diagram_button.setCursor(Qt.PointingHandCursor)
        self.duplicate_diagram_button.clicked.connect(self._on_duplicate_diagram)
        diagram_action_row.addWidget(self.duplicate_diagram_button)

        self.delete_diagram_button = QPushButton("このダイヤを削除")
        self.delete_diagram_button.setFixedSize(120, 30)
        self.delete_diagram_button.clicked.connect(self._on_delete_diagram)
        self.delete_diagram_button.setStyleSheet("QPushButton { color: #cc3333; border: none; text-decoration: underline; background-color: transparent; }")
        diagram_action_row.addWidget(self.delete_diagram_button)

        edit_form_layout.addLayout(diagram_action_row)

        self.right_stack.addWidget(self.edit_form_page)

        self.tab_widget.addTab(self.diagram_tab, "ダイヤ情報")

        # ==========================================
        # 2. 「カレンダー」タブ
        # ==========================================
        self.calendar_tab = QWidget()
        calendar_tab_main_layout = QVBoxLayout(self.calendar_tab)
        calendar_tab_main_layout.setContentsMargins(0, 0, 0, 0)
        calendar_tab_main_layout.setSpacing(0)

        # 上下スクロールエリア
        self.calendar_scroll_area = QScrollArea()
        self.calendar_scroll_area.setWidgetResizable(True)
        self.calendar_scroll_area.setFrameShape(QFrame.NoFrame)

        self.calendar_scroll_content = QWidget()
        self.calendar_vlayout = QVBoxLayout(self.calendar_scroll_content)
        self.calendar_vlayout.setContentsMargins(15, 15, 15, 15)
        self.calendar_vlayout.setSpacing(15)

        # 2-1. カレンダーエリア
        calendar_area_widget = QWidget()
        calendar_area_layout = QHBoxLayout(calendar_area_widget)
        calendar_area_layout.setContentsMargins(0, 0, 0, 0)
        calendar_area_layout.setSpacing(15)

        self.calendar_widget = DiagramCalendarWidget(self.project)
        self.calendar_widget.dates_selection_changed.connect(self._on_calendar_selection_changed)
        calendar_area_layout.addWidget(self.calendar_widget, stretch=0)

        # カレンダー右側垂直レイアウト
        cal_right_widget = QWidget()
        cal_right_layout = QVBoxLayout(cal_right_widget)
        cal_right_layout.setContentsMargins(0, 5, 0, 5)
        cal_right_layout.setSpacing(8)

        self.cal_selection_label = QLabel("選択中の日付のダイヤ:")
        self.cal_selection_label.setStyleSheet("font-weight: bold;")
        cal_right_layout.addWidget(self.cal_selection_label)

        self.cal_diag_combo = QComboBox()
        self.cal_diag_combo.currentIndexChanged.connect(self._on_cal_diag_combo_changed)
        cal_right_layout.addWidget(self.cal_diag_combo)

        cal_right_layout.addSpacing(10)

        lbl_default_title = QLabel("指定しない場合のダイヤ:")
        lbl_default_title.setStyleSheet("color: #555555;")
        cal_right_layout.addWidget(lbl_default_title)

        self.cal_default_diag_label = QLabel("未設定")
        self.cal_default_diag_label.setStyleSheet("color: #555555; font-size: 13px; padding-left: 10px;")
        cal_right_layout.addWidget(self.cal_default_diag_label)

        cal_right_layout.addStretch()
        calendar_area_layout.addWidget(cal_right_widget, stretch=1)

        self.calendar_vlayout.addWidget(calendar_area_widget)

        self.calendar_vlayout.addSpacing(10)

        # 2-2. 運行区分情報エリア
        self.period_area_label = QLabel("曜日別の所定ダイヤ:")
        self.period_area_label.setStyleSheet("font-size: 14px;")
        self.calendar_vlayout.addWidget(self.period_area_label)
        
        self.period_area_widget = QWidget()
        self.period_area_layout = QVBoxLayout(self.period_area_widget)
        self.period_area_layout.setContentsMargins(0, 0, 0, 0)
        self.period_area_layout.setSpacing(8)

        self.period_empty_label = QLabel("曜日別の所定ダイヤを設定するには運行区分を追加してください")
        self.period_empty_label.setStyleSheet("color: #888888; font-size: 13px; padding: 4px 0;")
        self.period_area_layout.addWidget(self.period_empty_label)

        self.calendar_vlayout.addWidget(self.period_area_widget)

        # 2-3. 期間別運行区分の追加ボタン
        self.add_period_button = QPushButton("期間別の運行区分を追加")
        self.add_period_button.setFixedHeight(32)
        self.add_period_button.clicked.connect(self._on_add_period)
        self.calendar_vlayout.addWidget(self.add_period_button)

        # 2-4. 運行区分を時系列順にソートボタン
        self.sort_periods_button = QPushButton("運行区分を時系列順にソート")
        self.sort_periods_button.setStyleSheet(
            "QPushButton { border: none; text-decoration: underline; background-color: transparent; } "
            "QPushButton:disabled { color: #aaaaaa; }"
        )
        self.sort_periods_button.setCursor(Qt.PointingHandCursor)
        self.sort_periods_button.clicked.connect(self._sort_periods)
        self.calendar_vlayout.addWidget(self.sort_periods_button)

        self.calendar_vlayout.addStretch()

        self.calendar_scroll_area.setWidget(self.calendar_scroll_content)
        calendar_tab_main_layout.addWidget(self.calendar_scroll_area)

        self.tab_widget.addTab(self.calendar_tab, "カレンダー")
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        # 初期データの読み込みと反映
        self._populate_diagram_list()
        self._populate_cal_diag_combo()
        self._rebuild_period_accordions()
        self._update_calendar_details()

    def _set_editing_enabled(self, enabled: bool):
        """編集フォームの有効/無効を切り替える"""
        if enabled:
            self.right_stack.setCurrentWidget(self.edit_form_page)
        else:
            self.right_stack.setCurrentWidget(self.placeholder_page)

        self.diagram_name_edit.setEnabled(enabled)
        self.diagram_initial_edit.setEnabled(enabled)
        self.background_color_picker.setEnabled(enabled)
        self.duplicate_diagram_button.setEnabled(enabled)
        self.delete_diagram_button.setEnabled(enabled)

    def _populate_diagram_list(self):
        """プロジェクトに登録されている運転ダイヤをリストに表示する"""
        self.diagram_list_widget.clear()
        initial_row = 0
        for i, did in enumerate(self.project.diagrams_order):
            diag = self.project.diagrams[did]
            item = QListWidgetItem(diag.get("diagram_name", did))
            item.setData(Qt.UserRole, did)
            bg_color = diag.get("background_color", "#cccccc")
            item.setBackground(QColor(bg_color))
            self.diagram_list_widget.addItem(item)
            if did == self.initial_diagram_id:
                initial_row = i

        if self.diagram_list_widget.count() > 0:
            self.diagram_list_widget.setCurrentRow(initial_row)
            self._set_editing_enabled(True)
        else:
            self._set_editing_enabled(False)

    def _on_diagrams_reordered(self, parent, start, end, destination, row):
        """並び替えられたダイヤリストの状態をプロジェクトデータに反映する"""
        new_order = []
        for i in range(self.diagram_list_widget.count()):
            item = self.diagram_list_widget.item(i)
            new_order.append(item.data(Qt.UserRole))

        self.project.diagrams_order = new_order
        # 親ウィンドウのmodifiedフラグを立てる
        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)
        self._refresh_calendar_tab()

    def _on_diagram_selected(self):
        """ダイヤリストの選択が変更されたときの処理"""
        selected_items = self.diagram_list_widget.selectedItems()
        if not selected_items:
            self._set_editing_enabled(False)
            self.diagram_id_display.clear()
            self.diagram_name_edit.clear()
            self.diagram_initial_edit.clear()
            return

        diagram_id = selected_items[0].data(Qt.UserRole)
        diagram_data = self.project.diagrams.get(diagram_id)
        if not diagram_data:
            self._set_editing_enabled(False)
            return

        self._set_editing_enabled(True)

        # シグナルをブロックして更新
        self.diagram_name_edit.blockSignals(True)
        self.diagram_initial_edit.blockSignals(True)
        self.background_color_picker.blockSignals(True)

        self.diagram_id_display.setText(diagram_id)
        self.diagram_name_edit.setText(diagram_data.get("diagram_name", ""))
        self.diagram_initial_edit.setText(diagram_data.get("diagram_initial", ""))

        current_color = diagram_data.get("background_color", "#cccccc")
        self.background_color_picker.set_color(current_color)

        self.diagram_name_edit.blockSignals(False)
        self.diagram_initial_edit.blockSignals(False)
        self.background_color_picker.blockSignals(False)

    def _on_diagram_name_changed(self, text: str):
        """ダイヤ名が変更されたときにプロジェクトデータとリスト表示を更新する"""
        selected_items = self.diagram_list_widget.selectedItems()
        if not selected_items:
            return
        diagram_id = selected_items[0].data(Qt.UserRole)
        diagram_data = self.project.diagrams.get(diagram_id)
        if not diagram_data:
            return

        diagram_data["diagram_name"] = text
        selected_items[0].setText(text)

        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)
        self._refresh_calendar_tab()

    def _on_diagram_initial_changed(self, text: str):
        """ダイヤ名の1文字表記が変更されたときにプロジェクトデータを更新する"""
        selected_items = self.diagram_list_widget.selectedItems()
        if not selected_items:
            return
        diagram_id = selected_items[0].data(Qt.UserRole)
        diagram_data = self.project.diagrams.get(diagram_id)
        if not diagram_data:
            return

        diagram_data["diagram_initial"] = text
        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)

    def _on_diagram_initial_editing_finished(self):
        """1文字表記の入力欄のフォーカスが外れたときに、2文字目以降を削除する"""
        text = self.diagram_initial_edit.text()
        if len(text) > 1:
            self.diagram_initial_edit.setText(text[0])

    def _on_background_color_changed(self, new_color_hex: str):
        """背景色が変更されたときにプロジェクトデータに反映する"""
        selected_items = self.diagram_list_widget.selectedItems()
        if not selected_items:
            return
        diagram_id = selected_items[0].data(Qt.UserRole)
        diagram_data = self.project.diagrams.get(diagram_id)
        if not diagram_data:
            return

        diagram_data["background_color"] = new_color_hex
        selected_items[0].setBackground(QColor(new_color_hex)) # リストアイテムの背景色も更新

        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)
        self.calendar_widget.updateCells()

    def _on_add_diagram(self):
        """ダイヤの追加ダイアログを表示し、データを追加する"""
        dialog = AddDiagramDialog(self, self.project)
        if dialog.exec() == QDialog.Accepted:
            diagram_id = dialog.id_edit.text().strip()
            diagram_name = dialog.name_edit.text().strip()
            diagram_initial = dialog.initial_edit.text().strip()

            # プロジェクトデータに新規運転ダイヤを追加
            self.project.diagrams[diagram_id] = {
                "diagram_id": diagram_id,
                "diagram_name": diagram_name,
                "diagram_initial": diagram_initial,
                "background_color": "#cccccc", # デフォルトの背景色
                "operations": {},
                "operation_groups": {},
                "operation_groups_order": []
            }
            self.project.diagrams_order.append(diagram_id)

            # 各運行系統に新しいダイヤ用の列車データ枠を作成
            for route in self.project.routes.values():
                if "trains_by_diagram" not in route:
                    route["trains_by_diagram"] = {}
                route["trains_by_diagram"][diagram_id] = {
                    "inbound_trains": {},
                    "inbound_trains_order": [],
                    "outbound_trains": {},
                    "outbound_trains_order": []
                }

            # リスト表示を更新
            self._populate_diagram_list()

            # 新しく追加された項目を選択状態にする
            for i in range(self.diagram_list_widget.count()):
                if self.diagram_list_widget.item(i).data(Qt.UserRole) == diagram_id:
                    self.diagram_list_widget.setCurrentRow(i)
                    break
            self._on_diagram_selected() # 新規追加されたダイヤの編集フォームを表示

            # メインウィンドウに変更フラグを立てる
            if hasattr(self.parent(), "set_modified"):
                self.parent().set_modified(True)
            self._refresh_calendar_tab()

    def _on_duplicate_diagram(self):
        """選択中の運転ダイヤを複製する"""
        selected_items = self.diagram_list_widget.selectedItems()
        if not selected_items:
            return

        source_diagram_id = selected_items[0].data(Qt.UserRole)

        dialog = DuplicateDiagramDialog(self, self.project, source_diagram_id)
        if dialog.exec() != QDialog.Accepted:
            return

        new_diagram_id = dialog.id_edit.text().strip()
        new_diagram_name = dialog.name_edit.text().strip()
        new_diagram_initial = dialog.initial_edit.text().strip()

        # ダイヤ本体のディープコピー
        source_diag = self.project.diagrams.get(source_diagram_id, {})
        new_diag = copy.deepcopy(source_diag)
        new_diag["diagram_id"] = new_diagram_id
        new_diag["diagram_name"] = new_diagram_name
        new_diag["diagram_initial"] = new_diagram_initial

        self.project.diagrams[new_diagram_id] = new_diag
        self.project.diagrams_order.append(new_diagram_id)

        # 各運行系統のデータに対する処理
        for route in self.project.routes.values():
            if "trains_by_diagram" not in route:
                route["trains_by_diagram"] = {}

            # trains_by_diagram に複製したダイヤのエントリを追加
            source_tbd = route["trains_by_diagram"].get(source_diagram_id)
            if source_tbd is not None:
                # to_be_saved が True の列車のみを含むようにコピー
                new_tbd = copy.deepcopy(source_tbd)
                for direction_key in ["inbound_trains", "outbound_trains"]:
                    order_key = f"{direction_key}_order"
                    if direction_key in new_tbd:
                        # to_be_saved=True でない列車を除外
                        filtered_ids = [
                            tid for tid in new_tbd.get(order_key, [])
                            if new_tbd[direction_key].get(tid, {}).get("to_be_saved") is True
                        ]
                        new_tbd[direction_key] = {
                            tid: new_tbd[direction_key][tid]
                            for tid in filtered_ids
                        }
                        new_tbd[order_key] = filtered_ids
            else:
                new_tbd = {
                    "inbound_trains": {},
                    "inbound_trains_order": [],
                    "outbound_trains": {},
                    "outbound_trains_order": []
                }

            route["trains_by_diagram"][new_diagram_id] = new_tbd

            # 逆引き用に列車のマスタデータへダイヤIDを紐付ける
            for train_key in ["inbound_trains", "outbound_trains"]:
                d_trains = source_tbd.get(train_key, {})

                for d_train_id, d_train in d_trains.items():
                    if not d_train["to_be_saved"]:
                        continue

                    m_train = route.get(train_key, {}).get(d_train_id)
                    if m_train is not None and new_diagram_id not in m_train["_diagram_ids"]:
                        m_train["_diagram_ids"].append(new_diagram_id)

        # リスト表示を更新し、複製されたダイヤを選択状態にする
        self._populate_diagram_list()
        for i in range(self.diagram_list_widget.count()):
            if self.diagram_list_widget.item(i).data(Qt.UserRole) == new_diagram_id:
                self.diagram_list_widget.setCurrentRow(i)
                break
        self._on_diagram_selected()

        # メインウィンドウに変更フラグを立てる
        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)
        self._refresh_calendar_tab()

    def _on_delete_diagram(self):
        """選択中の運転ダイヤを削除する"""
        selected_items = self.diagram_list_widget.selectedItems()
        if not selected_items:
            return

        diagram_id = selected_items[0].data(Qt.UserRole)
        diagram_name = self.project.diagrams.get(diagram_id, {}).get("diagram_name", diagram_id)

        reply = QMessageBox.question(
            self,
            "運転ダイヤの削除",
            f"「{diagram_name}」を削除しますか？\n"
            "このダイヤを削除すると、このダイヤのみに登録されている列車も全て削除されます。\n"
            "本当にダイヤを削除しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # プロジェクトデータからダイヤを削除
            del self.project.diagrams[diagram_id]
            self.project.diagrams_order.remove(diagram_id)

            # 各運行系統からこのダイヤの列車情報を削除
            for route_data in self.project.routes.values():
                if "trains_by_diagram" in route_data and diagram_id in route_data["trains_by_diagram"]:
                    del route_data["trains_by_diagram"][diagram_id]

            self._populate_diagram_list() # リストを再構築して表示を更新

            if hasattr(self.parent(), "set_modified"):
                self.parent().set_modified(True)
            self._refresh_calendar_tab()

    # ==========================================
    # カレンダータブ管理メソッド
    # ==========================================
    def _on_tab_changed(self, index: int):
        if index == 1:
            self._refresh_calendar_tab()

    def _refresh_calendar_tab(self):
        self._populate_cal_diag_combo()
        for pw in self.period_widgets:
            pw.refresh_combos()
        self.calendar_widget.updateCells()
        self._update_calendar_details()

    def _populate_cal_diag_combo(self):
        self.cal_diag_combo.blockSignals(True)
        current_data = self.cal_diag_combo.currentData()
        self.cal_diag_combo.clear()
        self.cal_diag_combo.addItem("指定しない", None)
        selected_idx = 0
        for i, did in enumerate(self.project.diagrams_order):
            diag = self.project.diagrams.get(did, {})
            name = diag.get("diagram_name", did)
            self.cal_diag_combo.addItem(name, did)
            if did == current_data:
                selected_idx = i + 1
        self.cal_diag_combo.setCurrentIndex(selected_idx)
        self.cal_diag_combo.blockSignals(False)

    def _on_calendar_selection_changed(self):
        self._update_calendar_details()

    def _update_calendar_details(self):
        selected_dates = self.calendar_widget.selected_dates
        if not selected_dates:
            self.cal_selection_label.setText("日付が選択されていません:")
            self.cal_diag_combo.setEnabled(False)
            self.cal_default_diag_label.setText("-")
            return

        self.cal_diag_combo.setEnabled(True)
        if len(selected_dates) == 1:
            d = next(iter(selected_dates))
            self.cal_selection_label.setText(f"{d.toString('yyyy-MM-dd')}のダイヤ:")
        else:
            self.cal_selection_label.setText(f"{len(selected_dates)}件の日付に対応するダイヤ")

        self.cal_diag_combo.blockSignals(True)
        exceptions = [self.project.date_exceptions.get(d.toString("yyyy-MM-dd")) for d in selected_dates]
        if len(set(exceptions)) == 1:
            target_diag = exceptions[0]
            if target_diag is None:
                self.cal_diag_combo.setCurrentIndex(0)
            else:
                idx = self.cal_diag_combo.findData(target_diag)
                if idx >= 0:
                    self.cal_diag_combo.setCurrentIndex(idx)
                else:
                    self.cal_diag_combo.setCurrentIndex(0)
        else:
            self.cal_diag_combo.setCurrentIndex(-1)
        self.cal_diag_combo.blockSignals(False)

        default_diags = []
        for d in selected_dates:
            iso_date = d.toString("yyyy-MM-dd")
            default_did = get_diagram_for_date(self.project, iso_date, ignore_date_exceptions=True)
            default_diags.append(default_did)

        unique_default_diags = list(set(default_diags))
        if len(unique_default_diags) > 1:
            self.cal_default_diag_label.setText("複数種類のダイヤ")
        else:
            did = unique_default_diags[0]
            if did and did in self.project.diagrams:
                name = self.project.diagrams[did].get("diagram_name", did)
                self.cal_default_diag_label.setText(name)
            elif did:
                self.cal_default_diag_label.setText(did)
            else:
                self.cal_default_diag_label.setText("未設定")

    def _on_cal_diag_combo_changed(self):
        selected_diag_id = self.cal_diag_combo.currentData()
        for d in self.calendar_widget.selected_dates:
            iso_date = d.toString("yyyy-MM-dd")
            if selected_diag_id is None:
                self.project.date_exceptions.pop(iso_date, None)
            else:
                self.project.date_exceptions[iso_date] = selected_diag_id

        self.calendar_widget.updateCells()
        self._update_calendar_details()
        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)

    def _update_periods_ui_state(self):
        """運行区分情報エリアの空表示状態およびソートボタンの有効/無効を更新する"""
        num_periods = len(self.project.calendar_periods)
        self.period_empty_label.setVisible(num_periods == 0)
        self.sort_periods_button.setEnabled(num_periods > 1)

    def _sort_periods(self):
        """運行区分を期間の時系列順にソートする"""
        self.project.calendar_periods.sort(key=lambda p: p.get("start_date") or "1901-01-01")
        self._rebuild_period_accordions()
        self._check_period_overlaps()
        self.calendar_widget.updateCells()
        self._update_calendar_details()
        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)

    def _rebuild_period_accordions(self):
        """運行区分情報アコーディオンウィジェットを全再構築する"""
        for pw in self.period_widgets:
            self.period_area_layout.removeWidget(pw)
            pw.deleteLater()
        self.period_widgets.clear()

        for period in self.project.calendar_periods:
            pw = CalendarPeriodAccordion(self, period)
            self.period_area_layout.addWidget(pw)
            self.period_widgets.append(pw)

        self._update_periods_ui_state()
        self._check_period_overlaps()

    def _remove_period_accordion(self, accordion: CalendarPeriodAccordion):
        if accordion in self.period_widgets:
            self.period_widgets.remove(accordion)
        self.period_area_layout.removeWidget(accordion)
        accordion.deleteLater()
        self._update_periods_ui_state()

    def _on_add_period(self):
        """期間の追加ボタン押下時の処理"""
        if self.project.calendar_periods and self.project.calendar_periods[-1].get("end_date"):
            try:
                last_end = QDate.fromString(self.project.calendar_periods[-1]["end_date"], "yyyy-MM-dd")
                start_qdate = last_end.addDays(1)
            except Exception:
                start_qdate = QDate.currentDate()
        else:
            start_qdate = QDate.currentDate()

        start_str = start_qdate.toString("yyyy-MM-dd")

        new_period = {
            "start_date": start_str,
            "end_date": None,
            "sunday": None,
            "monday": None,
            "tuesday": None,
            "wednesday": None,
            "thursday": None,
            "friday": None,
            "saturday": None,
        }
        self.project.calendar_periods.append(new_period)

        pw = CalendarPeriodAccordion(self, new_period)
        self.period_area_layout.addWidget(pw)
        self.period_widgets.append(pw)

        self._update_periods_ui_state()
        self._check_period_overlaps()
        self.calendar_widget.updateCells()
        self._update_calendar_details()
        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)

    def _on_period_start_date_modified(self):
        """期間の開始日が変更されたときの処理（時系列順ソートの確認）"""
        is_sorted = True
        for i in range(len(self.project.calendar_periods) - 1):
            s1 = self.project.calendar_periods[i].get("start_date") or "1901-01-01"
            s2 = self.project.calendar_periods[i + 1].get("start_date") or "1901-01-01"
            if s1 > s2:
                is_sorted = False
                break

        if not is_sorted:
            reply = QMessageBox.question(
                self,
                "確認",
                "期間別運行区分の並び順が時系列順になっていません。\n運行区分を期間の時系列順にソートしますか？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._sort_periods()
                return

        self._check_period_overlaps()
        self.calendar_widget.updateCells()
        self._update_calendar_details()
        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)

    def _check_period_overlaps(self):
        """期間同士の重複を検査し警告を表示する"""
        periods = self.project.calendar_periods
        for period_widget in self.period_widgets:
            p1 = period_widget.period
            s1 = p1.get("start_date") or "1901-01-01"
            e1 = p1.get("end_date") or "2200-12-31"
            has_overlap = False
            for p2 in periods:
                if p1 is p2:
                    continue
                s2 = p2.get("start_date") or "1901-01-01"
                e2 = p2.get("end_date") or "2200-12-31"

                is_disjoint = (e1 < s2) or (e2 < s1)
                if not is_disjoint:
                    has_overlap = True
                    break

            if has_overlap:
                period_widget.warning_label.setText("指定された期間が他の期間と重複しています")
            else:
                period_widget.warning_label.setText("")
