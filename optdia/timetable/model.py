import random
import string
import re
import copy
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QTimer, Signal
from PySide6.QtGui import QColor
from core.project import OptDiaProject
from core.history_manager import HistoryManager
from core.events import (
    BaseEvent, AddTrainEvent, ReorderTrainsEvent, ChangeTrainNumberEvent,
    AddTrainDiagramEvent, RemoveTrainDiagramEvent, AddTrainOperationEvent,
    RemoveTrainOperationEvent, ChangeTrainOperationEvent, ChangeTrainCarCountEvent,
    ChangeTrainTypeEvent, ChangeTrainNamedNumberEvent, ChangeTrainDestinationEvent,
    AddTrainStopEvent, RemoveTrainStopEvent, ChangeTrainStopEvent,
    AddSubsequentTrainEvent, RemoveSubsequentTrainEvent, ChangeSubsequentTrainEvent,
    ChangeTrainNoteEvent
)

TrackIdRole = Qt.UserRole + 100
StopTypeRole = Qt.UserRole + 101


# メインウィンドウの時刻表テーブルに紐付けられるモデル
class TimetableModel(QAbstractTableModel):
    trainsReordered = Signal()

    def __init__(self, project: OptDiaProject, history_manager: Optional[HistoryManager] = None):
        super().__init__()
        self.project = project
        self.history_manager = history_manager
        self.route_id = None
        self.diagram_id = None
        self.direction = "outbound"
        self.row_headers = ["列車番号", "運転日", "運用番号", "両数", "種別・愛称", "号数", "行き先"]
        self.train_ids = []
        self.station_rows = []
        self.full_stop_sequence = []
        self.full_stop_configs = []
        self._stop_lookup = {}  # normalization 高速化用
        self._dest_cache = {}    # 行き先表示高速化用
        self.auto_fill_enabled = False
        self.adjust_later_enabled = False

        if self.history_manager:
            self.history_manager.undone.connect(self._on_history_changed)
            self.history_manager.redone.connect(self._on_history_changed)

    def set_history_manager(self, history_manager: HistoryManager):
        if self.history_manager:
            try:
                self.history_manager.undone.disconnect(self._on_history_changed)
                self.history_manager.redone.disconnect(self._on_history_changed)
            except Exception:
                pass
        self.history_manager = history_manager
        if self.history_manager:
            self.history_manager.undone.connect(self._on_history_changed)
            self.history_manager.redone.connect(self._on_history_changed)

    def _on_history_changed(self, events: list):
        """Undo/Redo 実行時に表示を更新する。変更のあった列以外の表示は更新しない"""
        self.clear_destination_cache()

        # 構造的な変更（列車の追加/削除/並び替え/運転日追加・削除など）があるかチェック
        structural = False
        affected_train_ids = set()
        for ev in events:
            affected_train_ids.add(ev.train_id)
            if isinstance(ev, (AddTrainEvent, ReorderTrainsEvent, AddTrainDiagramEvent, RemoveTrainDiagramEvent)):
                structural = True

        if structural:
            self.update_data(self.route_id, self.diagram_id, self.direction)
        else:
            # マスタ列車の stops 逆引きマップを再構築
            if self.route_id:
                route = self.project.routes.get(self.route_id, {})
                train_key = "inbound_trains" if self.direction == "inbound" else "outbound_trains"
                for tid in affected_train_ids:
                    m_train = route.get(train_key, {}).get(tid)
                    if m_train:
                        self._normalize_train_stops(m_train)

            # 影響を受けた列のみ dataChanged を発行
            for tid in affected_train_ids:
                if tid in self.train_ids:
                    col = self.train_ids.index(tid)
                    self.dataChanged.emit(self.index(0, col), self.index(self.rowCount() - 1, col), [Qt.DisplayRole, Qt.EditRole, Qt.ForegroundRole, Qt.BackgroundRole, StopTypeRole])


    def set_auto_fill_enabled(self, enabled):
        self.auto_fill_enabled = enabled

    def set_adjust_later_enabled(self, enabled):
        self.adjust_later_enabled = enabled

    def _seconds_to_time(self, seconds: int):
        if seconds is None:
            return None
        seconds = max(0, seconds)
        hh = seconds // 3600
        mm = (seconds % 3600) // 60
        ss = seconds % 60
        return f"{hh:02d}:{mm:02d}:{ss:02d}"

    def move_train(self, from_idx, to_idx):
        if from_idx == to_idx:
            return

        tid_to_move = self.train_ids[from_idx]
        item = self.train_ids.pop(from_idx)
        self.train_ids.insert(to_idx, item)

        converted = False
        converted_tids = []
        if self.route_id and self.diagram_id:
            route = self.project.routes.get(self.route_id)
            if route:
                tbd = route.get("trains_by_diagram", {}).get(self.diagram_id, {})
                train_key = "inbound_trains" if self.direction == "inbound" else "outbound_trains"
                order_key = f"{train_key}_order"
                if order_key in tbd:
                    tbd[order_key][:] = self.train_ids

                    d_trains = tbd.get(train_key, {})
                    last_saved_idx = -1
                    for i in range(len(self.train_ids) - 1, -1, -1):
                        tid = self.train_ids[i]
                        t = d_trains.get(tid, {})
                        if t.get("to_be_saved"):
                            last_saved_idx = i
                            break

                    if last_saved_idx != -1:
                        for i in range(last_saved_idx):
                            tid = self.train_ids[i]
                            t = d_trains.get(tid)
                            if t and not t.get("to_be_saved"):
                                t["to_be_saved"] = True
                                converted_tids.append(tid)
                                converted = True

        if self.history_manager and self.route_id and self.diagram_id:
            ev = ReorderTrainsEvent(self.route_id, self.direction, tid_to_move, self.diagram_id, from_idx, to_idx, converted_tids)
            self.history_manager.push_events([ev])

        if converted:
            self.update_data(self.route_id, self.diagram_id, self.direction)
        else:
            self.beginResetModel()
            self.endResetModel()

        self.trainsReordered.emit()

    def _get_stations_in_segment(self, line_id, start_station_id, end_station_id):
        line_data = self.project.lines.get(line_id)
        if not line_data:
            return []
        line_station_ids = [s["station_id"] for s in line_data.get("station_list", [])]
        try:
            idx_start = line_station_ids.index(start_station_id)
            idx_end = line_station_ids.index(end_station_id)
        except ValueError:
            return []
        stations = []
        if idx_start <= idx_end:
            for i in range(idx_start, idx_end + 1):
                stations.append(line_station_ids[i])
        else:
            for i in range(idx_start, idx_end - 1, -1):
                stations.append(line_station_ids[i])
        return stations

    def _format_time(self, text: str):
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
                if len(s) != 6: return None
                hh, mm, ss = int(s[0:2]), int(s[2:4]), int(s[4:6])
            elif colon_count == 1:
                parts = text.split(':')
                if not parts[0] or not parts[1]: return None
                hh, mm, ss = int(parts[0]), int(parts[1]), 0
            elif colon_count == 2:
                parts = text.split(':')
                if not parts[0] or not parts[1] or not parts[2]: return None
                hh, mm, ss = int(parts[0]), int(parts[1]), int(parts[2])
            else:
                return None
        except ValueError:
            return None
        if 0 <= hh <= 99 and 0 <= mm < 60 and 0 <= ss < 60:
            return f"{hh:02d}:{mm:02d}:{ss:02d}"
        return None

    def _time_to_seconds(self, text: str):
        if not text: return None
        try:
            parts = text.split(':')
            if len(parts) == 3:
                h, m, s = map(int, parts)
                return h * 3600 + m * 60 + s
        except (ValueError, AttributeError):
            pass
        return None

    def update_data(self, route_id, diagram_id, direction):
        self.beginResetModel()
        self.route_id = route_id
        self.diagram_id = diagram_id
        self.direction = direction
        self.train_ids = []
        self.station_rows = []
        self.full_stop_sequence = []
        self.full_stop_configs = []
        self._dest_cache = {}

        if route_id and diagram_id:
            route = self.project.routes.get(route_id)
            if route:
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

                for seg in work_segments:
                    segment_id = seg["segment_id"]
                    line_id = seg["line_id"]
                    line_data = self.project.lines.get(line_id, {})
                    line_color = line_data.get("line_color", "#333333")

                    # 路線内での進行方向(inbound/outbound)を判定
                    line_station_ids = [s["station_id"] for s in line_data.get("station_list", [])]
                    try:
                        idx_start = line_station_ids.index(seg["start_station"])
                        idx_end = line_station_ids.index(seg["end_station"])
                    except ValueError: continue
                    seg_line_direction = "outbound" if idx_start <= idx_end else "inbound"

                    s_ids = self._get_stations_in_segment(line_id, seg["start_station"], seg["end_station"])
                    station_list = line_data.get("station_list", [])
                    for i, sid in enumerate(s_ids):
                        ls_item = next((s for s in station_list if s["station_id"] == sid), {})
                        track_id = ls_item.get("inbound_main_track" if seg_line_direction == "inbound" else "outbound_main_track")
                        
                        is_current_segment_start = (i == 0)
                        is_current_segment_end = (i == len(s_ids) - 1)

                        self.full_stop_sequence.append(sid)
                        self.full_stop_configs.append({
                            "segment_id": segment_id,
                            "station_id": sid, 
                            "line_id": line_id, 
                            "direction": seg_line_direction, 
                            "track_id": track_id,
                            "is_segment_start": is_current_segment_start,
                            "is_segment_end": is_current_segment_end
                        })

                        stop_idx = len(self.full_stop_sequence) - 1
                        s_data = self.project.stations.get(sid, {})
                        name = s_data.get("station_name", sid)
                        show_arr = is_current_segment_start or is_current_segment_end or s_data.get("show_arrival_time", False)
                        if i == 0:
                            self.station_rows.append({"name": f"{name} [発]", "stop_idx": stop_idx, "type": "dep", "line_color": line_color})
                        elif i == len(s_ids) - 1:
                            self.station_rows.append({"name": f"{name} [着]", "stop_idx": stop_idx, "type": "arr", "line_color": line_color})
                        elif show_arr:
                            self.station_rows.append({"name": f"{name} [着]", "stop_idx": stop_idx, "type": "arr", "line_color": line_color})
                            self.station_rows.append({"name": f"{name} [発]", "stop_idx": stop_idx, "type": "dep", "line_color": line_color})
                        else:
                            self.station_rows.append({"name": name, "stop_idx": stop_idx, "type": "dep", "line_color": line_color})
                
                # 駅情報の逆引き用マップ（normalizationの高速化用）
                self._stop_lookup = {}
                for i, cfg in enumerate(self.full_stop_configs):
                    key = (cfg["station_id"], cfg["segment_id"])
                    if key not in self._stop_lookup: self._stop_lookup[key] = []
                    self._stop_lookup[key].append(i)

                tbd = route.get("trains_by_diagram", {}).get(diagram_id, {})
                train_key = "inbound_trains" if direction == "inbound" else "outbound_trains"
                order_key = f"{train_key}_order"
                
                # ダイヤ側の列車情報(optdia_diagram_train_dict)
                d_trains = tbd.get(train_key, {})
                # 運行系統側の列車実体情報(optdia_train_dict)
                m_trains = route.get(train_key, {})
                order = tbd.get(order_key, []) # 列車IDの順序リスト

                # 末尾に列車の空データを20本追加（これらの列車はプロジェクトデータの保存時に除去される）
                unsaved_count = sum(1 for tid in order if d_trains.get(tid, {}).get("to_be_saved") is False)
                needed = 20 - unsaved_count
                if needed > 0:
                    chars = string.ascii_letters + string.digits
                    for _ in range(needed):
                        while True:
                            new_id = "".join(random.choices(chars, k=16)) # 16文字のランダムな英数字からなる列車IDを生成
                            if new_id not in d_trains: break
                        # ダイヤ側に参照用オブジェクトを作成
                        d_trains[new_id] = {
                            "train_id": new_id, "operations": [], "car_count": None,
                            "destination": None, "subsequent_trains": [], "to_be_saved": False
                        }
                        # 運行系統側に実体オブジェクトを作成
                        m_trains[new_id] = {
                            "train_number": "", "train_type_id": None,
                            "named_train_number": None, "note": "", "stops": [], "_diagram_ids": [self.diagram_id]
                        }
                        order.append(new_id)
                self.train_ids = order

        self._normalize_all_trains()
        self.endResetModel()

    def _normalize_all_trains(self):
        """現在の運行系統・ダイヤに含まれる全列車のストップデータを正規化（マージ・分割）する"""
        if not self.route_id or not self.diagram_id:
            return
        route = self.project.routes.get(self.route_id)
        if not route:
            return

        tbd = route.get("trains_by_diagram", {}).get(self.diagram_id, {})
        train_key = "inbound_trains" if self.direction == "inbound" else "outbound_trains"

        # ダイヤ側の列車属性を正規化（空文字列を行き先未設定として扱う）
        d_trains = tbd.get(train_key, {})
        for d_train in d_trains.values():
            if d_train.get("destination") == "":
                d_train["destination"] = None

        # 運行系統が持つマスタ列車のうち、現在の方面のものをすべて正規化する
        m_trains = route.get(train_key, {})
        for train in m_trains.values():
            self._normalize_train_stops(train)

    def _normalize_train_stops(self, train):
        """個別の列車の stops リストを現在の full_stop_configs に基づいて再構成（マージ・分割）する"""
        if not train.get("stops"):
            return

        # 空文字列を None に統一する（誤った仕様で作成されたデータへの対策）
        for s in train["stops"]:
            if s.get("arrival_time") == "": s["arrival_time"] = None
            if s.get("departure_time") == "": s["departure_time"] = None

        # 保存時に消去された stop_idx を、現在の駅順 (full_stop_configs) に基づいて復元する
        # JSONから読み込まれた直後は stop_idx が無いため、駅ID・路線ID・方向の並び順から推測する
        # 一時的に stop_idx が割り当てられた stops を格納するリスト
        stops_with_idx = []

        for s in train["stops"]:
            sid, seg_id = s["station_id"], s["segment_id"]
            # 高速な逆引きを使用して stop_idx を特定
            key = (sid, seg_id)
            for i in self._stop_lookup.get(key, []):
                cfg = self.full_stop_configs[i]
                if ((not cfg.get("is_segment_start") or s.get("arrival_time") is None) and
                    (not cfg.get("is_segment_end") or s.get("departure_time") is None)):
                    s["stop_idx"] = i
                    stops_with_idx.append(s)
                    break

        # stop_idx に基づいてソート（これでテーブル上の並び順と一致する）
        train["stops"].sort(key=lambda x: x.get("stop_idx", 0))
        # stop_idx が割り当てられなかった stops はここで除外される
        train["stops"] = sorted(stops_with_idx, key=lambda x: x["stop_idx"])
        # 表示・編集時の高速アクセス用マップを作成
        train["_stop_map"] = {s["stop_idx"]: s for s in train["stops"]}

        # セグメントの境界フラグに基づいて None 値を補正
        for s in train["stops"]:
            idx = s.get("stop_idx")
            if idx is not None and idx < len(self.full_stop_configs):
                config = self.full_stop_configs[idx]
                
                if config.get("is_segment_start"):
                    s["arrival_time"] = None
                if config.get("is_segment_end"):
                    s["departure_time"] = None

    def flags(self, index):
        if not index.isValid(): return Qt.ItemIsEnabled
        
        # フッター行（ボタン行）はテキスト編集を無効にする
        num_rows_before_footer = len(self.row_headers) + len(self.station_rows)
        if index.row() == num_rows_before_footer:
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable

        # 備考行 (num_rows_before_footer + 1) はクリックでポップアップを開くため標準の編集は無効化
        if index.row() == num_rows_before_footer + 1:
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable

        # 「運転日」行 (index 1) と「運用番号」行 (index 2) は編集不可
        if index.row() == 2: # 運用番号行のみ編集不可
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable

        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid() or role not in (Qt.EditRole, TrackIdRole, StopTypeRole): return False
        col = index.column()
        row = index.row()
        if not self.route_id or not self.diagram_id or col >= len(self.train_ids): return False
        route = self.project.routes.get(self.route_id)
        tbd = route.get("trains_by_diagram", {}).get(self.diagram_id, {})
        train_key = "inbound_trains" if self.direction == "inbound" else "outbound_trains"
        
        d_trains = tbd.get(train_key, {})
        m_trains = route.get(train_key, {})
        
        train_id = self.train_ids[col]
        d_train = d_trains.get(train_id)
        m_train = m_trains.get(train_id)
        if not d_train or not m_train: return False
        
        events_to_push = []
        changed = False
        if role == StopTypeRole:
            if row >= len(self.row_headers):
                row_idx = row - len(self.row_headers)
                if row_idx < len(self.station_rows):
                    row_def = self.station_rows[row_idx]
                    stop_idx = row_def["stop_idx"]
                    config = self.full_stop_configs[stop_idx]
                    seg_id = config["segment_id"]
                    sid = config["station_id"]
                    
                    if "stops" not in m_train: m_train["stops"] = []
                    stop = next((s for s in m_train["stops"] if s.get("stop_idx") == stop_idx), None)
                    if not stop:
                        stop = {
                            "segment_id": seg_id,
                            "station_id": sid,
                            "track_id": config["track_id"],
                            "arrival_time": None,
                            "departure_time": None,
                            "stop_type": value,
                            "stop_idx": stop_idx
                        }
                        m_train["stops"].append(stop)
                        events_to_push.append(AddTrainStopEvent(self.route_id, self.direction, train_id, len(m_train["stops"]) - 1, stop))
                        changed = True
                    elif stop.get("stop_type") != value:
                        old_stop = copy.deepcopy(stop)
                        stop["stop_type"] = value
                        events_to_push.append(ChangeTrainStopEvent(self.route_id, self.direction, train_id, stop_idx, old_stop, stop))
                        changed = True
                        
                    if changed:
                        m_train["stops"].sort(key=lambda x: x.get("stop_idx", 0))
                        try:
                            curr_idx = m_train["stops"].index(stop)
                            if curr_idx > 0:
                                prev_stop = m_train["stops"][curr_idx - 1]
                                if prev_stop.get("station_id") == stop.get("station_id"):
                                    old_p = copy.deepcopy(prev_stop)
                                    prev_stop["stop_type"] = value
                                    events_to_push.append(ChangeTrainStopEvent(self.route_id, self.direction, train_id, prev_stop.get("stop_idx"), old_p, prev_stop))
                            if curr_idx < len(m_train["stops"]) - 1:
                                next_stop = m_train["stops"][curr_idx + 1]
                                if next_stop.get("station_id") == stop.get("station_id"):
                                    old_n = copy.deepcopy(next_stop)
                                    next_stop["stop_type"] = value
                                    events_to_push.append(ChangeTrainStopEvent(self.route_id, self.direction, train_id, next_stop.get("stop_idx"), old_n, next_stop))
                        except ValueError:
                            pass
                        
                        if self.history_manager and events_to_push:
                            self.history_manager.push_events(events_to_push)
                        self._trigger_update(col, d_trains, index)
                    return changed
            return False

        changed = False
        if row == 0: # 列車番号
            if m_train.get("train_number") != value:
                old_num = m_train.get("train_number", "")
                m_train["train_number"] = value
                events_to_push.append(ChangeTrainNumberEvent(self.route_id, self.direction, train_id, old_num, value))
                changed = True
        elif row == 1 or row == 2: # 運転日または運用番号 (ボタンなので直接編集不可)
            # 運用番号はデリゲートで処理されるため、直接のテキスト入力は受け付けない
            return False
        elif row == 3: # 両数
            try:
                val = int(value) if value and value.strip() else None
                if d_train.get("car_count") != val:
                    old_cc = d_train.get("car_count")
                    d_train["car_count"] = val
                    events_to_push.append(ChangeTrainCarCountEvent(self.route_id, self.direction, train_id, self.diagram_id, old_cc, val))
                    changed = True
            except ValueError: return False
        elif row == 4: # 種別・愛称
            if m_train.get("train_type_id") != value:
                old_tt = m_train.get("train_type_id")
                m_train["train_type_id"] = value
                events_to_push.append(ChangeTrainTypeEvent(self.route_id, self.direction, train_id, old_tt, value))
                changed = True
        elif row == 5: # 号数
            try:
                val = int(value) if value and value.strip() else None
                if m_train.get("named_train_number") != val:
                    old_n = m_train.get("named_train_number")
                    m_train["named_train_number"] = val
                    events_to_push.append(ChangeTrainNamedNumberEvent(self.route_id, self.direction, train_id, old_n, val))
                    changed = True
            except ValueError: return False
        elif row == 6: # 行き先
            # 空文字列の場合は None に置き換えて保持する
            val = value if value else None
            if d_train.get("destination") != val:
                old_dest = d_train.get("destination")
                d_train["destination"] = val
                events_to_push.append(ChangeTrainDestinationEvent(self.route_id, self.direction, train_id, self.diagram_id, old_dest, val))
                changed = True
        elif row == len(self.row_headers) + len(self.station_rows) + 1: # 備考
            if m_train.get("note") != value:
                old_note = m_train.get("note", "")
                m_train["note"] = value
                events_to_push.append(ChangeTrainNoteEvent(self.route_id, self.direction, train_id, old_note, value))
                changed = True
        elif row >= len(self.row_headers):
            row_idx = row - len(self.row_headers)
            if row_idx < len(self.station_rows):
                row_def = self.station_rows[row_idx]
                stop_idx = row_def["stop_idx"]
                config = self.full_stop_configs[stop_idx]
                seg_id = config["segment_id"]
                sid = config["station_id"]

                # 番線IDの更新処理
                if role == TrackIdRole:
                    stop = next((s for s in m_train.get("stops", []) if s.get("stop_idx") == stop_idx), None)
                    if not stop:
                        # 時刻未入力の状態で番線だけ選んだ場合、ストップデータを新規作成
                        initial_arr = None
                        initial_dep = None
                        stop = {
                            "segment_id": seg_id, "station_id": sid,
                            "track_id": value,
                            "arrival_time": initial_arr, "departure_time": initial_dep,
                            "stop_type": 1, "stop_idx": stop_idx
                        }
                        m_train["stops"].append(stop)
                        events_to_push.append(AddTrainStopEvent(self.route_id, self.direction, train_id, len(m_train["stops"]) - 1, stop))
                        changed = True
                    elif stop.get("track_id") != value:
                        old_s = copy.deepcopy(stop)
                        stop["track_id"] = value
                        events_to_push.append(ChangeTrainStopEvent(self.route_id, self.direction, train_id, stop_idx, old_s, stop))
                        changed = True
                    
                    if changed:
                        if self.history_manager and events_to_push:
                            self.history_manager.push_events(events_to_push)
                        self._trigger_update(col, d_trains, index)
                    return changed

                if "stops" not in m_train: m_train["stops"] = []
                formatted_value = self._format_time(value)

                # Pre-edit check
                is_target_train = True
                for s in m_train.get("stops", []):
                    if s.get("arrival_time") is not None or s.get("departure_time") is not None:
                        is_target_train = False
                        break

                stations_with_time = set()
                for s in m_train.get("stops", []):
                    if s.get("arrival_time") is not None or s.get("departure_time") is not None:
                        stations_with_time.add(s.get("stop_idx"))
                has_multiple_stations = len(stations_with_time) >= 2
                
                # 管理用インデックス stop_idx を使用して、該当する駅訪問データを特定
                stop = next((s for s in m_train["stops"] if s.get("stop_idx") == stop_idx), None)
                old_stop_snapshot = copy.deepcopy(stop) if stop else None

                if not stop:
                    # 時刻が入力されていない場合は、新しいstopを作成しない
                    if formatted_value is None:
                        return False

                    # 運行系統内の路線ごとの始点駅であれば到着時刻をNoneに、終点駅であれば発車時刻をNoneに設定
                    initial_arrival_time = None
                    initial_departure_time = None

                    stop = {
                        "segment_id": seg_id,
                        "station_id": sid,
                        "track_id": config["track_id"],
                        "arrival_time": initial_arrival_time,
                        "departure_time": initial_departure_time,
                        "stop_type": 1,
                        "stop_idx": stop_idx
                    }
                    m_train["stops"].append(stop)
                    m_train["stops"].sort(key=lambda x: x.get("stop_idx", 0))
                    try:
                        curr_idx = m_train["stops"].index(stop)
                        if curr_idx > 0:
                            prev_stop = m_train["stops"][curr_idx - 1]
                            if prev_stop.get("station_id") == stop["station_id"]:
                                stop["stop_type"] = prev_stop.get("stop_type", 1)
                        if curr_idx < len(m_train["stops"]) - 1:
                            next_stop = m_train["stops"][curr_idx + 1]
                            if next_stop.get("station_id") == stop["station_id"]:
                                stop["stop_type"] = next_stop.get("stop_type", 1)
                    except ValueError:
                        pass

                time_key = "arrival_time" if row_def["type"] == "arr" else "departure_time"
                other_key = "departure_time" if row_def["type"] == "arr" else "arrival_time"
                old_time_str = stop.get(time_key)

                # 他のストップが変更される可能性に備えて、全ストップの事前スナップショットを記録
                all_stops_before = {s["stop_idx"]: copy.deepcopy(s) for s in m_train.get("stops", []) if "stop_idx" in s}

                if stop.get(time_key) != formatted_value:
                    stop[time_key] = formatted_value
                    # ユーザーが時刻を入力し、かつ、もう一方の時刻が未入力（None）の場合のみ自動補完する
                    # 運行系統内の各路線の始点・終点での「着のみ」「発のみ」の定義を壊さないように判定
                    if formatted_value is not None and stop.get(other_key) is None:
                        config_for_stop = self.full_stop_configs[stop_idx]
                        if (row_def["type"] == "arr" and not config_for_stop.get("is_segment_end")) or \
                           (row_def["type"] == "dep" and not config_for_stop.get("is_segment_start")):
                            stop[other_key] = formatted_value

                    # 発時刻が編集（入力または削除）された場合、中間駅かつ着時刻非表示なら着時刻も連動させる
                    if row_def["type"] == "dep":
                        station_data = self.project.stations.get(config["station_id"], {})
                        is_seg_boundary = config.get("is_segment_start") or config.get("is_segment_end")
                        show_arr = is_seg_boundary or station_data.get("show_arrival_time", False)
                        if not is_seg_boundary and not show_arr:
                            stop["arrival_time"] = formatted_value

                    stop["track_id"] = config["track_id"]
                    changed = True

                    # 同じ種別の列車から時刻を補完
                    if self.auto_fill_enabled and is_target_train and formatted_value is not None:
                        target_type_id = m_train.get("train_type_id")
                        ref_m_train = None
                        for c in range(col - 1, -1, -1):
                            prev_id = self.train_ids[c]
                            prev_m = m_trains.get(prev_id)
                            if prev_m and prev_m.get("train_type_id") == target_type_id:
                                prev_stop = next((s for s in prev_m.get("stops", []) if s.get("stop_idx") == stop_idx), None)
                                if prev_stop and (prev_stop.get("arrival_time") is not None or prev_stop.get("departure_time") is not None):
                                    ref_m_train = prev_m
                                    break
                        
                        if ref_m_train:
                            ref_stop = next((s for s in ref_m_train["stops"] if s.get("stop_idx") == stop_idx), None)
                            ref_time_str = None
                            if ref_stop:
                                if ref_stop.get(time_key) is not None:
                                    ref_time_str = ref_stop[time_key]
                                elif ref_stop.get(other_key) is not None:
                                    ref_time_str = ref_stop[other_key]
                            
                            if ref_time_str is not None:
                                t_ref = self._time_to_seconds(ref_time_str)
                                t_input = self._time_to_seconds(formatted_value)
                                if t_ref is not None and t_input is not None:
                                    diff = t_input - t_ref
                                    for ref_stop_item in ref_m_train["stops"]:
                                        ref_idx = ref_stop_item.get("stop_idx")
                                        if ref_idx is not None and ref_idx > stop_idx:
                                            target_stop_item = next((s for s in m_train["stops"] if s.get("stop_idx") == ref_idx), None)
                                            if not target_stop_item:
                                                ref_cfg = self.full_stop_configs[ref_idx]
                                                target_stop_item = {
                                                    "segment_id": ref_cfg["segment_id"],
                                                    "station_id": ref_stop_item["station_id"],
                                                    "track_id": ref_stop_item.get("track_id", ref_cfg["track_id"]),
                                                    "arrival_time": None,
                                                    "departure_time": None,
                                                    "stop_type": ref_stop_item.get("stop_type", 1),
                                                    "stop_idx": ref_idx
                                                }
                                                m_train["stops"].append(target_stop_item)
                                            
                                            if ref_stop_item.get("arrival_time") is not None:
                                                t_arr = self._time_to_seconds(ref_stop_item["arrival_time"])
                                                target_stop_item["arrival_time"] = self._seconds_to_time(t_arr + diff)
                                            if ref_stop_item.get("departure_time") is not None:
                                                t_dep = self._time_to_seconds(ref_stop_item["departure_time"])
                                                target_stop_item["departure_time"] = self._seconds_to_time(t_dep + diff)
                                    m_train["stops"].sort(key=lambda x: x.get("stop_idx", 0))

                    # 発着時刻の変更時に後の駅の発着時刻も増減
                    elif self.adjust_later_enabled and has_multiple_stations:
                        if old_time_str is not None and formatted_value is not None and old_time_str != formatted_value:
                            t_old = self._time_to_seconds(old_time_str)
                            t_new = self._time_to_seconds(formatted_value)
                            if t_old is not None and t_new is not None:
                                diff = t_new - t_old
                                if row_def["type"] == "arr" and stop.get("departure_time") is not None:
                                    curr_dep = self._time_to_seconds(stop["departure_time"])
                                    if curr_dep is not None:
                                        stop["departure_time"] = self._seconds_to_time(curr_dep + diff)
                                for sub_stop in m_train.get("stops", []):
                                    sub_idx = sub_stop.get("stop_idx")
                                    if sub_idx is not None and sub_idx > stop_idx:
                                        if sub_stop.get("arrival_time") is not None:
                                            sub_arr = self._time_to_seconds(sub_stop["arrival_time"])
                                            sub_stop["arrival_time"] = self._seconds_to_time(sub_arr + diff)
                                        if sub_stop.get("departure_time") is not None:
                                            sub_dep = self._time_to_seconds(sub_stop["departure_time"])
                                            sub_stop["departure_time"] = self._seconds_to_time(sub_dep + diff)

                if changed:
                    # stops の差分からイベントを構築
                    for s in m_train.get("stops", []):
                        s_idx = s.get("stop_idx")
                        if s_idx not in all_stops_before:
                            events_to_push.append(AddTrainStopEvent(self.route_id, self.direction, train_id, m_train["stops"].index(s), s))
                        elif all_stops_before[s_idx] != s:
                            events_to_push.append(ChangeTrainStopEvent(self.route_id, self.direction, train_id, s_idx, all_stops_before[s_idx], s))

        if changed:
            if self.history_manager and events_to_push:
                self.history_manager.push_events(events_to_push)
            self._trigger_update(col, d_trains, index)
            return True
        return False


    def clear_destination_cache(self):
        """行き先の表示キャッシュをクリアする"""
        self._dest_cache = {}

    def _trigger_update(self, col, d_trains, index):
        converted = False
        # 行き先表示（自動解決）は列車間の参照を含むため、時刻や属性の変更時はキャッシュをクリアする。
        # 影響範囲が広いため、安全のため全キャッシュをクリアする。
        self.clear_destination_cache()

        for i in range(col + 1):
            tid = self.train_ids[i]
            t = d_trains.get(tid)
            if t and not t.get("to_be_saved"):
                t["to_be_saved"] = True
                converted = True
        
        train_id = self.train_ids[col]
        route = self.project.routes.get(self.route_id)
        train_key = "inbound_trains" if self.direction == "inbound" else "outbound_trains"
        m_train = route.get(train_key, {}).get(train_id)
        if m_train:
            self._normalize_train_stops(m_train)

        if converted:
            # ダミー列車が実体化し、新しい空き枠を追加する必要がある場合は全体更新
            QTimer.singleShot(0, lambda: self.update_data(self.route_id, self.diagram_id, self.direction))
        else:
            # 単なるデータの更新であれば、その列全体の再描画通知のみ行う（Resetを避ける）
            self.dataChanged.emit(self.index(0, col), self.index(self.rowCount() - 1, col), [Qt.DisplayRole, Qt.ForegroundRole])

    def rowCount(self, parent=QModelIndex()):
        return len(self.row_headers) + len(self.station_rows) + 2

    def columnCount(self, parent=QModelIndex()):
        return len(self.train_ids)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid(): return None
        col, row = index.column(), index.row()
        if not self.route_id or not self.diagram_id: return None
        route = self.project.routes.get(self.route_id)
        if not route: return None
        tbd = route.get("trains_by_diagram", {}).get(self.diagram_id, {})
        train_key = "inbound_trains" if self.direction == "inbound" else "outbound_trains"
        
        d_trains = tbd.get(train_key, {})
        m_trains = route.get(train_key, {})
        
        if col >= len(self.train_ids): return None
        train_id = self.train_ids[col]
        
        d_train = d_trains.get(train_id, {})
        m_train = m_trains.get(train_id, {})

        if role == StopTypeRole:
            if row >= len(self.row_headers):
                row_idx = row - len(self.row_headers)
                if row_idx < len(self.station_rows):
                    row_def = self.station_rows[row_idx]
                    stop_map = m_train.get("_stop_map")
                    if stop_map is not None:
                        stop = stop_map.get(row_def["stop_idx"])
                    else:
                        stop = next((s for s in m_train.get("stops", []) if s.get("stop_idx") == row_def["stop_idx"]), None)
                    if stop:
                        return stop.get("stop_type", 1)
            return None

        if role == Qt.TextAlignmentRole:
            # フッター行と「運転日」行は中央揃え
            num_rows_before_footer = len(self.row_headers) + len(self.station_rows)
            if row == num_rows_before_footer or row == 1:
                return Qt.AlignCenter
            if row == num_rows_before_footer + 1:  # 備考行 (テキストを上寄せ表示)
                return Qt.AlignLeft | Qt.AlignTop
            if row < len(self.row_headers):
                return Qt.AlignCenter
            return Qt.AlignRight | Qt.AlignVCenter

        if role == Qt.BackgroundRole:
            tt = self.project.train_types.get(m_train.get("train_type_id"))
            return QColor(tt.get("background_color", "#ffffff")) if tt else None
        if role == Qt.ForegroundRole:
            if row == 0: # 列車番号
                tt = self.project.train_types.get(m_train.get("train_type_id"))
                if tt: return QColor(tt.get("main_color", "#333333"))
            elif row == 1: # 運転日
                return None # デフォルトのテキスト色を使用
            elif row == 3: # 両数
                # 両数が指定されていない場合は灰色、そうでなければデフォルト色でテキストを表示
                if d_train.get("car_count") is None:
                    return QColor(Qt.darkGray)
                else:
                    return None
            elif row == 4: # 種別・愛称
                tt = self.project.train_types.get(m_train.get("train_type_id"))
                if tt: return QColor(tt.get("main_color", "#333333"))
            elif row == 6: # 行き先
                if not d_train.get("destination"):
                    return QColor(Qt.gray)
            if row >= len(self.row_headers):
                row_idx = row - len(self.row_headers)
                if row_idx < len(self.station_rows):
                    row_def = self.station_rows[row_idx]
                    stop_map = m_train.get("_stop_map")
                    if stop_map is not None:
                        stop = stop_map.get(row_def["stop_idx"])
                    else:
                        stop = next((s for s in m_train.get("stops", []) if s.get("stop_idx") == row_def["stop_idx"]), None)
                    if stop and stop.get("stop_type", 1) in (0, -1):
                        return QColor(Qt.gray)

            if row >= len(self.row_headers):
                val = self.data(index, Qt.EditRole) # 秒を含む正確な時刻で比較
                secs = self._time_to_seconds(val)
                if secs is not None:
                    # 運転日行と運用番号行をスキップして前の時刻を探す
                    # row_headersの長さが7なので、時刻行の開始は7から
                    # 列車番号(0), 運転日(1), 運用番号(2), 両数(3), 種別・愛称(4), 号数(5), 行き先(6)
                    for r in range(row - 1, len(self.row_headers) - 1, -1): # 列車番号(0)より下は時刻行
                        p_val = self.data(self.index(r, col), Qt.EditRole)
                        p_secs = self._time_to_seconds(p_val)
                        if p_secs is not None:
                            if secs < p_secs: return QColor(Qt.red)
                            break
            return None
        if role in (Qt.DisplayRole, Qt.EditRole):
            if row == 0: return m_train.get("train_number", "") # 列車番号
            elif row == 1: # 運転日
                diagram_ids = m_train.get("_diagram_ids", [])
                all_diagram_ids = self.project.diagrams_order

                if len(diagram_ids) == len(all_diagram_ids) and all(did in diagram_ids for did in all_diagram_ids):
                    return "(毎日)"

                diagram_initials = []
                for did in diagram_ids:
                    diagram_data = self.project.diagrams.get(did)
                    if diagram_data:
                        diagram_initials.append(diagram_data.get("diagram_initial", ""))
                
                if len(diagram_initials) > 4:
                    return "".join(diagram_initials[:3]) + ".."
                else:
                    return "".join(diagram_initials)
            elif row == 2: # 運用番号
                ops = []
                operations_dict = self.project.diagrams.get(self.diagram_id, {}).get("operations", {})
                for op in d_train.get("operations", []):
                    op_id = op.get("operation_id") if isinstance(op, dict) else op
                    if op_id:
                        op_data = operations_dict.get(op_id)
                        op_num = op_data.get("operation_number") if op_data else op_id
                        ops.append(str(op_num))
                return "+".join(ops) if ops else ""
            elif row == 3: # 両数
                cc = d_train.get("car_count")
                if cc is None:
                    # 運用内の所定両数を合計する
                    total = 0
                    for op in d_train.get("operations", []):
                        op_id = op.get("operation_id") if isinstance(op, dict) else op
                        op_data = self.project.diagrams.get(self.diagram_id, {}).get("operations", {}).get(op_id, {}) if op_id else {}
                        total += op_data.get("car_count", 0)
                    cc = total if total > 0 else None
                if role == Qt.DisplayRole:
                    return f"{cc}両" if cc is not None else ""
                else:
                    return str(cc) if cc is not None else ""
            elif row == 4: # 種別・愛称
                tt = self.project.train_types.get(m_train.get("train_type_id"))
                name = (tt.get("train_type_short_name") or tt.get("train_type_name", "")) if tt else ""
                tname = m_train.get("train_name")
                return f"{name} {tname}" if tname else name
            elif row == 5: # 号数
                val = m_train.get("named_train_number")
                if role == Qt.DisplayRole:
                    return f"{val}号" if val is not None else ""
                else:
                    return str(val) if val is not None else ""
            elif row == 6: # 行き先
                if train_id in self._dest_cache:
                    return self._dest_cache[train_id]

                raw_dest = d_train.get("destination")
                if raw_dest:
                    res = raw_dest[:8] + ".." if len(raw_dest) > 8 else raw_dest
                else:
                    # 自動表示ロジック（再帰探索が含まれるためキャッシュが有効）
                    dest, is_branched = self._resolve_destination(d_train, m_train, self.diagram_id)
                    if is_branched:
                        res = dest
                    else:
                        res = dest[:8] + ".." if len(dest) > 8 else dest
                
                self._dest_cache[train_id] = res
                return res
            elif row >= len(self.row_headers): # 駅時刻行
                row_idx = row - len(self.row_headers)
                if row_idx < len(self.station_rows):
                    row_def = self.station_rows[row_idx]

                    # stop_map を使用して O(1) でアクセス（next(...) による走査を回避）
                    stop_map = m_train.get("_stop_map")
                    if stop_map is not None:
                        stop = stop_map.get(row_def["stop_idx"])
                    else:
                        stop = next((s for s in m_train.get("stops", []) if s.get("stop_idx") == row_def["stop_idx"]), None)

                    if stop:
                        full_time = stop.get("arrival_time" if row_def["type"] == "arr" else "departure_time", "")
                        if role == Qt.DisplayRole:
                            # 非編集時は時と分だけを表示 (HH:MM)
                            if full_time and len(full_time) == 8: # "HH:MM:SS" 形式を想定
                                return full_time[:5] # "HH:MM" の部分を返す
                            return full_time # 不正な形式または空の場合はそのまま返す
                        elif role == Qt.EditRole:
                            # 編集時は秒まで含めた完全な時刻を表示 (HH:MM:SS)
                            return full_time
        
        if role in (Qt.DisplayRole, Qt.EditRole):
            num_rows_before_footer = len(self.row_headers) + len(self.station_rows)
            if row == num_rows_before_footer + 1:
                return m_train.get("note", "")

        if role == Qt.DisplayRole:
            # フッター行のセルにはデータは返さない（デリゲートでボタンを描画するため）
            num_rows_before_footer = len(self.row_headers) + len(self.station_rows)
            if row == num_rows_before_footer:
                return None
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Vertical:
            if role == Qt.DisplayRole:
                if 0 <= section < len(self.row_headers): return self.row_headers[section]
                row_idx = section - len(self.row_headers)
                if 0 <= row_idx < len(self.station_rows): return self.station_rows[row_idx]["name"]
                num_rows_before_footer = len(self.row_headers) + len(self.station_rows)
                if section == num_rows_before_footer: return "連続する列車"
                if section == num_rows_before_footer + 1: return "備考"
            elif role == Qt.TextAlignmentRole:
                if 0 <= section < len(self.row_headers): return Qt.AlignCenter
                num_rows_before_footer = len(self.row_headers) + len(self.station_rows)
                if section == num_rows_before_footer or section == num_rows_before_footer + 1: return Qt.AlignCenter
                return Qt.AlignRight | Qt.AlignVCenter
        return None

    def _get_next_editable_index(self, current_index: QModelIndex) -> QModelIndex:
        return self.index(current_index.row() + 1, current_index.column())

    def _get_terminal_station_name(self, train):
        """列車の発着時刻データのうち最後の駅名を返す"""
        stops = train.get("stops", [])
        if not stops:
            return ""
        timed_stops = [s for s in stops if s.get("arrival_time") or s.get("departure_time")]
        if not timed_stops:
            return ""
        last_stop = timed_stops[-1]
        sid = last_stop.get("station_id")
        station_data = self.project.stations.get(sid, {})
        return station_data.get("station_name", sid)

    def _get_train_pair_from_sub_info(self, sub_info, diagram_id):
        """subsequent_trains の情報から (diagram_train, master_train) を取得する"""
        rid = sub_info.get("route_id")
        direction = sub_info.get("direction")
        tid = sub_info.get("train_id")
        if not rid or not direction or not tid:
            return None, None
        route = self.project.routes.get(rid)
        if not route:
            return None, None
        
        tbd = route.get("trains_by_diagram", {}).get(diagram_id, {})
        train_key = "inbound_trains" if direction == "inbound" else "outbound_trains"
        
        d_train = tbd.get(train_key, {}).get(tid)
        m_train = route.get(train_key, {}).get(tid)
        return d_train, m_train

    def _resolve_destination(self, d_train, m_train, diagram_id, depth=0, force_single=False):
        """行き先を解決する。
        未入力で連続する列車が設定されている場合は「(連続)」を返し、
        連続する列車も無ければ終着駅を返す。
        Returns: (destination_string, is_branched)
        """
        dest = d_train.get("destination")
        if dest:
            return dest, False

        subs = d_train.get("subsequent_trains", [])
        if subs:
            return "(連続)", False

        return self._get_terminal_station_name(m_train), False
