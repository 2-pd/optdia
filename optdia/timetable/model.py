import random
import string
import re
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QTimer, Signal
from PySide6.QtGui import QColor
from project import OptDiaProject

TrackIdRole = Qt.UserRole + 100

# メインウィンドウの時刻表テーブルに紐付けられるモデル
class TimetableModel(QAbstractTableModel):
    trainsReordered = Signal()

    def __init__(self, project: OptDiaProject):
        super().__init__()
        self.project = project
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

    def move_train(self, from_idx, to_idx):
        if from_idx == to_idx:
            return

        item = self.train_ids.pop(from_idx)
        self.train_ids.insert(to_idx, item)

        converted = False
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
                                converted = True

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
                
                # 駅情報の逆引き用マップ（normalizationの高速化用）
                self._stop_lookup = {}
                for i, cfg in enumerate(self.full_stop_configs):
                    key = (cfg["station_id"], cfg["line_id"], cfg["direction"])
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
            sid, lid, ldir = s["station_id"], s["line_id"], s["direction"]
            # 高速な逆引きを使用して stop_idx を特定
            key = (sid, lid, ldir)
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

        # 「運転日」行 (index 1) と「運用番号」行 (index 2) は編集不可
        if index.row() == 2: # 運用番号行のみ編集不可
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
        
        d_trains = tbd.get(train_key, {})
        m_trains = route.get(train_key, {})
        
        train_id = self.train_ids[col]
        d_train = d_trains.get(train_id)
        m_train = m_trains.get(train_id)
        if not d_train or not m_train: return False
        
        changed = False
        if row == 0: # 列車番号
            if m_train.get("train_number") != value:
                m_train["train_number"] = value
                changed = True
        elif row == 1 or row == 2: # 運転日または運用番号 (ボタンなので直接編集不可)
            # 運用番号はデリゲートで処理されるため、直接のテキスト入力は受け付けない
            return False
        elif row == 3: # 両数
            try:
                val = int(value) if value and value.strip() else None
                if d_train.get("car_count") != val:
                    d_train["car_count"] = val
                    changed = True
            except ValueError: return False
        elif row == 4: # 種別・愛称
            if m_train.get("train_type_id") != value:
                m_train["train_type_id"] = value
                changed = True
        elif row == 5: # 号数
            try:
                val = int(value) if value and value.strip() else None
                if m_train.get("named_train_number") != val:
                    m_train["named_train_number"] = val
                    changed = True
            except ValueError: return False
        elif row == 6: # 行き先
            # 空文字列の場合は None に置き換えて保持する
            val = value if value else None
            if d_train.get("destination") != val:
                d_train["destination"] = val
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
                    stop = next((s for s in m_train.get("stops", []) if s.get("stop_idx") == stop_idx), None)
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
                        m_train["stops"].append(stop)
                        changed = True
                    elif stop.get("track_id") != value:
                        stop["track_id"] = value
                        changed = True
                    
                    if changed:
                        self._trigger_update(col, d_trains, index)
                    return changed

                if "stops" not in m_train: m_train["stops"] = []
                formatted_value = self._format_time(value)
                
                # 管理用インデックス stop_idx を使用して、該当する駅訪問データを特定
                stop = next((s for s in m_train["stops"] if s.get("stop_idx") == stop_idx), None)

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
                    m_train["stops"].append(stop)
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
        
        d_trains = tbd.get(train_key, {})
        m_trains = route.get(train_key, {})
        
        if col >= len(self.train_ids): return None
        train_id = self.train_ids[col]
        
        d_train = d_trains.get(train_id, {})
        m_train = m_trains.get(train_id, {})

        if role == Qt.TextAlignmentRole:
            # フッター行と「運転日」行は中央揃え
            num_rows_before_footer = len(self.row_headers) + len(self.station_rows)
            if row == num_rows_before_footer or row == 1:
                return Qt.AlignCenter
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
            elif row == 4: # 種別・愛称
                tt = self.project.train_types.get(m_train.get("train_type_id"))
                if tt: return QColor(tt.get("main_color", "#333333"))
            elif row == 6: # 行き先
                if not d_train.get("destination"):
                    return QColor(Qt.gray)
            if row >= len(self.row_headers):
                val = self.data(index, Qt.EditRole) # 秒を含む正確な時刻で比較
                secs = self._time_to_seconds(val)
                if secs is not None:
                    # 運転日行と運用番号行をスキップして前の時刻を探す
                    # row_headersの長さが7になったので、時刻行の開始は7から
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
            elif row == 1: # 運転日 (新しく追加された行)
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
            elif row == 2: # 運用番号 (旧row 1)
                ops = [str(op.get("operation_id", "")) for op in d_train.get("operations", []) if op.get("operation_id")]
                return ",".join(ops) if ops else ""
            elif row == 3: # 両数 (旧row 2)
                cc = d_train.get("car_count")
                return str(cc) if cc is not None else ""
            elif row == 4: # 種別・愛称 (旧row 3)
                tt = self.project.train_types.get(m_train.get("train_type_id"))
                name = (tt.get("train_type_short_name") or tt.get("train_type_name", "")) if tt else ""
                tname = m_train.get("train_name")
                return f"{name} {tname}" if tname else name
            elif row == 5: # 号数 (旧row 4)
                val = m_train.get("named_train_number")
                return str(val) if val is not None else ""
            elif row == 6: # 行き先 (旧row 5)
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
        """行き先を再帰的に解決する。未入力なら終着駅を返す。
        Returns: (destination_string, is_branched)
        """
        if depth >= 5:
            return self._get_terminal_station_name(m_train), False

        dest = d_train.get("destination")
        if dest:
            return dest, False

        subs = d_train.get("subsequent_trains", [])
        if not force_single and len(subs) >= 2:
            # 再帰探索の過程で初めて複数の連続する列車を検出した場合
            results = []
            for sub_info in subs[:2]:
                st_d, st_m = self._get_train_pair_from_sub_info(sub_info, diagram_id)
                # 分岐後の探査では、さらなる分岐は追わず1つ目のみを辿る
                res, _ = self._resolve_destination(st_d, st_m, diagram_id, depth + 1, force_single=True) if st_d else (self._get_terminal_station_name(m_train), False)
                # 分岐表示用の文字数制限を適用
                results.append(res[:3] + ".." if len(res) > 4 else res)
            return "/".join(results), True

        if subs:
            st_d, st_m = self._get_train_pair_from_sub_info(subs[0], diagram_id)
            if st_d:
                return self._resolve_destination(st_d, st_m, diagram_id, depth + 1, force_single=force_single)

        return self._get_terminal_station_name(m_train), False
