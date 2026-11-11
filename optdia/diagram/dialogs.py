import copy
import re
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QSpinBox, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QMessageBox, QWidget, QListWidget, QListWidgetItem,
    QFrame
)
from PySide6.QtCore import Qt, QSize, QPoint
from PySide6.QtGui import QColor

from core.project import OptDiaProject, generate_random_id
from core.events import AddTrainEvent, ChangeTrainOperationEvent
from core.history_manager import HistoryManager
from common.gui_utils import HtmlDelegate
from dialogs.operation import VehicleOperationEditorDialog
from timetable.dialogs import DragDropListWidget, OperationItemWidget


def _format_time(text: str) -> Optional[str]:
    """
    timetable/model.py の _format_time と同様の整形処理。
    全角数字および全角コロンを半角に変換し、hh:mm:ss 形式に整形する。
    """
    if not text:
        return None
    table = str.maketrans("０１２３４５６７８９：", "0123456789:")
    text = text.translate(table)
    if not re.match(r"^[0-9:]+$", text):
        return None
    colon_count = text.count(':')
    hh, mm, ss = 0, 0, 0
    try:
        if colon_count == 0:
            s = text
            if len(s) <= 4:
                s += "00"
            s = s.zfill(6)
            if len(s) != 6:
                return None
            hh, mm, ss = int(s[0:2]), int(s[2:4]), int(s[4:6])
        elif colon_count == 1:
            parts = text.split(':')
            if not parts[0] or not parts[1]:
                return None
            hh, mm, ss = int(parts[0]), int(parts[1]), 0
        elif colon_count == 2:
            parts = text.split(':')
            if not parts[0] or not parts[1] or not parts[2]:
                return None
            hh, mm, ss = int(parts[0]), int(parts[1]), int(parts[2])
        else:
            return None
    except ValueError:
        return None
    if 0 <= hh <= 99 and 0 <= mm < 60 and 0 <= ss < 60:
        return f"{hh:02d}:{mm:02d}:{ss:02d}"
    return None


