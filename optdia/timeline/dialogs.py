import random
import string
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QSpinBox, QCheckBox, QPlainTextEdit, QPushButton,
    QComboBox, QRadioButton, QGroupBox, QMessageBox,
    QListWidget, QListWidgetItem, QFrame, QScrollArea, QWidget
)
from common.gui_utils import HtmlDelegate



class RolloverMinuteSpinBox(QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(-1, 60)

    def textFromValue(self, val: int) -> str:
        if val < 0:
            val = 59
        elif val > 59:
            val = 0
        return f"{val:02d}"


class TemporaryStablingDialog(QDialog):
    """一時入庫の設定ダイアログ"""

    def __init__(self, parent=None, event_data: dict = None, default_start_time: str = None, default_end_time: str = None):
        super().__init__(parent)
        self.setWindowTitle("一時入庫の設定")
        self.resize(400, 400)

        self.event_data = event_data

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # 1. 入庫場所名:
        lbl_location = QLabel("入庫場所名:")
        layout.addWidget(lbl_location)
        self.txt_location = QLineEdit()
        layout.addWidget(self.txt_location)

        # 2. 入庫時刻:
        lbl_start_time = QLabel("入庫時刻:")
        layout.addWidget(lbl_start_time)
        start_layout = QHBoxLayout()
        self.spin_start_hour = QSpinBox()
        self.spin_start_hour.setRange(0, 99)
        self.spin_start_min = RolloverMinuteSpinBox()

        lbl_start_h = QLabel("時")
        lbl_start_m = QLabel("分")
        start_layout.addWidget(self.spin_start_hour)
        start_layout.addWidget(lbl_start_h)
        start_layout.addWidget(self.spin_start_min)
        start_layout.addWidget(lbl_start_m)
        start_layout.addStretch()
        layout.addLayout(start_layout)

        # 3. 出庫時刻:
        lbl_end_time = QLabel("出庫時刻:")
        layout.addWidget(lbl_end_time)
        end_layout = QHBoxLayout()
        self.spin_end_hour = QSpinBox()
        self.spin_end_hour.setRange(0, 99)
        self.spin_end_min = RolloverMinuteSpinBox()

        lbl_end_h = QLabel("時")
        lbl_end_m = QLabel("分")
        end_layout.addWidget(self.spin_end_hour)
        end_layout.addWidget(lbl_end_h)
        end_layout.addWidget(self.spin_end_min)
        end_layout.addWidget(lbl_end_m)
        end_layout.addStretch()
        layout.addLayout(end_layout)

        # 4. 編成の差し替えが可能 チェックボックス
        self.chk_formations = QCheckBox("編成の差し替えが可能")
        layout.addWidget(self.chk_formations)

        # 5. 備考:
        lbl_note = QLabel("備考:")
        layout.addWidget(lbl_note)
        self.txt_note = QPlainTextEdit()
        layout.addWidget(self.txt_note)

        layout.addStretch()

        # 6. OK / キャンセル ボタン
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_ok = QPushButton("OK")
        self.btn_cancel = QPushButton("キャンセル")
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

        # シグナル設定
        self.spin_start_min.valueChanged.connect(
            lambda v: self._on_minute_changed(self.spin_start_min, self.spin_start_hour, v)
        )
        self.spin_end_min.valueChanged.connect(
            lambda v: self._on_minute_changed(self.spin_end_min, self.spin_end_hour, v)
        )
        self.btn_ok.clicked.connect(self._on_accept)
        self.btn_cancel.clicked.connect(self.reject)

        # 初期値のセット
        self._init_values(event_data, default_start_time, default_end_time)

    def _on_accept(self):
        self._set_modified()
        self.accept()

    def _set_modified(self):
        parent = self.parent()
        if parent:
            main_win = parent.window() if hasattr(parent, "window") else parent
            if hasattr(main_win, "set_modified"):
                main_win.set_modified(True)

    def _on_minute_changed(self, min_spin: QSpinBox, hour_spin: QSpinBox, val: int):
        if val == 60:
            min_spin.blockSignals(True)
            min_spin.setValue(0)
            min_spin.blockSignals(False)
            hour_spin.setValue(hour_spin.value() + 1)
        elif val == -1:
            min_spin.blockSignals(True)
            min_spin.setValue(59)
            min_spin.blockSignals(False)
            if hour_spin.value() > 0:
                hour_spin.setValue(hour_spin.value() - 1)

    def _parse_time(self, time_str: str):
        if not time_str:
            return 0, 0
        try:
            parts = time_str.split(":")
            return int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            return 0, 0

    def _init_values(self, event_data: dict, default_start_time: str, default_end_time: str):
        if event_data:
            self.txt_location.setText(event_data.get("stabled_location", ""))
            sh, sm = self._parse_time(event_data.get("start_time"))
            eh, em = self._parse_time(event_data.get("end_time"))
            self.chk_formations.setChecked(event_data.get("formations_can_changed", False))
            self.txt_note.setPlainText(event_data.get("note", ""))
        else:
            self.txt_location.setText("")
            sh, sm = self._parse_time(default_start_time)
            eh, em = self._parse_time(default_end_time)
            self.chk_formations.setChecked(False)
            self.txt_note.setPlainText("")

        self.spin_start_hour.setValue(sh)
        self.spin_start_min.blockSignals(True)
        self.spin_start_min.setValue(sm)
        self.spin_start_min.blockSignals(False)

        self.spin_end_hour.setValue(eh)
        self.spin_end_min.blockSignals(True)
        self.spin_end_min.setValue(em)
        self.spin_end_min.blockSignals(False)

    def get_data(self) -> dict:
        sh = self.spin_start_hour.value()
        sm = self.spin_start_min.value()
        if sm < 0: sm = 59
        elif sm > 59: sm = 0

        eh = self.spin_end_hour.value()
        em = self.spin_end_min.value()
        if em < 0: em = 59
        elif em > 59: em = 0

        return {
            "stabled_location": self.txt_location.text(),
            "start_time": f"{sh:02d}:{sm:02d}:00",
            "end_time": f"{eh:02d}:{em:02d}:00",
            "formations_can_changed": self.chk_formations.isChecked(),
            "note": self.txt_note.toPlainText()
        }


class AddDeadheadDialog(QDialog):
    """回送の追加ダイアログ"""

    def __init__(self, parent=None, project=None, diagram_id: str = None, operation_id: str = None, default_start_m: float = 0, default_end_m: float = 0, history_manager=None):
        super().__init__(parent)
        self.setWindowTitle("回送の追加")
        self.resize(400, 500)

        self.project = project
        self.diagram_id = diagram_id
        self.operation_id = operation_id
        self.history_manager = history_manager

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)


        # 1. 列車番号:
        lbl_train_num = QLabel("列車番号:")
        layout.addWidget(lbl_train_num)
        self.txt_train_number = QLineEdit()
        layout.addWidget(self.txt_train_number)

        # 2. 種別:
        lbl_train_type = QLabel("種別:")
        layout.addWidget(lbl_train_type)
        self.combo_train_type = QComboBox()
        layout.addWidget(self.combo_train_type)

        # 3. 登録先運行系統:
        lbl_route = QLabel("登録先運行系統:")
        layout.addWidget(lbl_route)
        self.combo_route = QComboBox()
        layout.addWidget(self.combo_route)

        # 4. 方面 (上り / 下り) ラジオボタン
        dir_layout = QHBoxLayout()
        self.radio_outbound = QRadioButton("下り")
        self.radio_inbound = QRadioButton("上り")
        self.radio_outbound.setChecked(True)
        dir_layout.addWidget(self.radio_outbound)
        dir_layout.addWidget(self.radio_inbound)
        dir_layout.addStretch()
        layout.addLayout(dir_layout)

        # 5. 「始発」グループボックス
        grp_start = QGroupBox("始発")
        grp_start_layout = QVBoxLayout(grp_start)
        grp_start_layout.setSpacing(8)

        # 1行目: 駅: + コンボボックス
        start_row1 = QHBoxLayout()
        lbl_start_st = QLabel("駅:")
        self.combo_start_station = QComboBox()
        start_row1.addWidget(lbl_start_st)
        start_row1.addWidget(self.combo_start_station, stretch=1)
        grp_start_layout.addLayout(start_row1)

        # 2行目: 時刻: + 時スピンボックス + 時 + 分スピンボックス + 分
        start_row2 = QHBoxLayout()
        lbl_start_time = QLabel("時刻:")
        self.spin_start_hour = QSpinBox()
        self.spin_start_hour.setRange(0, 99)
        self.spin_start_min = RolloverMinuteSpinBox()
        lbl_start_h = QLabel("時")
        lbl_start_m = QLabel("分")
        start_row2.addWidget(lbl_start_time)
        start_row2.addWidget(self.spin_start_hour)
        start_row2.addWidget(lbl_start_h)
        start_row2.addWidget(self.spin_start_min)
        start_row2.addWidget(lbl_start_m)
        start_row2.addStretch()
        grp_start_layout.addLayout(start_row2)

        layout.addWidget(grp_start)

        # 6. 「終着」グループボックス
        grp_end = QGroupBox("終着")
        grp_end_layout = QVBoxLayout(grp_end)
        grp_end_layout.setSpacing(8)

        # 1行目: 駅: + コンボボックス
        end_row1 = QHBoxLayout()
        lbl_end_st = QLabel("駅:")
        self.combo_end_station = QComboBox()
        end_row1.addWidget(lbl_end_st)
        end_row1.addWidget(self.combo_end_station, stretch=1)
        grp_end_layout.addLayout(end_row1)

        # 2行目: 時刻: + 時スピンボックス + 時 + 分スピンボックス + 分
        end_row2 = QHBoxLayout()
        lbl_end_time = QLabel("時刻:")
        self.spin_end_hour = QSpinBox()
        self.spin_end_hour.setRange(0, 99)
        self.spin_end_min = RolloverMinuteSpinBox()
        lbl_end_h = QLabel("時")
        lbl_end_m = QLabel("分")
        end_row2.addWidget(lbl_end_time)
        end_row2.addWidget(self.spin_end_hour)
        end_row2.addWidget(lbl_end_h)
        end_row2.addWidget(self.spin_end_min)
        end_row2.addWidget(lbl_end_m)
        end_row2.addStretch()
        grp_end_layout.addLayout(end_row2)

        layout.addWidget(grp_end)

        # 7. 方反 チェックボックス
        self.chk_reversed = QCheckBox("方反")
        layout.addWidget(self.chk_reversed)

        layout.addStretch()

        # 8. OK / キャンセル ボタン
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_ok = QPushButton("OK")
        self.btn_cancel = QPushButton("キャンセル")
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

        # シグナル設定
        self.spin_start_min.valueChanged.connect(
            lambda v: self._on_minute_changed(self.spin_start_min, self.spin_start_hour, v)
        )
        self.spin_end_min.valueChanged.connect(
            lambda v: self._on_minute_changed(self.spin_end_min, self.spin_end_hour, v)
        )
        self.combo_route.currentIndexChanged.connect(self._on_route_or_dir_changed)
        self.radio_outbound.toggled.connect(self._on_route_or_dir_changed)
        self.radio_inbound.toggled.connect(self._on_route_or_dir_changed)
        self.btn_ok.clicked.connect(self._on_ok_clicked)

        self.btn_cancel.clicked.connect(self.reject)
        self._init_data(default_start_m, default_end_m)

    def _on_minute_changed(self, min_spin: QSpinBox, hour_spin: QSpinBox, val: int):
        if val == 60:
            min_spin.blockSignals(True)
            min_spin.setValue(0)
            min_spin.blockSignals(False)
            hour_spin.setValue(hour_spin.value() + 1)
        elif val == -1:
            min_spin.blockSignals(True)
            min_spin.setValue(59)
            min_spin.blockSignals(False)
            if hour_spin.value() > 0:
                hour_spin.setValue(hour_spin.value() - 1)

    def _init_data(self, default_start_m: float, default_end_m: float):
        if not self.project:
            return

        # 種別コンボボックスの設定
        self.combo_train_type.blockSignals(True)
        self.combo_train_type.clear()
        deadhead_idx = -1
        for i, ttid in enumerate(self.project.train_types_order):
            tt = self.project.train_types.get(ttid, {})
            name = tt.get("train_type_name", ttid)
            self.combo_train_type.addItem(name, ttid)
            if name == "回送":
                deadhead_idx = i
        if deadhead_idx != -1:
            self.combo_train_type.setCurrentIndex(deadhead_idx)
        elif self.combo_train_type.count() > 0:
            self.combo_train_type.setCurrentIndex(0)
        self.combo_train_type.blockSignals(False)

        # 運行系統コンボボックスの設定
        self.combo_route.blockSignals(True)
        self.combo_route.clear()
        for rid in self.project.routes_order:
            r = self.project.routes.get(rid, {})
            name = r.get("route_name", rid)
            self.combo_route.addItem(name, rid)
        if self.combo_route.count() > 0:
            self.combo_route.setCurrentIndex(0)
        self.combo_route.blockSignals(False)

        # 時刻スピンボックスの初期値設定
        sh = int(default_start_m // 60)
        sm = int(default_start_m % 60)
        self.spin_start_hour.setValue(sh)
        self.spin_start_min.blockSignals(True)
        self.spin_start_min.setValue(sm)
        self.spin_start_min.blockSignals(False)

        eh = int(default_end_m // 60) if default_end_m else sh
        em = int(default_end_m % 60) if default_end_m else sm
        self.spin_end_hour.setValue(eh)
        self.spin_end_min.blockSignals(True)
        self.spin_end_min.setValue(em)
        self.spin_end_min.blockSignals(False)

        self._on_route_or_dir_changed()

    def _on_route_or_dir_changed(self):
        route_id = self.combo_route.currentData()
        direction = "inbound" if self.radio_inbound.isChecked() else "outbound"

        self.combo_start_station.blockSignals(True)
        self.combo_end_station.blockSignals(True)
        self.combo_start_station.clear()
        self.combo_end_station.clear()

        stations_seq = self._get_stations_for_route_direction(route_id, direction)
        for st_info in stations_seq:
            self.combo_start_station.addItem(st_info["display_name"], st_info)
            self.combo_end_station.addItem(st_info["display_name"], st_info)

        if self.combo_start_station.count() > 0:
            self.combo_start_station.setCurrentIndex(0)
        if self.combo_end_station.count() > 0:
            self.combo_end_station.setCurrentIndex(self.combo_end_station.count() - 1)

        self.combo_start_station.blockSignals(False)
        self.combo_end_station.blockSignals(False)

    def _get_stations_for_route_direction(self, route_id: str, direction: str) -> list:
        if not self.project or not route_id or route_id not in self.project.routes:
            return []
        route = self.project.routes[route_id]
        segments = route.get("line_segments", [])
        work_segments = []
        if direction == "inbound":
            for seg in reversed(segments):
                work_segments.append({
                    "segment_id": seg["segment_id"],
                    "line_id": seg["line_id"],
                    "start_station": seg["end_station"],
                    "end_station": seg["start_station"]
                })
        else:
            work_segments = segments

        stations_seq = []
        seq_idx = 0
        for seg in work_segments:
            segment_id = seg["segment_id"]
            line_id = seg["line_id"]
            line_data = self.project.lines.get(line_id, {})
            line_name = line_data.get("line_name", line_id)
            station_list = line_data.get("station_list", [])
            line_station_ids = [s["station_id"] for s in station_list]
            try:
                idx_start = line_station_ids.index(seg["start_station"])
                idx_end = line_station_ids.index(seg["end_station"])
            except ValueError:
                continue

            seg_line_direction = "outbound" if idx_start <= idx_end else "inbound"

            if idx_start <= idx_end:
                s_ids = line_station_ids[idx_start:idx_end + 1]
            else:
                s_ids = [line_station_ids[i] for i in range(idx_start, idx_end - 1, -1)]


            for sid in s_ids:
                s_data = self.project.stations.get(sid, {})
                st_name = s_data.get("station_name", sid)
                ls_item = next((s for s in station_list if s["station_id"] == sid), {})
                track_id = ls_item.get("inbound_main_track" if seg_line_direction == "inbound" else "outbound_main_track")
                display_name = f"{st_name}({line_name})"
                stations_seq.append({
                    "station_id": sid,
                    "station_name": st_name,
                    "line_name": line_name,
                    "segment_id": segment_id,
                    "track_id": track_id,
                    "seq_idx": seq_idx,
                    "display_name": display_name
                })
                seq_idx += 1
        return stations_seq

    def _on_ok_clicked(self):
        start_item = self.combo_start_station.currentData()
        end_item = self.combo_end_station.currentData()
        if not start_item or not end_item:
            return

        direction_str = "上り" if self.radio_inbound.isChecked() else "下り"
        if start_item["seq_idx"] >= end_item["seq_idx"]:
            QMessageBox.warning(self, "エラー", f"始発駅と終着駅の位置関係が{direction_str}の並び順に一致しません")
            return

        route_id = self.combo_route.currentData()
        if not route_id or route_id not in self.project.routes:
            return

        # 時刻の取得
        sh = self.spin_start_hour.value()
        sm = self.spin_start_min.value()
        if sm < 0: sm = 59
        elif sm > 59: sm = 0
        start_time_str = f"{sh:02d}:{sm:02d}:00"

        eh = self.spin_end_hour.value()
        em = self.spin_end_min.value()
        if em < 0: em = 59
        elif em > 59: em = 0
        end_time_str = f"{eh:02d}:{em:02d}:00"

        if start_time_str > end_time_str:
            QMessageBox.warning(self, "エラー", f"始発時刻と終着時刻が矛盾しています")
            return

        direction_key = "inbound" if self.radio_inbound.isChecked() else "outbound"
        train_key = "inbound_trains" if direction_key == "inbound" else "outbound_trains"
        order_key = f"{train_key}_order"

        route = self.project.routes[route_id]
        tbd = route.setdefault("trains_by_diagram", {}).setdefault(self.diagram_id, {})
        d_trains = tbd.setdefault(train_key, {})
        m_trains = route.setdefault(train_key, {})
        order = tbd.setdefault(order_key, [])

        # 列車IDの生成 (ランダムな16文字の英数字)
        chars = string.ascii_letters + string.digits
        while True:
            new_train_id = "".join(random.choices(chars, k=16))
            if new_train_id not in d_trains and new_train_id not in m_trains:
                break

        # 停車駅情報の構築
        start_stop = {
            "segment_id": start_item["segment_id"],
            "station_id": start_item["station_id"],
            "track_id": start_item.get("track_id"),
            "arrival_time": None,
            "departure_time": start_time_str,
            "stop_type": 1
        }

        end_st_data = self.project.stations.get(end_item["station_id"], {})
        show_arr = end_st_data.get("show_arrival_time", False)
        end_stop = {
            "segment_id": end_item["segment_id"],
            "station_id": end_item["station_id"],
            "track_id": end_item.get("track_id"),
            "arrival_time": end_time_str,
            "departure_time": None if show_arr else end_time_str,
            "stop_type": 1
        }

        train_type_id = self.combo_train_type.currentData()
        train_number = self.txt_train_number.text()

        # マスタ列車情報
        m_trains[new_train_id] = {
            "train_number": train_number,
            "train_type_id": train_type_id,
            "named_train_number": None,
            "note": "",
            "stops": [start_stop, end_stop],
            "_diagram_ids": [self.diagram_id]
        }

        # ダイヤ別列車情報
        d_trains[new_train_id] = {
            "train_id": new_train_id,
            "operations": [
                {
                    "operation_id": self.operation_id,
                    "formation_is_reversed": self.chk_reversed.isChecked()
                }
            ] if self.operation_id else [],
            "car_count": None,
            "destination": None,
            "subsequent_trains": [],
            "to_be_saved": True
        }

        # 順序リストへの挿入 (to_be_saved が True である最後の列車の直後)
        last_saved_idx = -1
        for i, tid in enumerate(order):
            if d_trains.get(tid, {}).get("to_be_saved") is True:
                last_saved_idx = i

        if last_saved_idx != -1:
            insert_idx = last_saved_idx + 1
        else:
            insert_idx = 0

        order.insert(insert_idx, new_train_id)

        if self.history_manager:
            from core.events import AddTrainEvent
            ev = AddTrainEvent(
                route_id=route_id,
                direction=direction_key,
                train_id=new_train_id,
                diagram_id=self.diagram_id,
                index=insert_idx,
                d_train=d_trains[new_train_id],
                m_train=m_trains[new_train_id]
            )
            self.history_manager.push_events([ev])

        self.accept()


class SelectCouplingPositionDialog(QDialog):
    """連結位置の選択ダイアログ"""

    def __init__(self, parent=None, project=None, diagram_id: str = None, operations_list: list = None):
        super().__init__(parent)
        self.setWindowTitle("連結位置の選択")
        self.setFixedSize(200, 400)
        self.project = project
        self.diagram_id = diagram_id
        self.operations_list = operations_list or []
        self.selected_index = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(5)

        # スクロールエリア
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        # 1. 説明ラベル
        lbl_info = QLabel("追加する運用が連結される位置を選択してください")
        lbl_info.setWordWrap(True)
        layout.addWidget(lbl_info)

        # 2. 前位側ラベル
        lbl_forward = QLabel("▲ 編成の前位側")
        lbl_forward.setStyleSheet("font-weight: bold; color: #555555;")
        layout.addWidget(lbl_forward)

        # 3. 先頭「ここに追加」ボタン
        btn_top = QPushButton("ここに追加")
        btn_top.clicked.connect(lambda: self._select_position(0))
        layout.addWidget(btn_top)

        # 4. 各運用の情報ラベルと「ここに追加」ボタン
        diagram = self.project.diagrams.get(self.diagram_id, {}) if self.project and self.diagram_id else {}
        operations_dict = diagram.get("operations", {})

        for idx, op_entry in enumerate(self.operations_list):
            op_id = op_entry.get("operation_id") if isinstance(op_entry, dict) else op_entry
            op_data = operations_dict.get(op_id, {})
            op_num = op_data.get("operation_number", op_id)
            car_count = op_data.get("car_count")
            car_count_str = f"{car_count}両" if car_count is not None else "?両"

            lbl_op = QLabel(f"{op_num} ({car_count_str})")
            lbl_op.setAlignment(Qt.AlignCenter)
            layout.addWidget(lbl_op)

            btn_insert = QPushButton("ここに追加")
            btn_insert.clicked.connect(lambda checked=False, target_idx=idx + 1: self._select_position(target_idx))
            layout.addWidget(btn_insert)

        layout.addStretch()
        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area)

    def _select_position(self, index: int):
        self.selected_index = index
        self.accept()

    def get_selected_index(self) -> int:
        return self.selected_index


class AddTrainToOperationDialog(QDialog):
    """列車の登録ダイアログ"""

    def __init__(self, parent=None, project=None, diagram_id: str = None, target_op_id: str = None,
                 start_m: float = 0.0, prev_last_station_id: str = None, history_manager=None):
        super().__init__(parent)
        self.setWindowTitle("列車の登録")
        self.setFixedSize(300, 400)

        self.project = project
        self.diagram_id = diagram_id
        self.target_op_id = target_op_id
        self.start_m = start_m
        self.prev_last_station_id = prev_last_station_id
        self.history_manager = history_manager

        # 垂直レイアウト
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)


        # 1. 列車番号で絞り込み 1行テキストボックス
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("列車番号で絞り込み")
        layout.addWidget(self.txt_search)

        # 2. 列車を選択するためのリストボックス
        self.list_trains = QListWidget()
        self.list_trains.setItemDelegate(HtmlDelegate(self.list_trains))
        layout.addWidget(self.list_trains)

        # 3. 既に運用を割り当て済みの列車も表示する チェックボックス
        self.chk_show_assigned = QCheckBox("既に運用を割り当て済みの列車も表示する")
        layout.addWidget(self.chk_show_assigned)

        # 4. 区切りの水平線
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        # 5. 方反 チェックボックス
        self.chk_reversed = QCheckBox("方反")
        layout.addWidget(self.chk_reversed)

        # 6. OK / キャンセル ボタン
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_ok = QPushButton("OK")
        self.btn_cancel = QPushButton("キャンセル")
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

        # シグナル接続
        self.txt_search.textChanged.connect(self._refresh_train_list)
        self.chk_show_assigned.toggled.connect(self._refresh_train_list)
        self.list_trains.itemDoubleClicked.connect(lambda item: self._on_ok_clicked())
        self.btn_ok.clicked.connect(self._on_ok_clicked)
        self.btn_cancel.clicked.connect(self.reject)

        # 初回リスト構築
        self._refresh_train_list()

    def _time_to_minutes(self, time_str: str):
        if not time_str:
            return None
        try:
            parts = time_str.split(":")
            return int(parts[0]) * 60 + int(parts[1])
        except (ValueError, IndexError):
            return None

    def _format_time_hhmm(self, time_str: str) -> str:
        if not time_str:
            return "--:--"
        try:
            parts = time_str.split(":")
            h, m = int(parts[0]), int(parts[1])
            return f"{h:02d}:{m:02d}"
        except (ValueError, IndexError):
            return time_str[:5] if len(time_str) >= 5 else time_str

    def _get_station_initial(self, station_id: str) -> str:
        if not station_id or not self.project:
            return ""
        st = self.project.stations.get(station_id, {})
        st_initial = st.get("station_initial")
        if st_initial:
            return str(st_initial)
        st_name = st.get("station_name", "")
        return st_name[0] if st_name else ""

    def _collect_candidate_trains(self) -> list:
        if not self.project or not self.diagram_id:
            return []

        search_query = self.txt_search.text().strip()
        show_assigned = self.chk_show_assigned.isChecked()

        candidates = []

        for route_id in self.project.routes_order:
            route = self.project.routes.get(route_id, {})
            tbd = route.get("trains_by_diagram", {}).get(self.diagram_id, {})
            for direction in ["inbound_trains", "outbound_trains"]:
                m_trains = route.get(direction, {})
                d_trains = tbd.get(direction, {})
                order = tbd.get(f"{direction}_order", list(d_trains.keys()))

                for train_id in order:
                    d_train = d_trains.get(train_id)
                    m_train = m_trains.get(train_id)
                    if not d_train or not m_train:
                        continue

                    # 保存対象でない場合は除外
                    if d_train.get("to_be_saved") is False:
                        continue

                    ops = d_train.get("operations", [])
                    op_ids = [op.get("operation_id") if isinstance(op, dict) else op for op in ops]

                    # 1. 自身の運用が含まれているものは常に除外
                    if self.target_op_id in op_ids:
                        continue

                    # 2. 既に運用が割り当てられており、show_assigned が False の場合は除外
                    if not show_assigned and len(ops) > 0:
                        continue

                    # 3. 列車番号で絞り込み（テキストで始まるもののみ）
                    train_number = m_train.get("train_number", "")
                    if search_query and not train_number.startswith(search_query):
                        continue

                    stops = m_train.get("stops", [])
                    if not stops:
                        continue

                    # 始発時刻と終着時刻の計算
                    valid_times = []
                    for s in stops:
                        arr = self._time_to_minutes(s.get("arrival_time"))
                        dep = self._time_to_minutes(s.get("departure_time"))
                        if arr is not None:
                            valid_times.append(arr)
                        if dep is not None:
                            valid_times.append(dep)

                    if not valid_times:
                        continue

                    first_dep = min(valid_times)
                    last_arr = max(valid_times)

                    # 透明な矩形の開始時刻以降の列車
                    if first_dep < self.start_m:
                        continue

                    first_stop = stops[0]
                    last_stop = stops[-1]

                    first_station_id = first_stop.get("station_id")
                    last_station_id = last_stop.get("station_id")

                    first_time_str = first_stop.get("departure_time") or first_stop.get("arrival_time") or ""
                    last_time_str = last_stop.get("arrival_time") or last_stop.get("departure_time") or ""

                    first_time_hhmm = self._format_time_hhmm(first_time_str)
                    last_time_hhmm = self._format_time_hhmm(last_time_hhmm_raw := last_time_str)

                    candidates.append({
                        "route_id": route_id,
                        "direction": direction,
                        "train_id": train_id,
                        "m_train": m_train,
                        "d_train": d_train,
                        "train_number": train_number,
                        "train_type_id": m_train.get("train_type_id"),
                        "first_station_id": first_station_id,
                        "last_station_id": last_station_id,
                        "first_dep": first_dep,
                        "last_arr": last_arr,
                        "first_time_hhmm": first_time_hhmm,
                        "last_time_hhmm": last_time_hhmm,
                        "operations": ops
                    })

        # ソート基準:
        # (1) 直前列車の終着駅を始発駅とする列車を優先 (0: 一致, 1: 不一致/直前なし)
        # (2) 始発時刻が早い列車を優先
        def sort_key(c):
            if self.prev_last_station_id is not None and c["first_station_id"] == self.prev_last_station_id:
                station_priority = 0
            else:
                station_priority = 1
            return (station_priority, c["first_dep"])

        candidates.sort(key=sort_key)
        return candidates[:50]

    def _refresh_train_list(self):
        self.list_trains.clear()
        candidates = self._collect_candidate_trains()

        for c in candidates:
            tt_id = c["train_type_id"]
            tt = self.project.train_types.get(tt_id) if tt_id and self.project else None
            main_color = tt.get("main_color", "#333333") if tt else "#333333"

            start_initial = self._get_station_initial(c["first_station_id"])
            end_initial = self._get_station_initial(c["last_station_id"])

            # 書式: <列車番号> <始発駅の駅名1文字表記><hh:mm形式の始発時刻> - <hh:mm形式の終着時刻><終着駅の駅名1文字表記>
            train_num = c["train_number"]
            start_part = f"{start_initial}{c['first_time_hhmm']}"
            end_part = f"{c['last_time_hhmm']}{end_initial}"

            # 列車番号はその列車の種別色、それ以外の部分は灰色で表示
            html_text = f"<span style='color:{main_color}; font-weight:bold;'>{train_num}</span> <span style='color:#888888;'>{start_part} - {end_part}</span>"

            item = QListWidgetItem()
            item.setText(html_text)
            item.setData(Qt.UserRole, c)
            self.list_trains.addItem(item)

        if self.list_trains.count() > 0:
            self.list_trains.setCurrentRow(0)

    def _on_ok_clicked(self):
        current_item = self.list_trains.currentItem()
        if not current_item:
            return

        c = current_item.data(Qt.UserRole)
        if not c:
            return

        route_id = c["route_id"]
        direction = c["direction"]
        train_id = c["train_id"]

        route = self.project.routes.get(route_id, {})
        tbd = route.get("trains_by_diagram", {}).get(self.diagram_id, {})
        d_trains = tbd.get(direction, {})
        d_train = d_trains.get(train_id)

        if not d_train:
            return

        ops = d_train.setdefault("operations", [])

        op_entry = {
            "operation_id": self.target_op_id,
            "formation_is_reversed": self.chk_reversed.isChecked()
        }

        direction_key = "inbound" if direction == "inbound_trains" else "outbound"

        if len(ops) > 0:
            dialog = SelectCouplingPositionDialog(
                self,
                project=self.project,
                diagram_id=self.diagram_id,
                operations_list=ops
            )
            if dialog.exec() == QDialog.Accepted:
                insert_idx = dialog.get_selected_index()
                if insert_idx is not None:
                    ops.insert(insert_idx, op_entry)
                    d_train["to_be_saved"] = True
                    if self.history_manager:
                        from core.events import AddTrainOperationEvent
                        ev = AddTrainOperationEvent(
                            route_id=route_id,
                            direction=direction_key,
                            train_id=train_id,
                            diagram_id=self.diagram_id,
                            index=insert_idx,
                            operation=op_entry
                        )
                        self.history_manager.push_events([ev])
                    self.accept()
        else:
            ops.append(op_entry)
            d_train["to_be_saved"] = True
            if self.history_manager:
                from core.events import AddTrainOperationEvent
                ev = AddTrainOperationEvent(
                    route_id=route_id,
                    direction=direction_key,
                    train_id=train_id,
                    diagram_id=self.diagram_id,
                    index=0,
                    operation=op_entry
                )
                self.history_manager.push_events([ev])
            self.accept()

