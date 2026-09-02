import random
import string
import copy
from PySide6.QtCore import Qt, QModelIndex, QSize
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QGroupBox, QLineEdit,
    QComboBox, QLabel, QScrollArea, QWidget, QListWidget, QListWidgetItem,
    QCheckBox, QPlainTextEdit, QMessageBox, QRadioButton, QButtonGroup, QSpinBox
)
from common.gui_utils import HtmlDelegate
from core.project import OptDiaProject
from dialogs.operation import VehicleOperationEditorDialog

# 列車を選択するためのポップアップダイアログ
class TrainPicker(QDialog):
    def __init__(self, parent, project: OptDiaProject, diagram_id: str, route_id: str, 
                 direction: str, excluded_ids: set, current_train_id: str = None, min_departure_time: str = None):
        super().__init__(parent, Qt.Popup)
        self.selected_train_id = None

        # 背景をライトグレーに設定
        # 子要素が背景色を引き継がないよう明示的に白を指定
        self.setStyleSheet("""
            QDialog { background-color: #f7f7f7; }
            QLineEdit, QListWidget { background-color: white; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("列車番号で検索...")
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        layout.addWidget(self.search_edit)
        
        self.list_widget = QListWidget(self)
        self.list_widget.setStyleSheet("border: 1px solid #dddddd;")
        self.list_widget.setItemDelegate(HtmlDelegate(self))
        
        route = project.routes.get(route_id, {})
        tbd = route.get("trains_by_diagram", {}).get(diagram_id, {})
        train_key = "inbound_trains" if direction == "inbound" else "outbound_trains"
        order_key = train_key + "_order"
        
        d_trains = tbd.get(train_key, {})
        m_trains = route.get(train_key, {})
        order = tbd.get(order_key, [])
        
        for tid in order:
            if tid in excluded_ids:
                continue
            
            d_train = d_trains[tid]
            m_train = m_trains[tid]
            if not d_train.get("to_be_saved"):
                continue

            # 列車情報を構築 (列車番号、種別、始発駅時刻)
            num = m_train.get("train_number") or "(番号なし)"
            tt = project.train_types.get(m_train.get("train_type_id"))
            tt_color = tt.get("main_color", "#333333") if tt else "#333333"

            first_stop = next((s for s in m_train.get("stops", []) if s.get("departure_time")), None)
            # 始発時刻が編集対象列車の終着時刻より前の場合は除外
            if min_departure_time and first_stop and first_stop.get("departure_time"):
                if first_stop["departure_time"] < min_departure_time:
                    continue

            tt_short = (tt.get("train_type_short_name") or tt.get("train_type_name") or "") if tt else ""
            tt_display = f"<font color='{tt_color}'>{tt_short}</font>"
            
            if first_stop:
                s_name = project.stations.get(first_stop["station_id"], {}).get("station_name", first_stop["station_id"])
                display_text = f"{num} {tt_display} <font color='#666666'>({s_name} {first_stop['departure_time'][:5]}発)</font>"
                search_text = f"{num} {tt_short} {s_name}"
            else:
                display_text = f"{num} {tt_display}"
                search_text = f"{num} {tt_short}"
                
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, tid)
            item.setData(Qt.UserRole + 1, search_text.lower())
            self.list_widget.addItem(item)
            
            # 現在設定されている列車がある場合はハイライトし、スクロールする
            if tid == current_train_id:
                self.list_widget.setCurrentItem(item)
                self.list_widget.scrollToItem(item)
            
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)

        # フィルタリングに関する説明ラベルを追加
        if min_departure_time:
            info_label = QLabel("始発時刻がもとの列車の終着時刻より早い列車は表示されません")
            info_label.setStyleSheet("color: gray; font-size: 12px;")
            info_label.setWordWrap(True)
            layout.addWidget(info_label)
        
        # 呼び出し元のボタンの幅に合わせる
        self.setFixedWidth(parent.width() if parent else 300)
        self.setFixedHeight(240 if min_departure_time else 220)
        self.search_edit.setFocus()

    def _on_search_text_changed(self, text):
        """検索テキストに基づいてリストアイテムをフィルタリングする"""
        search_term = text.lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            searchable = item.data(Qt.UserRole + 1) or ""
            item.setHidden(search_term not in searchable)

    def _on_item_clicked(self, item):
        self.selected_train_id = item.data(Qt.UserRole)
        self.accept()

# 運転ダイヤの選択ダイアログ
class DiagramPicker(QDialog):
    def __init__(self, parent, project: OptDiaProject, train_id: str, current_diagram_id: str, route_id: str, direction: str):
        super().__init__(parent)
        self.project = project
        self.train_id = train_id
        self.current_diagram_id = current_diagram_id
        self.route_id = route_id
        self.direction = direction
        
        self._initial_checkbox_states = {} # 初期チェック状態を保持
        self.setWindowTitle("運転ダイヤの選択")
        self.setFixedSize(320, 480)
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("この列車が運転されるダイヤを選択してください:"))
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignTop)
        
        self.checkboxes = {} # diagram_id -> QCheckBox
        
        # 現在の方面のマスタ列車情報を取得して、既に割り当てられているダイヤを特定
        route = project.routes.get(route_id)
        train_key = "inbound_trains" if direction == "inbound" else "outbound_trains"
        m_train = route.get(train_key, {}).get(train_id, {})
        active_diagram_ids = m_train.get("_diagram_ids", [])
        
        # プロジェクトのダイヤ定義順にチェックボックスを並べる
        for did in project.diagrams_order:
            diag = project.diagrams[did]
            bg_color = diag.get("background_color", "#ffffff")
            cb = QCheckBox(diag.get("diagram_name", did))
            if did in active_diagram_ids:
                cb.setChecked(True)
            
            # 現在表示中のダイヤは解除不可
            if did == current_diagram_id:
                cb.setEnabled(False)
                cb.setChecked(True)
            self._initial_checkbox_states[did] = cb.isChecked() # 初期状態を記録
            cb.setStyleSheet(f"QCheckBox {{ font-size: 14px; background-color: {bg_color}; }}")
            
            self.checkboxes[did] = cb
            self.scroll_layout.addWidget(cb)
            
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        buttons = QHBoxLayout()
        select_all_btn = QPushButton("すべて選択")
        buttons.addWidget(select_all_btn)
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("キャンセル")
        buttons.addStretch()
        buttons.addWidget(ok_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)
        
        select_all_btn.clicked.connect(self._on_select_all)
        ok_btn.clicked.connect(self._on_ok)
        cancel_btn.clicked.connect(self.reject)

    def _on_select_all(self):
        """すべてのチェックボックスを選択状態にする（ただし、無効化されているものは除く）"""
        for cb in self.checkboxes.values():
            if cb.isEnabled():
                cb.setChecked(True)

    def _on_ok(self):
        has_changed = False
        route = self.project.routes.get(self.route_id)
        train_key = "inbound_trains" if self.direction == "inbound" else "outbound_trains"
        order_key = train_key + "_order"
        m_train = route.get(train_key, {}).get(self.train_id)
        
        events_to_push = []

        # 現在のダイヤでダミー列車（未保存）だった場合、他のダイヤへの割り当て等により保存対象へ昇格させる
        current_tbd = route.get("trains_by_diagram", {}).get(self.current_diagram_id, {})
        current_d_train = current_tbd.get(train_key, {}).get(self.train_id)
        if current_d_train and not current_d_train.get("to_be_saved"):
            current_d_train["to_be_saved"] = True
            has_changed = True
        elif current_d_train and current_d_train.get("to_be_saved") and not self._initial_checkbox_states.get(self.current_diagram_id, False):
            has_changed = True # 現在のダイヤが元々to_be_saved=Falseだったが、今回to_be_saved=Trueになった場合

        from core.events import AddTrainDiagramEvent, RemoveTrainDiagramEvent

        for did, cb in self.checkboxes.items():
            if did == self.current_diagram_id: continue # 現在のダイヤはスキップ
                
            tbd = route.get("trains_by_diagram", {}).get(did, {})
            d_trains, order = tbd.get(train_key), tbd.get(order_key)
            
            # チェック状態が変更されたか、または初期状態と異なるかを確認
            if cb.isChecked() and self.train_id not in d_trains:
                # ダイヤへの追加: 列車ID以外のキーはNoneまたは空配列で初期化
                new_d_train = {
                    "train_id": self.train_id, "operations": [], "car_count": None,
                    "destination": None, "subsequent_trains": [], "to_be_saved": True
                }
                d_trains[self.train_id] = new_d_train
                # 挿入位置の決定: 末尾のダミー列車(to_be_saved=False)より前に挿入
                insert_idx = len(order)
                for i, tid in enumerate(order):
                    if not d_trains.get(tid, {}).get("to_be_saved", True):
                        insert_idx = i
                        break
                order.insert(insert_idx, self.train_id)
                if did not in m_train["_diagram_ids"]: m_train["_diagram_ids"].append(did)
                events_to_push.append(AddTrainDiagramEvent(self.route_id, self.direction, self.train_id, did, insert_idx, new_d_train))
                has_changed = True
            elif not cb.isChecked() and self.train_id in d_trains:
                # ダイヤからの削除
                old_d_train = copy.deepcopy(d_trains[self.train_id])
                old_idx = order.index(self.train_id) if self.train_id in order else 0
                if self.train_id in order: order.remove(self.train_id)
                del d_trains[self.train_id]
                if did in m_train["_diagram_ids"]: m_train["_diagram_ids"].remove(did)
                events_to_push.append(RemoveTrainDiagramEvent(self.route_id, self.direction, self.train_id, did, old_idx, old_d_train))
                has_changed = True

        # 逆引き用ダイヤIDリストをプロジェクト順でソート
        m_train["_diagram_ids"].sort(key=lambda x: self.project.diagrams_order.index(x) if x in self.project.diagrams_order else 999)
        
        view = self.parent()
        if view and hasattr(view, "model"):
            model = view.model()
            if hasattr(model, "history_manager") and model.history_manager and events_to_push:
                model.history_manager.push_events(events_to_push)

        if has_changed:
            self._set_modified()
        self.accept()

    def _set_modified(self):
        """メインウィンドウに変更を通知する"""
        view = self.parent()
        if view and hasattr(view, "model"):
            # モデルのデータが変更されたことを通知し、MainWindow の set_modified(True) を発火させる
            view.model().dataChanged.emit(QModelIndex(), QModelIndex(), [])

# 列車種別の選択ポップアップ
class TrainTypePicker(QDialog):
    def __init__(self, parent, project: OptDiaProject, current_id=None):
        super().__init__(parent, Qt.Popup)
        self.project = project
        self.selected_id = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.list_widget = QListWidget(self)
        self.list_widget.setStyleSheet("border: 1px solid #dddddd;")
        self.list_widget.setItemDelegate(HtmlDelegate(self))

        # 「設定しない」アイテムの追加
        none_item = QListWidgetItem("<font color='#888888'>設定しない</font>")
        none_item.setData(Qt.UserRole, None)
        self.list_widget.addItem(none_item)

        for tt_id in self.project.train_types_order:
            tt = self.project.train_types[tt_id]
            name, train_name = tt.get("train_type_name", ""), tt.get("train_name")
            color, bg_color = tt.get("main_color", "#333333"), tt.get("background_color", "#ffffff")
            display_name = f"{name} {train_name}" if train_name else name
            item = QListWidgetItem(f"<font color='{color}'>{display_name}</font>")
            item.setData(Qt.UserRole, tt_id)
            item.setBackground(QColor(bg_color))
            self.list_widget.addItem(item)

        if current_id is None:
            self.list_widget.setCurrentItem(none_item)
        else:
            for i in range(self.list_widget.count()):
                if self.list_widget.item(i).data(Qt.UserRole) == current_id:
                    self.list_widget.setCurrentItem(self.list_widget.item(i))
                    self.list_widget.scrollToItem(self.list_widget.item(i))
                    break
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)
        self.setFixedSize(200, min(400, self.list_widget.count() * 32 + 2))

    def _on_item_clicked(self, item):
        self.selected_id = item.data(Qt.UserRole)
        self.accept()

# 担当運用選択用のリストウィジェット
class DragDropListWidget(QListWidget):
    def __init__(self, parent_dialog):
        super().__init__(parent_dialog)
        self.parent_dialog = parent_dialog
        self.setDragDropMode(QListWidget.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setStyleSheet("border: none;")

    def dropEvent(self, event):
        # ドラッグ＆ドロップでアイテムが移動される前に、現在のウィジェットの状態を保存
        self.parent_dialog.sync_operations_to_project()
        super().dropEvent(event)
        # 移動後、カスタムウィジェットが再構築される
        self.parent_dialog.rebuild_item_widgets()
        self.parent_dialog.sync_operations_to_project()

# リストウィジェット内のカスタムアイテム用ウィジェット
class OperationItemWidget(QWidget):
    def __init__(self, parent_dialog, index_1based, operation_id=None, formation_is_reversed=False):
        super().__init__()
        self.dialog = parent_dialog
        self.operation_id = operation_id
        self.formation_is_reversed = formation_is_reversed

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        self.group_box = QGroupBox(f"{index_1based}つ目の運用")
        self.group_box.setStyleSheet("QGroupBox { border: 1px solid #aaa; border-radius: 4px; margin-top: 8px; background-color: #ffffff; padding-top: 2px; } QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 5px; background-color: #f7f7f7; }")
        group_layout = QVBoxLayout(self.group_box)
        group_layout.setContentsMargins(5, 10, 5, 0)

        # 1行目: 「運用グループ」を選択するコンボボックス
        self.group_combo = QComboBox()
        self.group_combo.setStyleSheet("QComboBox { border: 1px solid #aaa; border-radius: 3px; padding: 2px; min-height: 24px; }")
        self.group_combo.addItem("運用グループを選択", None)
        diagram = self.dialog.project.diagrams.get(self.dialog.diagram_id, {})
        operation_groups = diagram.get("operation_groups", {})
        operation_groups_order = diagram.get("operation_groups_order", [])
        for og_id in operation_groups_order:
            og = operation_groups[og_id]
            self.group_combo.addItem(og.get("operation_group_name", og_id), og_id)
        group_layout.addWidget(self.group_combo)

        # 2行目: 「運用」を選択するコンボボックス
        self.op_combo = QComboBox()
        self.op_combo.setStyleSheet("QComboBox { border: 1px solid #aaa; border-radius: 3px; padding: 2px; min-height: 24px; }")
        self.op_combo.addItem("運用を選択", None)
        group_layout.addWidget(self.op_combo)

        # 3行目: 「方反」チェックボックスと「削除」ボタン
        row3_layout = QHBoxLayout()
        row3_layout.setContentsMargins(0, 0, 0, 0)
        self.reversed_cb = QCheckBox("方反")
        self.reversed_cb.setChecked(formation_is_reversed)
        row3_layout.addWidget(self.reversed_cb)

        row3_layout.addStretch()

        self.del_btn = QPushButton("削除")
        self.del_btn.setStyleSheet("QPushButton { border: none; text-decoration: underline; background: transparent; color: #cc3333; }")
        self.del_btn.setCursor(Qt.PointingHandCursor)
        row3_layout.addWidget(self.del_btn)

        group_layout.addLayout(row3_layout)
        layout.addWidget(self.group_box)

        # 接続設定
        self.group_combo.currentIndexChanged.connect(self._on_group_changed)
        self.op_combo.currentIndexChanged.connect(self._on_op_changed)
        self.reversed_cb.toggled.connect(self._on_reversed_toggled)
        self.del_btn.clicked.connect(self._on_delete_clicked)

        # 初期値の反映
        self._init_combos()

    def _init_combos(self):
        diagram = self.dialog.project.diagrams.get(self.dialog.diagram_id, {})
        operation_groups = diagram.get("operation_groups", {})
        operation_groups_order = diagram.get("operation_groups_order", [])

        found_group_id = None
        if self.operation_id:
            for og_id in operation_groups_order:
                og = operation_groups[og_id]
                if self.operation_id in og.get("operations", []):
                    found_group_id = og_id
                    break

        self.group_combo.blockSignals(True)
        if found_group_id:
            idx = self.group_combo.findData(found_group_id)
            if idx >= 0:
                self.group_combo.setCurrentIndex(idx)
        else:
            self.group_combo.setCurrentIndex(0)
        self.group_combo.blockSignals(False)

        self._repopulate_ops(found_group_id)

        self.op_combo.blockSignals(True)
        if self.operation_id:
            idx = self.op_combo.findData(self.operation_id)
            if idx >= 0:
                self.op_combo.setCurrentIndex(idx)
        else:
            self.op_combo.setCurrentIndex(0)
        self.op_combo.blockSignals(False)

    def _repopulate_ops(self, group_id):
        self.op_combo.blockSignals(True)
        self.op_combo.clear()
        self.op_combo.addItem("運用を選択", None)

        diagram = self.dialog.project.diagrams.get(self.dialog.diagram_id, {})
        operations = diagram.get("operations", {})

        if group_id:
            og = diagram.get("operation_groups", {}).get(group_id, {})
            for op_id in og.get("operations", []):
                op = operations.get(op_id)
                if op:
                    self.op_combo.addItem(op.get("operation_number", op_id), op_id)
        else:
            for op_id, op in operations.items():
                self.op_combo.addItem(op.get("operation_number", op_id), op_id)

        self.op_combo.blockSignals(False)

    def _on_group_changed(self, index):
        group_id = self.group_combo.currentData()
        self._repopulate_ops(group_id)
        self.operation_id = None
        self.dialog.sync_operations_to_project()

    def _on_op_changed(self, index):
        self.operation_id = self.op_combo.currentData()

        # 運用が選択されたら、その運用が所属するグループに自動で切り替える
        if self.operation_id:
            diagram = self.dialog.project.diagrams.get(self.dialog.diagram_id, {})
            operation_groups = diagram.get("operation_groups", {})
            operation_groups_order = diagram.get("operation_groups_order", [])

            found_group_id = None
            for og_id in operation_groups_order:
                og = operation_groups[og_id]
                if self.operation_id in og.get("operations", []):
                    found_group_id = og_id
                    break

            if found_group_id:
                self.group_combo.blockSignals(True)
                idx = self.group_combo.findData(found_group_id)
                if idx >= 0 and idx != self.group_combo.currentIndex():
                    self.group_combo.setCurrentIndex(idx)
                self.group_combo.blockSignals(False)

        self.dialog.sync_operations_to_project()

    def _on_reversed_toggled(self, checked):
        self.formation_is_reversed = checked
        self.dialog.sync_operations_to_project()

    def _on_delete_clicked(self):
        self.dialog.delete_item_widget(self)


# 担当運用選択ポップアップ
class OperationPickerDialog(QDialog):
    def __init__(self, parent, project, diagram_id, route_id, direction, train_id):
        super().__init__(parent, Qt.Popup)
        self.project = project
        self.diagram_id = diagram_id
        self.route_id = route_id
        self.direction = direction
        self.train_id = train_id

        # 現在編集中の列車のダイヤデータを取得
        route = self.project.routes.get(self.route_id, {})
        train_key = "inbound_trains" if self.direction == "inbound" else "outbound_trains"
        self.d_train = route.get("trains_by_diagram", {}).get(self.diagram_id, {}).get(train_key, {}).get(self.train_id)

        self.setWindowTitle("担当運用選択")
        self.setFixedSize(300, 360)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(4)

        # ラベル
        label = QLabel("列車の担当運用(編成の前位側から)")
        layout.addWidget(label)

        # リストウィジェット
        self.list_widget = DragDropListWidget(self)
        layout.addWidget(self.list_widget)

        # 「担当運用の追加」ボタン
        self.add_btn = QPushButton("担当運用の追加")
        self.add_btn.clicked.connect(self._on_add_clicked)
        layout.addWidget(self.add_btn)

        # 「運用の追加・編集」ボタン (枠線なし、下線)
        self.edit_btn = QPushButton("運用の追加・編集")
        self.edit_btn.setStyleSheet("QPushButton { border: none; text-decoration: underline; background: transparent; }")
        self.edit_btn.clicked.connect(self._on_edit_clicked)
        layout.addWidget(self.edit_btn)

        # 既存の担当運用をリストにロード
        if self.d_train:
            ops = self.d_train.get("operations", [])
            for op in ops:
                op_id = op.get("operation_id")
                is_rev = op.get("formation_is_reversed", False)
                self.add_item(op_id, is_rev)

    def add_item(self, operation_id=None, formation_is_reversed=False):
        item = QListWidgetItem()
        item.setSizeHint(QSize(280, 120))
        item.setData(Qt.UserRole, operation_id)
        item.setData(Qt.UserRole + 1, formation_is_reversed)
        self.list_widget.addItem(item)

        idx = self.list_widget.count()
        widget = OperationItemWidget(self, idx, operation_id, formation_is_reversed)
        self.list_widget.setItemWidget(item, widget)

    def _on_add_clicked(self):
        self.add_item()
        self.sync_operations_to_project()

    def delete_item_widget(self, widget):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if self.list_widget.itemWidget(item) == widget:
                self.list_widget.takeItem(i)
                break
        self.rebuild_item_widgets()
        self.sync_operations_to_project()

    def rebuild_item_widgets(self):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            idx = i + 1
            if widget:
                widget.group_box.setTitle(f"{idx}つ目の運用")
            else:
                op_id = item.data(Qt.UserRole)
                is_rev = item.data(Qt.UserRole + 1) or False
                item.setSizeHint(QSize(280, 110))
                widget = OperationItemWidget(self, idx, op_id, is_rev)
                self.list_widget.setItemWidget(item, widget)

    def sync_operations_to_project(self):
        if not self.d_train:
            return

        from core.events import ChangeTrainOperationEvent
        old_ops = copy.deepcopy(self.d_train.get("operations", []))

        ops = []
        has_valid = False
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            if widget:
                op_id = widget.operation_id
                is_rev = widget.formation_is_reversed
                item.setData(Qt.UserRole, op_id)
                item.setData(Qt.UserRole + 1, is_rev)
            else:
                op_id = item.data(Qt.UserRole)
                is_rev = item.data(Qt.UserRole + 1) or False

            ops.append({
                "operation_id": op_id,
                "formation_is_reversed": is_rev
            })
            if op_id:
                has_valid = True

        self.d_train["operations"] = ops
        if has_valid:
            self.d_train["to_be_saved"] = True

        if old_ops != ops:
            view = self.parent()
            if view and hasattr(view, "model"):
                model = view.model()
                if hasattr(model, "history_manager") and model.history_manager:
                    ev = ChangeTrainOperationEvent(self.route_id, self.direction, self.train_id, self.diagram_id, old_ops, ops)
                    model.history_manager.push_events([ev])

        # メインウィンドウに変更を通知
        view = self.parent()
        if view and hasattr(view, "model"):
            view.model().dataChanged.emit(QModelIndex(), QModelIndex(), [])

    def closeEvent(self, event):
        # 運用が選択されていない項目を破棄
        if self.d_train and "operations" in self.d_train:
            original_ops = self.d_train["operations"]
            self.d_train["operations"] = [
                op for op in original_ops if op.get("operation_id")
            ]
            if len(self.d_train["operations"]) != len(original_ops):
                view = self.parent()
                if view and hasattr(view, "model"):
                    view.model().dataChanged.emit(QModelIndex(), QModelIndex(), [])
        super().closeEvent(event)

    def _on_edit_clicked(self):
        self.close()
        dialog = VehicleOperationEditorDialog(self.parent(), self.project, self.diagram_id)
        dialog.exec()

# 番線を選択するためのポップアップダイアログ
class TrackPicker(QDialog):
    def __init__(self, parent, station_data, current_track_id=None):
        super().__init__(parent, Qt.Popup)
        self.selected_id = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.list_widget = QListWidget(self)
        self.list_widget.setStyleSheet("border: 1px solid #dddddd;")
        
        # 「設定しない」アイテムの追加
        none_item = QListWidgetItem("設定しない")
        none_item.setData(Qt.UserRole, None)
        self.list_widget.addItem(none_item)
        if current_track_id is None:
            self.list_widget.setCurrentItem(none_item)

        tracks = station_data.get("tracks", {})
        order = station_data.get("tracks_order", [])
        for tid in order:
            track = tracks.get(tid, {})
            track_name = track.get("track_name") or tid
            item = QListWidgetItem(track_name)
            item.setData(Qt.UserRole, tid)
            self.list_widget.addItem(item)
            if tid == current_track_id:
                self.list_widget.setCurrentItem(item)
                self.list_widget.scrollToItem(item)
        
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)
        self.setFixedSize(150, min(300, self.list_widget.count() * 28 + 2))

    def _on_item_clicked(self, item):
        self.selected_id = item.data(Qt.UserRole)
        self.accept()

# 連続する列車の編集ダイアログ
class SubsequentTrainDialog(QDialog):
    def __init__(self, parent, project: OptDiaProject, d_train: dict, m_train: dict, diagram_id: str, 
                 route_id: str, direction: str):
        super().__init__(parent)
        self.project = project
        self.d_train = d_train # ダイヤ側の情報
        self.m_train = m_train # マスタ側の情報
        self.diagram_id = diagram_id
        self.route_id = route_id
        self.direction = direction
        self.setWindowTitle("連続する列車")
        self.setFixedSize(480, 720)

        main_layout = QVBoxLayout(self)

        # 説明文
        train_no = self.m_train.get("train_number") or "(番号なし)"
        desc_label = QLabel(
            f"列車 {train_no} から直接連続乗車可能な列車を選択してください。\n"
            "編成が別々の列車に分割される場合は複数の列車を設定することもできます。"
        )
        desc_label.setWordWrap(True)
        main_layout.addWidget(desc_label)

        # スクロール可能領域を作成
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignTop)
        
        # リストを初期表示
        self._refresh_list()
        
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        # ダイアログ最下部の追加ボタン
        self.add_button = QPushButton("連続する列車を追加")
        self.add_button.setFixedHeight(40)
        self.add_button.clicked.connect(self._on_add_clicked)
        main_layout.addWidget(self.add_button)

    def closeEvent(self, event):
        """ダイアログが閉じられる際に、train_idがNoneのエントリを削除する"""
        if "subsequent_trains" in self.d_train and self.d_train["subsequent_trains"]:
            original_count = len(self.d_train["subsequent_trains"])
            self.d_train["subsequent_trains"] = [
                item for item in self.d_train["subsequent_trains"]
                if item.get("train_id") is not None
            ]
            if len(self.d_train["subsequent_trains"]) != original_count:
                self._set_modified()
        super().closeEvent(event)

    def _refresh_list(self):
        """表示内容をクリアして再構築する"""
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        subsequent_list = self.d_train.get("subsequent_trains") or []
        for i, item in enumerate(subsequent_list):
            group = self._create_subsequent_group(i + 1, item)
            self.scroll_layout.addWidget(group)
        self.scroll_layout.addStretch()

    def _on_add_clicked(self):
        """新しい連続列車のエントリを追加して再描画する"""
        from core.events import ChangeSubsequentTrainEvent
        old_subs = copy.deepcopy(self.d_train.get("subsequent_trains", []))

        if "subsequent_trains" not in self.d_train or self.d_train["subsequent_trains"] is None:
            self.d_train["subsequent_trains"] = []
        
        self.d_train["subsequent_trains"].append({
            "route_id": self.route_id,
            "direction": self.direction,
            "train_id": None
        })

        self._record_subs_change(old_subs, self.d_train["subsequent_trains"])
        self._refresh_list()
        self._set_modified()

    def _create_subsequent_group(self, number, item_data):
        """個々の連続列車の設定用グループボックスを作成する"""
        idx = number - 1
        group = QGroupBox(f"連続する列車{number}")
        layout = QVBoxLayout(group)

        # 運行系統と方面の選択（横並び）
        top_layout = QHBoxLayout()

        route_combo = QComboBox()
        for rid in self.project.routes_order:
            r = self.project.routes[rid]
            route_combo.addItem(r.get("route_name", rid), rid)

        r_idx = route_combo.findData(item_data.get("route_id"))
        if r_idx >= 0:
            route_combo.setCurrentIndex(r_idx)
        top_layout.addWidget(route_combo, 1)
        route_combo.currentIndexChanged.connect(lambda _, ix=idx, cb=route_combo: self._on_route_changed(ix, cb.currentData()))

        dir_combo = QComboBox()
        dir_combo.setFixedWidth(80)
        dir_combo.addItem("下り", "outbound")
        dir_combo.addItem("上り", "inbound")

        d_idx = dir_combo.findData(item_data.get("direction"))
        if d_idx >= 0:
            dir_combo.setCurrentIndex(d_idx)
        top_layout.addWidget(dir_combo)
        dir_combo.currentIndexChanged.connect(lambda _, ix=idx, cb=dir_combo: self._on_direction_changed(ix, cb.currentData()))

        layout.addLayout(top_layout)

        # 列車選択ボタン（列車情報の表示用）
        train_btn = QPushButton()
        # 複数色のテキスト（HTML）を表示するために内部にラベルを配置
        btn_layout = QVBoxLayout(train_btn)
        btn_layout.setContentsMargins(5, 2, 5, 2)
        btn_label = QLabel(self._get_train_display_info(item_data))
        btn_label.setAlignment(Qt.AlignCenter)
        btn_label.setAttribute(Qt.WA_TransparentForMouseEvents) # クリックを下のボタンに透過させる
        btn_layout.addWidget(btn_label)
        
        train_btn.clicked.connect(lambda _, ix=idx, btn=train_btn: self._on_train_picker_clicked(ix, btn))
        layout.addWidget(train_btn)

        # 削除ボタン（枠線なし、右端に配置）
        del_btn = QPushButton("この連続設定を削除")
        del_btn.setStyleSheet("QPushButton { border: none; text-decoration: underline; background: transparent; }")
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.clicked.connect(lambda _, ix=idx: self._on_delete_subsequent(ix))
        layout.addWidget(del_btn, alignment=Qt.AlignRight)

        return group

    def _record_subs_change(self, old_subs, new_subs):
        from core.events import ChangeSubsequentTrainEvent
        view = self.parent()
        if view and hasattr(view, "model"):
            model = view.model()
            if hasattr(model, "history_manager") and model.history_manager:
                train_id = self.d_train.get("train_id")
                ev = ChangeSubsequentTrainEvent(self.route_id, self.direction, train_id, self.diagram_id, old_subs, new_subs)
                model.history_manager.push_events([ev])

    def _on_route_changed(self, index, new_route_id):
        """運行系統が変更されたら、選択中の列車をクリアする"""
        item = self.d_train["subsequent_trains"][index]
        if item["route_id"] != new_route_id:
            old_subs = copy.deepcopy(self.d_train.get("subsequent_trains", []))
            item["route_id"] = new_route_id
            item["train_id"] = None
            self._record_subs_change(old_subs, self.d_train["subsequent_trains"])
            self._refresh_list()
            self._set_modified()

    def _on_direction_changed(self, index, new_direction):
        """方面が変更されたら、選択中の列車をクリアする"""
        item = self.d_train["subsequent_trains"][index]
        if item["direction"] != new_direction:
            old_subs = copy.deepcopy(self.d_train.get("subsequent_trains", []))
            item["direction"] = new_direction
            item["train_id"] = None
            self._record_subs_change(old_subs, self.d_train["subsequent_trains"])
            self._refresh_list()
            self._set_modified()

    def _on_train_picker_clicked(self, index, button):
        """列車選択ボタンが押されたら、候補リストを表示する"""
        subsequent_list = self.d_train.get("subsequent_trains", [])
        item = subsequent_list[index]
        
        # 除外リストの作成: 編集中の列車自身 + 他のエントリで選択済みの列車
        excluded_ids = {self.d_train.get("train_id")}
        for i, other_item in enumerate(subsequent_list):
            if i != index and other_item.get("train_id"):
                excluded_ids.add(other_item["train_id"])
        
        # 編集対象の列車の終着時刻（最後に入力されている時刻）を取得
        min_dep_time = None
        stops = self.m_train.get("stops", [])
        timed_stops = [s for s in stops if s.get("arrival_time") or s.get("departure_time")]
        if timed_stops:
            last_stop = timed_stops[-1]
            min_dep_time = last_stop.get("arrival_time") or last_stop.get("departure_time")

        picker = TrainPicker(button, self.project, self.diagram_id, 
                             item["route_id"], item["direction"], excluded_ids,
                             item.get("train_id"), min_departure_time=min_dep_time)
        
        pos = button.mapToGlobal(button.rect().bottomLeft())
        picker.move(pos)
        
        if picker.exec() == QDialog.Accepted:
            old_subs = copy.deepcopy(self.d_train.get("subsequent_trains", []))
            item["train_id"] = picker.selected_train_id
            self._record_subs_change(old_subs, self.d_train["subsequent_trains"])
            # ボタン内部のラベルを探して更新
            label = button.findChild(QLabel)
            if label:
                label.setText(self._get_train_display_info(item))
            self._set_modified()

    def _on_delete_subsequent(self, index):
        """指定されたインデックスの連続列車設定を削除して再描画する"""
        if "subsequent_trains" in self.d_train:
            old_subs = copy.deepcopy(self.d_train.get("subsequent_trains", []))
            self.d_train["subsequent_trains"].pop(index)
            self._record_subs_change(old_subs, self.d_train["subsequent_trains"])
            self._refresh_list()
            self._set_modified()

    def _set_modified(self):
        """メインウィンドウに変更を通知する"""
        view = self.parent()
        if view and hasattr(view, "model"):
            model = view.model()
            # 連続する列車が変更されると行き先の自動解決結果が変わるため、キャッシュをクリアする
            if hasattr(model, "clear_destination_cache"):
                model.clear_destination_cache()
            model.dataChanged.emit(QModelIndex(), QModelIndex(), [])

    def _get_train_display_info(self, identifier):
        """列車IDに基づき、ボタンに表示する情報を取得する"""
        route_id, direction, train_id = identifier.get("route_id"), identifier.get("direction"), identifier.get("train_id")
        if not all([route_id, direction, train_id]): 
            return "<font color='#888888'>列車を選択してください</font>"
        
        route = self.project.routes.get(route_id)
        if not route: return "不明な運行系統"
        
        train_key = "inbound_trains" if direction == "inbound" else "outbound_trains"
        # 表示情報はマスタ側から取得
        m_train = route.get(train_key, {}).get(train_id)
        if not m_train: return "不明な列車"

        num = m_train.get("train_number") or "(番号なし)"
        tt = self.project.train_types.get(m_train.get("train_type_id"))
        tt_color = tt.get("main_color", "#333333") if tt else "#333333"
        tt_short = (tt.get("train_type_short_name") or tt.get("train_type_name") or "") if tt else ""
        tt_display = f"<font color='{tt_color}'>{tt_short}</font>"
        
        # 始発駅と時刻
        first_stop = next((s for s in m_train.get("stops", []) if s.get("departure_time")), None)
        if first_stop:
            s_name = self.project.stations.get(first_stop["station_id"], {}).get("station_name", first_stop["station_id"])
            return f"{num} {tt_display} <font color='#666666'>({s_name} {first_stop['departure_time'][:5]}発)</font>"
        return f"{num} {tt_display}"


# 備考編集ポップアップ
class NotePopup(QDialog):
    def __init__(self, parent, initial_text):
        super().__init__(parent, Qt.Popup)
        self.setFixedSize(200, 200)
        self.setStyleSheet("""
            QDialog {
                background-color: #fcfcfc;
                border: 1px solid #cccccc;
                border-radius: 4px;
            }
            QLabel {
                font-weight: bold;
                font-size: 12px;
                color: #333333;
            }
            QPlainTextEdit {
                background-color: #ffffff;
                border: 1px solid #cccccc;
                border-radius: 2px;
                padding: 4px;
                font-size: 14px;
            }
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #cccccc;
                border-radius: 2px;
                padding: 4px 8px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton#saveBtn {
                background-color: #0078d4;
                color: white;
                border: 1px solid #006cc1;
            }
            QPushButton#saveBtn:hover {
                background-color: #006cc1;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        label = QLabel("備考", self)
        layout.addWidget(label)

        self.text_edit = QPlainTextEdit(self)
        self.text_edit.setPlainText(initial_text)
        layout.addWidget(self.text_edit)

        # OK / Cancel ボタン
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.cancel_btn = QPushButton("キャンセル", self)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("OK", self)
        self.save_btn.setObjectName("saveBtn")
        self.save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.save_btn)

        layout.addLayout(btn_layout)

    def get_text(self):
        return self.text_edit.toPlainText()


