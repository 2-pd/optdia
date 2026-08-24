import random
import string
from PySide6.QtCore import Qt, QByteArray, QDataStream, QIODevice
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, QStackedWidget, QTabWidget, QWidget, QPushButton, QLineEdit, QColorDialog,
    QGroupBox, QSpinBox, QPlainTextEdit, QFormLayout, QScrollArea, QAbstractItemView
)
from project import OptDiaProject
from common.gui_utils import create_color_square_pixmap
from common.widgets import ColorPickerWidget


class OperationHourSpinBox(QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(-1, 99)
        self.setSuffix("時")

    def textFromValue(self, val: int) -> str:
        if val == -1:
            return "--"
        return str(val)

    def valueFromText(self, text: str) -> int:
        clean_text = text.replace("時", "").strip()
        if clean_text == "--" or not clean_text:
            return -1
        try:
            return int(clean_text)
        except ValueError:
            return -1


class OperationMinuteSpinBox(QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(-1, 60)
        self.setSuffix("分")

    def textFromValue(self, val: int) -> str:
        if val == -1:
            return "--"
        if val < 0:
            val = 59
        elif val > 59:
            val = 0
        return f"{val:02d}"

    def valueFromText(self, text: str) -> int:
        clean_text = text.replace("分", "").strip()
        if clean_text == "--" or not clean_text:
            return -1
        try:
            return int(clean_text)
        except ValueError:
            return -1


class OperationGroupListWidget(QListWidget):
    """運用リスト項目（運用のドラッグアンドドロップ）を受け入れる運用グループのカスタムリストウィジェット"""
    def __init__(self, parent_dialog, parent=None):
        super().__init__(parent)
        self.dialog = parent_dialog

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-optdia-op-id") or event.mimeData().hasFormat("application/x-qabstractitemmodeldatalist"):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-optdia-op-id"):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasFormat("application/x-optdia-op-id"):
            byte_data = event.mimeData().data("application/x-optdia-op-id")
            stream = QDataStream(byte_data, QIODevice.ReadOnly)
            op_id = stream.readQString()
            target_item = self.itemAt(event.position().toPoint())
            if target_item and op_id:
                target_og_id = target_item.data(Qt.UserRole)
                self.dialog._move_operation_to_group(op_id, target_og_id)
            event.acceptProposedAction()
            return

        # 内部で運用グループ自体のドラッグアンドドロップ入れ替えを行う場合はスーパークラスの処理
        super().dropEvent(event)

class OperationListWidget(QListWidget):
    """運用のカスタムMIMEデータをサポートする運用リストウィジェット"""
    def __init__(self, parent=None):
        super().__init__(parent)

    def mimeData(self, items):
        mime_data = super().mimeData(items)
        if items:
            op_id = items[0].data(Qt.UserRole)
            if op_id:
                encoded_data = QByteArray()
                stream = QDataStream(encoded_data, QIODevice.WriteOnly)
                stream.writeQString(op_id)
                mime_data.setData("application/x-optdia-op-id", encoded_data)
        return mime_data

# 車両運用情報編集ダイアログ
class VehicleOperationEditorDialog(QDialog):
    def __init__(self, parent, project: OptDiaProject, diagram_id: str, initial_group_id: str = None, initial_operation_id: str = None):
        super().__init__(parent)
        self.project = project
        self.diagram_id = diagram_id
        self._min_car_count_auto = False
        self._max_car_count_auto = False
        self._is_syncing_car_counts = False
        self._is_updating_time = False

        diagram = self.project.diagrams.get(diagram_id, {})
        diagram_name = diagram.get("diagram_name", "")
        title = f"{diagram_name}の車両運用情報" if diagram_name else "車両運用情報"
        self.setWindowTitle(title)
        self.resize(960, 640)

        # 水平レイアウト
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 左側の垂直レイアウト (幅240px固定)
        left_panel = QWidget()
        left_panel.setFixedWidth(240)
        left_panel.setStyleSheet("background-color: #f7f7f7;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(5)
        
        group_label = QLabel("<b>運用グループ</b>")
        left_layout.addWidget(group_label)
        
        self.group_list = OperationGroupListWidget(self)
        self.group_list.setDragDropMode(QListWidget.DragDrop)
        self.group_list.setDefaultDropAction(Qt.MoveAction)
        self.group_list.setAcceptDrops(True)
        self.group_list.model().rowsMoved.connect(self._on_groups_reordered)
        self.group_list.itemSelectionChanged.connect(self._on_group_selected)
        self.group_list.setStyleSheet("QListWidget::item { height: 32px; }")
        left_layout.addWidget(self.group_list)
        
        diagram = self.project.diagrams.get(diagram_id, {})
        operation_groups = diagram.get("operation_groups", {})
        operation_groups_order = diagram.get("operation_groups_order", [])

        if initial_operation_id and not initial_group_id:
            for og_id, og in operation_groups.items():
                if initial_operation_id in og.get("operations", []):
                    initial_group_id = og_id
                    break

        # 運用グループのリスト
        initial_row = 0
        for idx, og_id in enumerate(operation_groups_order):
            og = operation_groups[og_id]
            item = QListWidgetItem(og.get("operation_group_name", ""))
            item.setData(Qt.UserRole, og_id)
            item.setBackground(QColor(og.get("main_color", "#ffffff")))
            self.group_list.addItem(item)
            if initial_group_id and og_id == initial_group_id:
                initial_row = idx

        # 「運用グループのリスト」の下にスペースを設けて、そこに「運用グループの追加」というボタンを追加
        self.add_group_button = QPushButton("運用グループの追加")
        self.add_group_button.clicked.connect(self._on_add_operation_group)
        left_layout.addWidget(self.add_group_button)

        # 並び替えに関する説明文を追加
        left_layout.addSpacing(10)
        drag_info_label = QLabel("ドラッグ操作により運用の並び替えや別の運用グループへの移動が可能です")
        drag_info_label.setWordWrap(True)
        drag_info_label.setStyleSheet("color: #888888; font-size: 12px;")
        left_layout.addWidget(drag_info_label)
            
        main_layout.addWidget(left_panel, stretch=1)

        # 右側のスタックドウィジェット
        self.stacked_widget = QStackedWidget()
        
        # 1. 運用グループが登録されているときに表示するタブウィジェット
        self.tab_widget = QTabWidget()
        self.tab_operation = QWidget()
        self.tab_group = QWidget()
        self.tab_widget.addTab(self.tab_operation, "運用情報")
        self.tab_widget.addTab(self.tab_group, "運用グループ情報")
        self.stacked_widget.addWidget(self.tab_widget)

        # 運用情報タブのレイアウト設定 (水平レイアウトで2分割)
        tab_op_layout = QHBoxLayout(self.tab_operation)
        tab_op_layout.setContentsMargins(10, 10, 10, 10)
        tab_op_layout.setSpacing(10)

        # 左側の領域(幅160px)
        left_op_panel = QWidget()
        left_op_panel.setFixedWidth(160)
        left_op_layout = QVBoxLayout(left_op_panel)
        left_op_layout.setContentsMargins(0, 0, 0, 0)
        left_op_layout.setSpacing(5)

        op_header_label = QLabel("<b>運用</b>")
        left_op_layout.addWidget(op_header_label)

        self.op_list = OperationListWidget()
        self.op_list.setDragEnabled(True)
        self.op_list.setDragDropMode(QListWidget.DragDrop)
        self.op_list.setDefaultDropAction(Qt.MoveAction)
        self.op_list.model().rowsMoved.connect(self._on_ops_reordered)
        self.op_list.itemSelectionChanged.connect(self._on_operation_selected)
        left_op_layout.addWidget(self.op_list)

        self.add_op_button = QPushButton("運用の追加")
        self.add_op_button.clicked.connect(self._on_add_operation)
        left_op_layout.addWidget(self.add_op_button)

        tab_op_layout.addWidget(left_op_panel)

        # 右側の領域 (編集用)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)

        self.op_detail_container = QWidget()
        right_op_layout = QVBoxLayout(self.op_detail_container)
        right_op_layout.setContentsMargins(10, 0, 10, 0)
        right_op_layout.setSpacing(10)

        # 運用番号
        op_num_layout = QHBoxLayout()
        op_num_layout.addWidget(QLabel("運用番号:"))
        self.op_number_edit = QLineEdit()
        self.op_number_edit.textChanged.connect(self._on_op_number_changed)
        op_num_layout.addWidget(self.op_number_edit)
        right_op_layout.addLayout(op_num_layout)

        # 所定の編成両数
        car_count_layout = QHBoxLayout()
        car_count_layout.addWidget(QLabel("所定の編成両数:"))
        self.op_car_count_spin = QSpinBox()
        self.op_car_count_spin.setFixedWidth(100)
        self.op_car_count_spin.setSuffix("両")
        self.op_car_count_spin.setRange(0, 999)
        self.op_car_count_spin.valueChanged.connect(self._on_op_car_count_changed)
        car_count_layout.addWidget(self.op_car_count_spin)
        car_count_layout.addStretch()
        right_op_layout.addLayout(car_count_layout)

        # 充当可能な編成両数
        allow_car_layout = QHBoxLayout()
        allow_car_layout.addWidget(QLabel("充当可能な編成両数:"))
        
        allow_car_layout.addWidget(QLabel("最小:"))
        self.op_min_car_count_spin = QSpinBox()
        self.op_min_car_count_spin.setFixedWidth(100)
        self.op_min_car_count_spin.setSuffix("両")
        self.op_min_car_count_spin.setRange(0, 999)
        self.op_min_car_count_spin.valueChanged.connect(self._on_op_min_car_count_changed)
        allow_car_layout.addWidget(self.op_min_car_count_spin)

        allow_car_layout.addWidget(QLabel(" 最大:"))
        self.op_max_car_count_spin = QSpinBox()
        self.op_max_car_count_spin.setFixedWidth(100)
        self.op_max_car_count_spin.setSuffix("両")
        self.op_max_car_count_spin.setRange(0, 999)
        self.op_max_car_count_spin.valueChanged.connect(self._on_op_max_car_count_changed)
        allow_car_layout.addWidget(self.op_max_car_count_spin)
        allow_car_layout.addStretch()
        right_op_layout.addLayout(allow_car_layout)

        # 表示色の選択ボタン
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("表示色:"))
        self.op_color_picker = ColorPickerWidget("#ffffff")
        self.op_color_picker.colorChanged.connect(self._on_op_color_changed)
        color_layout.addWidget(self.op_color_picker)
        color_layout.addStretch()
        right_op_layout.addLayout(color_layout)

        # 出庫グループボックス
        start_group = QGroupBox("出庫")
        start_layout = QFormLayout(start_group)
        start_layout.setContentsMargins(10, 10, 10, 10)
        start_layout.setSpacing(8)

        self.start_location_edit = QLineEdit()
        self.start_location_edit.textChanged.connect(self._on_start_location_changed)
        start_layout.addRow("出庫場所:", self.start_location_edit)

        self.start_track_edit = QLineEdit()
        self.start_track_edit.textChanged.connect(self._on_start_track_changed)
        start_layout.addRow("出庫番線等:", self.start_track_edit)

        start_time_layout = QHBoxLayout()
        self.start_hour_spin = OperationHourSpinBox()
        self.start_hour_spin.valueChanged.connect(self._on_start_hour_changed)
        start_time_layout.addWidget(self.start_hour_spin)

        self.start_min_spin = OperationMinuteSpinBox()
        self.start_min_spin.valueChanged.connect(self._on_start_min_changed)
        start_time_layout.addWidget(self.start_min_spin)
        start_time_layout.addStretch()

        self.btn_use_first_train = QPushButton("初列車の情報を使用")
        self.btn_use_first_train.setCursor(Qt.PointingHandCursor)
        self.btn_use_first_train.setStyleSheet("QPushButton { border: none; text-decoration: underline; background-color: transparent; font-size: 12px; }")
        self.btn_use_first_train.clicked.connect(self._on_use_first_train_info)
        start_time_layout.addWidget(self.btn_use_first_train)

        start_layout.addRow("出庫時間:", start_time_layout)
        right_op_layout.addWidget(start_group)

        # 入庫グループボックス
        end_group = QGroupBox("入庫")
        end_layout = QFormLayout(end_group)
        end_layout.setContentsMargins(10, 10, 10, 10)
        end_layout.setSpacing(8)

        self.end_location_edit = QLineEdit()
        self.end_location_edit.textChanged.connect(self._on_end_location_changed)
        end_layout.addRow("入庫場所:", self.end_location_edit)

        self.end_track_edit = QLineEdit()
        self.end_track_edit.textChanged.connect(self._on_end_track_changed)
        end_layout.addRow("入庫番線等:", self.end_track_edit)

        end_time_layout = QHBoxLayout()
        self.end_hour_spin = OperationHourSpinBox()
        self.end_hour_spin.valueChanged.connect(self._on_end_hour_changed)
        end_time_layout.addWidget(self.end_hour_spin)

        self.end_min_spin = OperationMinuteSpinBox()
        self.end_min_spin.valueChanged.connect(self._on_end_min_changed)
        end_time_layout.addWidget(self.end_min_spin)
        end_time_layout.addStretch()

        self.btn_use_last_train = QPushButton("終列車の情報を使用")
        self.btn_use_last_train.setCursor(Qt.PointingHandCursor)
        self.btn_use_last_train.setStyleSheet("QPushButton { border: none; text-decoration: underline; background-color: transparent; font-size: 12px; }")
        self.btn_use_last_train.clicked.connect(self._on_use_last_train_info)
        end_time_layout.addWidget(self.btn_use_last_train)

        end_layout.addRow("入庫時間:", end_time_layout)
        right_op_layout.addWidget(end_group)

        # 備考
        note_layout = QVBoxLayout()
        note_layout.addWidget(QLabel("備考:"))
        self.op_note_edit = QPlainTextEdit()
        self.op_note_edit.textChanged.connect(self._on_op_note_changed)
        self.op_note_edit.setMaximumHeight(80)
        note_layout.addWidget(self.op_note_edit)
        right_op_layout.addLayout(note_layout)

        right_op_layout.addStretch()

        scroll_area.setWidget(self.op_detail_container)
        tab_op_layout.addWidget(scroll_area, stretch=1)

        # 運用グループ情報タブのレイアウト設定
        tab_group_layout = QVBoxLayout(self.tab_group)
        tab_group_layout.setContentsMargins(20, 20, 20, 20)
        tab_group_layout.setSpacing(10)

        # 運用グループ名
        tab_group_layout.addWidget(QLabel("運用グループ名:"))
        self.group_name_edit = QLineEdit()
        self.group_name_edit.textChanged.connect(self._on_group_name_changed)
        tab_group_layout.addWidget(self.group_name_edit)

        # 運用グループの表示色
        tab_group_layout.addSpacing(10)
        tab_group_layout.addWidget(QLabel("運用グループの表示色:"))
        self.group_color_picker = ColorPickerWidget("#ffffff")
        self.group_color_picker.colorChanged.connect(self._on_group_color_changed)
        tab_group_layout.addWidget(self.group_color_picker)

        tab_group_layout.addStretch()

        # 2. 運用グループが登録されていないときに表示するラベル
        self.placeholder_page = QWidget()
        placeholder_layout = QVBoxLayout(self.placeholder_page)
        placeholder_label = QLabel("運用グループを追加してください")
        placeholder_label.setAlignment(Qt.AlignCenter)
        placeholder_label.setStyleSheet("color: #888888; font-size: 18px;")
        placeholder_layout.addWidget(placeholder_label)
        self.stacked_widget.addWidget(self.placeholder_page)

        main_layout.addWidget(self.stacked_widget, stretch=3)

        # 表示の切り替え
        if len(operation_groups_order) > 0:
            self.stacked_widget.setCurrentIndex(0)
            self.group_list.setCurrentRow(initial_row)
            if initial_operation_id:
                for r in range(self.op_list.count()):
                    if self.op_list.item(r).data(Qt.UserRole) == initial_operation_id:
                        self.op_list.setCurrentRow(r)
                        break
        else:
            self.stacked_widget.setCurrentIndex(1)

    def _on_add_operation_group(self):
        diagram = self.project.diagrams.get(self.diagram_id, {})
        operation_groups = diagram.get("operation_groups", {})
        operation_groups_order = diagram.get("operation_groups_order", [])

        # ランダムな英数字8文字のIDを生成
        chars = string.ascii_letters + string.digits
        while True:
            new_id = ''.join(random.choices(chars, k=8))
            if new_id not in operation_groups:
                break

        # 新しい運用グループを追加
        new_group = {
            "operation_group_id": new_id,
            "operation_group_name": "新しい運用グループ",
            "main_color": "#ffffff",
            "operations": []
        }
        operation_groups[new_id] = new_group
        operation_groups_order.append(new_id)

        # リストウィジェットに項目を追加
        item = QListWidgetItem("新しい運用グループ")
        item.setData(Qt.UserRole, new_id)
        item.setBackground(QColor(new_group.get("main_color", "#ffffff")))
        self.group_list.addItem(item)

        # 表示の切り替えと選択
        if len(operation_groups_order) == 1:
            self.stacked_widget.setCurrentIndex(0)
            self.group_list.setCurrentRow(0)
        else:
            self.group_list.setCurrentRow(self.group_list.count() - 1)

        # 変更されたことを通知
        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)

    def _on_group_selected(self):
        selected_items = self.group_list.selectedItems()
        if not selected_items:
            self.group_name_edit.clear()
            self.group_color_picker.set_color("#ffffff")
            self.op_list.clear()
            self._on_operation_selected()
            return

        og_id = selected_items[0].data(Qt.UserRole)
        diagram = self.project.diagrams.get(self.diagram_id, {})
        operation_groups = diagram.get("operation_groups", {})
        og = operation_groups.get(og_id)
        if not og:
            return

        self.group_name_edit.blockSignals(True)
        self.group_name_edit.setText(og.get("operation_group_name", ""))
        self.group_name_edit.blockSignals(False)

        main_color = og.get("main_color", "#ffffff")
        self.group_color_picker.set_color(main_color)

        # 運用のクリアと読み込み
        self.op_list.blockSignals(True)
        self.op_list.clear()
        operations_dict = diagram.get("operations", {})
        for op_id in og.get("operations", []):
            op = operations_dict.get(op_id)
            if op:
                item = QListWidgetItem(op.get("operation_number", ""))
                item.setData(Qt.UserRole, op_id)
                self.op_list.addItem(item)
        self.op_list.blockSignals(False)

        # 運用が存在すれば最初の運用を選択、なければ右側のフォームを無効化
        if self.op_list.count() > 0:
            self.op_list.setCurrentRow(0)
        else:
            self.op_list.clearSelection()
            self._on_operation_selected()

    def _on_operation_selected(self):
        self._min_car_count_auto = False
        self._max_car_count_auto = False
        selected_items = self.op_list.selectedItems()
        if not selected_items:
            self.op_detail_container.setEnabled(False)
            self._clear_op_details()
            return

        self.op_detail_container.setEnabled(True)
        op_id = selected_items[0].data(Qt.UserRole)
        diagram = self.project.diagrams.get(self.diagram_id, {})
        op = diagram.get("operations", {}).get(op_id)
        if not op:
            return

        # 全てのシグナルをブロック
        self._block_op_signals(True)

        self.op_number_edit.setText(op.get("operation_number", ""))
        self.op_car_count_spin.setValue(op.get("car_count", 0))
        self.op_min_car_count_spin.setValue(op.get("min_car_count", 0))
        self.op_max_car_count_spin.setValue(op.get("max_car_count", 0))

        main_color = op.get("main_color", "#ffffff")
        self.op_color_picker.set_color(main_color)

        self.start_location_edit.setText(op.get("start_location", ""))
        self.start_track_edit.setText(op.get("start_track") or "")
        
        sh, sm = self._parse_time(op.get("start_time"))
        self.start_hour_spin.setValue(sh)
        self.start_min_spin.setValue(sm)

        self.end_location_edit.setText(op.get("end_location", ""))
        self.end_track_edit.setText(op.get("end_track") or "")

        eh, em = self._parse_time(op.get("end_time"))
        self.end_hour_spin.setValue(eh)
        self.end_min_spin.setValue(em)

        self.op_note_edit.setPlainText(op.get("note", ""))

        self._block_op_signals(False)

    def _parse_time(self, time_str):
        if not time_str:
            return -1, -1
        try:
            parts = time_str.split(":")
            h = int(parts[0]) if len(parts) > 0 else -1
            m = int(parts[1]) if len(parts) > 1 else -1
            return h, m
        except Exception:
            return -1, -1

    def _time_to_seconds(self, time_str: str):
        if not time_str:
            return None
        try:
            parts = time_str.split(":")
            h = int(parts[0]) if len(parts) > 0 else 0
            m = int(parts[1]) if len(parts) > 1 else 0
            s = int(parts[2]) if len(parts) > 2 else 0
            return h * 3600 + m * 60 + s
        except Exception:
            return None

    def _block_op_signals(self, block):
        self.op_number_edit.blockSignals(block)
        self.op_car_count_spin.blockSignals(block)
        self.op_min_car_count_spin.blockSignals(block)
        self.op_max_car_count_spin.blockSignals(block)
        self.op_color_picker.blockSignals(block)
        self.start_location_edit.blockSignals(block)
        self.start_track_edit.blockSignals(block)
        self.start_hour_spin.blockSignals(block)
        self.start_min_spin.blockSignals(block)
        self.end_location_edit.blockSignals(block)
        self.end_track_edit.blockSignals(block)
        self.end_hour_spin.blockSignals(block)
        self.end_min_spin.blockSignals(block)
        self.op_note_edit.blockSignals(block)

    def _clear_op_details(self):
        self._min_car_count_auto = False
        self._max_car_count_auto = False
        self._block_op_signals(True)
        self.op_number_edit.clear()
        self.op_car_count_spin.setValue(0)
        self.op_min_car_count_spin.setValue(0)
        self.op_max_car_count_spin.setValue(0)
        self.op_color_picker.set_color("#ffffff")
        self.start_location_edit.clear()
        self.start_track_edit.clear()
        self.start_hour_spin.setValue(-1)
        self.start_min_spin.setValue(-1)
        self.end_location_edit.clear()
        self.end_track_edit.clear()
        self.end_hour_spin.setValue(-1)
        self.end_min_spin.setValue(-1)
        self.op_note_edit.clear()
        self._block_op_signals(False)

    def _get_current_op(self):
        selected_items = self.op_list.selectedItems()
        if not selected_items:
            return None, None
        op_id = selected_items[0].data(Qt.UserRole)
        diagram = self.project.diagrams.get(self.diagram_id, {})
        op = diagram.get("operations", {}).get(op_id)
        return op_id, op

    def _on_op_number_changed(self, text: str):
        op_id, op = self._get_current_op()
        if op:
            op["operation_number"] = text
            selected_items = self.op_list.selectedItems()
            if selected_items:
                selected_items[0].setText(text)
            self._set_modified()

    def _on_op_car_count_changed(self, val: int):
        op_id, op = self._get_current_op()
        if op:
            op["car_count"] = val
            self._is_syncing_car_counts = True
            try:
                if self.op_min_car_count_spin.value() == 0 or self._min_car_count_auto:
                    self._min_car_count_auto = True
                    self.op_min_car_count_spin.setValue(val)
                    op["min_car_count"] = val
                if self.op_max_car_count_spin.value() == 0 or self._max_car_count_auto:
                    self._max_car_count_auto = True
                    self.op_max_car_count_spin.setValue(val)
                    op["max_car_count"] = val
            finally:
                self._is_syncing_car_counts = False
            self._set_modified()

    def _on_op_min_car_count_changed(self, val: int):
        if not self._is_syncing_car_counts:
            self._min_car_count_auto = False
        op_id, op = self._get_current_op()
        if op:
            op["min_car_count"] = val
            self._set_modified()

    def _on_op_max_car_count_changed(self, val: int):
        if not self._is_syncing_car_counts:
            self._max_car_count_auto = False
        op_id, op = self._get_current_op()
        if op:
            op["max_car_count"] = val
            self._set_modified()

    def _on_op_color_changed(self, new_color_hex: str):
        op_id, op = self._get_current_op()
        if not op:
            return
        op["main_color"] = new_color_hex
        self._set_modified()

    def _on_start_location_changed(self, text: str):
        op_id, op = self._get_current_op()
        if op:
            op["start_location"] = text
            self._set_modified()

    def _on_start_track_changed(self, text: str):
        op_id, op = self._get_current_op()
        if op:
            op["start_track"] = text if text else None
            self._set_modified()

    def _on_start_hour_changed(self, val: int):
        if self._is_updating_time:
            return
        self._is_updating_time = True
        try:
            if val == -1:
                self.start_min_spin.setValue(-1)
            elif val >= 0 and self.start_min_spin.value() == -1:
                self.start_min_spin.setValue(0)
        finally:
            self._is_updating_time = False
        self._on_start_time_changed()

    def _on_start_min_changed(self, val: int):
        if self._is_updating_time:
            return
        self._is_updating_time = True
        try:
            h = self.start_hour_spin.value()
            if h == -1:
                if val >= 0:
                    self.start_hour_spin.setValue(0)
                    if val >= 60:
                        self.start_min_spin.setValue(0)
                        self.start_hour_spin.setValue(1)
            else:
                if val >= 60:
                    self.start_min_spin.setValue(0)
                    self.start_hour_spin.setValue(min(99, h + 1))
                elif val <= -1:
                    if h > 0:
                        self.start_min_spin.setValue(59)
                        self.start_hour_spin.setValue(h - 1)
                    else:
                        self.start_min_spin.setValue(-1)
                        self.start_hour_spin.setValue(-1)
        finally:
            self._is_updating_time = False
        self._on_start_time_changed()

    def _on_start_time_changed(self):
        op_id, op = self._get_current_op()
        if op:
            h = self.start_hour_spin.value()
            m = self.start_min_spin.value()
            if h == -1 or m == -1:
                op["start_time"] = None
            else:
                op["start_time"] = f"{h:02d}:{m:02d}:00"
            self._set_modified()

    def _on_end_location_changed(self, text: str):
        op_id, op = self._get_current_op()
        if op:
            op["end_location"] = text
            self._set_modified()

    def _on_end_track_changed(self, text: str):
        op_id, op = self._get_current_op()
        if op:
            op["end_track"] = text if text else None
            self._set_modified()

    def _on_end_hour_changed(self, val: int):
        if self._is_updating_time:
            return
        self._is_updating_time = True
        try:
            if val == -1:
                self.end_min_spin.setValue(-1)
            elif val >= 0 and self.end_min_spin.value() == -1:
                self.end_min_spin.setValue(0)
        finally:
            self._is_updating_time = False
        self._on_end_time_changed()

    def _on_end_min_changed(self, val: int):
        if self._is_updating_time:
            return
        self._is_updating_time = True
        try:
            h = self.end_hour_spin.value()
            if h == -1:
                if val >= 0:
                    self.end_hour_spin.setValue(0)
                    if val >= 60:
                        self.end_min_spin.setValue(0)
                        self.end_hour_spin.setValue(1)
            else:
                if val >= 60:
                    self.end_min_spin.setValue(0)
                    self.end_hour_spin.setValue(min(99, h + 1))
                elif val <= -1:
                    if h > 0:
                        self.end_min_spin.setValue(59)
                        self.end_hour_spin.setValue(h - 1)
                    else:
                        self.end_min_spin.setValue(-1)
                        self.end_hour_spin.setValue(-1)
        finally:
            self._is_updating_time = False
        self._on_end_time_changed()

    def _on_end_time_changed(self):
        op_id, op = self._get_current_op()
        if op:
            h = self.end_hour_spin.value()
            m = self.end_min_spin.value()
            if h == -1 or m == -1:
                op["end_time"] = None
            else:
                op["end_time"] = f"{h:02d}:{m:02d}:00"
            self._set_modified()

    def _get_operation_trains_info(self, target_op_id: str):
        """
        現在編集中の車両運用(target_op_id)が割り当てられている列車の情報を収集し、
        各列車の最初の発車時刻・最後の到着時刻および始発駅・終着駅を取得してリストで返す。
        """
        matched_trains = []
        for route in self.project.routes.values():
            tbd = route.get("trains_by_diagram", {}).get(self.diagram_id, {})
            for direction in ["inbound_trains", "outbound_trains"]:
                m_trains = route.get(direction, {})
                d_trains = tbd.get(direction, {})
                for train_id, d_train in d_trains.items():
                    ops = d_train.get("operations", [])
                    op_ids = [op.get("operation_id") if isinstance(op, dict) else op for op in ops]
                    if target_op_id in op_ids:
                        m_train = m_trains.get(train_id)
                        if not m_train:
                            continue
                        stops = m_train.get("stops", [])
                        if not stops:
                            continue

                        # 最初の発車時刻 (最初の有効な発車時刻、なければ最初の到着時刻)
                        first_dep_str = None
                        for s in stops:
                            if s.get("departure_time"):
                                first_dep_str = s["departure_time"]
                                break
                            elif s.get("arrival_time") and first_dep_str is None:
                                first_dep_str = s["arrival_time"]

                        # 最後の到着時刻 (最後の有効な到着時刻、なければ最後の発車時刻)
                        last_arr_str = None
                        for s in reversed(stops):
                            if s.get("arrival_time"):
                                last_arr_str = s["arrival_time"]
                                break
                            elif s.get("departure_time") and last_arr_str is None:
                                last_arr_str = s["departure_time"]

                        if first_dep_str is None and last_arr_str is None:
                            continue

                        first_dep_sec = self._time_to_seconds(first_dep_str) if first_dep_str else None
                        last_arr_sec = self._time_to_seconds(last_arr_str) if last_arr_str else None

                        sort_dep_sec = first_dep_sec if first_dep_sec is not None else (last_arr_sec if last_arr_sec is not None else 0)

                        first_station_id = stops[0].get("station_id") if stops else None
                        last_station_id = stops[-1].get("station_id") if stops else None

                        matched_trains.append({
                            "train_id": train_id,
                            "first_dep_sec": sort_dep_sec,
                            "first_dep_str": first_dep_str,
                            "last_arr_sec": last_arr_sec,
                            "last_arr_str": last_arr_str,
                            "first_station_id": first_station_id,
                            "last_station_id": last_station_id,
                        })
        return matched_trains

    def _on_use_first_train_info(self):
        op_id, op = self._get_current_op()
        if not op_id or not op:
            return
        matched_trains = self._get_operation_trains_info(op_id)
        if not matched_trains:
            return
        first_train = min(matched_trains, key=lambda t: t["first_dep_sec"])
        dep_str = first_train.get("first_dep_str")
        if dep_str:
            h, m = self._parse_time(dep_str)
            self.start_hour_spin.setValue(h)
            self.start_min_spin.setValue(m)
            self._on_start_time_changed()

        first_st_id = first_train.get("first_station_id")
        if first_st_id and self.project:
            st = self.project.stations.get(first_st_id, {})
            st_name = st.get("station_name", "")
            if st_name:
                self.start_location_edit.setText(st_name)

    def _on_use_last_train_info(self):
        op_id, op = self._get_current_op()
        if not op_id or not op:
            return
        matched_trains = self._get_operation_trains_info(op_id)
        if not matched_trains:
            return
        last_train = max(matched_trains, key=lambda t: (t["last_arr_sec"] if t["last_arr_sec"] is not None else t["first_dep_sec"]))
        arr_str = last_train.get("last_arr_str") or last_train.get("first_dep_str")
        if arr_str:
            h, m = self._parse_time(arr_str)
            self.end_hour_spin.setValue(h)
            self.end_min_spin.setValue(m)
            self._on_end_time_changed()

        last_st_id = last_train.get("last_station_id")
        if last_st_id and self.project:
            st = self.project.stations.get(last_st_id, {})
            st_name = st.get("station_name", "")
            if st_name:
                self.end_location_edit.setText(st_name)

    def _on_op_note_changed(self):
        op_id, op = self._get_current_op()
        if op:
            op["note"] = self.op_note_edit.toPlainText()
            self._set_modified()

    def _set_modified(self):
        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)

    def _on_add_operation(self):
        selected_items = self.group_list.selectedItems()
        if not selected_items:
            return
        og_id = selected_items[0].data(Qt.UserRole)
        diagram = self.project.diagrams.get(self.diagram_id, {})
        operation_groups = diagram.get("operation_groups", {})
        og = operation_groups.get(og_id)
        if not og:
            return

        # ランダムな英数字10文字のIDを生成
        chars = string.ascii_letters + string.digits
        operations = diagram.get("operations", {})
        while True:
            new_op_id = ''.join(random.choices(chars, k=10))
            if new_op_id not in operations:
                break

        new_op = {
            "operation_number": "新しい運用",
            "car_count": 0,
            "min_car_count": 0,
            "max_car_count": 0,
            "main_color": "#ffffff",
            "start_location": "",
            "start_track": None,
            "start_time": None,
            "end_location": "",
            "end_track": None,
            "end_time": None,
            "note": "",
            "temporary_stabling_events": []
        }

        operations[new_op_id] = new_op
        og.setdefault("operations", []).append(new_op_id)

        # リストウィジェットに追加
        item = QListWidgetItem("新しい運用")
        item.setData(Qt.UserRole, new_op_id)
        self.op_list.addItem(item)

        # 新しく追加された運用を選択
        self.op_list.setCurrentRow(self.op_list.count() - 1)
        self._set_modified()

    def _on_ops_reordered(self, parent, start, end, destination, row):
        selected_items = self.group_list.selectedItems()
        if not selected_items:
            return
        og_id = selected_items[0].data(Qt.UserRole)
        diagram = self.project.diagrams.get(self.diagram_id, {})
        operation_groups = diagram.get("operation_groups", {})
        og = operation_groups.get(og_id)
        if not og:
            return

        new_order = []
        for i in range(self.op_list.count()):
            item = self.op_list.item(i)
            new_order.append(item.data(Qt.UserRole))
        og["operations"] = new_order
        self._set_modified()

    def _on_group_name_changed(self, text: str):
        selected_items = self.group_list.selectedItems()
        if not selected_items:
            return
        og_id = selected_items[0].data(Qt.UserRole)
        diagram = self.project.diagrams.get(self.diagram_id, {})
        operation_groups = diagram.get("operation_groups", {})
        og = operation_groups.get(og_id)
        if not og:
            return

        og["operation_group_name"] = text
        selected_items[0].setText(text)

        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)

    def _on_group_color_changed(self, new_color_hex: str):
        selected_items = self.group_list.selectedItems()
        if not selected_items:
            return
        og_id = selected_items[0].data(Qt.UserRole)
        diagram = self.project.diagrams.get(self.diagram_id, {})
        operation_groups = diagram.get("operation_groups", {})
        og = operation_groups.get(og_id)
        if not og:
            return

        og["main_color"] = new_color_hex
        selected_items[0].setBackground(QColor(new_color_hex))

        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)

    def _on_groups_reordered(self, parent, start, end, destination, row):
        new_order = []
        for i in range(self.group_list.count()):
            item = self.group_list.item(i)
            new_order.append(item.data(Qt.UserRole))
        
        diagram = self.project.diagrams.get(self.diagram_id, {})
        diagram["operation_groups_order"] = new_order
        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)

    def _move_operation_to_group(self, op_id: str, target_group_id: str):
        selected_items = self.group_list.selectedItems()
        source_group_id = selected_items[0].data(Qt.UserRole) if selected_items else None
        if not source_group_id or source_group_id == target_group_id:
            return

        diagram = self.project.diagrams.get(self.diagram_id, {})
        operation_groups = diagram.get("operation_groups", {})
        source_og = operation_groups.get(source_group_id)
        target_og = operation_groups.get(target_group_id)

        if not source_og or not target_og:
            return

        source_ops = source_og.get("operations", [])
        if op_id in source_ops:
            source_ops.remove(op_id)

        target_ops = target_og.setdefault("operations", [])
        if op_id not in target_ops:
            target_ops.append(op_id)

        self._set_modified()

        # 現在の運用リストから該当運用を削除し、必要に応じて選択を更新
        self._on_group_selected()