def _time_to_seconds(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    try:
        parts = text.split(':')
        if len(parts) == 3:
            h, m, s = map(int, parts)
            return h * 3600 + m * 60 + s
        elif len(parts) == 2:
            h, m = map(int, parts)
            return h * 3600 + m * 60
    except (ValueError, AttributeError):
        return None
    return None


def _seconds_to_time(seconds: Optional[int]) -> Optional[str]:
    if seconds is None:
        return None
    seconds = max(0, seconds)
    hh = seconds // 3600
    mm = (seconds % 3600) // 60
    ss = seconds % 60
    return f"{hh:02d}:{mm:02d}:{ss:02d}"


class StationPickerPopup(QDialog):
    """
    駅選択ポップアップ（ボタン押下時に表示されるリストウィジェット）。
    幅300px、高さ400pxのリストから1駅を選択する。
    """
    def __init__(self, parent, route_sequence: List[Dict[str, Any]], current_route_idx: Optional[int] = None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.selected_route_idx: Optional[int] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)

        self.list_widget = QListWidget(self)
        self.list_widget.setFixedSize(298, 398)
        layout.addWidget(self.list_widget)

        for item in route_sequence:
            ridx = item["route_idx"]
            sname = item["station_name"]
            lw_item = QListWidgetItem(sname)
            lw_item.setData(Qt.UserRole, ridx)
            self.list_widget.addItem(lw_item)

        # 現在選択されている駅を初期選択状態にする
        if current_route_idx is not None:
            for i in range(self.list_widget.count()):
                lw_item = self.list_widget.item(i)
                if lw_item.data(Qt.UserRole) == current_route_idx:
                    self.list_widget.setCurrentItem(lw_item)
                    self.list_widget.scrollToItem(lw_item)
                    break

        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.setFixedSize(300, 400)

    def _on_item_clicked(self, item: QListWidgetItem):
        self.selected_route_idx = item.data(Qt.UserRole)
        self.accept()


class TrainTableWidget(QTableWidget):
    """
    セルをダブルクリックしなくても Delete キーや Backspace キーを押すだけで
    選択セルの内容を削除できるように拡張した QTableWidget
    """
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            selected_items = self.selectedItems()
            if selected_items:
                for item in selected_items:
                    item.setText("")
                return
        super().keyPressEvent(event)


class AddTrainDialog(QDialog):
    """
    運行ダイヤグラム用「列車の追加」ダイアログ
    """
    def __init__(self, parent, project: OptDiaProject, route_id: str, diagram_id: str,
                 history_manager: Optional[HistoryManager] = None,
                 default_station_id: Optional[str] = None,
                 default_hour: int = 0, default_minute: int = 0):
        super().__init__(parent)
        self.setWindowTitle("列車の追加")
        self.resize(640, 640)

        self.project = project
        self.route_id = route_id
        self.diagram_id = diagram_id
        self.history_manager = history_manager

        self.full_route_sequence: List[Dict[str, Any]] = []
        self._build_full_route_sequence()

        self._is_formatting_table = False
        self._is_updating_minute = False

        # 始発・終着駅の選択状態（route_idx で管理）
        self._dep_route_idx: Optional[int] = None
        self._arr_route_idx: Optional[int] = None

        self._init_ui(default_station_id, default_hour, default_minute)

        self._auto_fill_times_if_possible()

    def _build_full_route_sequence(self):
        """
        運行系統（路線部分区間群）の順序に沿った全駅リストを構築する。
        各要素:
        {
            "segment_id": str,
            "line_id": str,
            "station_entry_id": str,
            "station_id": str,
            "station_name": str,
            "track_id": Optional[str],
            "is_segment_start": bool,
            "is_segment_end": bool,
            "show_arrival_time": bool,
            "route_idx": int
        }
        """
        self.full_route_sequence = []
        route = self.project.routes.get(self.route_id, {})
        segments = route.get("line_segments", [])

        idx_counter = 0
        for seg in segments:
            seg_id = seg.get("segment_id")
            line_id = seg.get("line_id")
            line_data = self.project.lines.get(line_id, {})

            start_entry = seg.get("start_station_entry", seg.get("start_station"))
            end_entry = seg.get("end_station_entry", seg.get("end_station"))

            line_entries = line_data.get("station_entries", [])
            line_eids = [s.get("station_entry_id") for s in line_entries]

            if start_entry not in line_eids or end_entry not in line_eids:
                continue

            idx_start = line_eids.index(start_entry)
            idx_end = line_eids.index(end_entry)

            seg_direction = "outbound" if idx_start <= idx_end else "inbound"

            if idx_start <= idx_end:
                seg_entries_slice = line_entries[idx_start:idx_end + 1]
            else:
                seg_entries_slice = line_entries[idx_start:idx_end - 1 if idx_end > 0 else None:-1] if idx_end > 0 else line_entries[idx_start::-1]

            num_in_seg = len(seg_entries_slice)
            for i, ls_item in enumerate(seg_entries_slice):
                sid = ls_item.get("station_id")
                seid = ls_item.get("station_entry_id")
                track_id = ls_item.get("inbound_main_track" if seg_direction == "inbound" else "outbound_main_track")
                st_obj = self.project.stations.get(sid, {})
                s_name = st_obj.get("station_name", sid)
                show_arr = st_obj.get("show_arrival_time", False)

                self.full_route_sequence.append({
                    "segment_id": seg_id,
                    "line_id": line_id,
                    "station_entry_id": seid,
                    "station_id": sid,
                    "station_name": s_name,
                    "track_id": track_id,
                    "is_segment_start": (i == 0),
                    "is_segment_end": (i == num_in_seg - 1),
                    "show_arrival_time": show_arr,
                    "route_idx": idx_counter
                })
                idx_counter += 1

    def _init_ui(self, default_station_id: Optional[str], default_hour: int, default_minute: int):
        main_layout = QVBoxLayout(self)

        # 上部コンテンツ（左側と右側）
        content_layout = QHBoxLayout()

        # ==========================================
        # 左側の領域
        # ==========================================
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 10, 0)

        # 1. 列車番号: ラベル & 1行テキストボックス
        lbl_train_num = QLabel("列車番号:")
        self.txt_train_number = QLineEdit()
        left_layout.addWidget(lbl_train_num)
        left_layout.addWidget(self.txt_train_number)

        # 2. 種別・愛称 / 号数 ラベル
        lbl_type_name = QLabel("種別・愛称 / 号数")
        left_layout.addWidget(lbl_type_name)

        type_h_layout = QHBoxLayout()
        # 列車種別選択用コンボボックス
        # 選択肢形式: 「<列車種別名> <列車愛称(Noneの場合は非表示)>」
        self.combo_train_type = QComboBox()
        for ttid in self.project.train_types_order:
            tt = self.project.train_types.get(ttid, {})
            name = tt.get("train_type_name", "")
            nickname = tt.get("train_name")
            display_text = f"{name} {nickname}" if nickname else name
            self.combo_train_type.addItem(display_text, ttid)
        type_h_layout.addWidget(self.combo_train_type, 1)

        # 号数を入力するためのスピンボックス (幅60px、単位「号」、0〜999、0は「なし」)
        self.spin_named_number = QSpinBox()
        self.spin_named_number.setFixedWidth(60)
        self.spin_named_number.setRange(0, 999)
        self.spin_named_number.setSpecialValueText("なし")
        self.spin_named_number.setSuffix("号")
        self.spin_named_number.setValue(0)
        type_h_layout.addWidget(self.spin_named_number)
        left_layout.addLayout(type_h_layout)

        # 3. 始発: ラベル & 始発駅選択ボタン
        lbl_dep_station = QLabel("始発:")
        self.btn_dep_station = QPushButton()
        self.btn_dep_station.setFlat(False)
        left_layout.addWidget(lbl_dep_station)
        left_layout.addWidget(self.btn_dep_station)

        # 始発時刻スピンボックス群 (時と分は別々。時: 0〜99。分: -1〜60で自動調整)
        time_h_layout = QHBoxLayout()
        lbl_time = QLabel("始発時刻:")
        self.spin_dep_hour = QSpinBox()
        self.spin_dep_hour.setRange(0, 99)
        self.spin_dep_hour.setSuffix("時")
        self.spin_dep_hour.setValue(default_hour)

        self.spin_dep_min = QSpinBox()
        self.spin_dep_min.setRange(-1, 60)
        self.spin_dep_min.setSuffix("分")
        self.spin_dep_min.setValue(default_minute)

        time_h_layout.addWidget(lbl_time)
        time_h_layout.addWidget(self.spin_dep_hour)
        time_h_layout.addWidget(self.spin_dep_min)
        left_layout.addLayout(time_h_layout)

        # 4. 終着: ラベル & 終着駅選択ボタン
        lbl_arr_station = QLabel("終着:")
        self.btn_arr_station = QPushButton()
        self.btn_arr_station.setFlat(False)
        left_layout.addWidget(lbl_arr_station)
        left_layout.addWidget(self.btn_arr_station)

        # デフォルト始発駅の設定
        dep_selected_idx = 0
        if default_station_id:
            for i, item in enumerate(self.full_route_sequence):
                if item["station_id"] == default_station_id:
                    dep_selected_idx = i
                    break

        # デフォルト終着駅の設定（始発駅より後の駅、なければ末尾）
        arr_selected_idx = len(self.full_route_sequence) - 1

        # 内部状態を設定してボタンラベルを更新
        if self.full_route_sequence:
            self._dep_route_idx = self.full_route_sequence[dep_selected_idx]["route_idx"]
            self._arr_route_idx = self.full_route_sequence[arr_selected_idx]["route_idx"]
            self.btn_dep_station.setText(self.full_route_sequence[dep_selected_idx]["station_name"])
            self.btn_arr_station.setText(self.full_route_sequence[arr_selected_idx]["station_name"])

        # 5. 警告ラベル（始発駅と終着駅が同じ駅の場合）
        self.lbl_station_warning = QLabel("始発駅と終着駅で同じ駅エントリが選択されています。")
        self.lbl_station_warning.setStyleSheet("color: #cc3333;")
        self.lbl_station_warning.setVisible(False)
        left_layout.addWidget(self.lbl_station_warning)

        left_layout.addStretch()
        content_layout.addWidget(left_widget, 1)

        # ==========================================
        # 右側の領域（テーブルウィジェット）
        # ==========================================
        self.table_widget = TrainTableWidget()
        self.table_widget.setColumnCount(1)
        self.table_widget.setHorizontalHeaderLabels(["発着時刻"])
        self.table_widget.horizontalHeader().setStretchLastSection(True)
        self.table_widget.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table_widget.itemChanged.connect(self._on_table_item_changed)
        self.table_widget.setFixedWidth(240)
        content_layout.addWidget(self.table_widget, 1)

        main_layout.addLayout(content_layout)

        # ==========================================
        # 下部のボタンエリア
        # ==========================================
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_ok = QPushButton("OK")
        self.btn_cancel = QPushButton("キャンセル")
        self.btn_ok.clicked.connect(self._on_ok_clicked)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok.setProperty("class", "ok_button")
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        main_layout.addLayout(btn_layout)

        # シグナル接続
        self.btn_dep_station.clicked.connect(self._on_dep_station_btn_clicked)
        self.btn_arr_station.clicked.connect(self._on_arr_station_btn_clicked)
        self.combo_train_type.currentIndexChanged.connect(self._on_train_type_or_dest_changed)

        # 初回のテーブル更新
        self._update_table_rows()
        self._check_station_warning()

        # 始発時刻の前回値を記録し、スピンボックス変更シグナルを接続
        self.prev_dep_hour = self.spin_dep_hour.value()
        self.prev_dep_min = self.spin_dep_min.value()
        self.spin_dep_hour.valueChanged.connect(self._on_hour_value_changed)
        self.spin_dep_min.valueChanged.connect(self._on_minute_value_changed)

    def _on_hour_value_changed(self, new_h: int):
        if self._is_updating_minute:
            return
        diff_sec = (new_h - self.prev_dep_hour) * 3600
        self.prev_dep_hour = new_h
        if diff_sec != 0:
            self._shift_table_times(diff_sec)

    def _on_minute_value_changed(self, val: int):
        """分のスピンボックスが-1分や60分になったときは、即座に59分、0分に書き換え、時のスピンボックスを増減する"""
        if self._is_updating_minute:
            return
        self._is_updating_minute = True
        try:
            target_min = val
            hour_delta = 0
            if val == 60:
                target_min = 0
                self.spin_dep_min.setValue(0)
                if self.spin_dep_hour.value() < 99:
                    hour_delta = 1
                    self.spin_dep_hour.setValue(self.spin_dep_hour.value() + 1)
            elif val == -1:
                target_min = 59
                self.spin_dep_min.setValue(59)
                if self.spin_dep_hour.value() > 0:
                    hour_delta = -1
                    self.spin_dep_hour.setValue(self.spin_dep_hour.value() - 1)

            # 分および繰り上がり・繰り下がりによる差分秒数を計算
            diff_sec = ((target_min - self.prev_dep_min) + hour_delta * 60) * 60
            self.prev_dep_min = target_min
            self.prev_dep_hour = self.spin_dep_hour.value()
            if diff_sec != 0:
                self._shift_table_times(diff_sec)
        finally:
            self._is_updating_minute = False

    def _shift_table_times(self, diff_sec: int):
        """始発時刻スピンボックスの増減に合わせて、テーブルに表示されている各時刻を同じだけ増減する"""
        if diff_sec == 0:
            return
        self._is_formatting_table = True
        try:
            for r in range(self.table_widget.rowCount()):
                cell_item = self.table_widget.item(r, 0)
                if not cell_item:
                    continue
                time_str = cell_item.text().strip()
                if not time_str:
                    continue
                sec = _time_to_seconds(time_str)
                if sec is not None:
                    new_sec = max(0, sec + diff_sec)
                    new_time_str = _seconds_to_time(new_sec)
                    cell_item.setText(new_time_str)
                    cell_item.setData(Qt.UserRole + 1, new_time_str)
        finally:
            self._is_formatting_table = False

    def _check_station_warning(self):
        dep_ridx = self._dep_route_idx
        arr_ridx = self._arr_route_idx
        same_station = False
        if dep_ridx is not None and arr_ridx is not None:
            dep_item = next((x for x in self.full_route_sequence if x["route_idx"] == dep_ridx), None)
            arr_item = next((x for x in self.full_route_sequence if x["route_idx"] == arr_ridx), None)
            if dep_item and arr_item and dep_item["station_entry_id"] == arr_item["station_entry_id"]:
                same_station = True
        self.lbl_station_warning.setVisible(same_station)

    def _on_dep_station_btn_clicked(self):
        popup = StationPickerPopup(self, self.full_route_sequence, self._dep_route_idx)
        btn_pos = self.btn_dep_station.mapToGlobal(QPoint(0, self.btn_dep_station.height()))
        popup.move(btn_pos)
        if popup.exec() and popup.selected_route_idx is not None:
            self._dep_route_idx = popup.selected_route_idx
            dep_item = next((x for x in self.full_route_sequence if x["route_idx"] == self._dep_route_idx), None)
            if dep_item:
                self.btn_dep_station.setText(dep_item["station_name"])
            self._on_station_selection_changed()

    def _on_arr_station_btn_clicked(self):
        popup = StationPickerPopup(self, self.full_route_sequence, self._arr_route_idx)
        btn_pos = self.btn_arr_station.mapToGlobal(QPoint(0, self.btn_arr_station.height()))
        popup.move(btn_pos)
        if popup.exec() and popup.selected_route_idx is not None:
            self._arr_route_idx = popup.selected_route_idx
            arr_item = next((x for x in self.full_route_sequence if x["route_idx"] == self._arr_route_idx), None)
            if arr_item:
                self.btn_arr_station.setText(arr_item["station_name"])
            self._on_station_selection_changed()

    def _on_station_selection_changed(self):
        self._check_station_warning()
        self._update_table_rows()
        self._auto_fill_times_if_possible()

    def _on_train_type_or_dest_changed(self):
        self._auto_fill_times_if_possible()

    def _get_selected_interval_items(self) -> List[Dict[str, Any]]:
        dep_ridx = self._dep_route_idx
        arr_ridx = self._arr_route_idx
        if dep_ridx is None or arr_ridx is None or not self.full_route_sequence:
            return []

        if dep_ridx <= arr_ridx:
            return self.full_route_sequence[dep_ridx:arr_ridx + 1]
        else:
            return self.full_route_sequence[dep_ridx:arr_ridx - 1 if arr_ridx > 0 else None:-1] if arr_ridx > 0 else self.full_route_sequence[dep_ridx::-1]

    def _update_table_rows(self):
        """
        垂直ヘッダーへ始発駅から終着駅までの間にある駅名を1行に1つずつ表示し、
        セル(1列のみ表示、水平ヘッダーには「発着時刻」と表示する。)には各行の駅に対応する発着時刻をhh:mm:ss形式で入力可能とする。
        ただし、始発駅と部分区間の最初の駅は発車時刻専用の入力セル、
        終着駅と部分区間の最後の駅は終着時刻専用の入力セルを表示し、
        それ以外の駅のうちshow_arrival_time=Trueの駅では到着時刻と発車時刻を別々の行に表示する。
        発車時刻専用の行では「[発]」、到着時刻専用の行では「[着]」をそれぞれ駅名の末尾に付加して表示する。
        """
        items = self._get_selected_interval_items()
        self.table_widget.blockSignals(True)
        self.table_widget.setRowCount(0)

        if not items:
            self.table_widget.blockSignals(False)
            return

        row_defs = []
        n_items = len(items)

        # 上り/下りの判定: items[0] の route_idx が items[-1] より大きければ上り列車
        # full_route_sequence は下り方向で構築されているため、is_segment_start/is_segment_end の
        # 意味が上り列車では逆転する。上り列車では is_segment_end が「区間への入口(発)」、
        # is_segment_start が「区間からの出口(着)」となる。
        is_inbound = (items[0]["route_idx"] > items[-1]["route_idx"]) if n_items > 1 else False

        for i, item in enumerate(items):
            is_first = (i == 0)
            is_last = (i == n_items - 1)
            is_seg_start = item.get("is_segment_start", False)
            is_seg_end = item.get("is_segment_end", False)
            show_arr = item.get("show_arrival_time", False)
            name = item.get("station_name", "")

            # 上り列車の場合、区間フラグの役割を入れ替えて解釈する
            if is_inbound:
                seg_entry_point = is_seg_end    # 区間への入口（下り向き「終点」が上り向き「始点」）
                seg_exit_point = is_seg_start   # 区間からの出口（下り向き「始点」が上り向き「終点」）
            else:
                seg_entry_point = is_seg_start  # 区間への入口（下り向き「始点」がそのまま「始点」）
                seg_exit_point = is_seg_end     # 区間からの出口（下り向き「終点」がそのまま「終点」）

            if is_first:
                # 始発駅: 発車時刻専用
                row_defs.append({
                    "header": f"{name} [発]",
                    "type": "dep",
                    "item": item
                })
            elif is_last:
                # 終着駅: 到着時刻専用
                row_defs.append({
                    "header": f"{name} [着]",
                    "type": "arr",
                    "item": item
                })
            elif seg_exit_point and seg_entry_point:
                # 隣接する区間の接続点（前の区間の出口かつ次の区間の入口）:
                # 到着[着]→発車[発]の順で表示
                row_defs.append({
                    "header": f"{name} [着]",
                    "type": "arr",
                    "item": item
                })
                row_defs.append({
                    "header": f"{name} [発]",
                    "type": "dep",
                    "item": item
                })
            elif seg_exit_point:
                # 区間の出口（前の区間の終点）: 到着時刻専用
                row_defs.append({
                    "header": f"{name} [着]",
                    "type": "arr",
                    "item": item
                })
            elif seg_entry_point:
                # 区間の入口（次の区間の始点）: 発車時刻専用
                row_defs.append({
                    "header": f"{name} [発]",
                    "type": "dep",
                    "item": item
                })
            elif show_arr:
                # 中間駅（show_arrival_time=True）: 到着時刻→発車時刻の順で表示
                row_defs.append({
                    "header": f"{name} [着]",
                    "type": "arr",
                    "item": item
                })
                row_defs.append({
                    "header": f"{name} [発]",
                    "type": "dep",
                    "item": item
                })
            else:
                # 中間駅（show_arrival_time=False）: 発時刻のみ
                row_defs.append({
                    "header": name,
                    "type": "dep",
                    "item": item
                })

        self.table_widget.setRowCount(len(row_defs))
        v_headers = []
        for r, rdef in enumerate(row_defs):
            v_headers.append(rdef["header"])
            cell_item = QTableWidgetItem("")
            cell_item.setData(Qt.UserRole, rdef)
            self.table_widget.setItem(r, 0, cell_item)

        self.table_widget.setVerticalHeaderLabels(v_headers)
        self.table_widget.blockSignals(False)

        # 始発駅の発時刻にデフォルトの始発時刻を設定
        if len(row_defs) > 0 and row_defs[0]["type"] == "dep":
            h = self.spin_dep_hour.value()
            m = self.spin_dep_min.value()
            init_time = f"{h:02d}:{m:02d}:00"
            self.table_widget.item(0, 0).setText(init_time)
            self.table_widget.item(0, 0).setData(Qt.UserRole + 1, init_time)

    def _on_table_item_changed(self, item: QTableWidgetItem):
        """
        発着時刻のセルに変更が行われたときは、timetable/model.pyの関数_format_timeと同様の処理で入力内容を整形する。
        既に入力されている発着時刻を編集して増減させたときに、その駅よりあとの駅の時刻も同じだけ自動で増減する。
        また、最初の駅の時刻を編集したときは、始発時刻スピンボックスへその時刻を反映する。
        """
        if self._is_formatting_table:
            return

        text = item.text().strip()
        old_time_str = item.data(Qt.UserRole + 1)
        row = item.row()

        if not text:
            # 空白化された場合
            item.setData(Qt.UserRole + 1, None)
            return

        formatted = _format_time(text)
        self._is_formatting_table = True
        try:
            if formatted is not None:
                item.setText(formatted)
                item.setData(Qt.UserRole + 1, formatted)

                # 時刻の増減差分を計算
                if old_time_str:
                    t_old = _time_to_seconds(old_time_str)
                    t_new = _time_to_seconds(formatted)
                    if t_old is not None and t_new is not None:
                        diff_sec = t_new - t_old
                        if diff_sec != 0:
                            # その駅よりあとの駅の時刻も同じだけ自動で増減
                            for r in range(row + 1, self.table_widget.rowCount()):
                                cell_next = self.table_widget.item(r, 0)
                                if not cell_next:
                                    continue
                                next_time_str = cell_next.text().strip()
                                if not next_time_str:
                                    continue
                                sec = _time_to_seconds(next_time_str)
                                if sec is not None:
                                    updated_time = _seconds_to_time(max(0, sec + diff_sec))
                                    cell_next.setText(updated_time)
                                    cell_next.setData(Qt.UserRole + 1, updated_time)

                # 最初の駅の時刻を編集したときは、始発時刻スピンボックスへその時刻を反映
                if row == 0 and formatted is not None:
                    sec = _time_to_seconds(formatted)
                    if sec is not None:
                        h = sec // 3600
                        m = (sec % 3600) // 60
                        # スピンボックス更新（スピンボックスのシグナルによるテーブル再シフトを防止）
                        self.prev_dep_hour = h
                        self.prev_dep_min = m
                        self.spin_dep_hour.blockSignals(True)
                        self.spin_dep_min.blockSignals(True)
                        self.spin_dep_hour.setValue(h)
                        self.spin_dep_min.setValue(m)
                        self.spin_dep_hour.blockSignals(False)
                        self.spin_dep_min.blockSignals(False)
            else:
                item.setText("")
                item.setData(Qt.UserRole + 1, None)
        finally:
            self._is_formatting_table = False

    def _auto_fill_times_if_possible(self):
        """
        同一種別・同一方向かつ始発駅を経由する列車で選択中の始発時刻より前にあるものの中で最後の列車
        (前になければ後にあるものの中で最初の列車)から、選択中の始発駅から選択中の終着駅までの
        各経由駅の所要時間を計算して、右側のテーブルに時刻を自動入力する。

        ただし、時刻基準で選ばれた列車の終着駅が入力された終着駅より手前にある場合（終着駅の時刻が
        自動入力できない場合）で、同じ方向・同じ種別の列車で指定された終着駅と同じかそれより遠い駅まで
        運転される列車があるならば、そちらを優先して所要時間を参照する。
        """
        tt_id = self.combo_train_type.currentData()
        if not tt_id:
            return

        interval_items = self._get_selected_interval_items()
        if not interval_items:
            return

        start_station_id = interval_items[0]["station_id"]
        end_station_entry_id = interval_items[-1]["station_entry_id"]
        start_route_idx = interval_items[0]["route_idx"]
        end_route_idx = interval_items[-1]["route_idx"]
        is_outbound = (start_route_idx <= end_route_idx)

        # 選択中の始発時刻
        dep_h = self.spin_dep_hour.value()
        dep_m = self.spin_dep_min.value()
        selected_dep_sec = dep_h * 3600 + dep_m * 60

        route = self.project.routes.get(self.route_id, {})
        tbd = route.get("trains_by_diagram", {}).get(self.diagram_id, {})
        d_inbound = tbd.get("inbound_trains", {})
        d_outbound = tbd.get("outbound_trains", {})
        m_inbound = route.get("inbound_trains", {})
        m_outbound = route.get("outbound_trains", {})

        # ダイヤグラム上に表示されている列車から同一種別かつ始発駅を経由する列車を収集
        # 追加する列車の方向(上り/下り)に合わせて、同一方向の列車のみを候補とする
        candidate_trains = []

        if is_outbound:
            dir_pairs = [(d_outbound, m_outbound)]
        else:
            dir_pairs = [(d_inbound, m_inbound)]

        entry_to_sid = getattr(self.project, "station_entry_to_station_id", {})

        for d_dict, m_dict in dir_pairs:
            for tid, d_train in d_dict.items():
                if not d_train.get("to_be_saved", True):
                    continue
                m_train = m_dict.get(tid)
                if not m_train:
                    continue
                if m_train.get("train_type_id") != tt_id:
                    continue

                stops = m_train.get("stops", [])
                # 始発駅を経由しているか確認
                matched_stop = None
                for st in stops:
                    sid = entry_to_sid.get(st.get("station_entry_id"), st.get("station_id"))
                    if sid == start_station_id:
                        matched_stop = st
                        break

                if not matched_stop:
                    continue

                # 始発駅での発着時刻
                dep_time_str = matched_stop.get("departure_time") or matched_stop.get("arrival_time")
                ref_dep_sec = _time_to_seconds(dep_time_str)
                if ref_dep_sec is None:
                    continue

                # この列車が終着駅（end_station_entry_id）以降まで運転されているか確認
                # stops の中に end_station_entry_id が含まれていれば「到達可能」とみなす
                reaches_dest = any(
                    st.get("station_entry_id") == end_station_entry_id
                    for st in stops
                )

                candidate_trains.append({
                    "m_train": m_train,
                    "ref_dep_sec": ref_dep_sec,
                    "matched_stop": matched_stop,
                    "reaches_dest": reaches_dest
                })

        if not candidate_trains:
            return

        # 選択中の始発時刻より前にあるものの中で最後の列車（前になければ後にあるものの中で最初の列車）
        earlier_trains = [t for t in candidate_trains if t["ref_dep_sec"] <= selected_dep_sec]
        later_trains = [t for t in candidate_trains if t["ref_dep_sec"] > selected_dep_sec]

        if earlier_trains:
            earlier_trains.sort(key=lambda t: t["ref_dep_sec"])
            time_chosen = earlier_trains[-1]
        elif later_trains:
            later_trains.sort(key=lambda t: t["ref_dep_sec"])
            time_chosen = later_trains[0]
        else:
            return

        # 時刻基準で選ばれた列車が終着駅に到達しない場合、終着駅まで運転される列車を優先して選ぶ
        if not time_chosen["reaches_dest"]:
            # 終着駅に到達する候補が存在するか確認
            dest_reachable = [t for t in candidate_trains if t["reaches_dest"]]
            if dest_reachable:
                # 同じく「始発時刻より前で最後→なければ後で最初」のルールで選ぶ
                dest_earlier = [t for t in dest_reachable if t["ref_dep_sec"] <= selected_dep_sec]
                dest_later = [t for t in dest_reachable if t["ref_dep_sec"] > selected_dep_sec]
                if dest_earlier:
                    dest_earlier.sort(key=lambda t: t["ref_dep_sec"])
                    chosen = dest_earlier[-1]
                else:
                    dest_later.sort(key=lambda t: t["ref_dep_sec"])
                    chosen = dest_later[0]
            else:
                chosen = time_chosen
        else:
            chosen = time_chosen

        ref_train = chosen["m_train"]
        ref_start_dep_sec = chosen["ref_dep_sec"]
        ref_stops = ref_train.get("stops", [])

        # 各経由駅の所要時間を参照列車から計算
        # station_id -> {arr_diff: int, dep_diff: int}
        station_offsets: Dict[str, Dict[str, Optional[int]]] = {}
        for st in ref_stops:
            sid = getattr(self.project, "station_entry_to_station_id", {}).get(
                st.get("station_entry_id"), st.get("station_id")
            )
            if not sid:
                continue
            arr_s = _time_to_seconds(st.get("arrival_time"))
            dep_s = _time_to_seconds(st.get("departure_time"))

            arr_diff = (arr_s - ref_start_dep_sec) if arr_s is not None else None
            dep_diff = (dep_s - ref_start_dep_sec) if dep_s is not None else None

            if sid not in station_offsets:
                station_offsets[sid] = {"arr_diff": arr_diff, "dep_diff": dep_diff}

        # テーブルの各セルに時刻を自動入力
        self._is_formatting_table = True
        try:
            for r in range(self.table_widget.rowCount()):
                cell_item = self.table_widget.item(r, 0)
                if not cell_item:
                    continue
                rdef = cell_item.data(Qt.UserRole)
                if not rdef:
                    continue
                st_item = rdef["item"]
                sid = st_item["station_id"]
                row_type = rdef["type"]

                if sid in station_offsets:
                    offsets = station_offsets[sid]
                    diff = offsets["dep_diff"] if row_type == "dep" else offsets["arr_diff"]
                    if diff is None and row_type == "arr":
                        diff = offsets["dep_diff"]
                    if diff is None and row_type == "dep":
                        diff = offsets["arr_diff"]

                    if diff is not None:
                        calc_sec = selected_dep_sec + diff
                        time_str = _seconds_to_time(calc_sec)
                        cell_item.setText(time_str)
                        cell_item.setData(Qt.UserRole + 1, time_str)
                elif r == 0 and row_type == "dep":
                    time_str = _seconds_to_time(selected_dep_sec)
                    cell_item.setText(time_str)
                    cell_item.setData(Qt.UserRole + 1, time_str)
        finally:
            self._is_formatting_table = False

    def _on_ok_clicked(self):
        """
        「OK」ボタンが押されたときには、入力内容に応じて、
        運行ダイヤグラムで表示中の運行系統・運転ダイヤの上り列車情報または下り列車情報
        (運行系統上での始発駅と終着駅の位置関係から上り下りを判定)の末尾
        (to_be_savedがTrueでない列車よりは前)に新しい列車が挿入される。
        このとき、HistoryManagerクラスのインスタンスへ、列車の追加イベントのインスタンスを登録すること。
        """
        dep_ridx = self._dep_route_idx
        arr_ridx = self._arr_route_idx
        if dep_ridx is None or arr_ridx is None:
            self.reject()
            return

        if dep_ridx == arr_ridx:
            QMessageBox.critical(
                self,
                "エラー",
                "経由駅のない列車を追加することはできません"
            )
            return

        interval_items = self._get_selected_interval_items()
        if not interval_items:
            self.reject()
            return

        # 運行系統上での始発駅と終着駅の位置関係から上り下りを判定
        # 起点側(インデックス小)から終点側(大)へ向かうのが「下り(outbound)」、逆が「上り(inbound)」
        direction = "outbound" if dep_ridx <= arr_ridx else "inbound"

        route = self.project.routes.get(self.route_id, {})
        tbd = route.setdefault("trains_by_diagram", {}).setdefault(self.diagram_id, {})
        train_key = "inbound_trains" if direction == "inbound" else "outbound_trains"
        order_key = f"{train_key}_order"

        d_trains = tbd.setdefault(train_key, {})
        order = tbd.setdefault(order_key, [])
        m_trains = route.setdefault(train_key, {})

        # テーブルの入力内容から stops を構築
        # 各駅の arrival_time, departure_time を収集
        item_stops_map: Dict[int, Dict[str, Any]] = {}
        for r in range(self.table_widget.rowCount()):
            cell_item = self.table_widget.item(r, 0)
            if not cell_item:
                continue
            rdef = cell_item.data(Qt.UserRole)
            if not rdef:
                continue
            time_str = cell_item.text().strip() or None
            st_item = rdef["item"]
            ridx = st_item["route_idx"]
            row_type = rdef["type"]

            if ridx not in item_stops_map:
                item_stops_map[ridx] = {
                    "segment_id": st_item["segment_id"],
                    "station_entry_id": st_item["station_entry_id"],
                    "track_id": st_item["track_id"],
                    "arrival_time": None,
                    "departure_time": None,
                    "stop_type": 1
                }

            if row_type == "arr":
                item_stops_map[ridx]["arrival_time"] = time_str
            elif row_type == "dep":
                item_stops_map[ridx]["departure_time"] = time_str

        # stops を interval_items の順にリスト化
        stops = []
        n_items = len(interval_items)
        is_inbound = (direction == "inbound")
        for i, item in enumerate(interval_items):
            ridx = item["route_idx"]
            stop_data = item_stops_map.get(ridx, {
                "segment_id": item["segment_id"],
                "station_entry_id": item["station_entry_id"],
                "track_id": item["track_id"],
                "arrival_time": None,
                "departure_time": None,
                "stop_type": 1
            })

            # 部分区間端の判定（上り列車の場合は進行方向に対して始点と終点の意味が逆転する）
            is_seg_start = item.get("is_segment_end") if is_inbound else item.get("is_segment_start")
            is_seg_end = item.get("is_segment_start") if is_inbound else item.get("is_segment_end")
            is_seg_boundary = is_seg_start or is_seg_end
            show_arr = item.get("show_arrival_time", False)

            # 始発駅・部分区間始点
            if i == 0 or is_seg_start:
                stop_data["arrival_time"] = None

            # 終着駅・部分区間終点
            if i == n_items - 1:
                # 列車の終着駅の経由駅情報では、その駅が部分区間の端の駅でなくshow_arrival_time=Trueでもないならば発時刻をNoneとせずに着時刻と同じ値を設定する
                if not is_seg_boundary and not show_arr:
                    stop_data["departure_time"] = stop_data.get("arrival_time")
                else:
                    stop_data["departure_time"] = None
            elif is_seg_end:
                stop_data["departure_time"] = None

            # 中間駅かつ着時刻非表示で発時刻のみ入力されている場合、着時刻にも同じ値を設定
            if i > 0 and i < n_items - 1 and not is_seg_boundary:
                if not show_arr:
                    if stop_data["departure_time"] and not stop_data["arrival_time"]:
                        stop_data["arrival_time"] = stop_data["departure_time"]

            # 発着時刻の入力されていない通過駅には経由駅情報を生成しない
            if stop_data.get("arrival_time") is None and stop_data.get("departure_time") is None:
                continue

            stops.append(stop_data)

        # 列車IDの生成
        existing_ids = set(m_trains.keys()) | set(d_trains.keys())
        while True:
            new_train_id = generate_random_id()
            if new_train_id not in existing_ids:
                break

        train_num = self.txt_train_number.text().strip()
        tt_id = self.combo_train_type.currentData()
        named_num = self.spin_named_number.value()
        named_num_val = named_num if named_num >= 0 else None

        new_d_train = {
            "train_id": new_train_id,
            "operations": [],
            "car_count": None,
            "destination": None,
            "subsequent_trains": [],
            "to_be_saved": True
        }

        new_m_train = {
            "train_number": train_num,
            "train_type_id": tt_id,
            "named_train_number": named_num_val,
            "note": "",
            "stops": stops,
            "_diagram_ids": [self.diagram_id]
        }

        # 挿入位置: to_be_saved が True でない列車より前、末尾
        insert_idx = len(order)
        for i, tid in enumerate(order):
            dt = d_trains.get(tid, {})
            if dt.get("to_be_saved") is False:
                insert_idx = i
                break

        d_trains[new_train_id] = new_d_train
        m_trains[new_train_id] = new_m_train
        order.insert(insert_idx, new_train_id)

        # 履歴マネージャへのイベント登録
        if self.history_manager:
            ev = AddTrainEvent(
                self.route_id, direction, new_train_id, self.diagram_id,
                insert_idx, new_d_train, new_m_train
            )
            self.history_manager.push_events([ev])

        self.accept()


