import random
import string
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, QStackedWidget, QTabWidget, QWidget, QPushButton, QLineEdit, QColorDialog
)
from project import OptDiaProject
from common.gui_utils import create_color_square_pixmap

# 車両運用情報編集ダイアログ
class VehicleOperationEditorDialog(QDialog):
    def __init__(self, parent, project: OptDiaProject, diagram_id: str):
        super().__init__(parent)
        self.project = project
        self.diagram_id = diagram_id
        self.setWindowTitle("車両運用情報")
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
        
        self.group_list = QListWidget()
        self.group_list.setDragDropMode(QListWidget.InternalMove)
        self.group_list.model().rowsMoved.connect(self._on_groups_reordered)
        self.group_list.itemSelectionChanged.connect(self._on_group_selected)
        left_layout.addWidget(self.group_list)
        
        diagram = self.project.diagrams.get(diagram_id, {})
        operation_groups = diagram.get("operation_groups", {})
        operation_groups_order = diagram.get("operation_groups_order", [])

        # 運用グループ名のリスト
        for og_id in operation_groups_order:
            og = operation_groups[og_id]
            item = QListWidgetItem(og.get("operation_group_name", ""))
            item.setData(Qt.UserRole, og_id)
            item.setBackground(QColor(og.get("main_color", "#ffffff")))
            self.group_list.addItem(item)

        # 「運用グループ名のリスト」の下にスペースを設けて、そこに「運用グループの追加」というボタンを追加
        left_layout.addSpacing(10)
        self.add_group_button = QPushButton("運用グループの追加")
        self.add_group_button.clicked.connect(self._on_add_operation_group)
        left_layout.addWidget(self.add_group_button)
            
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
        color_picker_layout = QHBoxLayout()
        self.group_color_square = QLabel()
        self.group_color_square.setFixedSize(20, 20)
        self.group_color_square.setStyleSheet("border: 1px solid #cccccc;")
        color_picker_layout.addWidget(self.group_color_square)
        self.group_color_button = QPushButton("#ffffff")
        self.group_color_button.clicked.connect(self._on_pick_group_color)
        color_picker_layout.addWidget(self.group_color_button)
        color_picker_layout.addStretch()
        tab_group_layout.addLayout(color_picker_layout)

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
            self.group_list.setCurrentRow(0)
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
            self.group_color_button.setText("#ffffff")
            self.group_color_square.setPixmap(create_color_square_pixmap("#ffffff"))
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
        self.group_color_button.setText(main_color)
        self.group_color_square.setPixmap(create_color_square_pixmap(main_color))

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

    def _on_pick_group_color(self):
        selected_items = self.group_list.selectedItems()
        if not selected_items:
            return
        og_id = selected_items[0].data(Qt.UserRole)
        diagram = self.project.diagrams.get(self.diagram_id, {})
        operation_groups = diagram.get("operation_groups", {})
        og = operation_groups.get(og_id)
        if not og:
            return

        initial_color = QColor(og.get("main_color", "#ffffff"))
        color = QColorDialog.getColor(initial_color, self)
        if color.isValid():
            new_color_hex = color.name()
            og["main_color"] = new_color_hex
            self.group_color_button.setText(new_color_hex)
            self.group_color_square.setPixmap(create_color_square_pixmap(new_color_hex))
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