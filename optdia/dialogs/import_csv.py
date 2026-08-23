import csv
import re
import random
import string
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton, QMessageBox, QFileDialog, QLabel, QComboBox, QProgressDialog, QApplication
)
from PySide6.QtCore import Qt

# インポートオプションダイアログ
class ImportCsvSettingsDialog(QDialog):
    def __init__(self, route_name, diagram_name, direction_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("インポートオプション")
        self.resize(420, 280)
        
        layout = QVBoxLayout(self)

        # インポート対象をラベルに表示
        self.lbl_target = QLabel("インポート対象:", self)
        label_text = f"{route_name} / {diagram_name} {direction_text}"
        self.lbl_target_info = QLabel(label_text, self)
        self.lbl_target_info.setStyleSheet("font-size: 16px; padding-left: 10px;")
        layout.addWidget(self.lbl_target)
        layout.addWidget(self.lbl_target_info)
        
        layout.addSpacing(20)
        
        # CSVファイルの文字コードを選択するためのコンボボックス
        self.lbl_encoding = QLabel("CSVファイルの文字コード:", self)
        self.combo_encoding = QComboBox(self)
        self.combo_encoding.addItem("UTF-8", "utf-8-sig")
        self.combo_encoding.addItem("Shift-JIS", "shift-jis")
        self.combo_encoding.setCurrentIndex(0)
        layout.addWidget(self.lbl_encoding)
        layout.addWidget(self.combo_encoding)
        
        layout.addSpacing(20)
        
        # チェックボックス
        self.chk_delete_existing = QCheckBox("既存の列車を全て削除してからインポート", self)
        self.chk_delete_existing.setChecked(False)
        layout.addWidget(self.chk_delete_existing)
        
        self.chk_skip_duplicate_number = QCheckBox("既存の列車と列車番号が重複する列車を除外", self)
        self.chk_skip_duplicate_number.setChecked(False)
        layout.addWidget(self.chk_skip_duplicate_number)
        
        self.chk_delete_existing.stateChanged.connect(self._on_delete_existing_changed)
        
        layout.addStretch()
        
        # ボタン (OK / キャンセル)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_ok = QPushButton("OK", self)
        self.btn_cancel = QPushButton("キャンセル", self)
        
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(btn_layout)

    def _on_delete_existing_changed(self, state):
        """「既存の列車を全て削除してからインポート」の状態変化に応じて「重複除外」チェックを制御"""
        self.chk_skip_duplicate_number.setEnabled(state == 0)


def parse_csv_time(val):
    if not val:
        return None, False
    val = str(val).strip()
    if not val:
        return None, False
        
    # 全角数字・コロン・はてなマークを半角に変換
    table = str.maketrans("０１２３４５６７８９：？", "0123456789:?")
    val = val.translate(table)
    
    is_passing = False
    if val.endswith("?"):
        is_passing = True
        val = val[:-1].strip()

    if not val:
        return None, False
        
    # コロン形式のパース
    if ":" in val:
        parts = val.split(":")
        try:
            if len(parts) == 2:
                hh = int(parts[0])
                mm = int(parts[1])
                ss = 0
            elif len(parts) >= 3:
                hh = int(parts[0])
                mm = int(parts[1])
                ss = int(parts[2])
            else:
                return None, False
            if 0 <= hh <= 99 and 0 <= mm < 60 and 0 <= ss < 60:
                return f"{hh:02d}:{mm:02d}:{ss:02d}", is_passing
        except ValueError:
            pass
        return None, False
        
    # 数値形式のパース
    if val.isdigit():
        n = len(val)
        try:
            if 1 <= n <= 2:
                hh = 0
                mm = int(val)
                ss = 0
            elif 3 <= n <= 4:
                mm = int(val[-2:])
                hh = int(val[:-2])
                ss = 0
            elif 5 <= n <= 6:
                ss = int(val[-2:])
                mm = int(val[-4:-2])
                hh = int(val[:-4])
            else:
                return None, False
            if 0 <= hh <= 99 and 0 <= mm < 60 and 0 <= ss < 60:
                return f"{hh:02d}:{mm:02d}:{ss:02d}", is_passing
        except ValueError:
            pass
            
    return None, False


def time_to_seconds(text):
    if not text:
        return None
    try:
        parts = text.split(':')
        if len(parts) == 3:
            h, m, s = map(int, parts)
            return h * 3600 + m * 60 + s
    except (ValueError, AttributeError):
        pass
    return None


def _add_seconds_to_time(time_str, seconds):
    """時刻文字列(HH:MM:SS)に指定秒数を加算して返す"""
    if not time_str:
        return time_str
    parts = time_str.split(':')
    if len(parts) == 3:
        try:
            total = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2]) + seconds
            h = total // 3600
            m = (total % 3600) // 60
            s = total % 60
            return f"{h:02d}:{m:02d}:{s:02d}"
        except ValueError:
            pass
    return time_str


