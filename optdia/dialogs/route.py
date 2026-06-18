import random
import string
import re
from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QMessageBox, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QStackedWidget, QComboBox, QFormLayout,
    QWidget, QPushButton, QSizePolicy, QScrollArea
)
from project import OptDiaProject

# 運行系統の追加ダイアログ
class AddRouteDialog(QDialog):
    def __init__(self, parent, project: OptDiaProject):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("運行系統の追加")
        self.setFixedSize(400, 240)

        layout = QVBoxLayout(self)

        # 運行系統ID
        layout.addWidget(QLabel("運行系統ID:"))
        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("例) midosuji_namboku")
        self.id_edit.textChanged.connect(self._clear_id_error)
        layout.addWidget(self.id_edit)

        # 警告表示スペース
        self.warning_label = QLabel("")
        self.warning_label.setStyleSheet("color: red; padding-left: 5px;")
        layout.addWidget(self.warning_label)

        # 運行系統名
        layout.addWidget(QLabel("運行系統名:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例) 御堂筋線・南北線系統")
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
        self.id_edit.setStyleSheet("")
        self.warning_label.setText("")

    def _on_add_clicked(self):
        route_id = self.id_edit.text().strip()
        if not route_id:
            self.warning_label.setText("IDを指定してください")
            self.id_edit.setStyleSheet("background-color: #ffeeee;")
            return
        if not re.match(r"^[a-zA-Z0-9_]+$", route_id):
            self.warning_label.setText("IDには半角英数字とアンダーバーのみが使用可能です")
            self.id_edit.setStyleSheet("background-color: #ffeeee;")
            return
        if route_id in self.project.routes:
            self.warning_label.setText("既に使用されているIDです")
            self.id_edit.setStyleSheet("background-color: #ffeeee;")
            return
        self.accept()


# 路線と区間の選択ダイアログ
class SelectSegmentDialog(QDialog):
    def __init__(self, parent, project: OptDiaProject, is_add=True,
                 initial_line=None, initial_start=None, initial_end=None,
                 existing_segments: list = None, editing_segment_index: int = None):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("路線と区間の選択")
        self.existing_segments = existing_segments if existing_segments is not None else []
        self.editing_segment_index = editing_segment_index
        self.setFixedSize(480, 320)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # 路線選択
        self.line_combo = QComboBox()
        self.line_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for lid in self.project.lines_order:
            line = self.project.lines[lid]
            if len(line.get("station_list", [])) >= 2:
                self.line_combo.addItem(line.get("line_name", lid), lid)
        
        form_layout.addRow("路線:", self.line_combo)

        # 区間選択 (始点 〜 終点)
        station_layout = QHBoxLayout()
        station_layout.setContentsMargins(0, 0, 0, 0)
        self.start_combo = QComboBox()
        self.end_combo = QComboBox()
        station_layout.addWidget(self.start_combo, 1)
        station_layout.addWidget(QLabel("〜"))
        station_layout.addWidget(self.end_combo, 1)
        form_layout.addRow("区間:", station_layout)

        # 起点と終点の反転
        self.invert_btn = QPushButton("起点と終点の反転")
        self.invert_btn.setStyleSheet("QPushButton { border: none; text-decoration: underline; background-color: transparent; }")
        self.invert_btn.setCursor(Qt.PointingHandCursor)
        self.invert_btn.clicked.connect(self._invert_stations)

        invert_container = QHBoxLayout()
        invert_container.setContentsMargins(0, 10, 0, 10)
        invert_container.addStretch()
        invert_container.addWidget(self.invert_btn)
        invert_container.addStretch()
        form_layout.addRow("", invert_container)

        # 警告表示用ラベル
        self.warning_label = QLabel("")
        self.warning_label.setStyleSheet("color: orange;")
        self.warning_label.setFixedHeight(50)
        self.warning_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.warning_label.setWordWrap(True)
        form_layout.addRow(self.warning_label)

        layout.addLayout(form_layout)

        # 説明文
        desc_label = QLabel("区間を逆向きに設定することで、上り列車が別路線に下り列車として直通するような運行系統を設定できます")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(desc_label)

        layout.addStretch()

        # ボタンエリア
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.ok_button = QPushButton("追加" if is_add else "決定")
        self.cancel_button = QPushButton("キャンセル")
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.ok_button.clicked.connect(self._on_ok_clicked)
        self.cancel_button.clicked.connect(self.reject)

        self.line_combo.currentIndexChanged.connect(self._on_line_changed)
        self.start_combo.currentIndexChanged.connect(self._validate_segment)
        self.end_combo.currentIndexChanged.connect(self._validate_segment)

        # 初期値の設定
        if initial_line:
            idx = self.line_combo.findData(initial_line)
            if idx >= 0:
                self.line_combo.setCurrentIndex(idx)
        
        self._on_line_changed()

        if initial_start:
            idx = self.start_combo.findData(initial_start)
            if idx >= 0: self.start_combo.setCurrentIndex(idx)
        if initial_end:
            idx = self.end_combo.findData(initial_end)
            if idx >= 0: self.end_combo.setCurrentIndex(idx)

        self._validate_segment()

    def _on_line_changed(self):
        self.start_combo.clear()
        self.end_combo.clear()
        line_id = self.line_combo.currentData()
        if not line_id: return
        
        line_data = self.project.lines.get(line_id)
        for s_item in line_data.get("station_list", []):
            sid = s_item["station_id"]
            s_name = self.project.stations.get(sid, {}).get("station_name", sid)
            self.start_combo.addItem(s_name, sid)
            self.end_combo.addItem(s_name, sid)
        
        if self.start_combo.count() >= 2:
            self.end_combo.setCurrentIndex(self.end_combo.count() - 1)

    def _invert_stations(self):
        s_idx = self.start_combo.currentIndex()
        e_idx = self.end_combo.currentIndex()
        self.start_combo.setCurrentIndex(e_idx)
        self.end_combo.setCurrentIndex(s_idx)

    def _validate_segment(self):
        """現在選択されている区間が妥当かどうか（他区間の端点を途中に含まないか）をチェックし、警告を表示する"""
        data = self.get_data()
        line_id = data["line_id"]
        start_sid = data["start_station"]
        end_sid = data["end_station"]

        if not line_id or not start_sid or not end_sid or start_sid == end_sid:
            self.warning_label.clear()
            return

        # 他の部分区間の末端駅（始点・終点）を収集
        all_other_endpoints = set()
        for i, seg in enumerate(self.existing_segments):
            if self.editing_segment_index is not None and i == self.editing_segment_index:
                continue
            all_other_endpoints.add(seg.get("start_station"))
            all_other_endpoints.add(seg.get("end_station"))

        # 現在選択中の区間の駅リストを取得
        stations = self._get_stations_in_segment_ordered(line_id, start_sid, end_sid)
        if len(stations) <= 2:
            self.warning_label.clear()
            return

        # 途中駅の抽出（始点と終点を除く）
        intermediate_stations = stations[1:-1]
        has_endpoint_in_middle = any(sid in all_other_endpoints for sid in intermediate_stations)

        if has_endpoint_in_middle:
            self.warning_label.setText("選択中の区間の途中に他の区間の末端駅が含まれます。\n分岐駅が存在する場合はその駅で区間を分割してください。")
        else:
            self.warning_label.clear()

    def _get_stations_in_segment_ordered(self, line_id, start_station_id, end_station_id):
        """指定された路線の区間に含まれる駅のIDリストを順序通りに返す"""
        line_data = self.project.lines.get(line_id)
        if not line_data:
            return []

        line_station_ids = [s["station_id"] for s in line_data.get("station_list", [])]

        try:
            idx_start = line_station_ids.index(start_station_id)
            idx_end = line_station_ids.index(end_station_id)
        except ValueError:
            return [] # 路線で駅が見つからない場合

        stations = []
        if idx_start <= idx_end:
            # 順向き
            for i in range(idx_start, idx_end + 1):
                stations.append(line_station_ids[i])
        else:
            # 逆向き
            for i in range(idx_start, idx_end - 1, -1): # range(start, stop, step) -> stop is exclusive
                stations.append(line_station_ids[i])
        
        return stations

    def _get_segment_direction(self, line_id, start_station_id, end_station_id):
        """指定された区間の方向を判定する ('forward' または 'reverse')"""
        line_data = self.project.lines.get(line_id)
        if not line_data:
            return None
        line_station_ids = [s["station_id"] for s in line_data.get("station_list", [])]
        try:
            idx_start = line_station_ids.index(start_station_id)
            idx_end = line_station_ids.index(end_station_id)
        except ValueError:
            return None
        return "forward" if idx_start <= idx_end else "reverse"

    def get_data(self):
        return {
            "line_id": self.line_combo.currentData(),
            "start_station": self.start_combo.currentData(),
            "end_station": self.end_combo.currentData()
        }

    def _on_ok_clicked(self):
        """OK/追加ボタンが押された際のバリデーションと処理"""
        if self.start_combo.currentData() == self.end_combo.currentData():
            QMessageBox.warning(self, "エラー", "区間の起点と終点に同じ駅を設定することはできません。")
            return
        
        new_segment_data = self.get_data()
        new_line_id = new_segment_data["line_id"]
        new_start_sid = new_segment_data["start_station"]
        new_end_sid = new_segment_data["end_station"]

        new_stations = self._get_stations_in_segment_ordered(new_line_id, new_start_sid, new_end_sid)
        new_segment_direction = self._get_segment_direction(new_line_id, new_start_sid, new_end_sid)
        # 区間内の駅間（エッジ）の集合を作成
        new_edges = set(zip(new_stations, new_stations[1:]))

        for i, existing_segment in enumerate(self.existing_segments):
            # 編集中の区間自身とは重複チェックを行わない
            if self.editing_segment_index is not None and i == self.editing_segment_index:
                continue

            existing_line_id = existing_segment["line_id"]
            existing_start_sid = existing_segment["start_station"]
            existing_end_sid = existing_segment["end_station"]

            # 路線IDが同じ場合にのみ重複をチェック
            if new_line_id == existing_line_id:
                existing_segment_direction = self._get_segment_direction(existing_line_id, existing_start_sid, existing_end_sid)

                # 方向が同じ場合にのみ重複とみなす
                if new_segment_direction == existing_segment_direction:
                    existing_stations = self._get_stations_in_segment_ordered(existing_line_id, existing_start_sid, existing_end_sid)
                    existing_edges = set(zip(existing_stations, existing_stations[1:]))

                    if new_edges.intersection(existing_edges):
                        QMessageBox.warning(self, "エラー", "この区間は、既に登録されている他の区間と重複しています。方向が同じ区間は重複できません。")
                        return
        
        self.accept()


# 区間の分割ダイアログ
class SplitSegmentDialog(QDialog):
    def __init__(self, parent, project: OptDiaProject, line_id: str, start_sid: str, end_sid: str):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("区間の分割")
        self.setFixedSize(400, 150)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.station_combo = QComboBox()

        # 中間駅のリストアップ
        line_data = self.project.lines.get(line_id, {})
        station_ids = [s["station_id"] for s in line_data.get("station_list", [])]

        try:
            idx_start = station_ids.index(start_sid)
            idx_end = station_ids.index(end_sid)
        except ValueError:
            self.reject()
            return

        # 順方向か逆方向かでスライスを調整して中間駅を抽出
        if idx_start < idx_end:
            intermediate_ids = station_ids[idx_start + 1 : idx_end]
        else:
            intermediate_ids = station_ids[idx_start - 1 : idx_end : -1]

        for sid in intermediate_ids:
            s_name = self.project.stations.get(sid, {}).get("station_name", sid)
            self.station_combo.addItem(s_name, sid)

        form_layout.addRow("分割点とする駅:", self.station_combo)
        layout.addLayout(form_layout)
        layout.addStretch()

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.split_button = QPushButton("分割")
        self.cancel_button = QPushButton("キャンセル")
        button_layout.addWidget(self.split_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.split_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def get_selected_station_id(self):
        return self.station_combo.currentData()


# 運行系統編集ダイアログ
class RouteEditorDialog(QDialog):
    def __init__(self, parent, project: OptDiaProject, initial_route_id=None):
        super().__init__(parent)
        self.project = project
        self.initial_route_id = initial_route_id
        self.setWindowTitle("運行系統情報")
        self.setFixedSize(960, 640)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 左側のサイドバー (幅200px固定)
        sidebar = QWidget()
        sidebar.setObjectName("route_editor_sidebar")
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet("#route_editor_sidebar { background-color: #f7f7f7; border-right: 1px solid #dddddd; }")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        sidebar_layout.setSpacing(5)

        sidebar_layout.addWidget(QLabel("<b>運行系統一覧</b>"))

        # 運行系統リスト
        self.route_list_widget = QListWidget()
        self.route_list_widget.setStyleSheet("font-size: 14px;")
        self.route_list_widget.setDragDropMode(QListWidget.InternalMove)
        self.route_list_widget.model().rowsMoved.connect(self._on_routes_reordered)
        self.route_list_widget.itemSelectionChanged.connect(self._on_route_selected)
        sidebar_layout.addWidget(self.route_list_widget)

        # 運行系統追加ボタン
        self.add_route_button = QPushButton("運行系統の追加")
        self.add_route_button.clicked.connect(self._on_add_route)
        sidebar_layout.addWidget(self.add_route_button)

        sidebar_layout.addSpacing(10)
        desc_label = QLabel("運行系統や路線の区間はドラッグ操作で並び替え可能です")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #888888; font-size: 12px;")
        sidebar_layout.addWidget(desc_label)

        main_layout.addWidget(sidebar)

        # 右側のスタックドウィジェット
        self.right_stack = QStackedWidget()
        main_layout.addWidget(self.right_stack)

        # 1. プレースホルダーページ (データなし)
        self.placeholder_page = QWidget()
        placeholder_layout = QVBoxLayout(self.placeholder_page)
        placeholder_label = QLabel("運行系統を追加してください")
        placeholder_label.setAlignment(Qt.AlignCenter)
        placeholder_label.setStyleSheet("color: #888888; font-size: 18px;")
        placeholder_layout.addWidget(placeholder_label)
        self.right_stack.addWidget(self.placeholder_page)

        # 2. 運行系統編集フォームページ
        self.edit_form_page = QWidget()
        edit_form_layout = QHBoxLayout(self.edit_form_page)
        edit_form_layout.setContentsMargins(0, 0, 0, 0)
        edit_form_layout.setSpacing(0)

        # メイン編集エリア (左側)
        self.form_main_area = QWidget()
        self.form_main_layout = QVBoxLayout(self.form_main_area)
        self.form_main_layout.setContentsMargins(20, 20, 20, 20)
        self.form_main_layout.setSpacing(10)

        # 運行系統基本情報 (IDと名称)
        route_info_form = QFormLayout()
        self.route_id_edit = QLineEdit()
        self.route_id_edit.setReadOnly(True)
        self.route_id_edit.setStyleSheet("background-color: #eeeeee; color: #888888;")
        route_info_form.addRow("運行系統ID(変更不可):", self.route_id_edit)

        self.route_name_edit = QLineEdit()
        self.route_name_edit.textChanged.connect(self._on_route_name_changed)
        route_info_form.addRow("運行系統名:", self.route_name_edit)
        self.form_main_layout.addLayout(route_info_form)

        # 含まれる路線とその区間
        self.form_main_layout.addSpacing(10)
        self.form_main_layout.addWidget(QLabel("<b>含まれる路線とその区間</b>"))

        # カラムヘッダー
        seg_header_layout = QHBoxLayout()
        # 余白を削除
        seg_header_layout.setContentsMargins(0, 0, 0, 0)
        # 色バー用のスペース（アラインメント維持用）
        header_spacer = QWidget()
        header_spacer.setFixedWidth(10)
        seg_header_layout.addWidget(header_spacer)
        line_header = QLabel("路線名")
        line_header.setFixedWidth(140)
        line_header.setAlignment(Qt.AlignCenter)
        seg_header_layout.addWidget(line_header)
        segment_header = QLabel("区間")
        segment_header.setAlignment(Qt.AlignCenter)
        seg_header_layout.addWidget(segment_header, stretch=1)
        operation_header = QLabel("操作")
        operation_header.setFixedWidth(154) # ボタン3つ(50*3) + 間隔(2*2)
        operation_header.setAlignment(Qt.AlignCenter)
        seg_header_layout.addWidget(operation_header)
        self.form_main_layout.addLayout(seg_header_layout)

        # ヘッダー下部の境界線
        header_border = QWidget()
        header_border.setFixedHeight(1)
        header_border.setStyleSheet("background-color: #cccccc;")
        self.form_main_layout.addWidget(header_border)

        # 部分区間リスト
        self.segment_list_widget = QListWidget()
        self.segment_list_widget.setDragDropMode(QListWidget.InternalMove)
        # 並び替え操作を維持しつつ、選択ハイライトを無効化し、ホバー時のみ背景色を表示する
        self.segment_list_widget.setFocusPolicy(Qt.NoFocus)
        self.segment_list_widget.setStyleSheet(
            "QListWidget { border: none; background-color: transparent; }"
            "QListWidget::item:hover { background-color: #dddddd; }"
            "QListWidget::item:selected { background-color: transparent; }"
            "QListWidget::item:selected:hover { background-color: #dddddd; }"
        )
        self.segment_list_widget.model().rowsMoved.connect(self._on_segments_reordered)
        self.form_main_layout.addWidget(self.segment_list_widget)

        # 区間追加ボタン
        self.add_segment_button = QPushButton("路線の区間を追加")
        self.add_segment_button.clicked.connect(self._on_add_segment)
        self.form_main_layout.addWidget(self.add_segment_button)

        # 運行系統削除ボタン
        self.delete_route_button = QPushButton("この運行系統を削除")
        self.delete_route_button.setFixedSize(120, 30)
        self.delete_route_button.clicked.connect(self._on_delete_route)
        self.delete_route_button.setStyleSheet("QPushButton { color: #cc3333; border: none; text-decoration: underline; background-color: transparent; }")
        self.form_main_layout.addWidget(self.delete_route_button, alignment=Qt.AlignRight)

        edit_form_layout.addWidget(self.form_main_area, stretch=1)

        # 駅順序プレビュー領域 (右側 220px)
        self.station_preview_area = QScrollArea()
        self.station_preview_area.setFixedWidth(220)
        self.station_preview_area.setWidgetResizable(True)
        self.station_preview_area.setStyleSheet("QScrollArea { border: none; border-left: 1px solid #dddddd; }")
        
        self.station_preview_content = QWidget()
        self.station_preview_layout = QVBoxLayout(self.station_preview_content)
        self.station_preview_layout.setContentsMargins(10, 10, 10, 10)
        self.station_preview_layout.setSpacing(0)

        # 駅順序プレビューの見出し
        lbl_preview = QLabel("駅順序プレビュー")
        lbl_preview.setStyleSheet("font-size: 14px; border: none;")
        self.station_preview_layout.addWidget(lbl_preview)
        
        self.direction_label = QLabel("下り列車の経由順で表示中")
        self.direction_label.setStyleSheet("font-size: 12px; color: #888888; padding-top: 10px; padding-bottom: 20px;")
        self.station_preview_layout.addWidget(self.direction_label)

        self.station_preview_layout.addStretch() # 内容を上部に寄せる

        self.station_preview_area.setWidget(self.station_preview_content)
        edit_form_layout.addWidget(self.station_preview_area)

        self.right_stack.addWidget(self.edit_form_page)

        # 初期リスト表示と表示切り替え
        self._populate_route_list()

    def _populate_route_list(self):
        self.route_list_widget.clear()
        initial_row = 0
        for i, rid in enumerate(self.project.routes_order):
            route = self.project.routes[rid]
            item = QListWidgetItem(route.get("route_name", rid))
            item.setData(Qt.UserRole, rid)
            self.route_list_widget.addItem(item)
            if rid == self.initial_route_id:
                initial_row = i
        
        if self.route_list_widget.count() > 0:
            self.right_stack.setCurrentWidget(self.edit_form_page)
            self.route_list_widget.setCurrentRow(initial_row)
        else:
            self.right_stack.setCurrentWidget(self.placeholder_page)

    def _on_routes_reordered(self, parent, start, end, destination, row):
        """運行系統の並び替えをプロジェクトデータに反映する"""
        new_order = []
        for i in range(self.route_list_widget.count()):
            item = self.route_list_widget.item(i)
            new_order.append(item.data(Qt.UserRole))
        
        self.project.routes_order = new_order
        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)

    def _on_route_selected(self):
        """運行系統の選択が変更されたときの処理"""
        selected = self.route_list_widget.selectedItems()
        if not selected:
            self.route_id_edit.clear()
            self.route_name_edit.clear()
            self.segment_list_widget.clear()
            return

        route_id = selected[0].data(Qt.UserRole)
        route_data = self.project.routes.get(route_id)
        if not route_data:
            return

        # シグナルをブロックして更新
        self.route_name_edit.blockSignals(True)
        self.route_id_edit.setText(route_id)
        self.route_name_edit.setText(route_data.get("route_name", ""))
        self.route_name_edit.blockSignals(False)

        self._populate_segment_list(route_data)
        self._populate_station_preview(route_data)

    def _on_route_name_changed(self, text: str):
        """名称が変更されたときにプロジェクトデータとサイドバーを更新する"""
        route_id = self.route_id_edit.text()
        if not route_id or route_id not in self.project.routes:
            return
        
        self.project.routes[route_id]["route_name"] = text
        
        # サイドバーのテキストを更新
        selected = self.route_list_widget.selectedItems()
        if selected and selected[0].data(Qt.UserRole) == route_id:
            selected[0].setText(text)

        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)

    def _get_stations_in_segment(self, line_id, start_station_id, end_station_id):
        """指定された路線の区間に含まれる駅のIDリストを順序通りに返す"""
        line_data = self.project.lines.get(line_id)
        if not line_data:
            return []

        line_station_ids = [s["station_id"] for s in line_data.get("station_list", [])]

        try:
            idx_start = line_station_ids.index(start_station_id)
            idx_end = line_station_ids.index(end_station_id)
        except ValueError:
            return [] # 路線で駅が見つからない場合

        stations_in_segment = []
        if idx_start <= idx_end:
            # 順向き
            for i in range(idx_start, idx_end + 1):
                stations_in_segment.append(line_station_ids[i])
        else:
            # 逆向き
            for i in range(idx_start, idx_end - 1, -1): # range(start, stop, step) -> stop is exclusive
                stations_in_segment.append(line_station_ids[i])
        
        return stations_in_segment

    def _populate_station_preview(self, route_data: dict):
        """駅順序プレビューエリアに駅のリストを表示する"""
        # 既存の動的に追加された駅アイテムとストレッチアイテムを削除
        # 見出しとdirection_labelは残すため、インデックス2から逆順に削除
        for i in reversed(range(2, self.station_preview_layout.count())):
            item = self.station_preview_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()
            self.station_preview_layout.removeItem(item)

        segments = route_data.get("line_segments", [])
        
        # すべての部分区間の末端駅（始点・終点）を収集
        all_endpoints = set()
        for s in segments:
            all_endpoints.add(s.get("start_station"))
            all_endpoints.add(s.get("end_station"))

        for seg in segments:
            line_id = seg.get("line_id")
            # line_colorが取得できない場合はデフォルト色を設定
            line_color = self.project.lines.get(line_id, {}).get("line_color", "#333333")
            start_sid = seg.get("start_station")
            end_sid = seg.get("end_station")

            stations_in_this_segment = self._get_stations_in_segment(line_id, start_sid, end_sid)
            
            line_color = self.project.lines.get(line_id, {}).get("line_color", "#333333")
            # 駅番号取得用のリストを取得
            line_station_list = self.project.lines.get(line_id, {}).get("station_list", [])

            for i, sid in enumerate(stations_in_this_segment):
                station_name = self.project.stations.get(sid, {}).get("station_name", sid)

                # 駅番号を取得して駅名の前に付加
                ls_item = next((s for s in line_station_list if s.get("station_id") == sid), None)
                s_num = ls_item.get("station_number") if ls_item else None
                display_name = f"[{s_num}] {station_name}" if s_num else station_name

                if sid == start_sid and i == 0:
                    display_name += " <span style='font-size: 12px; color: gray; font-weight: normal;'>(発)</span>"
                elif sid == end_sid and i == len(stations_in_this_segment) - 1:
                    display_name += " <span style='font-size: 12px; color: gray; font-weight: normal;'>(着)</span>"
                
                station_line_widget = QWidget()
                station_line_widget.setFixedHeight(40) # 行の高さを40pxに設定
                station_line_widget.setProperty("is_preview_station_item", True) # 削除対象を識別
                station_line_layout = QHBoxLayout(station_line_widget) # 5pxのスペースを設ける
                station_line_layout.setContentsMargins(0, 0, 0, 0)
                station_line_layout.setSpacing(5)

                color_bar = QLabel()
                color_bar.setFixedWidth(5)
                color_bar.setStyleSheet(f"background-color: {line_color};")
                station_line_layout.addWidget(color_bar)

                station_label = QLabel(display_name)
                
                # 駅の表示スタイルを設定
                station_data = self.project.stations.get(sid, {})
                if sid in all_endpoints and sid != start_sid and sid != end_sid:
                    # 他区間の末端駅はオレンジ色
                    station_label.setStyleSheet("color: orange;")
                elif station_data.get("is_signal_station", False):
                    # 信号場は灰色
                    station_label.setStyleSheet("color: gray;")
                elif station_data.get("is_major_station", False):
                    # 主要駅は太字
                    font = station_label.font()
                    font.setBold(True)
                    station_label.setFont(font)
                else:
                    # デフォルトのスタイルに戻す
                    station_label.setStyleSheet("")
                    station_label.setFont(QFont()) # 太字を解除
                
                station_line_layout.addWidget(station_label)
                station_line_layout.addStretch()

                self.station_preview_layout.addWidget(station_line_widget)
        self.station_preview_layout.addStretch() # 最後にストレッチを追加

        if not segments:
            self.direction_label.setText("表示する駅がありません\n路線の区間を追加してください")
        else:
            self.direction_label.setText("下り列車の経由順で表示中")
    def _populate_segment_list(self, route_data: dict):
        """選択された系統に含まれる路線の部分区間リストを表示する"""
        self.segment_list_widget.clear()
        segments = route_data.get("line_segments") or []
        
        # すべての部分区間の末端駅（始点・終点）を収集
        all_endpoints = set()
        for s in segments:
            all_endpoints.add(s.get("start_station"))
            all_endpoints.add(s.get("end_station"))

        for i, seg in enumerate(segments):
            item_widget = QWidget()
            item_layout = QHBoxLayout(item_widget) # 上下に10pxの余白を設ける
            item_layout.setContentsMargins(0, 10, 0, 10)
            
            # 路線名
            line_id = seg.get("line_id")
            line_color = self.project.lines.get(line_id, {}).get("line_color", "#333333")
            line_name = self.project.lines.get(line_id, {}).get("line_name", line_id)

            # 色バー
            color_bar = QLabel()
            color_bar.setFixedWidth(10)
            color_bar.setStyleSheet(f"background-color: {line_color};")
            item_layout.addWidget(color_bar)

            line_label = QLabel(line_name)
            line_label.setFixedWidth(140)
            line_label.setAlignment(Qt.AlignCenter)
            item_layout.addWidget(line_label)
            
            # 区間 (始点駅-終点駅)
            start_sid = seg.get("start_station")
            end_sid = seg.get("end_station")

            # 途中に他区間の末端駅が含まれているかチェック
            stations_in_this_segment = self._get_stations_in_segment(line_id, start_sid, end_sid)
            intermediate_stations = stations_in_this_segment[1:-1]
            conflicting_sids = [sid for sid in intermediate_stations if sid in all_endpoints]

            if conflicting_sids:
                segment_label = QLabel("【!】分岐駅を途中に含む")
                segment_label.setStyleSheet("color: orange;")

                # 具体的な駅名をツールチップで表示
                conflicting_names = [self.project.stations.get(sid, {}).get("station_name", sid) for sid in conflicting_sids]
                segment_label.setToolTip("途中に含まれる他区間の末端駅:\n" + "\n".join(conflicting_names))
            else:
                start_name = self.project.stations.get(start_sid, {}).get("station_name", start_sid)
                end_name = self.project.stations.get(end_sid, {}).get("station_name", end_sid)
                segment_label = QLabel(f"{start_name} - {end_name}")

            segment_label.setAlignment(Qt.AlignCenter)
            item_layout.addWidget(segment_label, stretch=1)
            
            # 操作ボタン
            btn_layout = QHBoxLayout()
            btn_layout.setContentsMargins(0, 0, 0, 0)
            btn_layout.setSpacing(2)
            btn_edit = QPushButton("編集")
            btn_edit.setFixedSize(50, 30)
            btn_edit.clicked.connect(lambda _, s=seg, idx=i: self._on_edit_segment(s, idx))
            btn_split = QPushButton("分割")
            btn_split.setFixedSize(50, 30)
            btn_split.clicked.connect(lambda _, s=seg, idx=i: self._on_split_segment(s, idx))
            btn_delete = QPushButton("削除")
            btn_delete.setFixedSize(50, 30)
            btn_delete.clicked.connect(lambda _, idx=i: self._on_delete_segment(idx))
            btn_layout.addWidget(btn_edit)
            btn_layout.addWidget(btn_split)
            btn_layout.addWidget(btn_delete)
            item_layout.addLayout(btn_layout, stretch=0)
            
            list_item = QListWidgetItem()
            # ドラッグ＆ドロップ後にデータを復元するため、セグメントの辞書データを保持
            list_item.setData(Qt.UserRole, seg)
            list_item.setSizeHint(item_widget.sizeHint())
            self.segment_list_widget.addItem(list_item)
            self.segment_list_widget.setItemWidget(list_item, item_widget)
        self.segment_list_widget.update()

    def _get_expected_route_sequence(self, segments, is_inbound):
        """運行系統の定義から、期待される(路線ID, 駅ID)の並び順リストを生成する"""
        route_stations = []
        target_segments = segments[::-1] if is_inbound else segments
        for s in target_segments:
            s_stations = self._get_stations_in_segment(s["line_id"], s["start_station"], s["end_station"])
            if is_inbound:
                s_stations = s_stations[::-1]
            for sid in s_stations:
                route_stations.append((s["line_id"], sid))
        return route_stations

    def _get_segment_range_in_sequence(self, segments, index, is_inbound):
        """特定の区間インデックスが、期待される駅シーケンス内のどの範囲(start, end)に相当するかを返す"""
        # 各セグメントの駅数を計算
        seg_lengths = [len(self._get_stations_in_segment(s["line_id"], s["start_station"], s["end_station"])) for s in segments]

        if not is_inbound:
            start_idx = sum(seg_lengths[:index])
            end_idx = start_idx + seg_lengths[index] - 1
        else:
            # inboundは逆順(セグメントリストの末尾側から)にシーケンスが組まれる
            start_idx = sum(seg_lengths[index+1:])
            end_idx = start_idx + seg_lengths[index] - 1
        return start_idx, end_idx

    def _on_segments_reordered(self, parent, start, end, destination, row):
        """路線の区間の並び替えをプロジェクトデータに反映する"""
        selected = self.route_list_widget.selectedItems()
        if not selected:
            return
        route_id = selected[0].data(Qt.UserRole)
        route_data = self.project.routes.get(route_id)
        if not route_data:
            return

        new_segments = []
        for i in range(self.segment_list_widget.count()):
            item = self.segment_list_widget.item(i)
            new_segments.append(item.data(Qt.UserRole))
        
        route_data["line_segments"] = new_segments
        
        # 操作ボタンのクロージャが参照するインデックスを正しく更新するためにリストを再描画
        self._populate_segment_list(route_data)
        self._populate_station_preview(route_data) # プレビューの更新

        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)

    def _on_add_route(self):
        """運行系統の追加ダイアログを表示し、データを追加する"""
        dialog = AddRouteDialog(self, self.project)
        if dialog.exec() == QDialog.Accepted:
            route_id = dialog.id_edit.text().strip()
            route_name = dialog.name_edit.text().strip()

            # プロジェクトデータに新規運行系統を追加
            self.project.routes[route_id] = {
                "route_id": route_id,
                "route_name": route_name,
                "line_segments" : [],
                "inbound_trains" : {},
                "outbound_trains" : {},
                "trains_by_diagram": {}
            }
            self.project.routes_order.append(route_id)

            # 既存の運転ダイヤごとに列車データ枠を作成
            for did in self.project.diagrams_order:
                self.project.routes[route_id]["trains_by_diagram"][did] = {
                    "inbound_trains": {},
                    "inbound_trains_order": [],
                    "outbound_trains": {},
                    "outbound_trains_order": []
                }

            # リスト表示を更新
            self._populate_route_list()

            # 新しく追加された項目を選択状態にする
            for i in range(self.route_list_widget.count()):
                if self.route_list_widget.item(i).text() == route_name:
                    self.route_list_widget.setCurrentRow(i)
                    break

            # 変更フラグを立てる (MainWindow)
            if hasattr(self.parent(), "set_modified"):
                self.parent().set_modified(True)

    def _on_add_segment(self):
        """路線の区間追加ダイアログを表示し、データを追加する"""
        valid_line_ids = [lid for lid in self.project.lines_order if len(self.project.lines[lid].get("station_list", [])) >= 2]
        if not valid_line_ids:
            QMessageBox.warning(self, "情報", "追加可能な路線がありません")
            return

        # 現在選択されている運行系統のデータを取得
        selected = self.route_list_widget.selectedItems()
        if not selected: return
        route_id = selected[0].data(Qt.UserRole)
        route_data = self.project.routes.get(route_id)
        dialog = SelectSegmentDialog(self, self.project, is_add=True, existing_segments=route_data.get("line_segments", []))
        if dialog.exec() == QDialog.Accepted:
            selected = self.route_list_widget.selectedItems()
            if not selected: return
            route_id = selected[0].data(Qt.UserRole)
            route_data = self.project.routes.get(route_id)
            
            route_data["line_segments"].append(dialog.get_data())
            self._populate_segment_list(route_data)
            self._populate_station_preview(route_data) # プレビューの更新
            if hasattr(self.parent(), "set_modified"):
                self.parent().set_modified(True)

    def _on_delete_route(self):
        """選択中の運行系統を削除する"""
        selected_items = self.route_list_widget.selectedItems()
        if not selected_items:
            return
        
        route_id = selected_items[0].data(Qt.UserRole)
        route_name = self.project.routes.get(route_id, {}).get("route_name", route_id)

        reply = QMessageBox.question(
            self,
            "運行系統の削除",
            f"「{route_name}」を削除しますか？\n"
            "この運行系統を削除すると、この運行系統に登録されている列車も全て削除されます。\n"
            "本当に運行系統を削除しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # プロジェクトデータから運行系統を削除
            del self.project.routes[route_id]
            self.project.routes_order.remove(route_id)

            self._populate_route_list() # リストを再構築して表示を更新
            
            if hasattr(self.parent(), "set_modified"):
                self.parent().set_modified(True)

    def _on_edit_segment(self, segment_data, index):
        """路線の区間編集ダイアログを表示し、データを更新する"""
        # 現在選択されている運行系統のデータを取得
        selected = self.route_list_widget.selectedItems()
        if not selected: return
        route_id = selected[0].data(Qt.UserRole)
        route_data = self.project.routes.get(route_id)

        # 編集前の状態を記録
        old_line_id = segment_data.get("line_id")
        old_start = segment_data.get("start_station")
        old_end = segment_data.get("end_station")
        old_stations = self._get_stations_in_segment(old_line_id, old_start, old_end)

        dialog = SelectSegmentDialog(
            self, self.project, is_add=False, 
            initial_line=old_line_id,
            initial_start=old_start,
            initial_end=old_end,
            existing_segments=route_data.get("line_segments", []), 
            editing_segment_index=index
        )

        if dialog.exec() == QDialog.Accepted:
            selected = self.route_list_widget.selectedItems()
            if not selected: return
            route_id = selected[0].data(Qt.UserRole)
            route_data = self.project.routes.get(route_id)
            
            new_data = dialog.get_data()
            new_line_id = new_data["line_id"]
            new_start = new_data["start_station"]
            new_end = new_data["end_station"]
            new_stations = self._get_stations_in_segment(new_line_id, new_start, new_end)

            # 停車駅(stops)は運行系統直下のマスタ情報(optdia_train)にあるため、
            # ダイヤに関わらず運行系統内の全列車を1回だけ更新すればよい
            segments = route_data.get("line_segments", [])

            for train_key in ["inbound_trains", "outbound_trains"]:
                is_inbound = (train_key == "inbound_trains")
                
                # 期待されるシーケンスと、編集対象区間のインデックス範囲を取得
                route_stations = self._get_expected_route_sequence(segments, is_inbound)
                r_start_idx, r_end_idx = self._get_segment_range_in_sequence(segments, index, is_inbound)

                # 走行方向に応じた新しい区間の末端（起点・終点）を特定
                seg_start = new_end if is_inbound else new_start
                seg_end = new_start if is_inbound else new_end
                
                for train in route_data.get(train_key, {}).values():
                    stops = train.get("stops", [])
                    new_stops = []
                    
                    r_ptr = 0
                    for stop in stops:
                        matched_r_idx = -1
                        temp_r_ptr = r_ptr
                        while temp_r_ptr < len(route_stations):
                            if (stop.get("line_id") == route_stations[temp_r_ptr][0] and 
                                stop.get("station_id") == route_stations[temp_r_ptr][1]):
                                matched_r_idx = temp_r_ptr
                                r_ptr = temp_r_ptr + 1
                                break
                            temp_r_ptr += 1

                        # この停車駅が、編集対象の区間に属するかを判定
                        if matched_r_idx != -1 and r_start_idx <= matched_r_idx <= r_end_idx:
                            # 1. 除外されたかどうかの判定 (路線変更 or 駅削除)
                            if old_line_id != new_line_id or stop.get("station_id") not in new_stations:
                                continue # 削除（リストに追加しない）
                            
                            # 2. 新しい区間の末端に対するNone設定の適用
                            if stop.get("line_id") == new_line_id:
                                if stop.get("station_id") == seg_start:
                                    stop["arrival_time"] = None
                                if stop.get("station_id") == seg_end:
                                    stop["departure_time"] = None
                        
                        new_stops.append(stop)
                    train["stops"] = new_stops

            route_data["line_segments"][index] = new_data
            self._populate_segment_list(route_data)
            self._populate_station_preview(route_data) # プレビューの更新
            if hasattr(self.parent(), "set_modified"):
                self.parent().set_modified(True)

    def _on_split_segment(self, segment_data, index):
        """路線の区間を分割するダイアログを表示し、データを更新する"""
        line_id = segment_data.get("line_id")
        start_sid = segment_data.get("start_station")
        end_sid = segment_data.get("end_station")
        
        line_data = self.project.lines.get(line_id, {})
        station_ids = [s["station_id"] for s in line_data.get("station_list", [])]
        
        try:
            idx_start = station_ids.index(start_sid)
            idx_end = station_ids.index(end_sid)
        except ValueError:
            return

        # 駅数が3駅未満（隣接駅など）の場合は分割不可
        if abs(idx_start - idx_end) < 2:
            QMessageBox.information(self, "情報", "この区間はこれ以上分割できません")
            return
            
        dialog = SplitSegmentDialog(self, self.project, line_id, start_sid, end_sid)
        if dialog.exec() == QDialog.Accepted:
            split_sid = dialog.get_selected_station_id()
            
            selected = self.route_list_widget.selectedItems()
            if not selected: return
            route_id = selected[0].data(Qt.UserRole)
            route_data = self.project.routes.get(route_id)

            segments = route_data.get("line_segments", [])

            # 停車駅(stops)は運行系統直下のマスタ情報にあるため、ダイヤに関わらず1回だけ更新
            stations_in_this_segment = self._get_stations_in_segment(line_id, start_sid, end_sid)
            rel_idx = stations_in_this_segment.index(split_sid)

            for train_key in ["inbound_trains", "outbound_trains"]:
                is_inbound = (train_key == "inbound_trains")
                
                # 期待されるシーケンスと、分割駅が属するセグメントの開始位置を取得
                route_stations = self._get_expected_route_sequence(segments, is_inbound)
                r_start_idx, _ = self._get_segment_range_in_sequence(segments, index, is_inbound)

                # 期待されるリスト内での分割駅の正確な位置を特定
                if not is_inbound:
                    target_route_idx = r_start_idx + rel_idx
                else:
                    target_route_idx = r_start_idx + (len(stations_in_this_segment) - 1 - rel_idx)

                for train in route_data.get(train_key, {}).values():
                    stops = train.get("stops", [])

                    # 列車が持つ停車駅リスト(stops)と、運行系統が定義する期待される駅リスト(route_stations)を突き合わせ、
                    # target_route_idx に対応する stops 内のインデックス(split_idx)を探す
                    split_idx = -1
                    r_ptr = 0
                    for s_idx, stop in enumerate(stops):
                        while r_ptr < len(route_stations):
                            if (stop.get("line_id") == route_stations[r_ptr][0] and 
                                stop.get("station_id") == route_stations[r_ptr][1]):
                                if r_ptr == target_route_idx:
                                    split_idx = s_idx
                                r_ptr += 1
                                break
                            r_ptr += 1
                        if split_idx != -1: break

                    if split_idx != -1:
                        orig_stop = stops[split_idx]
                        
                        # 進行方向における前段区間の「終点」としてのデータ（発時刻をNoneに設定）
                        stop_terminal = orig_stop.copy()
                        stop_terminal["departure_time"] = None
                        
                        # 進行方向における後段区間の「起点」としてのデータ（着時刻をNoneに設定）
                        stop_origin = orig_stop.copy()
                        stop_origin["arrival_time"] = None
                        
                        # 1つの停車駅データを、境界を跨ぐ2つのデータに分割して挿入
                        stops[split_idx : split_idx+1] = [stop_terminal, stop_origin]
            
            # 分割処理：元の要素を削除し、新しい2つの区間を挿入
            route_data["line_segments"].pop(index)
            route_data["line_segments"].insert(index, {"line_id": line_id, "start_station": start_sid, "end_station": split_sid})
            route_data["line_segments"].insert(index + 1, {"line_id": line_id, "start_station": split_sid, "end_station": end_sid})
            
            self._populate_segment_list(route_data)
            self._populate_station_preview(route_data) # プレビューの更新
            if hasattr(self.parent(), "set_modified"):
                self.parent().set_modified(True)

    def _on_delete_segment(self, index):
        """選択された区間を削除する"""
        selected = self.route_list_widget.selectedItems()
        if not selected: return
        route_id = selected[0].data(Qt.UserRole)
        route_data = self.project.routes.get(route_id)
        if route_data and 0 <= index < len(route_data["line_segments"]):
            # 削除されるセグメントの情報
            segment_data = route_data["line_segments"][index]
            line_id = segment_data.get("line_id")
            start_sid = segment_data.get("start_station")
            end_sid = segment_data.get("end_station")

            # 停車駅(stops)は運行系統直下のマスタ情報にあるため、ダイヤに関わらず1回だけ更新
            segments = route_data.get("line_segments", [])

            for train_key in ["inbound_trains", "outbound_trains"]:
                is_inbound = (train_key == "inbound_trains")
                
                # 期待されるシーケンスと、削除対象区間のインデックス範囲を取得
                route_stations = self._get_expected_route_sequence(segments, is_inbound)
                r_start_idx, r_end_idx = self._get_segment_range_in_sequence(segments, index, is_inbound)

                # 走行方向における起点と終点（境界判定用）
                seg_start_sid = end_sid if is_inbound else start_sid
                seg_end_sid = start_sid if is_inbound else end_sid

                for train in route_data.get(train_key, {}).values():
                    stops = train.get("stops", [])
                    new_stops = []
                    r_ptr = 0
                    for stop in stops:
                        matched_r_idx = -1
                        temp_r_ptr = r_ptr
                        while temp_r_ptr < len(route_stations):
                            if (stop.get("line_id") == route_stations[temp_r_ptr][0] and 
                                stop.get("station_id") == route_stations[temp_r_ptr][1]):
                                matched_r_idx = temp_r_ptr
                                r_ptr = temp_r_ptr + 1
                                break
                            temp_r_ptr += 1

                        # この停車駅が、削除対象の区間に属するかを判定
                        if matched_r_idx != -1 and r_start_idx <= matched_r_idx <= r_end_idx:
                            sid = stop.get("station_id")
                            # 境界駅において、隣接する残る区間のためのデータ（着時刻or発時刻がある）なら保持
                            if sid == seg_start_sid and stop.get("arrival_time") is not None:
                                pass # 他の区間の終了点としての役割があるため保持
                            elif sid == seg_end_sid and stop.get("departure_time") is not None:
                                pass # 他の区間の開始点としての役割があるため保持
                            else:
                                continue # 削除（リストに追加しない）

                        new_stops.append(stop)
                    train["stops"] = new_stops

            route_data["line_segments"].pop(index)
            self._populate_segment_list(route_data)
            self._populate_station_preview(route_data) # プレビューの更新
            if hasattr(self.parent(), "set_modified"):
                self.parent().set_modified(True)