from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QGroupBox, QLineEdit,
    QComboBox, QLabel, QScrollArea, QWidget, QListWidget, QListWidgetItem,
    QCheckBox,
)
from common.gui_utils import HtmlDelegate
from project import OptDiaProject

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

# 列車に割り当てる運転ダイヤを選択するためのダイアログ
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
        
        # 現在のダイヤでダミー列車（未保存）だった場合、他のダイヤへの割り当て等により保存対象へ昇格させる
        current_tbd = route.get("trains_by_diagram", {}).get(self.current_diagram_id, {})
        current_d_train = current_tbd.get(train_key, {}).get(self.train_id)
        if current_d_train and not current_d_train.get("to_be_saved"):
            current_d_train["to_be_saved"] = True
            has_changed = True
        elif current_d_train and current_d_train.get("to_be_saved") and not self._initial_checkbox_states.get(self.current_diagram_id, False):
            has_changed = True # 現在のダイヤが元々to_be_saved=Falseだったが、今回to_be_saved=Trueになった場合

        for did, cb in self.checkboxes.items():
            if did == self.current_diagram_id: continue # 現在のダイヤはスキップ
                
            tbd = route.get("trains_by_diagram", {}).get(did, {})
            d_trains, order = tbd.get(train_key), tbd.get(order_key)
            
            # チェック状態が変更されたか、または初期状態と異なるかを確認
            if cb.isChecked() and self.train_id not in d_trains:
                # ダイヤへの追加: 列車ID以外のキーはNoneまたは空配列で初期化
                d_trains[self.train_id] = {
                    "train_id": self.train_id, "operations": [], "car_count": None,
                    "destination": None, "subsequent_trains": [], "to_be_saved": True
                }
                # 挿入位置の決定: 末尾のダミー列車(to_be_saved=False)より前に挿入
                insert_idx = len(order)
                for i, tid in enumerate(order):
                    if not d_trains.get(tid, {}).get("to_be_saved", True):
                        insert_idx = i
                        break
                order.insert(insert_idx, self.train_id)
                if did not in m_train["_diagram_ids"]: m_train["_diagram_ids"].append(did)
                has_changed = True
            elif not cb.isChecked() and self.train_id in d_trains:
                # ダイヤからの削除
                if self.train_id in order: order.remove(self.train_id)
                del d_trains[self.train_id]
                if did in m_train["_diagram_ids"]: m_train["_diagram_ids"].remove(did)
                has_changed = True

        # 逆引き用ダイヤIDリストをプロジェクト順でソート
        m_train["_diagram_ids"].sort(key=lambda x: self.project.diagrams_order.index(x) if x in self.project.diagrams_order else 999)
        
        if has_changed:
            self._set_modified()
        self.accept()

    def _set_modified(self):
        """メインウィンドウに変更を通知する"""
        view = self.parent()
        if view and hasattr(view, "model"):
            # モデルのデータが変更されたことを通知し、MainWindow の set_modified(True) を発火させる
            view.model().dataChanged.emit(QModelIndex(), QModelIndex(), [])

# 列車種別を選択するためのポップアップダイアログ
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

# 担当運用選択ポップアップ
class OperationPickerDialog(QDialog):
    def __init__(self, parent, project, diagram_id):
        super().__init__(parent, Qt.Popup)
        self.project = project
        self.diagram_id = diagram_id
        self.setWindowTitle("担当運用選択")
        self.setFixedSize(300, 360)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5,5,5,5)
        layout.setSpacing(4)
        # ラベル
        label = QLabel("列車の担当運用(編成の前位側から)")
        layout.addWidget(label)
        # リストウィジェット (枠線なし)
        list_widget = QListWidget(self)
        list_widget.setStyleSheet("border: none;")
        layout.addWidget(list_widget)
        # 「担当運用の追加」ボタン
        add_btn = QPushButton("担当運用の追加")
        layout.addWidget(add_btn)
        # 「運用の追加・編集」ボタン (枠線なし、下線)
        edit_btn = QPushButton("運用の追加・編集")
        edit_btn.setStyleSheet("QPushButton { border: none; text-decoration: underline; background: transparent; }")
        edit_btn.clicked.connect(self._on_edit_clicked)
        layout.addWidget(edit_btn)
        self.list_widget = list_widget
        self.add_btn = add_btn
        self.edit_btn = edit_btn

    def _on_edit_clicked(self):
        self.close()
        from dialogs.operation import VehicleOperationEditorDialog
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

# 「連続する列車」を編集するダイアログ
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
        if "subsequent_trains" not in self.d_train or self.d_train["subsequent_trains"] is None:
            self.d_train["subsequent_trains"] = []
        
        self.d_train["subsequent_trains"].append({
            "route_id": self.route_id,
            "direction": self.direction,
            "train_id": None
        })
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

    def _on_route_changed(self, index, new_route_id):
        """運行系統が変更されたら、選択中の列車をクリアする"""
        item = self.d_train["subsequent_trains"][index]
        if item["route_id"] != new_route_id:
            item["route_id"] = new_route_id
            item["train_id"] = None
            self._refresh_list()
            self._set_modified()

    def _on_direction_changed(self, index, new_direction):
        """方面が変更されたら、選択中の列車をクリアする"""
        item = self.d_train["subsequent_trains"][index]
        if item["direction"] != new_direction:
            item["direction"] = new_direction
            item["train_id"] = None
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
            item["train_id"] = picker.selected_train_id
            # ボタン内部のラベルを探して更新
            label = button.findChild(QLabel)
            if label:
                label.setText(self._get_train_display_info(item))
            self._set_modified()

    def _on_delete_subsequent(self, index):
        """指定されたインデックスの連続列車設定を削除して再描画する"""
        if "subsequent_trains" in self.d_train:
            self.d_train["subsequent_trains"].pop(index)
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