def delete_train(parent_view, train_data):
    """
    ダイヤグラム上の列車を削除する
    """
    from core.events import RemoveTrainEvent, RemoveTrainDiagramEvent

    main_win = parent_view.window()
    project = getattr(main_win, "project", parent_view.scene.project)
    diagram_id = getattr(parent_view.scene, "diagram_id", None)
    history_manager = getattr(main_win, "history_manager", None)

    if not project or not diagram_id:
        return False

    # rendered_trains に格納済みの識別情報を使用
    train_id = train_data.get("train_id")
    direction = train_data.get("direction")
    route_id = train_data.get("route_id")
    train_number = train_data.get("train_number") or "(番号なし)"

    if not train_id or not direction or not route_id:
        return False

    route = project.routes.get(route_id)
    if not route:
        return False

    train_key = "inbound_trains" if direction == "inbound" else "outbound_trains"
    order_key = f"{train_key}_order"
    tbd = route.get("trains_by_diagram", {}).get(diagram_id, {})
    d_trains = tbd.get(train_key, {})
    order = tbd.get(order_key, [])
    m_trains = route.get(train_key, {})

    m_train = m_trains.get(train_id)
    d_train = d_trains.get(train_id)
    if not m_train or not d_train:
        return False

    # 削除確認ダイアログ
    reply = QMessageBox.question(
        parent_view,
        "列車の削除",
        f"列車 {train_number} を削除しますか？",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No
    )
    if reply != QMessageBox.Yes:
        return False

    # 複数ダイヤで運転されている列車があるか確認
    actual_diagram_ids = []
    for did in project.diagrams_order:
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

    events_to_push = []

    if delete_from_all_diagrams:
        # 全運転ダイヤおよび運行系統マスタから削除 -> RemoveTrainEvent
        if hasattr(project, "remove_all_train_links"):
            project.remove_all_train_links(route_id, direction, train_id)
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

                # 削除する列車に担当運用が設定されていた場合、operation_train_lookup を更新する
                ops = d_trains_by_diagram[did][1].get("operations", [])
                if ops and hasattr(project, "update_operation_train_lookup"):
                    project.update_operation_train_lookup(
                        did, route_id, direction, train_id,
                        ops, []
                    )

        m_train_snapshot = copy.deepcopy(m_train)
        if train_id in m_trains:
            del m_trains[train_id]

        ev = RemoveTrainEvent(route_id, direction, train_id, d_trains_by_diagram, m_train_snapshot)
        events_to_push.append(ev)
    else:
        # 現在の運転ダイヤからのみ削除
        if len(actual_diagram_ids) <= 1:
            # 登録が1つのみ -> RemoveTrainEvent（マスタからも削除）
            if hasattr(project, "remove_all_train_links"):
                project.remove_all_train_links(route_id, direction, train_id)
            old_idx = order.index(train_id) if train_id in order else 0
            d_trains_by_diagram = {diagram_id: (old_idx, copy.deepcopy(d_train))}
            if train_id in order:
                order.remove(train_id)
            if train_id in d_trains:
                del d_trains[train_id]
            m_train_snapshot = copy.deepcopy(m_train)
            if train_id in m_trains:
                del m_trains[train_id]

            # 削除する列車に担当運用が設定されていた場合、operation_train_lookup を更新する
            ops = d_trains_by_diagram[diagram_id][1].get("operations", [])
            if ops and hasattr(project, "update_operation_train_lookup"):
                project.update_operation_train_lookup(
                    diagram_id, route_id, direction, train_id,
                    ops, []
                )

            ev = RemoveTrainEvent(route_id, direction, train_id, d_trains_by_diagram, m_train_snapshot)
            events_to_push.append(ev)
        else:
            # 複数ダイヤに登録済み -> 現在のダイヤからのみ削除（RemoveTrainDiagramEvent）
            old_idx = order.index(train_id) if train_id in order else 0
            old_d_train = copy.deepcopy(d_train)
            if train_id in order:
                order.remove(train_id)
            if train_id in d_trains:
                del d_trains[train_id]
            if "_diagram_ids" in m_train and diagram_id in m_train["_diagram_ids"]:
                m_train["_diagram_ids"].remove(diagram_id)
            if hasattr(project, "remove_subsequent_link"):
                for sub in old_d_train.get("subsequent_trains", []):
                    project.remove_subsequent_link(route_id, direction, train_id, sub)
            ev = RemoveTrainDiagramEvent(route_id, direction, train_id, diagram_id, old_idx, old_d_train)
            events_to_push.append(ev)

    if history_manager and events_to_push:
        history_manager.push_events(events_to_push)

    return True