# 丸かっこ(半角・全角)とその内容を除去する正規表現
_PAREN_RE = re.compile(r'[\(（][^\)）]*[\)）]')


# CSVから時刻表をインポートする処理の本体
def import_timetable_from_csv(parent_window):
    # 1. 表示状態チェック
    is_displayed = False
    if hasattr(parent_window, "right_stack") and hasattr(parent_window, "timetable_content_stack"):
        if parent_window.right_stack.currentIndex() == 0 and parent_window.timetable_content_stack.currentIndex() == 0:
            is_displayed = True
            
    # モデルおよびroute_id / diagram_idの確認
    model = getattr(parent_window, "timetable_model", None)
    if not model or not model.route_id or not model.diagram_id:
        is_displayed = False
        
    if not is_displayed:
        QMessageBox.warning(parent_window, "警告", "インポート先の時刻表が表示されていません")
        return
        
    # 2. ファイル選択ダイアログを表示
    filepath, _ = QFileDialog.getOpenFileName(
        parent_window,
        "時刻表をCSVからインポート",
        "",
        "CSVファイル (*.csv)"
    )
    if not filepath:
        return
        
    # 3. インポートオプションダイアログを表示
    route_name = parent_window.route_list_widget.currentItem().text()
    diagram_name = parent_window.diagram_list_widget.currentItem().text()
    direction_text = "上り" if model.direction == "inbound" else "下り"
    
    dialog = ImportCsvSettingsDialog(route_name, diagram_name, direction_text, parent_window)
    if dialog.exec() != QDialog.Accepted:
        return
        
    # 4. インポート処理
    encoding = dialog.combo_encoding.currentData()

    progress = QProgressDialog("CSVからデータをインポートしています...", None, 0, 0, parent_window)
    progress.setWindowTitle("インポート中")
    progress.setWindowModality(Qt.WindowModal)
    progress.setCancelButton(None)
    progress.show()
    QApplication.processEvents()

    try:
        project = model.project
        route_id = model.route_id
        diagram_id = model.diagram_id
        direction = model.direction
        
        route = project.routes.get(route_id)
        if not route:
            raise ValueError("運行系統が見つかりません。")

        # CSV読み込み
        with open(filepath, "r", newline="", encoding=encoding) as f:
            reader = csv.reader(f)
            csv_rows = list(reader)
        
        if not csv_rows:
            progress.close()
            QMessageBox.warning(parent_window, "警告", "CSVファイルが空です。")
            return
            
        # 発着の区別列(2列目)があるかどうかを判定
        # いずれかのメタデータ行が存在し、かつ2列目のそのすべてが空欄である場合
        metadata_headers = ["列車番号", "列番", "運転日", "運用番号", "運番", "運用", "両数", "種別", "列車種別", "号数", "行き先", "行先", "連続する列車", "備考"]
        has_metadata = False
        all_col1_empty = True
        
        for row in csv_rows:
            if not row:
                continue
            header = row[0].strip()
            # メタデータ行かどうかの判定 (前方一致含む)
            is_meta = any(header.startswith(h) for h in metadata_headers)
            if is_meta:
                has_metadata = True
                if len(row) > 1 and row[1].strip() != "":
                    all_col1_empty = False
                    
        has_distinction_col = has_metadata and all_col1_empty
        
        # 行のフィルタリングとパース
        parsed_rows = []
        station_rows_parsed = []
        
        # 運行系統内の全駅IDと名前のマップ
        full_stop_configs = model.full_stop_configs
        route_station_names = {}
        for cfg in full_stop_configs:
            sid = cfg["station_id"]
            s_data = project.stations.get(sid, {})
            name = s_data.get("station_name", sid)
            route_station_names[name] = sid
            
        for r_idx, row in enumerate(csv_rows):
            if not row:
                continue
            header = row[0].strip()
            
            # 発着区別列のチェック
            distinction_val = ""
            if has_distinction_col and len(row) > 1:
                distinction_val = row[1].strip()
                if distinction_val not in ("", "着", "発"):
                    # 無効な文字がある場合は行自体を無視
                    continue
            
            # 列車データの開始列インデックス
            start_col = 2 if has_distinction_col else 1
            train_cols = [c.strip() for c in row[start_col:]]
            
            # メタデータ行の判定
            matched_header = None
            for mh in metadata_headers:
                if header.startswith(mh):
                    matched_header = mh
                    break
                    
            if matched_header:
                parsed_rows.append({
                    "type": "metadata",
                    "key": matched_header,
                    "values": train_cols
                })
            else:
                # 駅行判定
                # ヘッダーから [着], [発] を抽出
                station_name = header
                type_hint = None
                if header.endswith("[着]"):
                    station_name = header[:-3].strip()
                    type_hint = "arrival"
                elif header.endswith("[発]"):
                    station_name = header[:-3].strip()
                    type_hint = "departure"
                elif header.endswith(" [着]"):
                    station_name = header[:-4].strip()
                    type_hint = "arrival"
                elif header.endswith(" [発]"):
                    station_name = header[:-4].strip()
                    type_hint = "departure"
                    
                # 駅名マッチング(丸かっこ除去フォールバック付き)
                matched_sid = route_station_names.get(station_name)
                if matched_sid is None and _PAREN_RE.search(station_name):
                    _stripped_name = _PAREN_RE.sub("", station_name).strip()
                    matched_sid = route_station_names.get(_stripped_name)
                    
                if matched_sid is not None:
                    station_id = matched_sid
                    # 行のタイプ決定
                    row_type = type_hint
                    if row_type is None:
                        if has_distinction_col and distinction_val in ("着", "発"):
                            row_type = "arrival" if distinction_val == "着" else "departure"
                        else:
                            row_type = "both"
                            
                    station_rows_parsed.append({
                        "station_id": station_id,
                        "station_name": station_name,
                        "type": row_type,
                        "values": train_cols
                    })
                    
        # 列車列の数
        num_trains = 0
        for r in parsed_rows:
            num_trains = max(num_trains, len(r["values"]))
        for r in station_rows_parsed:
            num_trains = max(num_trains, len(r["values"]))
            
        if num_trains == 0:
            progress.close()
            QMessageBox.information(parent_window, "情報", "インポートする列車データが見つかりませんでした。")
            return
            
        # 既存列車の削除処理
        tbd = route.setdefault("trains_by_diagram", {}).setdefault(diagram_id, {})
        train_key = "inbound_trains" if direction == "inbound" else "outbound_trains"
        order_key = f"{train_key}_order"
        m_trains = route.setdefault(train_key, {})
        
        tbd.setdefault(train_key, {})
        tbd.setdefault(order_key, [])
        
        if dialog.chk_delete_existing.isChecked():
            tids_to_remove = [tid for tid in tbd[order_key] if tbd[train_key].get(tid, {}).get("to_be_saved") is True]
            for tid in tids_to_remove:
                if tid in tbd[order_key]:
                    tbd[order_key].remove(tid)
                if tid in tbd[train_key]:
                    del tbd[train_key][tid]
                m_train = m_trains.get(tid)
                if m_train:
                    if diagram_id in m_train.get("_diagram_ids", []):
                        m_train["_diagram_ids"].remove(diagram_id)
                    if not m_train.get("_diagram_ids"):
                        if tid in m_trains:
                            del m_trains[tid]
                            
        # 新規列車インポート
        imported_train_ids = []
        imported_train_subsequents = [] # (new_tid, raw_subsequent_str, diagram_id) 一時保存用
        
        chars = string.ascii_letters + string.digits
        
        # 重複列車番号チェック用に既存列車番号セットを収集
        existing_train_numbers = set()
        if not dialog.chk_delete_existing.isChecked() and dialog.chk_skip_duplicate_number.isChecked():
            for _tid in tbd.get(order_key, []):
                _dt = tbd.get(train_key, {}).get(_tid)
                if _dt and _dt.get("to_be_saved"):
                    _mt = m_trains.get(_tid, {})
                    _tn = _mt.get("train_number", "")
                    if _tn:
                        existing_train_numbers.add(_tn)
        
        # 深夜列車の24時間オフセット判定 - 各列車の始発時刻を収集
        _first_times = []
        for _ci in range(num_trains):
            _ft = None
            for _row in station_rows_parsed:
                _t_str = _row["values"][_ci] if _ci < len(_row["values"]) else ""
                _t_val, _ = parse_csv_time(_t_str)
                if _t_val is not None:
                    _ft = time_to_seconds(_t_val)
                    break
            _first_times.append(_ft)
        
        midnight_offset_flags = [False] * num_trains
        _seen_evening = False
        for _ci in range(num_trains):
            _t = _first_times[_ci]
            if _t is not None:
                if _t >= 18 * 3600:
                    _seen_evening = True
                elif _seen_evening and _t < 6 * 3600:
                    midnight_offset_flags[_ci] = True
        
        for col_idx in range(num_trains):
            QApplication.processEvents()
            # メタデータ抽出
            train_number = None
            operation_day = None
            operation_number = None
            car_count = None
            train_type_str = None
            named_train_number = None
            destination = None
            subsequent_str = None
            note = None
            
            for pr in parsed_rows:
                vals = pr["values"]
                val = vals[col_idx] if col_idx < len(vals) else ""
                val = val.strip()
                if not val:
                    continue
                    
                key = pr["key"]
                if key in ("列車番号", "列番"):
                    train_number = val
                elif key == "運転日":
                    operation_day = val
                elif key in ("運用番号", "運番", "運用"):
                    operation_number = val
                elif key == "両数":
                    # 単位「両」より後ろを除去して数値化
                    val_clean = val.split("両", 1)[0].strip()
                    try:
                        car_count = int(val_clean)
                    except ValueError:
                        car_count = None
                elif key in ("種別", "列車種別"):
                    train_type_str = val
                elif key == "号数":
                    # 単位「号」を除去して数値化
                    val_clean = val.replace("号", "").strip()
                    try:
                        named_train_number = int(val_clean)
                    except ValueError:
                        named_train_number = None
                elif key in ("行き先", "行先"):
                    destination = val
                elif key == "連続する列車":
                    subsequent_str = val
                elif key == "備考":
                    note = val
            
            # 重複列車番号チェック
            if existing_train_numbers and train_number and train_number in existing_train_numbers:
                continue
            
            # 種別が未指定の場合のデフォルト設定 (「普通」→「各駅停車」→「各停」の順で検索、なければ「普通」を新規作成)
            if not train_type_str:
                _default_names = ["普通", "各駅停車", "各停"]
                for _dn in _default_names:
                    for _tt in project.train_types.values():
                        if (_tt.get("train_type_name") == _dn or
                                _tt.get("train_type_short_name") == _dn or
                                _tt.get("train_name") == _dn):
                            train_type_str = _dn
                            break
                    if train_type_str:
                        break
                if not train_type_str:
                    train_type_str = "普通"
                    
            # 列車種別の決定
            train_type_id = None
            if train_type_str:
                # 既存種別を検索
                for ttid, tt in project.train_types.items():
                    if (tt.get("train_type_name") == train_type_str or 
                        tt.get("train_type_short_name") == train_type_str or 
                        tt.get("train_name") == train_type_str):
                        train_type_id = ttid
                        break
                if not train_type_id:
                    # 新規種別を生成
                    while True:
                        new_tt_id = "".join(random.choices(chars, k=10))
                        if new_tt_id not in project.train_types:
                            break
                    new_type = {
                        "train_type_id": new_tt_id,
                        "train_type_name": train_type_str,
                        "train_type_short_name": train_type_str,
                        "train_name": None,
                        "is_in_service": True,
                        "main_color": "#333333",
                        "background_color": "#ffffff",
                        "line_weight": "normal",
                        "line_style": "solid"
                    }
                    project.train_types[new_tt_id] = new_type
                    project.train_types_order.append(new_tt_id)
                    train_type_id = new_tt_id

            # 運転ダイヤ (diagram_ids) の決定
            target_diagrams = [diagram_id]
            if operation_day:
                if operation_day == "(毎日)":
                    target_diagrams = list(project.diagrams_order)
                else:
                    target_diagrams = []
                    # 現在のダイヤは必ず入れる
                    if diagram_id not in target_diagrams:
                        target_diagrams.append(diagram_id)
                    # 他のダイヤを検索
                    for d_id in project.diagrams_order:
                        if d_id == diagram_id:
                            continue
                        diag_data = project.diagrams.get(d_id, {})
                        diag_initial = diag_data.get("diagram_initial") or ""
                        diag_name_first = (diag_data.get("diagram_name") or " ")[0]
                        if diag_initial in operation_day or diag_name_first in operation_day:
                            # 同じ列車番号が既に存在するかチェック
                            if train_number:
                                other_tbd = route.get("trains_by_diagram", {}).get(d_id, {})
                                other_d_trains = other_tbd.get(train_key, {})
                                other_m_trains = route.get(train_key, {})
                                exists = False
                                for o_tid in other_d_trains:
                                    o_m = other_m_trains.get(o_tid, {})
                                    if o_m.get("train_number") == train_number:
                                        exists = True
                                        break
                                if exists:
                                    continue
                            target_diagrams.append(d_id)
                            
            # 列車ID生成
            while True:
                new_tid = "".join(random.choices(chars, k=16))
                if new_tid not in m_trains:
                    break
                    
            # 各ダイヤでの運用番号(operation)の生成と設定
            # 運用番号はダイヤ毎に独立して管理されるため、ダイヤ毎に処理する
            diagram_ops_map = {} # diag_id -> [op_ids]
            
            for d_id in target_diagrams:
                ops_list = []
                if operation_number:
                    diag_data = project.diagrams.get(d_id, {})
                    ops_dict = diag_data.setdefault("operations", {})
                    op_groups = diag_data.setdefault("operation_groups", {})
                    op_groups_order = diag_data.setdefault("operation_groups_order", [])
                    
                    parts = [p.strip() for p in operation_number.split("+") if p.strip()]
                    for part in parts:
                        # 既存の運用番号を検索
                        found_op_id = None
                        for op_id, op_val in ops_dict.items():
                            if op_val.get("operation_number") == part:
                                found_op_id = op_id
                                break
                        if not found_op_id:
                            # 運用を新規作成
                            while True:
                                new_op_id = "".join(random.choices(chars, k=10))
                                if new_op_id not in ops_dict:
                                    break
                            new_op = {
                                "operation_number": part,
                                "car_count": 0,
                                "min_car_count": 0,
                                "max_car_count": 0,
                                "main_color": "#ffffff",
                                "start_location": "",
                                "start_track": None,
                                "start_time": None,
                                "end_location": "",
                                "end_track": None,
                                "end_time": None,
                                "note": "",
                                "temporary_stabling_events": []
                            }
                            ops_dict[new_op_id] = new_op
                            found_op_id = new_op_id
                            
                            # 「インポートされた運用」グループへの所属
                            group_id = None
                            for og_id, og_val in op_groups.items():
                                if og_val.get("operation_group_name") == "インポートされた運用":
                                    group_id = og_id
                                    break
                            if not group_id:
                                while True:
                                    new_og_id = "".join(random.choices(chars, k=8))
                                    if new_og_id not in op_groups:
                                        break
                                new_group = {
                                    "operation_group_id": new_og_id,
                                    "operation_group_name": "インポートされた運用",
                                    "main_color": "#ffffff",
                                    "operations": []
                                }
                                op_groups[new_og_id] = new_group
                                op_groups_order.append(new_og_id)
                                group_id = new_og_id
                                
                            op_groups[group_id].setdefault("operations", []).append(found_op_id)
                        ops_list.append({
                            "operation_id": found_op_id,
                            "formation_is_reversed": False
                        })
                diagram_ops_map[d_id] = ops_list

            # 駅時刻データの抽出（各CSV駅行ごと）
            # sid -> list of {type, arr_time, dep_time, arr_passing, dep_passing}
            station_csv_data = {}
            for row in station_rows_parsed:
                sid = row["station_id"]
                t_str = row["values"][col_idx] if col_idx < len(row["values"]) else ""
                t_val, is_passing = parse_csv_time(t_str)
                t_type = row["type"]
                
                if sid not in station_csv_data:
                    station_csv_data[sid] = []
                station_csv_data[sid].append({
                    "type": t_type,
                    "val": t_val,
                    "is_passing": is_passing,
                    "raw_str": t_str
                })

            # この列車が実際に通過/停車するフルコンフィグ上のインデックス範囲を特定
            # CSV上に時刻が存在する駅の最初と最後
            first_idx = None
            last_idx = None
            for idx, cfg in enumerate(full_stop_configs):
                sid = cfg["station_id"]
                data_list = station_csv_data.get(sid, [])
                if any(d["val"] is not None for d in data_list):
                    if first_idx is None:
                        first_idx = idx
                    last_idx = idx

            stops_raw = []
            if first_idx is not None and last_idx is not None:
                # 始発から終着までの経由駅候補を走査
                for cfg_idx in range(first_idx, last_idx + 1):
                    cfg = full_stop_configs[cfg_idx]
                    sid = cfg["station_id"]
                    
                    data_list = station_csv_data.get(sid, [])
                    configs_for_sid = [(i, c) for i, c in enumerate(full_stop_configs) if c["station_id"] == sid]
                    config_pos = [i for i, c in configs_for_sid].index(cfg_idx)

                    # デフォルト stop_dict
                    stop_dict = {
                        "segment_id": cfg["segment_id"],
                        "station_id": sid,
                        "arrival_time": None,
                        "departure_time": None,
                        "track_id": cfg.get("track_id"),
                        "stop_type": 1
                    }

                    # CSVデータの紐付け logic
                    arr_val, arr_pass = None, False
                    dep_val, dep_pass = None, False

                    if len(data_list) == 1 and len(configs_for_sid) == 1:
                        # 通常の1駅1区間
                        d = data_list[0]
                        if d["type"] == "arrival":
                            arr_val, arr_pass = d["val"], d["is_passing"]
                        elif d["type"] == "departure":
                            dep_val, dep_pass = d["val"], d["is_passing"]
                        else: # both
                            if cfg_idx != first_idx:
                                arr_val, arr_pass = d["val"], d["is_passing"]
                            if cfg_idx != last_idx:
                                dep_val, dep_pass = d["val"], d["is_passing"]

                    elif len(data_list) == 2 and len(configs_for_sid) == 1:
                        # 1駅1区間だが着行と発行が分かれている
                        for d in data_list:
                            if d["type"] == "arrival":
                                arr_val, arr_pass = d["val"], d["is_passing"]
                            elif d["type"] == "departure":
                                dep_val, dep_pass = d["val"], d["is_passing"]
                            else:
                                if d == data_list[0]:
                                    arr_val, arr_pass = d["val"], d["is_passing"]
                                else:
                                    dep_val, dep_pass = d["val"], d["is_passing"]

                    elif len(configs_for_sid) > 1:
                        # 境界駅（複数部分区間に跨る）
                        # 列車がこの境界駅を跨いで運転されているか判定
                        is_train_start_here = (cfg_idx == first_idx)
                        is_train_end_here = (cfg_idx == last_idx)
                        is_intermediate_boundary = (not is_train_start_here and not is_train_end_here)

                        if len(data_list) >= len(configs_for_sid) and config_pos < len(data_list):
                            # CSV行も複数行記載されている場合
                            d = data_list[config_pos]
                            if d["type"] == "arrival":
                                arr_val, arr_pass = d["val"], d["is_passing"]
                            elif d["type"] == "departure":
                                dep_val, dep_pass = d["val"], d["is_passing"]
                            else:
                                if not cfg.get("is_segment_start"):
                                    arr_val, arr_pass = d["val"], d["is_passing"]
                                if not cfg.get("is_segment_end"):
                                    dep_val, dep_pass = d["val"], d["is_passing"]
                        else:
                            # CSV行が1行にまとまっている場合
                            d = data_list[0] if data_list else {"val": None, "is_passing": False, "type": "both"}
                            if is_train_end_here:
                                # 終着駅として着のみ
                                arr_val, arr_pass = d["val"], d["is_passing"]
                            elif is_train_start_here:
                                # 始発駅として発のみ
                                dep_val, dep_pass = d["val"], d["is_passing"]
                            elif is_intermediate_boundary:
                                # 部分区間Aの着時刻のみ (config_pos == 0) / 部分区間Bの発時刻のみ (config_pos == 1)
                                if config_pos == 0:
                                    arr_val, arr_pass = d["val"], d["is_passing"]
                                else:
                                    dep_val, dep_pass = d["val"], d["is_passing"]

                    # 発時刻の行しか存在しない場合の補填
                    has_arr_or_both = any(d["type"] in ("arrival", "both") for d in data_list)
                    if not has_arr_or_both and dep_val and not arr_val and cfg_idx != first_idx:
                        arr_val, arr_pass = dep_val, dep_pass

                    stop_dict["arrival_time"] = arr_val
                    stop_dict["departure_time"] = dep_val
                    
                    if arr_pass or dep_pass:
                        stop_dict["stop_type"] = 0
                    else:
                        stop_dict["stop_type"] = 1

                    stops_raw.append(stop_dict)
            
            # 深夜列車の24時間オフセット適用
            if midnight_offset_flags[col_idx]:
                for _s in stops_raw:
                    if _s.get("arrival_time"):
                        _s["arrival_time"] = _add_seconds_to_time(_s["arrival_time"], 86400)
                    if _s.get("departure_time"):
                        _s["departure_time"] = _add_seconds_to_time(_s["departure_time"], 86400)
            
            # 時刻逆戻り補正: 前の時刻より小さい時刻が出たら24時間加算
            _prev_secs = None
            for _s in stops_raw:
                for _time_key in ("arrival_time", "departure_time"):
                    _t = _s.get(_time_key)
                    if _t is None:
                        continue
                    _t_secs = time_to_seconds(_t)
                    if _t_secs is None:
                        continue
                    if _prev_secs is not None and _t_secs < _prev_secs:
                        _s[_time_key] = _add_seconds_to_time(_t, 86400)
                        _t_secs += 86400
                    _prev_secs = _t_secs
            
            # 4. 各列車の経由駅情報の検査と補填処理
            num_stops = len(stops_raw)
            for s_idx, stop_item in enumerate(stops_raw):
                sid = stop_item["station_id"]
                s_data = project.stations.get(sid, {})
                show_arr = s_data.get("show_arrival_time", False)

                is_first_station = (s_idx == 0)
                is_last_station = (s_idx == num_stops - 1)

                if is_first_station and show_arr:
                    stop_item["arrival_time"] = None

                if is_last_station and show_arr:
                    stop_item["departure_time"] = None

                # 全経由駅での None の補填（始発駅の着時刻、終着駅の発時刻を除く）
                if not is_first_station and stop_item["arrival_time"] is None and stop_item["departure_time"] is not None:
                    stop_item["arrival_time"] = stop_item["departure_time"]

                if not (is_last_station and show_arr) and stop_item["departure_time"] is None and stop_item["arrival_time"] is not None:
                    stop_item["departure_time"] = stop_item["arrival_time"]

                # 上記に関わらず、各部分区間(optdia_line_segment)の端点駅における着時刻/発時刻のクリア
                seg_id = stop_item["segment_id"]

                # optdia_line_segment での始点駅・終点駅を特定
                seg_start_station = None
                seg_end_station = None
                for seg in route.get("line_segments", []):
                    if seg.get("segment_id") == seg_id:
                        if direction == "outbound":
                            seg_start_station = seg.get("start_station")
                            seg_end_station = seg.get("end_station")
                        else: # inbound
                            seg_start_station = seg.get("end_station")
                            seg_end_station = seg.get("start_station")
                        break

                if sid == seg_start_station:
                    stop_item["arrival_time"] = None
                if sid == seg_end_station:
                    stop_item["departure_time"] = None

            # 空の経由駅情報を除去
            stops_clean = [s for s in stops_raw if s.get("arrival_time") is not None or s.get("departure_time") is not None]
            
            # 各部分区間 (segment_id) の経由駅数が1つしかない場合、その経由駅情報を除去
            from collections import Counter
            seg_counts = Counter(s["segment_id"] for s in stops_clean if "segment_id" in s)
            stops_clean = [s for s in stops_clean if seg_counts.get(s.get("segment_id"), 0) > 1]
            
            # マスタ列車の保存
            m_train = {
                "train_number": train_number or "",
                "train_type_id": train_type_id,
                "named_train_number": named_train_number,
                "note": note or "",
                "stops": stops_clean,
                "_diagram_ids": sorted(target_diagrams, key=lambda x: project.diagrams_order.index(x) if x in project.diagrams_order else 999)
            }
            m_trains[new_tid] = m_train
            imported_train_ids.append(new_tid)
            
            # ダイヤ別列車の保存
            for d_id in target_diagrams:
                d_tbd = route.setdefault("trains_by_diagram", {}).setdefault(d_id, {})
                d_trains = d_tbd.setdefault(train_key, {})
                d_order = d_tbd.setdefault(order_key, [])
                
                d_train = {
                    "train_id": new_tid,
                    "operations": diagram_ops_map.get(d_id, []),
                    "car_count": car_count,
                    "destination": destination,
                    "subsequent_trains": [],
                    "to_be_saved": True
                }
                d_trains[new_tid] = d_train
                
                # 末尾のダミー列車(to_be_saved=False)より前に挿入
                insert_idx = len(d_order)
                for idx_check, check_tid in enumerate(d_order):
                    if not d_trains.get(check_tid, {}).get("to_be_saved", True):
                        insert_idx = idx_check
                        break
                d_order.insert(insert_idx, new_tid)
                
                if subsequent_str:
                    imported_train_subsequents.append((new_tid, subsequent_str, d_id))
                    
        # 5. 連続する列車(subsequent_trains)の関連付け
        for tid, sub_str, d_id in imported_train_subsequents:
            d_tbd = route.get("trains_by_diagram", {}).get(d_id, {})
            d_train = d_tbd.get(train_key, {}).get(tid)
            if not d_train:
                continue
                
            m_train = m_trains.get(tid, {})
            # この列車の最初の発車時刻を特定
            first_dep_secs = None
            for s in m_train.get("stops", []):
                if s.get("departure_time"):
                    first_dep_secs = time_to_seconds(s["departure_time"])
                    break
            if first_dep_secs is None:
                continue
                
            target_nums = [n.strip() for n in sub_str.split(" ") if n.strip()]
            resolved_subs = []
            
            for t_num in target_nums:
                # 全ての運行系統、ダイヤ、方面から列車を検索
                candidates = []
                for r_id in project.routes_order:
                    r_data = project.routes.get(r_id, {})
                    for d_direction in ("inbound", "outbound"):
                        d_train_key = "inbound_trains" if d_direction == "inbound" else "outbound_trains"
                        r_m_trains = r_data.get(d_train_key, {})
                        
                        r_tbd = r_data.get("trains_by_diagram", {}).get(d_id, {})
                        r_d_trains = r_tbd.get(d_train_key, {})
                        
                        for c_tid in r_d_trains:
                            c_m = r_m_trains.get(c_tid, {})
                            if c_m.get("train_number") == t_num:
                                # 終着時刻の特定
                                last_arr_secs = None
                                stops_list = c_m.get("stops", [])
                                # 後ろから探索
                                for stop in reversed(stops_list):
                                    if stop.get("arrival_time"):
                                        last_arr_secs = time_to_seconds(stop["arrival_time"])
                                        break
                                    elif stop.get("departure_time"):
                                        last_arr_secs = time_to_seconds(stop["departure_time"])
                                        break
                                        
                                if last_arr_secs is not None and last_arr_secs <= first_dep_secs:
                                    candidates.append({
                                        "route_id": r_id,
                                        "direction": d_direction,
                                        "train_id": c_tid,
                                        "last_arr_secs": last_arr_secs
                                    })
                                    
                if candidates:
                    # 終着時刻が最も遅いものを選択
                    best_cand = max(candidates, key=lambda x: x["last_arr_secs"])
                    resolved_subs.append({
                        "route_id": best_cand["route_id"],
                        "direction": best_cand["direction"],
                        "train_id": best_cand["train_id"]
                    })
            d_train["subsequent_trains"] = resolved_subs

        # 表示更新と保存フラグ設定
        model.update_data(route_id, diagram_id, direction)
        parent_window.set_modified(True)
        progress.close()
        QMessageBox.information(parent_window, "情報", "CSVインポートが完了しました。")
        
    except Exception as e:
        progress.close()
        import traceback
        traceback.print_exc()
        QMessageBox.critical(parent_window, "エラー", f"CSVインポート中にエラーが発生しました:\n{e}")