def split_train_at_cell(parent, model, index):
    if not index.isValid():
        return

    row = index.row()
    col = index.column()

    if row < len(model.row_headers) or row >= len(model.row_headers) + len(model.station_rows):
        return

    if col < 0 or col >= len(model.train_ids):
        return

    row_idx = row - len(model.row_headers)
    row_def = model.station_rows[row_idx]
    stop_idx = row_def["stop_idx"]
    cfg = model.full_stop_configs[stop_idx]
    station_id = cfg["station_id"]

    route_id = model.route_id
    diagram_id = model.diagram_id
    direction = model.direction

    route = model.project.routes.get(route_id)
    if not route:
        return

    train_key = "inbound_trains" if direction == "inbound" else "outbound_trains"
    d_trains = route.get("trains_by_diagram", {}).get(diagram_id, {}).get(train_key, {})
    m_trains = route.get(train_key, {})

    train_id = model.train_ids[col]
    m_train = m_trains.get(train_id)
    d_train = d_trains.get(train_id)

    if not m_train or not d_train:
        return

    # 右クリックされたセルに発着時刻が入力されているかチェック
    stop = next((s for s in m_train.get("stops", []) if s.get("stop_idx") == stop_idx), None)
    has_time = False
    if stop:
        if row_def["type"] == "arr":
            has_time = bool(stop.get("arrival_time"))
        else:
            has_time = bool(stop.get("departure_time"))

    if not has_time:
        QMessageBox.warning(parent, "エラー", "発着時刻が未入力の駅で列車を分割することはできません")
        return

    # 発着時刻が入力されている最初と最後の駅では分割させない
    timed_stops = [s for s in m_train.get("stops", []) if s.get("arrival_time") or s.get("departure_time")]
    if not timed_stops:
        QMessageBox.warning(parent, "エラー", "列車は途中の停車駅でのみ分割可能です")
        return

    first_station_id = timed_stops[0]["station_id"]
    last_station_id = timed_stops[-1]["station_id"]

    if station_id == first_station_id or station_id == last_station_id:
        QMessageBox.warning(parent, "エラー", "列車は途中の停車駅でのみ分割可能です")
        return

    # 分割を実行するか確認
    station_name = model.project.stations.get(station_id, {}).get("station_name", station_id)
    reply = QMessageBox.question(
        parent,
        "確認",
        f"{station_name}でこの列車を分割しますか？",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No
    )
    if reply != QMessageBox.Yes:
        return

    from core.events import AddTrainEvent, ChangeTrainStopEvent, RemoveTrainStopEvent, ChangeSubsequentTrainEvent
    events_to_push = []
    old_m_stops = copy.deepcopy(m_train.get("stops", []))

    # 列車の分割
    # 1. 新しい列車IDを生成
    chars = string.ascii_letters + string.digits
    while True:
        new_train_id = "".join(random.choices(chars, k=16))
        if new_train_id not in m_trains:
            break

    # 2. 列車マスタデータをコピー
    new_m_train = copy.deepcopy(m_train)
    new_stops = []
    # 分割位置より前の経由駅情報は除外
    for s in new_m_train.get("stops", []):
        s_copy = s.copy()
        if s_copy["stop_idx"] < stop_idx:
            s_copy["arrival_time"] = None
            s_copy["departure_time"] = None
        elif s_copy["stop_idx"] == stop_idx:
            s_copy["arrival_time"] = None
        if s_copy.get("arrival_time") is not None or s_copy.get("departure_time") is not None:
            new_stops.append(s_copy)
    new_m_train["stops"] = new_stops

    # 3. オリジナルの列車データから分割位置よりあとの経由駅情報を除去
    orig_stops = []
    for s in m_train.get("stops", []):
        s_copy = s.copy()
        if s_copy["stop_idx"] == stop_idx and model.project.stations.get(s_copy["station_id"], {}).get("show_arrival_time", False):
            s_copy["departure_time"] = None
        elif s_copy["stop_idx"] > stop_idx:
            s_copy["arrival_time"] = None
            s_copy["departure_time"] = None
        if s_copy.get("arrival_time") is not None or s_copy.get("departure_time") is not None:
            orig_stops.append(s_copy)
    m_train["stops"] = orig_stops

    # 運行系統に新しい列車マスタデータを追加
    m_trains[new_train_id] = new_m_train

    # 4. オリジナルの列車データを参照している各ダイヤのダイヤ別列車情報を処理
    diagram_ids = list(m_train.get("_diagram_ids", []))
    new_m_train["_diagram_ids"] = list(diagram_ids)

    for did in model.project.diagrams_order:
        tbd_for_did = route.get("trains_by_diagram", {}).get(did, {})
        d_trains_for_did = tbd_for_did.get(train_key, {})
        d_order_for_did = tbd_for_did.get(f"{train_key}_order", [])
        if train_id in d_trains_for_did and d_trains_for_did[train_id].get("to_be_saved") is True:
            orig_d_train = d_trains_for_did[train_id]
            old_orig_subs = copy.deepcopy(orig_d_train.get("subsequent_trains", []))
            # 運転ダイヤ別の列車情報をコピー
            new_d_train = copy.deepcopy(orig_d_train)
            new_d_train["train_id"] = new_train_id
            new_d_train["to_be_saved"] = True
            
            # オリジナルの列車データの連続する列車を削除してコピーの列車の識別情報を記載
            orig_d_train["subsequent_trains"] = [{
                "route_id": route_id,
                "direction": direction,
                "train_id": new_train_id
            }]
            events_to_push.append(ChangeSubsequentTrainEvent(route_id, direction, train_id, did, old_orig_subs, orig_d_train["subsequent_trains"]))
            
            # オリジナルの列車データのIDの直後にコピーの列車のIDを挿入
            if train_id in d_order_for_did:
                idx = d_order_for_did.index(train_id)
                d_order_for_did.insert(idx + 1, new_train_id)
                insert_idx = idx + 1
            else:
                d_order_for_did.append(new_train_id)
                insert_idx = len(d_order_for_did) - 1
                
            d_trains_for_did[new_train_id] = new_d_train
            events_to_push.append(AddTrainEvent(route_id, direction, new_train_id, did, insert_idx, new_d_train, new_m_train))

    # オリジナル列車の stop 変更イベント
    for old_s in old_m_stops:
        s_idx = old_s.get("stop_idx")
        matching = next((s for s in m_train["stops"] if s.get("stop_idx") == s_idx), None)
        if not matching:
            events_to_push.append(RemoveTrainStopEvent(route_id, direction, train_id, s_idx, old_s))
        elif matching != old_s:
            events_to_push.append(ChangeTrainStopEvent(route_id, direction, train_id, s_idx, old_s, matching))

    # 経由駅情報の正規化
    model._normalize_train_stops(m_train)
    model._normalize_train_stops(new_m_train)

    if model.history_manager and events_to_push:
        model.history_manager.push_events(events_to_push)

    # 時刻表テーブルのモデルを更新
    model.update_data(model.route_id, model.diagram_id, model.direction)
    model.dataChanged.emit(QModelIndex(), QModelIndex(), [])


