import re
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QWidget, QListWidget, QListWidgetItem,
    QStackedWidget, QColorDialog, QMessageBox
)
from project import OptDiaProject
from common.gui_utils import create_color_square_pixmap

# 運転ダイヤの追加ダイアログ
class AddDiagramDialog(QDialog):
    def __init__(self, parent, project: OptDiaProject):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("運転ダイヤの追加")
        self.setFixedSize(400, 240)

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
        layout.addWidget(self.name_edit)

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

    def _on_add_clicked(self):
        """入力内容を検証し、問題なければ accept する"""
        diagram_id = self.id_edit.text().strip()

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

        self.accept()


# 運転ダイヤ情報編集ダイアログ
class DiagramEditorDialog(QDialog):
    def __init__(self, parent, project: OptDiaProject, initial_diagram_id=None):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("運転ダイヤ情報")
        self.setFixedSize(640, 480)
        self.initial_diagram_id = initial_diagram_id

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

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

        main_layout.addWidget(sidebar)

        # 右側のスタックドウィジェット
        self.right_stack = QStackedWidget()
        main_layout.addWidget(self.right_stack, stretch=1)

        # 1. プレースホルダーページ (データなし)
        self.placeholder_page = QWidget()
        placeholder_layout = QVBoxLayout(self.placeholder_page)
        placeholder_label = QLabel("ダイヤを追加してください")
        placeholder_label.setAlignment(Qt.AlignCenter)
        placeholder_label.setStyleSheet("color: #888888; font-size: 18px;")
        placeholder_layout.addWidget(placeholder_label)
        self.right_stack.addWidget(self.placeholder_page)

        # 2. ダイヤ編集フォームページ
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

        # 背景色
        edit_form_layout.addSpacing(10)
        edit_form_layout.addWidget(QLabel("背景色:"))
        color_picker_layout = QHBoxLayout()
        self.background_color_square = QLabel()
        self.background_color_square.setFixedSize(20, 20)
        self.background_color_square.setStyleSheet("border: 1px solid #cccccc;") # 枠線で視認性を向上
        color_picker_layout.addWidget(self.background_color_square)
        self.background_color_button = QPushButton("#cccccc") # 初期色コード
        self.background_color_button.clicked.connect(self._on_pick_background_color)
        color_picker_layout.addWidget(self.background_color_button)
        color_picker_layout.addStretch()
        edit_form_layout.addLayout(color_picker_layout)

        edit_form_layout.addStretch() # 空白スペース

        # ダイヤ削除ボタン
        self.delete_diagram_button = QPushButton("このダイヤを削除")
        self.delete_diagram_button.setFixedSize(120, 30)
        self.delete_diagram_button.clicked.connect(self._on_delete_diagram)
        self.delete_diagram_button.setStyleSheet("QPushButton { color: #cc3333; border: none; text-decoration: underline; background-color: transparent; }")
        edit_form_layout.addWidget(self.delete_diagram_button, alignment=Qt.AlignRight)

        self.right_stack.addWidget(self.edit_form_page)

        self._populate_diagram_list()

    def _set_editing_enabled(self, enabled: bool):
        """編集フォームの有効/無効を切り替える"""
        if enabled:
            self.right_stack.setCurrentWidget(self.edit_form_page)
        else:
            self.right_stack.setCurrentWidget(self.placeholder_page)

        self.diagram_name_edit.setEnabled(enabled)
        self.background_color_button.setEnabled(enabled)
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

    def _on_diagram_selected(self):
        """ダイヤリストの選択が変更されたときの処理"""
        selected_items = self.diagram_list_widget.selectedItems()
        if not selected_items:
            self._set_editing_enabled(False)
            self.diagram_id_display.clear()
            self.diagram_name_edit.clear()
            self.background_color_button.setText("#cccccc")
            self.background_color_square.setPixmap(create_color_square_pixmap("#cccccc"))
            return

        diagram_id = selected_items[0].data(Qt.UserRole)
        diagram_data = self.project.diagrams.get(diagram_id)
        if not diagram_data:
            self._set_editing_enabled(False)
            return

        self._set_editing_enabled(True)
        
        # シグナルをブロックして更新
        self.diagram_name_edit.blockSignals(True)
        self.diagram_id_display.setText(diagram_id)
        self.diagram_name_edit.setText(diagram_data.get("diagram_name", ""))
        
        current_color = diagram_data.get("background_color", "#cccccc")
        self.background_color_button.setText(current_color)
        self.background_color_square.setPixmap(create_color_square_pixmap(current_color))
        
        self.diagram_name_edit.blockSignals(False)

    def _on_diagram_name_changed(self, text: str):
        """ダイヤ名が変更されたときにプロジェクトデータとリスト表示を更新する"""
        selected_items = self.diagram_list_widget.selectedItems()
        if not selected_items: return
        diagram_id = selected_items[0].data(Qt.UserRole)
        diagram_data = self.project.diagrams.get(diagram_id)
        if not diagram_data: return
        
        diagram_data["diagram_name"] = text
        selected_items[0].setText(text) # リストアイテムの表示も更新
        
        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)

    def _on_pick_background_color(self):
        """背景色選択ダイアログを表示し、選択された色をプロジェクトデータに反映する"""
        selected_items = self.diagram_list_widget.selectedItems()
        if not selected_items: return
        diagram_id = selected_items[0].data(Qt.UserRole)
        diagram_data = self.project.diagrams.get(diagram_id)
        
        initial_color = QColor(diagram_data.get("background_color", "#cccccc"))
        color = QColorDialog.getColor(initial_color, self)
        if color.isValid():
            new_color_hex = color.name()
            diagram_data["background_color"] = new_color_hex
            self.background_color_button.setText(new_color_hex)
            self.background_color_square.setPixmap(create_color_square_pixmap(new_color_hex))
            selected_items[0].setBackground(QColor(new_color_hex)) # リストアイテムの背景色も更新

            if hasattr(self.parent(), "set_modified"):
                self.parent().set_modified(True)

    def _on_add_diagram(self):
        """ダイヤの追加ダイアログを表示し、データを追加する"""
        dialog = AddDiagramDialog(self, self.project)
        if dialog.exec() == QDialog.Accepted:
            diagram_id = dialog.id_edit.text().strip()
            diagram_name = dialog.name_edit.text().strip()

            # プロジェクトデータに新規運転ダイヤを追加
            self.project.diagrams[diagram_id] = {
                "diagram_id": diagram_id,
                "diagram_name": diagram_name,
                "background_color": "#cccccc" # デフォルトの背景色
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

            # 変更フラグを立てる (MainWindow)
            if hasattr(self.parent(), "set_modified"):
                self.parent().set_modified(True)

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
            "このダイヤを削除すると、このダイヤに登録されている列車も全て削除されます。\n"
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