import random
import string
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QMessageBox, QLabel,
    QLineEdit, QListWidget, QListWidgetItem,
    QCheckBox, QColorDialog, QStackedWidget, QComboBox, QFormLayout,
    QWidget, QPushButton
)
from core.project import OptDiaProject
from common.gui_utils import HtmlDelegate, create_color_square_pixmap
from common.widgets import LineSampleWidget, ColorPickerWidget

# 列車種別の追加ダイアログ
class AddTrainTypeDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("種別の追加")
        self.setFixedSize(480, 240)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例) 区間急行")
        form_layout.addRow("列車種別名:", self.name_edit)

        self.nickname_edit = QLineEdit()
        self.nickname_edit.setPlaceholderText("例) ラピート")
        form_layout.addRow("列車愛称(なければ空欄):", self.nickname_edit)

        self.short_name_edit = QLineEdit()
        self.short_name_edit.setPlaceholderText("例) 区急")
        self.short_name_edit.setFixedWidth(100)
        form_layout.addRow("短縮表記:", self.short_name_edit)

        layout.addLayout(form_layout)
        layout.addStretch()

        # ボタンエリア
        button_layout = QHBoxLayout()
        self.add_button = QPushButton("追加")
        self.cancel_button = QPushButton("キャンセル")
        button_layout.addStretch()
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.add_button.clicked.connect(self._on_add_clicked)
        self.cancel_button.clicked.connect(self.reject)

    def _on_add_clicked(self):
        """入力チェック"""
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "エラー", "列車種別名を入力してください。")
            return
        if not self.short_name_edit.text().strip():
            QMessageBox.warning(self, "エラー", "短縮表記を入力してください。")
            return
        self.accept()