class DuplicateTrainWithConditionsDialog(QDialog):
    """「条件を指定して列車を複製」ダイアログ"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("条件を指定して列車を複製")
        self.setFixedSize(320, 480)

        layout = QVBoxLayout(self)

        # 1. ラベル
        layout.addWidget(QLabel("指定時間後の列車として複製する"))

        # 2. ラジオボタン（「0分」「10分」「12分」「15分」「20分」「30分」「1時間」「2時間」「3時間」「カスタム」）
        options = [
            ("0分", 0),
            ("10分", 10),
            ("12分", 12),
            ("15分", 15),
            ("20分", 20),
            ("30分", 30),
            ("1時間", 60),
            ("2時間", 120),
            ("3時間", 180),
            ("カスタム", None)
        ]

        self.btn_group = QButtonGroup(self)
        self.radio_buttons = []
        for i, (text, minutes) in enumerate(options):
            rb = QRadioButton(text)
            rb.setData = minutes
            self.btn_group.addButton(rb, i)
            self.radio_buttons.append((rb, minutes))
            layout.addWidget(rb)
            if i == 0:
                rb.setChecked(True)

        # 3. 「分」という単位の設定されたスピンボックス（カスタム選択時のみ有効、-360〜360）
        custom_layout = QHBoxLayout()
        self.spin_box = QSpinBox()
        self.spin_box.setRange(-360, 360)
        self.spin_box.setValue(0)
        self.spin_box.setSuffix(" 分")
        self.spin_box.setEnabled(False)
        custom_layout.addWidget(self.spin_box)
        layout.addLayout(custom_layout)

        self.btn_group.idToggled.connect(self._on_radio_toggled)

        layout.addSpacing(20)

        # 4. 「連続する列車も複製」チェックボックス
        self.duplicate_subs_cb = QCheckBox("連続する列車も複製")
        layout.addWidget(self.duplicate_subs_cb)

        layout.addStretch()

        # 5. 「OK」「キャンセル」ボタン
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.ok_btn = QPushButton("OK")
        self.cancel_btn = QPushButton("キャンセル")
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)

    def _on_radio_toggled(self, id, checked):
        if checked:
            # 最後の選択肢がカスタム
            is_custom = (id == len(self.radio_buttons) - 1)
            self.spin_box.setEnabled(is_custom)

    def get_offset_minutes(self) -> int:
        selected_id = self.btn_group.checkedId()
        _, minutes = self.radio_buttons[selected_id]
        if minutes is None:
            return self.spin_box.value()
        return minutes

    def should_duplicate_subsequent(self) -> bool:
        return self.duplicate_subs_cb.isChecked()


def _generate_unique_train_id(existing_ids) -> str:
    chars = string.ascii_letters + string.digits
    while True:
        tid = "".join(random.choices(chars, k=16))
        if tid not in existing_ids:
            return tid


def _shift_time_str(time_str: Optional[str], offset_minutes: int) -> Optional[str]:
    if not time_str:
        return None
    try:
        parts = [int(p) for p in time_str.split(":")]
        if len(parts) == 2:
            hh, mm, ss = parts[0], parts[1], 0
        elif len(parts) == 3:
            hh, mm, ss = parts[0], parts[1], parts[2]
        else:
            return time_str
        total_sec = hh * 3600 + mm * 60 + ss + offset_minutes * 60
        # 負の時刻は0:00:00未満にならないようにするか、そのまま正規化（通常鉄道ダイヤでは0〜99時間）
        total_sec = max(0, total_sec)
        new_hh = total_sec // 3600
        new_mm = (total_sec % 3600) // 60
        new_ss = total_sec % 60
        return f"{new_hh:02d}:{new_mm:02d}:{new_ss:02d}"
    except Exception:
        return time_str


def add_empty_train(model, col: int, side: str):
    """
    空の列車を挿入する
    side: "left" or "right"
    """
    if not model.route_id or not model.diagram_id:
        return
    route = model.project.routes.get(model.route_id)
    if not route:
        return

    train_key = "inbound_trains" if model.direction == "inbound" else "outbound_trains"
    order_key = f"{train_key}_order"
    tbd = route.setdefault("trains_by_diagram", {}).setdefault(model.diagram_id, {})
    d_trains = tbd.setdefault(train_key, {})
    order = tbd.setdefault(order_key, [])
    m_trains = route.setdefault(train_key, {})

    new_train_id = _generate_unique_train_id(set(m_trains.keys()) | set(d_trains.keys()))

    new_d_train = {
        "train_id": new_train_id,
        "operations": [],
        "car_count": None,
        "destination": None,
        "subsequent_trains": [],
        "to_be_saved": True
    }
    new_m_train = {
        "train_number": "",
        "train_type_id": None,
        "named_train_number": None,
        "note": "",
        "stops": [],
        "_diagram_ids": [model.diagram_id]
    }

    insert_idx = col if side == "left" else col + 1
    insert_idx = max(0, min(insert_idx, len(order)))

    d_trains[new_train_id] = new_d_train
    m_trains[new_train_id] = new_m_train
    order.insert(insert_idx, new_train_id)

    from core.events import AddTrainEvent
    ev = AddTrainEvent(model.route_id, model.direction, new_train_id, model.diagram_id, insert_idx, new_d_train, new_m_train)
    if model.history_manager:
        model.history_manager.push_events([ev])

    model.update_data(model.route_id, model.diagram_id, model.direction)
    model.dataChanged.emit(QModelIndex(), QModelIndex(), [])


def duplicate_train(model, col: int, offset_minutes: int = 0, duplicate_subsequent: bool = False):
    """
    指定列の列車を複製する
    """
    if not model.route_id or not model.diagram_id or col < 0 or col >= len(model.train_ids):
        return
    route = model.project.routes.get(model.route_id)
    if not route:
        return

    train_key = "inbound_trains" if model.direction == "inbound" else "outbound_trains"
    order_key = f"{train_key}_order"
    tbd = route.setdefault("trains_by_diagram", {}).setdefault(model.diagram_id, {})
    d_trains = tbd.setdefault(train_key, {})
    order = tbd.setdefault(order_key, [])
    m_trains = route.setdefault(train_key, {})

    src_train_id = model.train_ids[col]
    src_d_train = d_trains.get(src_train_id)
    src_m_train = m_trains.get(src_train_id)
    if not src_d_train or not src_m_train:
        return

    from core.events import AddTrainEvent
    events_to_push = []

    def _clone_single_train(s_rid, s_dir, s_tid, shift_min, is_root=False):
        s_route = model.project.routes.get(s_rid)
        if not s_route:
            return None
        s_t_key = "inbound_trains" if s_dir == "inbound" else "outbound_trains"
        s_o_key = f"{s_t_key}_order"
        s_tbd = s_route.setdefault("trains_by_diagram", {}).setdefault(model.diagram_id, {})
        s_d_trains = s_tbd.setdefault(s_t_key, {})
        s_order = s_tbd.setdefault(s_o_key, [])
        s_m_trains = s_route.setdefault(s_t_key, {})

        s_d = s_d_trains.get(s_tid)
        s_m = s_m_trains.get(s_tid)
        if not s_d or not s_m:
            return None

        new_tid = _generate_unique_train_id(set(s_m_trains.keys()) | set(s_d_trains.keys()))

        new_d = copy.deepcopy(s_d)
        new_d["train_id"] = new_tid
        new_d["operations"] = []  # 運用番号は継承しない
        new_d["to_be_saved"] = True
        new_d["subsequent_trains"] = []  # 後で設定

        new_m = copy.deepcopy(s_m)
        orig_num = s_m.get("train_number", "")
        new_m["train_number"] = f"{orig_num}のコピー"
        new_m["_diagram_ids"] = [model.diagram_id]  # 運転日は継承しない（現在のダイヤのみ）

        # 時刻をシフト
        if shift_min != 0:
            for s in new_m.get("stops", []):
                if s.get("arrival_time") is not None:
                    s["arrival_time"] = _shift_time_str(s["arrival_time"], shift_min)
                if s.get("departure_time") is not None:
                    s["departure_time"] = _shift_time_str(s["departure_time"], shift_min)

        # 挿入位置の決定
        if is_root:
            ins_idx = col + 1
        else:
            ins_idx = len(s_order)
            if s_tid in s_order:
                ins_idx = s_order.index(s_tid) + 1

        ins_idx = max(0, min(ins_idx, len(s_order)))

        s_d_trains[new_tid] = new_d
        s_m_trains[new_tid] = new_m
        s_order.insert(ins_idx, new_tid)

        events_to_push.append(AddTrainEvent(s_rid, s_dir, new_tid, model.diagram_id, ins_idx, new_d, new_m))
        return new_tid, new_d, new_m, s_d

    # 複製対象を再帰的/連鎖的に探索・複製
    visited = set()

    def _duplicate_chain(s_rid, s_dir, s_tid, is_root=False):
        if (s_rid, s_dir, s_tid) in visited:
            return None
        visited.add((s_rid, s_dir, s_tid))

        cloned = _clone_single_train(s_rid, s_dir, s_tid, offset_minutes, is_root=is_root)
        if not cloned:
            return None
        new_tid, new_d, new_m, orig_d = cloned

        if duplicate_subsequent:
            orig_subs = orig_d.get("subsequent_trains", [])
            new_subs = []
            for sub in orig_subs:
                sub_rid = sub.get("route_id")
                sub_dir = sub.get("direction")
                sub_tid = sub.get("train_id")
                if sub_rid and sub_dir and sub_tid:
                    cloned_sub_tid = _duplicate_chain(sub_rid, sub_dir, sub_tid, is_root=False)
                    if cloned_sub_tid:
                        new_subs.append({
                            "route_id": sub_rid,
                            "direction": sub_dir,
                            "train_id": cloned_sub_tid
                        })
            new_d["subsequent_trains"] = new_subs

        return new_tid

    _duplicate_chain(model.route_id, model.direction, src_train_id, is_root=True)

    if model.history_manager and events_to_push:
        model.history_manager.push_events(events_to_push)

    model.update_data(model.route_id, model.diagram_id, model.direction)
    model.dataChanged.emit(QModelIndex(), QModelIndex(), [])


def delete_train(parent_view, model, col: int):
    """
    指定列の列車を削除する
    """
    if not model.route_id or not model.diagram_id or col < 0 or col >= len(model.train_ids):
        return
    route = model.project.routes.get(model.route_id)
    if not route:
        return

    train_key = "inbound_trains" if model.direction == "inbound" else "outbound_trains"
    order_key = f"{train_key}_order"
    tbd = route.get("trains_by_diagram", {}).get(model.diagram_id, {})
    d_trains = tbd.get(train_key, {})
    order = tbd.get(order_key, [])
    m_trains = route.get(train_key, {})

    train_id = model.train_ids[col]
    m_train = m_trains.get(train_id)
    d_train = d_trains.get(train_id)
    if not m_train or not d_train:
        return

    train_num = m_train.get("train_number") or "(番号なし)"

    # 1. 「列車 <列車番号> を削除しますか？」確認ダイアログ
    reply = QMessageBox.question(
        parent_view,
        "列車の削除",
        f"列車 {train_num} を削除しますか？",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No
    )
    if reply != QMessageBox.Yes:
        return

    # 運転日（_diagram_ids または 各運転ダイヤのd_trains）をチェック
    diagram_ids = list(m_train.get("_diagram_ids", []))
    # _diagram_ids に含まれていなくても実際のダイヤに存在する場合を考慮
    actual_diagram_ids = []
    for did in model.project.diagrams_order:
        tbd_for_did = route.get("trains_by_diagram", {}).get(did, {})
        if train_id in tbd_for_did.get(train_key, {}):
            actual_diagram_ids.append(did)

    delete_from_all_diagrams = False
    if len(actual_diagram_ids) > 1:
        reply2 = QMessageBox.question(
            parent_view,
            "他の運転ダイヤからの削除",
            "他の運転ダイヤからも列車を削除しますか？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply2 == QMessageBox.Yes:
            delete_from_all_diagrams = True

    from core.events import RemoveTrainEvent, RemoveTrainDiagramEvent

    events_to_push = []

    if delete_from_all_diagrams:
        # 全運転ダイヤおよび運行系統マスタから削除 -> RemoveTrainEvent
        d_trains_by_diagram = {}
        for did in actual_diagram_ids:
            tbd_for_did = route.get("trains_by_diagram", {}).get(did, {})
            d_train_dict = tbd_for_did.get(train_key, {})
            d_order_list = tbd_for_did.get(order_key, [])
            if train_id in d_train_dict:
                d_idx = d_order_list.index(train_id) if train_id in d_order_list else len(d_order_list) - 1
                d_trains_by_diagram[did] = (d_idx, copy.deepcopy(d_train_dict[train_id]))
                if train_id in d_order_list:
                    d_order_list.remove(train_id)
                del d_train_dict[train_id]

        m_train_snapshot = copy.deepcopy(m_train)
        if train_id in m_trains:
            del m_trains[train_id]

        ev = RemoveTrainEvent(model.route_id, model.direction, train_id, d_trains_by_diagram, m_train_snapshot)
        events_to_push.append(ev)
    else:
        # 現在の運転ダイヤからのみ削除 -> RemoveTrainDiagramEvent (もし登録が1つだけならマスタからも消えるRemoveTrainEventにするか、仕様通りRemoveTrainDiagramEvent)
        # 登録が1つだけの場合は RemoveTrainEvent を使用
        if len(actual_diagram_ids) <= 1:
            d_trains_by_diagram = {model.diagram_id: (col, copy.deepcopy(d_train))}
            if train_id in order:
                order.remove(train_id)
            if train_id in d_trains:
                del d_trains[train_id]
            m_train_snapshot = copy.deepcopy(m_train)
            if train_id in m_trains:
                del m_trains[train_id]
            ev = RemoveTrainEvent(model.route_id, model.direction, train_id, d_trains_by_diagram, m_train_snapshot)
            events_to_push.append(ev)
        else:
            old_idx = order.index(train_id) if train_id in order else col
            old_d_train = copy.deepcopy(d_train)
            if train_id in order:
                order.remove(train_id)
            if train_id in d_trains:
                del d_trains[train_id]
            if "_diagram_ids" in m_train and model.diagram_id in m_train["_diagram_ids"]:
                m_train["_diagram_ids"].remove(model.diagram_id)
            ev = RemoveTrainDiagramEvent(model.route_id, model.direction, train_id, model.diagram_id, old_idx, old_d_train)
            events_to_push.append(ev)

    if model.history_manager and events_to_push:
        model.history_manager.push_events(events_to_push)

    model.update_data(model.route_id, model.diagram_id, model.direction)
    model.dataChanged.emit(QModelIndex(), QModelIndex(), [])