class OperationCandidatePicker(QDialog):
    """
    始発駅を終着駅とし、始発時刻以前に到着する列車の候補リストを表示するポップアップダイアログ
    """
    def __init__(self, parent, candidate_items: list):
        super().__init__(parent, Qt.Popup)
        self.selected_operations = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self.list_widget = QListWidget(self)
        self.list_widget.setStyleSheet("border: 1px solid #dddddd;")
        self.list_widget.setItemDelegate(HtmlDelegate(self))

        for display_html, op_list in candidate_items:
            item = QListWidgetItem(display_html)
            item.setData(Qt.UserRole, op_list)
            self.list_widget.addItem(item)

        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)

        item_height = 28
        total_h = min(280, max(60, len(candidate_items) * item_height + 12))
        self.resize(260, total_h)

    def _on_item_clicked(self, item):
        self.selected_operations = item.data(Qt.UserRole)
        self.accept()


class OperationPickerDialog(QDialog):
    """
    ダイヤグラム用の担当運用選択ダイアログ（モーダルウィンドウ形式）
    """
    def __init__(self, parent, project: OptDiaProject, diagram_id: str, route_id: str, direction: str, train_id: str):
        super().__init__(parent)
        self.setWindowModality(Qt.WindowModal)
        self.main_win = parent.window() if hasattr(parent, "window") else None
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
        self.setFixedSize(360, 480)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(4)

        # ラベル
        label = QLabel("列車の担当運用(編成の前位側から)")
        layout.addWidget(label)

        # リストウィジェット
        self.list_widget = DragDropListWidget(self)
        layout.addWidget(self.list_widget)

        # 「候補から運用を選択」ボタン
        self.candidate_btn = QPushButton("候補から運用を選択")
        self.candidate_btn.clicked.connect(self._on_candidate_clicked)
        layout.addWidget(self.candidate_btn)

        # 「担当運用の追加」ボタン
        self.add_btn = QPushButton("担当運用の追加")
        self.add_btn.clicked.connect(self._on_add_clicked)
        layout.addWidget(self.add_btn)

        # 「運用の追加・編集」ボタン
        self.edit_btn = QPushButton("運用の追加・編集")
        self.edit_btn.setProperty("class", "text_button")
        self.edit_btn.clicked.connect(self._on_edit_clicked)
        layout.addWidget(self.edit_btn)

        layout.addSpacing(10)

        # 最下部: 「OK」「キャンセル」ボタン
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_ok = QPushButton("OK")
        self.btn_cancel = QPushButton("キャンセル")
        self.btn_ok.clicked.connect(self._on_ok_clicked)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok.setProperty("class", "ok_button")
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

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

    def delete_item_widget(self, widget):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if self.list_widget.itemWidget(item) == widget:
                self.list_widget.takeItem(i)
                break
        self.rebuild_item_widgets()

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

    def _save_widget_states_to_items(self):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            if widget:
                item.setData(Qt.UserRole, widget.operation_id)
                item.setData(Qt.UserRole + 1, widget.formation_is_reversed)

    def sync_operations_to_project(self):
        """
        DragDropListWidget内部でのドロップ時や、内部同期用。
        ダイアログ編集中はプロジェクトへ直接書き込まずアイテム状態の同期のみ行う。
        """
        self._save_widget_states_to_items()

    def _on_ok_clicked(self):
        if not self.d_train:
            self.accept()
            return

        self._save_widget_states_to_items()

        old_ops = copy.deepcopy(self.d_train.get("operations", []))

        ops = []
        has_valid = False
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            if widget:
                op_id = widget.operation_id
                is_rev = widget.formation_is_reversed
            else:
                op_id = item.data(Qt.UserRole)
                is_rev = item.data(Qt.UserRole + 1) or False

            # 有効な運用IDのみを保持（未選択の項目は除外）
            if op_id:
                ops.append({
                    "operation_id": op_id,
                    "formation_is_reversed": is_rev
                })
                has_valid = True

        self.d_train["operations"] = ops
        if has_valid:
            self.d_train["to_be_saved"] = True

        main_win = self.main_win or (self.parent().window() if self.parent() else None)
        if old_ops != ops:
            history_manager = getattr(main_win, "history_manager", None)
            if history_manager:
                ev = ChangeTrainOperationEvent(self.route_id, self.direction, self.train_id, self.diagram_id, old_ops, ops)
                history_manager.push_events([ev])

            if hasattr(self.project, "update_operation_train_lookup"):
                self.project.update_operation_train_lookup(
                    self.diagram_id, self.route_id, self.direction, self.train_id,
                    old_ops, ops
                )

        # メインウィンドウに変更を通知・再描画
        if hasattr(main_win, "set_modified"):
            main_win.set_modified(True)
        if hasattr(main_win, "_update_diagram_view"):
            main_win._update_diagram_view()
        if hasattr(main_win, "timetable_model") and main_win.timetable_model:
            main_win.timetable_model.update_data(
                main_win.timetable_model.route_id,
                main_win.timetable_model.diagram_id,
                main_win.timetable_model.direction
            )

        self.accept()

    def _get_current_train_first_stop_info(self):
        """現在の列車の始発駅(station_id)と始発時刻(秒)を取得する"""
        route = self.project.routes.get(self.route_id, {})
        train_key = "inbound_trains" if self.direction == "inbound" else "outbound_trains"
        m_train = route.get(train_key, {}).get(self.train_id, {})
        stops = m_train.get("stops", [])

        first_stop = None
        for s in stops:
            dep = s.get("departure_time")
            arr = s.get("arrival_time")
            if dep is not None or arr is not None:
                first_stop = s
                break

        if not first_stop:
            return None, None

        seid = first_stop.get("station_entry_id")
        sid = getattr(self.project, "station_entry_to_station_id", {}).get(seid, first_stop.get("station_id"))
        dep_time_str = first_stop.get("departure_time") or first_stop.get("arrival_time")
        dep_sec = _time_to_seconds(dep_time_str)
        return sid, dep_sec

    def _get_train_terminal_stop_info(self, m_train):
        """指定された列車の終着駅(station_id)と終着時刻(秒)を取得する"""
        stops = m_train.get("stops", [])
        last_stop = None
        for s in reversed(stops):
            dep = s.get("departure_time")
            arr = s.get("arrival_time")
            if dep is not None or arr is not None:
                last_stop = s
                break

        if not last_stop:
            return None, None

        seid = last_stop.get("station_entry_id")
        sid = getattr(self.project, "station_entry_to_station_id", {}).get(seid, last_stop.get("station_id"))
        arr_time_str = last_stop.get("arrival_time") or last_stop.get("departure_time")
        arr_sec = _time_to_seconds(arr_time_str)
        return sid, arr_sec

    def _find_candidate_trains(self):
        """
        右クリックされた列車の始発駅を終着駅とする列車のリスト
        (上りか下りかを区別せず、右クリックされた列車の始発時刻以前に到着するものを、到着時刻の遅い順に10件)
        """
        target_station_id, target_dep_sec = self._get_current_train_first_stop_info()
        if not target_station_id or target_dep_sec is None:
            return []

        candidates = []
        diagram = self.project.diagrams.get(self.diagram_id, {})
        operations_map = diagram.get("operations", {})

        for r_id, route in self.project.routes.items():
            tbd = route.get("trains_by_diagram", {}).get(self.diagram_id, {})
            for dir_key in ["inbound_trains", "outbound_trains"]:
                m_trains = route.get(dir_key, {})
                d_trains = tbd.get(dir_key, {})

                for tid, d_train in d_trains.items():
                    if not d_train.get("to_be_saved"):
                        continue
                    m_train = m_trains.get(tid)
                    if not m_train:
                        continue

                    # 自身は除外
                    if r_id == self.route_id and dir_key == ("inbound_trains" if self.direction == "inbound" else "outbound_trains") and tid == self.train_id:
                        continue

                    term_sid, term_arr_sec = self._get_train_terminal_stop_info(m_train)
                    if term_sid == target_station_id and term_arr_sec is not None:
                        if term_arr_sec <= target_dep_sec:
                            # 担当運用が存在するか確認
                            ops = d_train.get("operations", [])
                            # 有効な運用IDを持つもののみ
                            valid_ops = [op for op in ops if op.get("operation_id")]
                            if not valid_ops:
                                continue

                            candidates.append({
                                "route_id": r_id,
                                "train_id": tid,
                                "m_train": m_train,
                                "d_train": d_train,
                                "arr_sec": term_arr_sec,
                                "valid_ops": valid_ops
                            })

        # 到着時刻の遅い順にソート (降順)
        candidates.sort(key=lambda c: c["arr_sec"], reverse=True)
        top10 = candidates[:10]

        # リスト項目のHTMLおよび運用リストを作成
        items = []
        for cand in top10:
            m_train = cand["m_train"]
            num = m_train.get("train_number") or "(列車番号なし)"
            tt_id = m_train.get("train_type_id")
            tt = self.project.train_types.get(tt_id) if tt_id else None
            tt_color = tt.get("main_color", "#333333") if tt else "#333333"

            op_numbers = []
            for op in cand["valid_ops"]:
                op_id = op.get("operation_id")
                op_obj = operations_map.get(op_id, {})
                op_num = op_obj.get("operation_number") or str(op_id)
                op_numbers.append(op_num)

            joined_op_numbers = "+".join(op_numbers)
            display_html = f"<b><font color='{tt_color}'>{num}</font></b> ({joined_op_numbers})"
            items.append((display_html, cand["valid_ops"]))

        return items

    def _on_candidate_clicked(self):
        candidate_items = self._find_candidate_trains()
        if not candidate_items:
            QMessageBox.information(self, "候補がありません", "選択可能な運用の候補が見つかりませんでした。")
            return

        picker = OperationCandidatePicker(self, candidate_items)
        btn_pos = self.candidate_btn.mapToGlobal(self.candidate_btn.rect().bottomLeft())
        picker.move(btn_pos)
        if picker.exec() and picker.selected_operations:
            selected_ops = picker.selected_operations

            # 既に運用が1つ以上設定されているかチェック
            existing_valid_ops = False
            for i in range(self.list_widget.count()):
                item = self.list_widget.item(i)
                widget = self.list_widget.itemWidget(item)
                if widget and widget.operation_id:
                    existing_valid_ops = True
                    break
                elif item.data(Qt.UserRole):
                    existing_valid_ops = True
                    break

            if existing_valid_ops:
                res = QMessageBox.question(
                    self,
                    "上書きの確認",
                    "既に設定されている内容を上書きしますか？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if res != QMessageBox.Yes:
                    return

            # 上書き設定
            self.list_widget.clear()
            for op in selected_ops:
                op_id = op.get("operation_id")
                is_rev = op.get("formation_is_reversed", False)
                self.add_item(op_id, is_rev)

    def _on_edit_clicked(self):
        dialog = VehicleOperationEditorDialog(self.parent(), self.project, self.diagram_id)
        dialog.exec()