# 列車種別情報編集ダイアログ
class TrainTypeEditorDialog(QDialog):
    def __init__(self, parent, project: OptDiaProject):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("種別情報")
        self.setFixedSize(720, 540)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 左側の垂直レイアウト (幅180px固定)
        left_panel = QWidget()
        left_panel.setObjectName("train_type_left_panel")
        left_panel.setFixedWidth(180)
        left_panel.setStyleSheet("#train_type_left_panel { background-color: #f7f7f7; border-right: 1px solid #dddddd; }")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(5)

        left_layout.addWidget(QLabel("<b>種別の一覧</b>"))
        
        self.train_type_list_widget = QListWidget()
        self.train_type_list_widget.setStyleSheet("font-size: 12px;")
        self.train_type_list_widget.setItemDelegate(HtmlDelegate(self))
        self.train_type_list_widget.setDragDropMode(QListWidget.InternalMove)
        self.train_type_list_widget.itemSelectionChanged.connect(self._on_train_type_selected)
        self.train_type_list_widget.model().rowsMoved.connect(self._on_train_types_reordered)
        left_layout.addWidget(self.train_type_list_widget)
        
        self.add_train_type_button = QPushButton("種別の追加")
        self.add_train_type_button.clicked.connect(self._on_add_train_type)
        left_layout.addWidget(self.add_train_type_button)

        main_layout.addWidget(left_panel)

        # 右側の編集用フォームエリア
        self.tt_right_stack = QStackedWidget()
        main_layout.addWidget(self.tt_right_stack, stretch=1)

        # --- 編集フォームページ ---
        self.tt_editor_page = QWidget()
        self.tt_editor_layout = QVBoxLayout(self.tt_editor_page)
        self.tt_editor_layout.setContentsMargins(10, 10, 10, 10)
        
        # フォームコンテナ
        self.tt_form_container = QWidget()
        self.tt_form_layout = QFormLayout(self.tt_form_container)
        
        self.tt_name_edit = QLineEdit()
        self.tt_name_edit.textChanged.connect(self._on_train_type_form_changed)
        self.tt_form_layout.addRow("列車種別名:", self.tt_name_edit)
        
        self.tt_nickname_edit = QLineEdit()
        self.tt_nickname_edit.textChanged.connect(self._on_train_type_form_changed)
        self.tt_form_layout.addRow("列車愛称:", self.tt_nickname_edit)
        
        self.tt_short_name_edit = QLineEdit()
        self.tt_short_name_edit.setFixedWidth(100)
        self.tt_short_name_edit.textChanged.connect(self._on_train_type_form_changed)
        self.tt_form_layout.addRow("短縮表記:", self.tt_short_name_edit)
        
        spacer_tt_1 = QWidget()
        spacer_tt_1.setFixedHeight(5)
        self.tt_form_layout.addRow(spacer_tt_1)

        self.tt_in_service_check = QCheckBox("営業列車")
        self.tt_in_service_check.stateChanged.connect(self._on_train_type_form_changed)
        self.tt_form_layout.addRow("", self.tt_in_service_check)
        
        spacer_tt_2 = QWidget()
        spacer_tt_2.setFixedHeight(5)
        self.tt_form_layout.addRow(spacer_tt_2)

        # 種別の基本色
        self.tt_main_color_picker = ColorPickerWidget("#333333")
        self.tt_main_color_picker.colorChanged.connect(self._on_tt_main_color_changed)
        self.tt_form_layout.addRow("種別の基本色:", self.tt_main_color_picker)
        
        # 時刻表背景色
        self.tt_bg_color_picker = ColorPickerWidget("#ffffff")
        self.tt_bg_color_picker.colorChanged.connect(self._on_tt_bg_color_changed)
        self.tt_form_layout.addRow("時刻表での背景色:", self.tt_bg_color_picker)
        
        # ダイアグラム表示設定
        spacer_tt_3 = QWidget()
        spacer_tt_3.setFixedHeight(10)
        self.tt_form_layout.addRow(spacer_tt_3)

        tt_diagram_label = QLabel("<b>ダイアグラムでの表示</b>")
        tt_diagram_label.setStyleSheet("font-size: 14px;")
        self.tt_form_layout.addRow(tt_diagram_label)
        
        self.tt_line_style_layout = QHBoxLayout()
        self.tt_weight_combo = QComboBox()
        self.tt_weight_combo.addItem("標準", "normal")
        self.tt_weight_combo.addItem("太", "bold")
        self.tt_weight_combo.addItem("細", "thin")
        self.tt_weight_combo.currentIndexChanged.connect(self._on_train_type_form_changed)
        
        self.tt_style_combo = QComboBox()
        self.tt_style_combo.addItem("実線", "solid")
        self.tt_style_combo.addItem("破線", "dashed")
        self.tt_style_combo.addItem("点線", "dotted")
        self.tt_style_combo.currentIndexChanged.connect(self._on_train_type_form_changed)
        
        self.tt_line_style_layout.addWidget(self.tt_weight_combo)
        self.tt_line_style_layout.addWidget(self.tt_style_combo)
        self.tt_form_layout.addRow("線のスタイル:", self.tt_line_style_layout)

        self.line_sample_widget = LineSampleWidget()
        self.tt_form_layout.addRow("プレビュー", self.line_sample_widget)
        
        self.tt_editor_layout.addWidget(self.tt_form_container)
        self.tt_editor_layout.addStretch()

        # 下部ボタンエリア (複製 / 削除)
        bottom_button_layout = QHBoxLayout()
        bottom_button_layout.addStretch()

        # 複製ボタン
        self.duplicate_tt_button = QPushButton("この種別のコピーを作成")
        self.duplicate_tt_button.setFixedWidth(200)
        self.duplicate_tt_button.clicked.connect(self._on_duplicate_train_type)
        bottom_button_layout.addWidget(self.duplicate_tt_button)
        
        # 削除ボタン
        self.delete_tt_button = QPushButton("この種別を削除")
        self.delete_tt_button.setFixedSize(120, 30)
        self.delete_tt_button.clicked.connect(self._on_delete_train_type)
        self.delete_tt_button.setStyleSheet("QPushButton { color: #cc3333; border: none; text-decoration: underline; background-color: transparent; }")
        bottom_button_layout.addWidget(self.delete_tt_button)
        
        self.tt_editor_layout.addLayout(bottom_button_layout)

        self.tt_right_stack.addWidget(self.tt_editor_page)

        # プレースホルダー
        self.tt_placeholder_page = QWidget()
        self.tt_placeholder_layout = QVBoxLayout(self.tt_placeholder_page)
        self.tt_empty_label = QLabel("種別を追加してください")
        self.tt_empty_label.setAlignment(Qt.AlignCenter)
        self.tt_empty_label.setStyleSheet("color: #888888; font-size: 18px;")
        self.tt_placeholder_layout.addWidget(self.tt_empty_label)
        
        self.tt_right_stack.addWidget(self.tt_placeholder_page)

        # 初期状態の設定
        self._set_tt_form_enabled(False)

        # 初期リスト表示
        self._populate_train_type_list()

        # 種別があれば最初を選択
        if self.train_type_list_widget.count() > 0:
            self.train_type_list_widget.setCurrentRow(0)

    def _on_train_types_reordered(self, parent, start, end, destination, row):
        """並び替えられた列車種別リストの状態をプロジェクトデータに反映する"""
        new_order = []
        for i in range(self.train_type_list_widget.count()):
            item = self.train_type_list_widget.item(i)
            new_order.append(item.data(Qt.UserRole))
        
        self.project.train_types_order = new_order
        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)

    def _on_train_type_selected(self):
        """リストで種別が選択された際にフォームの内容を更新する"""
        selected_items = self.train_type_list_widget.selectedItems()
        if not selected_items:
            self._set_tt_form_enabled(False)
            return

        tt_id = selected_items[0].data(Qt.UserRole)
        tt_data = self.project.train_types.get(tt_id)
        if not tt_data:
            self._set_tt_form_enabled(False)
            return

        self._set_tt_form_enabled(True)
        
        # UI更新中のシグナルをブロック
        self.tt_name_edit.blockSignals(True)
        self.tt_nickname_edit.blockSignals(True)
        self.tt_short_name_edit.blockSignals(True)
        self.tt_in_service_check.blockSignals(True)
        self.tt_weight_combo.blockSignals(True)
        self.tt_style_combo.blockSignals(True)
        self.duplicate_tt_button.setEnabled(True)
        self.delete_tt_button.setEnabled(True)

        self.tt_name_edit.setText(tt_data.get("train_type_name", ""))
        self.tt_nickname_edit.setText(tt_data.get("train_name") or "")
        self.tt_short_name_edit.setText(tt_data.get("train_type_short_name", ""))
        self.tt_in_service_check.setChecked(tt_data.get("is_in_service", True))
        
        main_color = tt_data.get("main_color", "#333333")
        self.tt_main_color_picker.set_color(main_color)
        
        bg_color = tt_data.get("background_color", "#ffffff")
        self.tt_bg_color_picker.set_color(bg_color)
        
        weight = tt_data.get("line_weight", "normal")
        idx_w = self.tt_weight_combo.findData(weight)
        self.tt_weight_combo.setCurrentIndex(idx_w if idx_w >= 0 else 0)
        
        style = tt_data.get("line_style", "solid")
        idx_s = self.tt_style_combo.findData(style)
        self.tt_style_combo.setCurrentIndex(idx_s if idx_s >= 0 else 0)

        self.tt_name_edit.blockSignals(False)
        self.tt_nickname_edit.blockSignals(False)
        self.tt_short_name_edit.blockSignals(False)
        self.tt_in_service_check.blockSignals(False)
        self.tt_weight_combo.blockSignals(False)
        self.tt_style_combo.blockSignals(False)
        self.duplicate_tt_button.setEnabled(True)
        self.delete_tt_button.setEnabled(True)
        
        self._update_line_sample()

    def _on_train_type_form_changed(self):
        """フォームの内容が変更された際にプロジェクトデータとリスト表示を更新する"""
        selected_items = self.train_type_list_widget.selectedItems()
        if not selected_items: return
        tt_id = selected_items[0].data(Qt.UserRole)
        tt_data = self.project.train_types.get(tt_id)
        if not tt_data: return
        
        tt_data["train_type_name"] = self.tt_name_edit.text()
        nickname = self.tt_nickname_edit.text().strip()
        tt_data["train_name"] = nickname if nickname else None
        tt_data["train_type_short_name"] = self.tt_short_name_edit.text()
        tt_data["is_in_service"] = self.tt_in_service_check.isChecked()
        tt_data["line_weight"] = self.tt_weight_combo.currentData()
        tt_data["line_style"] = self.tt_style_combo.currentData()
        
        self._update_line_sample()
        
        # リストの再描画のためにアイテムのテキストを再セット
        name = tt_data["train_type_name"]
        train_name = tt_data["train_name"]
        display_name = f"{name} {train_name}" if train_name else name
        main_color = tt_data.get("main_color", "#333333")
        html_text = f"<font color='{main_color}'>{display_name}</font>"
        selected_items[0].setText(html_text)
        
        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)

    def _on_tt_main_color_changed(self, new_hex: str):
        """基本色が変更されたときの処理"""
        selected_items = self.train_type_list_widget.selectedItems()
        if not selected_items: return
        tt_id = selected_items[0].data(Qt.UserRole)
        tt_data = self.project.train_types.get(tt_id)
        if not tt_data: return
        
        tt_data["main_color"] = new_hex
        self._on_train_type_form_changed()

    def _on_tt_bg_color_changed(self, new_hex: str):
        """背景色が変更されたときの処理"""
        selected_items = self.train_type_list_widget.selectedItems()
        if not selected_items: return
        tt_id = selected_items[0].data(Qt.UserRole)
        tt_data = self.project.train_types.get(tt_id)
        if not tt_data: return
        
        tt_data["background_color"] = new_hex
        selected_items[0].setBackground(QColor(new_hex))
        self._on_train_type_form_changed()

    def _populate_train_type_list(self):
        """列車種別の一覧をリストに表示する"""
        self.train_type_list_widget.clear()
        for tt_id in self.project.train_types_order:
            tt = self.project.train_types[tt_id]
            name = tt.get("train_type_name", "")
            train_name = tt.get("train_name")
            display_name = f"{name} {train_name}" if train_name else name

            main_color = tt.get("main_color", "#333333")
            bg_color = tt.get("background_color", "#ffffff")

            # 文字色を反映したHTMLテキストを生成
            html_text = f"<font color='{main_color}'>{display_name}</font>"
            
            item = QListWidgetItem(html_text)
            item.setData(Qt.UserRole, tt_id)
            item.setBackground(QColor(bg_color))
            self.train_type_list_widget.addItem(item)

    def _on_add_train_type(self):
        """「種別の追加」ダイアログを表示し、データを生成する"""
        dialog = AddTrainTypeDialog(self)
        if dialog.exec() == QDialog.Accepted:
            # ランダムな10文字のIDを生成
            chars = string.ascii_letters + string.digits
            while True:
                new_id = ''.join(random.choices(chars, k=10))
                if new_id not in self.project.train_types:
                    break

            nickname = dialog.nickname_edit.text().strip()
            new_type = {
                "train_type_id": new_id,
                "train_type_name": dialog.name_edit.text().strip(),
                "train_type_short_name": dialog.short_name_edit.text().strip(),
                "train_name": nickname if nickname else None,
                "is_in_service": True,
                "main_color": "#333333",
                "background_color": "#ffffff",
                "line_weight": "normal",
                "line_style": "solid"
            }
            
            self.project.train_types[new_id] = new_type
            self.project.train_types_order.append(new_id)
            
            self._populate_train_type_list()
            
            # 新しく追加された種別を選択
            for i in range(self.train_type_list_widget.count()):
                if self.train_type_list_widget.item(i).data(Qt.UserRole) == new_id:
                    self.train_type_list_widget.setCurrentRow(i)
                    break

            if hasattr(self.parent(), "set_modified"):
                self.parent().set_modified(True)

    def _on_duplicate_train_type(self):
        """現在選択中の列車種別のコピーを作成する"""
        selected_items = self.train_type_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "エラー", "複製する列車種別を選択してください。")
            return

        original_tt_id = selected_items[0].data(Qt.UserRole)
        original_tt_data = self.project.train_types.get(original_tt_id)
        if not original_tt_data:
            QMessageBox.warning(self, "エラー", "選択された列車種別データが見つかりません。")
            return

        # 新しいIDを生成
        chars = string.ascii_letters + string.digits
        while True:
            new_id = ''.join(random.choices(chars, k=10))
            if new_id not in self.project.train_types:
                break

        # データを複製し、IDと名前を更新
        new_type = original_tt_data.copy()
        new_type["train_type_id"] = new_id
        new_type["train_type_name"] = f"(コピー) {original_tt_data.get('train_type_name', '')}"

        self.project.train_types[new_id] = new_type
        self.project.train_types_order.append(new_id)

        self._populate_train_type_list()
        self.train_type_list_widget.setCurrentRow(self.train_type_list_widget.count() - 1) # 新しい項目を選択
        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)

    def _update_line_sample(self):
        """線のサンプルウィジェットを現在の設定で更新する"""
        selected_items = self.train_type_list_widget.selectedItems()
        if not selected_items: return
        tt_id = selected_items[0].data(Qt.UserRole)
        tt_data = self.project.train_types.get(tt_id)
        
        self.line_sample_widget.set_line_properties(
            tt_data.get("main_color", "#333333"),
            tt_data.get("line_weight", "normal"),
            tt_data.get("line_style", "solid")
        )

    def _set_tt_form_enabled(self, enabled):
        """右側フォームの表示・非表示を切り替える"""
        if enabled:
            self.tt_right_stack.setCurrentWidget(self.tt_editor_page)
        else:
            self.tt_right_stack.setCurrentWidget(self.tt_placeholder_page)
        
        # 新しいボタンの有効/無効を設定
        self.delete_tt_button.setEnabled(enabled)

    def _on_delete_train_type(self):
        """選択中の列車種別を削除する"""
        selected_items = self.train_type_list_widget.selectedItems()
        if not selected_items:
            return

        tt_id = selected_items[0].data(Qt.UserRole)

        reply = QMessageBox.question(
            self,
            "列車種別の削除",
            "この列車種別を削除すると、この種別が設定されている全ての列車から種別情報が削除されます。\n"
            "本当に列車種別を削除しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # プロジェクトデータから種別を削除
            if tt_id in self.project.train_types:
                del self.project.train_types[tt_id]
            if tt_id in self.project.train_types_order:
                self.project.train_types_order.remove(tt_id)

            # 全ての運行系統の全ての列車（マスタデータ）を走査して種別設定を解除
            for route in self.project.routes.values():
                for key in ["inbound_trains", "outbound_trains"]:
                    master_trains_dict = route.get(key, {})
                    for m_train in master_trains_dict.values():
                        if m_train.get("train_type_id") == tt_id:
                            m_train["train_type_id"] = None

            # UIの更新
            self._populate_train_type_list()

            # 削除後に項目が残っていれば最初の項目を選択状態にする
            if self.train_type_list_widget.count() > 0:
                self.train_type_list_widget.setCurrentRow(0)

            if hasattr(self.parent(), "set_modified"):
                self.parent().set_modified(True)