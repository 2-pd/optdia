from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QGroupBox, QLineEdit,
    QComboBox, QLabel, QScrollArea, QWidget, QListWidget, QListWidgetItem
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
        
        trains = tbd.get(train_key, {})
        order = tbd.get(order_key, [])
        
        for tid in order:
            if tid in excluded_ids:
                continue
            
            train = trains[tid]
            if not train.get("to_be_saved"):
                continue

            # 列車情報を構築 (列車番号、種別、始発駅時刻)
            num = train.get("train_number") or "(番号なし)"
            tt = project.train_types.get(train.get("train_type_id"))
            tt_color = tt.get("main_color", "#333333") if tt else "#333333"

            first_stop = next((s for s in train.get("stops", []) if s.get("departure_time")), None)
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

# 「連続する列車」を編集するダイアログ
class SubsequentTrainDialog(QDialog):
    def __init__(self, parent, project: OptDiaProject, train_data: dict, diagram_id: str, 
                 route_id: str, direction: str):
        super().__init__(parent)
        self.project = project
        self.train_data = train_data
        self.diagram_id = diagram_id
        self.route_id = route_id
        self.direction = direction
        self.setWindowTitle("連続する列車")
        self.setFixedSize(480, 720)

        main_layout = QVBoxLayout(self)

        # 説明文
        train_no = self.train_data.get("train_number") or "(番号なし)"
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
        if "subsequent_trains" in self.train_data and self.train_data["subsequent_trains"]:
            original_count = len(self.train_data["subsequent_trains"])
            self.train_data["subsequent_trains"] = [
                item for item in self.train_data["subsequent_trains"]
                if item.get("train_id") is not None
            ]
            if len(self.train_data["subsequent_trains"]) != original_count:
                self._set_modified()
        super().closeEvent(event)

    def _refresh_list(self):
        """表示内容をクリアして再構築する"""
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        subsequent_list = self.train_data.get("subsequent_trains") or []
        for i, item in enumerate(subsequent_list):
            group = self._create_subsequent_group(i + 1, item)
            self.scroll_layout.addWidget(group)
        self.scroll_layout.addStretch()

    def _on_add_clicked(self):
        """新しい連続列車のエントリを追加して再描画する"""
        if "subsequent_trains" not in self.train_data or self.train_data["subsequent_trains"] is None:
            self.train_data["subsequent_trains"] = []
        
        self.train_data["subsequent_trains"].append({
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
        item = self.train_data["subsequent_trains"][index]
        if item["route_id"] != new_route_id:
            item["route_id"] = new_route_id
            item["train_id"] = None
            self._refresh_list()
            self._set_modified()

    def _on_direction_changed(self, index, new_direction):
        """方面が変更されたら、選択中の列車をクリアする"""
        item = self.train_data["subsequent_trains"][index]
        if item["direction"] != new_direction:
            item["direction"] = new_direction
            item["train_id"] = None
            self._refresh_list()
            self._set_modified()

    def _on_train_picker_clicked(self, index, button):
        """列車選択ボタンが押されたら、候補リストを表示する"""
        subsequent_list = self.train_data.get("subsequent_trains", [])
        item = subsequent_list[index]
        
        # 除外リストの作成: 編集中の列車自身 + 他のエントリで選択済みの列車
        excluded_ids = {self.train_data.get("train_id")}
        for i, other_item in enumerate(subsequent_list):
            if i != index and other_item.get("train_id"):
                excluded_ids.add(other_item["train_id"])
        
        # 編集対象の列車の終着時刻（最後に入力されている時刻）を取得
        min_dep_time = None
        stops = self.train_data.get("stops", [])
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
        if "subsequent_trains" in self.train_data:
            self.train_data["subsequent_trains"].pop(index)
            self._refresh_list()
            self._set_modified()

    def _set_modified(self):
        """メインウィンドウに変更を通知する"""
        view = self.parent()
        if view and hasattr(view, "model"):
            view.model().dataChanged.emit(QModelIndex(), QModelIndex(), [])

    def _get_train_display_info(self, identifier):
        """列車IDに基づき、ボタンに表示する情報を取得する"""
        route_id, direction, train_id = identifier.get("route_id"), identifier.get("direction"), identifier.get("train_id")
        if not all([route_id, direction, train_id]): 
            return "<font color='#888888'>列車を選択してください</font>"
        
        route = self.project.routes.get(route_id)
        if not route: return "不明な運行系統"
        tbd = route.get("trains_by_diagram", {}).get(self.diagram_id, {})
        train = tbd.get("inbound_trains" if direction == "inbound" else "outbound_trains", {}).get(train_id)
        if not train: return "不明な列車"

        num = train.get("train_number") or "(番号なし)"
        tt = self.project.train_types.get(train.get("train_type_id"))
        tt_color = tt.get("main_color", "#333333") if tt else "#333333"
        tt_short = (tt.get("train_type_short_name") or tt.get("train_type_name") or "") if tt else ""
        tt_display = f"<font color='{tt_color}'>{tt_short}</font>"
        
        # 始発駅と時刻
        first_stop = next((s for s in train.get("stops", []) if s.get("departure_time")), None)
        if first_stop:
            s_name = self.project.stations.get(first_stop["station_id"], {}).get("station_name", first_stop["station_id"])
            return f"{num} {tt_display} <font color='#666666'>({s_name} {first_stop['departure_time'][:5]}発)</font>"
        return f"{num} {tt_display}"