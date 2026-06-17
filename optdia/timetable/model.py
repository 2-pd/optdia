import random
import string
import re
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QTimer
from PySide6.QtGui import QColor
from project import OptDiaProject

TrackIdRole = Qt.UserRole + 100

# メインウィンドウの時刻表テーブルに紐付けられるモデル
class TimetableModel(QAbstractTableModel):
    def __init__(self, project: OptDiaProject):
        super().__init__()
        self.project = project
        self.route_id = None
        self.diagram_id = None
        self.direction = "outbound"
        self.row_headers = ["列車番号", "運用番号", "両数", "種別・愛称", "号数", "行き先"]
        self.train_ids = []
        self.station_rows = []
        self.full_stop_sequence = []
        self.full_stop_configs = []

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

        if route_id and diagram_id:
            route = self.project.routes.get(route_id)
            if route:
                segments = route.get("line_segments", [])
                work_segments = []
                if direction == "inbound":
                    for seg in reversed(segments):
                        work_segments.append({
                            "line_id": seg["line_id"],
                            "start_station": seg["end_station"],
                            "end_station": seg["start_station"]
                        })
                else:
                    work_segments = segments

                for seg in work_segments:
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
                        if i == 0:
                            self.station_rows.append({"name": f"{name} [発]", "stop_idx": stop_idx, "type": "dep", "line_color": line_color})
                        elif i == len(s_ids) - 1:
                            self.station_rows.append({"name": f"{name} [着]", "stop_idx": stop_idx, "type": "arr", "line_color": line_color})
                        elif s_data.get("show_arrival_time", False):
                            self.station_rows.append({"name": f"{name} [着]", "stop_idx": stop_idx, "type": "arr", "line_color": line_color})
                            self.station_rows.append({"name": f"{name} [発]", "stop_idx": stop_idx, "type": "dep", "line_color": line_color})
                        else:
                            self.station_rows.append({"name": name, "stop_idx": stop_idx, "type": "dep", "line_color": line_color})
                tbd = route.get("trains_by_diagram", {}).get(diagram_id, {})
                train_dict_key = "inbound_trains" if direction == "inbound" else "outbound_trains"
                train_order_key = "inbound_trains_order" if direction == "inbound" else "outbound_trains_order"
                trains = tbd.get(train_dict_key, {})
                order = tbd.get(train_order_key, [])

                # 末尾に列車の空データを10本追加（これらの列車はプロジェクトデータの保存時に除去される）
                unsaved_count = sum(1 for tid in order if trains.get(tid, {}).get("to_be_saved") is False)
                needed = 10 - unsaved_count
                if needed > 0:
                    chars = string.ascii_letters + string.digits
                    for _ in range(needed):
                        while True:
                            new_id = "".join(random.choices(chars, k=16)) # 16文字のランダムな英数字からなる列車IDを生成
                            if new_id not in trains: break
                        trains[new_id] = {
                            "train_id": new_id, "train_number": "", "operations": [], "train_type_id": None,
                            "named_train_number": None, "car_count": None, "destination": None,
                            "subsequent_trains": [], "note": "", "stops": [], "to_be_saved": False
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
        # 現在の方面に該当する列車のみを処理する
        train_key = "inbound_trains" if self.direction == "inbound" else "outbound_trains"
        trains = tbd.get(train_key, {})
        for train in trains.values():
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
            sid, lid, ldir = s["station_id"], s["line_id"], s["direction"]
            # 一致する設定を full_stop_configs 全体から探す（順序に依存しないように）
            for i in range(len(self.full_stop_configs)):
                cfg = self.full_stop_configs[i]
                if (cfg["station_id"] == sid and cfg["line_id"] == lid and cfg["direction"] == ldir and
                    (not cfg.get("is_segment_start") or s.get("arrival_time") is None) and
                    (not cfg.get("is_segment_end") or s.get("departure_time") is None)):
                    # 境界駅の整合性を保ちつつ、中間駅での欠損（ユーザーによる削除）を許容する

                    s["stop_idx"] = i
                    stops_with_idx.append(s)
                    break

        # stop_idx に基づいてソート（これでテーブル上の並び順と一致する）
        train["stops"].sort(key=lambda x: x.get("stop_idx", 0))
        # stop_idx が割り当てられなかった stops はここで除外される
        train["stops"] = sorted(stops_with_idx, key=lambda x: x["stop_idx"])

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

        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid() or role not in (Qt.EditRole, TrackIdRole): return False
        col = index.column()
        row = index.row()
        if not self.route_id or not self.diagram_id or col >= len(self.train_ids): return False
        route = self.project.routes.get(self.route_id)
        tbd = route.get("trains_by_diagram", {}).get(self.diagram_id, {})
        train_key = "inbound_trains" if self.direction == "inbound" else "outbound_trains"
        trains = tbd.get(train_key, {})
        train_id = self.train_ids[col]
        train = trains.get(train_id)
        if not train: return False
        changed = False
        if row == 0:
            if train.get("train_number") != value:
                train["train_number"] = value
                changed = True
        elif row == 2:
            try:
                val = int(value) if value and value.strip() else None
                if train.get("car_count") != val:
                    train["car_count"] = val
                    changed = True
            except ValueError: return False
        elif row == 3:
            if train.get("train_type_id") != value:
                train["train_type_id"] = value
                changed = True
        elif row == 4:
            try:
                val = int(value) if value and value.strip() else None
                if train.get("named_train_number") != val:
                    train["named_train_number"] = val
                    changed = True
            except ValueError: return False
        elif row == 5:
            if train.get("destination") != value:
                train["destination"] = value
                changed = True
        elif row >= len(self.row_headers):
            row_idx = row - len(self.row_headers)
            if row_idx < len(self.station_rows):
                row_def = self.station_rows[row_idx]
                stop_idx = row_def["stop_idx"]
                config = self.full_stop_configs[stop_idx]
                sid = config["station_id"]
                lid = config["line_id"]
                ldir = config["direction"]

                # 番線IDの更新処理
                if role == TrackIdRole:
                    stop = next((s for s in train.get("stops", []) if s.get("stop_idx") == stop_idx), None)
                    if not stop:
                        # 時刻未入力の状態で番線だけ選んだ場合、ストップデータを新規作成
                        config_for_stop = self.full_stop_configs[stop_idx]
                        initial_arr = None
                        initial_dep = None
                        stop = {
                            "station_id": sid, "line_id": lid, "direction": ldir,
                            "track_id": value,
                            "arrival_time": initial_arr, "departure_time": initial_dep,
                            "stop_type": 1, "stop_idx": stop_idx
                        }
                        train["stops"].append(stop)
                        changed = True
                    elif stop.get("track_id") != value:
                        stop["track_id"] = value
                        changed = True
                    
                    if changed:
                        self._trigger_update(col, trains, index)
                    return changed

                if "stops" not in train: train["stops"] = []
                formatted_value = self._format_time(value)
                
                # 管理用インデックス stop_idx を使用して、該当する駅訪問データを特定
                stop = next((s for s in train["stops"] if s.get("stop_idx") == stop_idx), None)

                if not stop:
                    # 時刻が入力されていない場合は、新しいstopを作成しない
                    if formatted_value is None:
                        return False

                    # 運行系統内の路線ごとの始点駅であれば到着時刻をNoneに、終点駅であれば発車時刻をNoneに設定
                    config_for_stop = self.full_stop_configs[stop_idx]
                    initial_arrival_time = None
                    initial_departure_time = None

                    stop = {
                        "station_id": sid,
                        "line_id": lid,
                        "direction": ldir,
                        "track_id": config["track_id"],
                        "arrival_time": initial_arrival_time,
                        "departure_time": initial_departure_time,
                        "stop_type": 1,
                        "stop_idx": stop_idx
                    }
                    train["stops"].append(stop)
                time_key = "arrival_time" if row_def["type"] == "arr" else "departure_time"
                other_key = "departure_time" if row_def["type"] == "arr" else "arrival_time"
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
                        if not config.get("is_segment_start") and not config.get("is_segment_end") and \
                           not station_data.get("show_arrival_time"):
                            stop["arrival_time"] = formatted_value

                    stop["track_id"] = config["track_id"]
                    changed = True
        if changed:
            self._trigger_update(col, trains, index)
            return True
        return False

    def _trigger_update(self, col, trains, index):
        for i in range(col + 1):
            tid = self.train_ids[i]
            t = trains.get(tid)
            if t and t.get("to_be_saved") is False: t["to_be_saved"] = True
        QTimer.singleShot(0, lambda: self.update_data(self.route_id, self.diagram_id, self.direction))
        self.dataChanged.emit(index, index, [Qt.EditRole, Qt.DisplayRole])

    def rowCount(self, parent=QModelIndex()):
        return len(self.row_headers) + len(self.station_rows) + 1

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
        trains = tbd.get(train_key, {})
        if col >= len(self.train_ids): return None
        train_id = self.train_ids[col]
        train = trains.get(train_id, {})

        if role == Qt.TextAlignmentRole:
            # フッター行（ボタン行）は中央揃え
            num_rows_before_footer = len(self.row_headers) + len(self.station_rows)
            if row == num_rows_before_footer:
                return Qt.AlignCenter
            if row < len(self.row_headers):
                return Qt.AlignCenter
            return Qt.AlignRight | Qt.AlignVCenter

        if role == Qt.BackgroundRole:
            tt = self.project.train_types.get(train.get("train_type_id"))
            return QColor(tt.get("background_color", "#ffffff")) if tt else None
        if role == Qt.ForegroundRole:
            if row in (0, 3):
                tt = self.project.train_types.get(train.get("train_type_id"))
                if tt: return QColor(tt.get("main_color", "#333333"))
            if row >= len(self.row_headers):
                val = self.data(index, Qt.DisplayRole)
                secs = self._time_to_seconds(val)
                if secs is not None:
                    for r in range(row - 1, len(self.row_headers) - 1, -1):
                        p_val = self.data(self.index(r, col), Qt.DisplayRole)
                        p_secs = self._time_to_seconds(p_val)
                        if p_secs is not None:
                            if secs < p_secs: return QColor(Qt.red)
                            break
            return None
        if role in (Qt.DisplayRole, Qt.EditRole):
            if row == 0: return train.get("train_number", "")
            elif row == 1:
                ops = [str(op.get("operation_id", "")) for op in train.get("operations", []) if op.get("operation_id")]
                return ",".join(ops) if ops else ""
            elif row == 2:
                cc = train.get("car_count")
                return str(cc) if cc is not None else ""
            elif row == 3:
                tt = self.project.train_types.get(train.get("train_type_id"))
                name = (tt.get("train_type_short_name") or tt.get("train_type_name", "")) if tt else ""
                tname = train.get("train_name")
                return f"{name} {tname}" if tname else name
            elif row == 4:
                val = train.get("named_train_number")
                return str(val) if val is not None else ""
            elif row == 5: return train.get("destination", "")
            elif row >= len(self.row_headers):
                row_idx = row - len(self.row_headers)
                if row_idx < len(self.station_rows):
                    row_def = self.station_rows[row_idx]
                    # 管理用インデックス stop_idx を使用してデータを特定
                    stop = next((s for s in train.get("stops", []) if s.get("stop_idx") == row_def["stop_idx"]), None)

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
                if section == len(self.row_headers) + len(self.station_rows): return "連続する列車"
            elif role == Qt.TextAlignmentRole:
                if 0 <= section < len(self.row_headers): return Qt.AlignCenter
                if section == len(self.row_headers) + len(self.station_rows): return Qt.AlignCenter
                return Qt.AlignRight | Qt.AlignVCenter
        return None

    def _get_next_editable_index(self, current_index: QModelIndex) -> QModelIndex:
        return self.index(current_index.row() + 1, current_index.column())
