import csv
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton, QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt

# エクスポートオプションダイアログ
class ExportCsvSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("エクスポートオプション")
        self.resize(320, 480)
        
        layout = QVBoxLayout(self)
        
        # チェックボックスの定義
        self.chk_in_service_only = QCheckBox("営業列車以外も出力する", self)
        self.chk_split_station = QCheckBox("発/着の区別を駅名とは別の列に出力", self)
        self.chk_train_number = QCheckBox("列車番号を出力", self)
        self.chk_operation_day = QCheckBox("運転日を出力", self)
        self.chk_operation_number = QCheckBox("運用番号を出力", self)
        self.chk_car_count = QCheckBox("両数を出力", self)
        self.chk_train_type = QCheckBox("種別・愛称を出力", self)
        self.chk_named_number = QCheckBox("号数を出力", self)
        self.chk_destination = QCheckBox("行き先を出力", self)
        self.chk_resolve_destination = QCheckBox("各列車の行き先に連続する列車の行き先を反映", self)
        self.chk_subsequent = QCheckBox("連続する列車を出力", self)
        self.chk_note = QCheckBox("備考を出力", self)
        self.chk_include_pass = QCheckBox("通過・運転停車の時刻も出力する", self)
        self.chk_show_seconds = QCheckBox("発着時刻は秒まで出力する", self)
        self.chk_over24 = QCheckBox("24時以降の時刻表記を使用する", self)
        
        # デフォルトのチェック状態
        self.chk_in_service_only.setChecked(True)
        self.chk_split_station.setChecked(False)
        self.chk_train_number.setChecked(True)
        self.chk_operation_day.setChecked(True)
        self.chk_operation_number.setChecked(True)
        self.chk_car_count.setChecked(True)
        self.chk_train_type.setChecked(True)
        self.chk_named_number.setChecked(True)
        self.chk_destination.setChecked(True)
        self.chk_resolve_destination.setChecked(True)
        self.chk_subsequent.setChecked(True)
        self.chk_note.setChecked(True)
        self.chk_include_pass.setChecked(True)
        self.chk_show_seconds.setChecked(False)
        self.chk_over24.setChecked(True)
        
        # レイアウトへの追加
        layout.addWidget(self.chk_in_service_only)
        layout.addWidget(self.chk_split_station)
        layout.addWidget(self.chk_train_number)
        layout.addWidget(self.chk_operation_day)
        layout.addWidget(self.chk_operation_number)
        layout.addWidget(self.chk_car_count)
        layout.addWidget(self.chk_train_type)
        layout.addWidget(self.chk_named_number)
        layout.addWidget(self.chk_destination)
        layout.addWidget(self.chk_resolve_destination)
        layout.addWidget(self.chk_subsequent)
        layout.addWidget(self.chk_note)
        layout.addWidget(self.chk_include_pass)
        layout.addWidget(self.chk_show_seconds)
        layout.addWidget(self.chk_over24)
        
        # ボタン (OK / キャンセル)
        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton("OK", self)
        self.btn_cancel = QPushButton("キャンセル", self)
        
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(btn_layout)


def _time_str_to_seconds(time_str):
    """「hh:mm:ss」形式の時刻文字列を秒数に変換する。変換できない場合は None を返す。"""
    if not time_str:
        return None
    parts = time_str.split(":")
    if len(parts) != 3:
        return None
    try:
        h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
        return h * 3600 + m * 60 + s
    except (ValueError, TypeError):
        return None


def _format_time(time_str, show_seconds, use_over24):
    """
    「hh:mm:ss」形式の時刻文字列を出力用にフォーマットする。
    - show_seconds: True の場合「hh:mm:ss」形式、False の場合「hh:mm」形式で出力
    - use_over24: False の場合、24時以降の時刻は 24 時間を減算して出力
    空文字列や None の場合は空文字列を返す。
    """
    if not time_str:
        return ""
    secs = _time_str_to_seconds(time_str)
    if secs is None:
        return time_str  # 不正な形式はそのまま返す
    if not use_over24:
        secs = secs % 86400  # 24時間を減算 (86400秒)
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    if show_seconds:
        return f"{h:02d}:{m:02d}:{s:02d}"
    else:
        return f"{h:02d}:{m:02d}"


def _get_train_pair_for_export(sub_info, project, diagram_id):
    """subsequent_trains の情報から (diagram_train, master_train) を取得する"""
    rid = sub_info.get("route_id")
    direction = sub_info.get("direction")
    tid = sub_info.get("train_id")
    if not rid or not direction or not tid:
        return None, None
    route = project.routes.get(rid)
    if not route:
        return None, None
    tbd = route.get("trains_by_diagram", {}).get(diagram_id, {})
    train_key = "inbound_trains" if direction == "inbound" else "outbound_trains"
    d_train = tbd.get(train_key, {}).get(tid)
    m_train = route.get(train_key, {}).get(tid)
    return d_train, m_train


def _get_terminal_station_name_for_export(m_train, project):
    """列車の終着駅名を返す"""
    if not m_train:
        return ""
    stops = m_train.get("stops", [])
    if not stops:
        return ""
    timed_stops = [s for s in stops if s.get("arrival_time") or s.get("departure_time")]
    if not timed_stops:
        return ""
    last_stop = timed_stops[-1]
    sid = last_stop.get("station_id")
    station_data = project.stations.get(sid, {})
    return station_data.get("station_name", sid)


def _resolve_destination_for_export(d_train, m_train, project, diagram_id, depth=0, force_single=False):
    """
    エクスポート用に行き先を解決する。
    - destination が設定されている場合はその値を返す。
    - destination が None の場合は subsequent_trains を再帰探索する（最大5階層）。
    - subsequent_trains に2つ以上の列車がある場合:
        - force_single==False の場合は全件探索し、「/」で連結。
        - そうでない場合は1件目のみ探索。
    - 最終的に行き先が解決できない場合は終着駅名を返す。
    Returns: destination_string (str)
    """
    dest = d_train.get("destination")
    if dest:
        return dest

    if depth >= 5:
        return _get_terminal_station_name_for_export(m_train, project)

    subs = d_train.get("subsequent_trains") or []
    if not subs:
        return _get_terminal_station_name_for_export(m_train, project)

    if len(subs) > 1 and not force_single:
        # force_single でない場合は全件探索して「/」で連結
        results = []
        for i, sub_info in enumerate(subs):
            sub_d, sub_m = _get_train_pair_for_export(sub_info, project, diagram_id)
            if sub_d is not None:
                # 2件目以降は force_single=True で再帰
                sub_dest = _resolve_destination_for_export(
                    sub_d, sub_m, project, diagram_id,
                    depth=depth + 1,
                    force_single=(i > 0)
                )
                results.append(sub_dest)
        return "/".join(r for r in results if r)
    else:
        # 1件目のみ探索
        sub_info = subs[0]
        sub_d, sub_m = _get_train_pair_for_export(sub_info, project, diagram_id)
        if sub_d is not None:
            return _resolve_destination_for_export(
                sub_d, sub_m, project, diagram_id,
                depth=depth + 1,
                force_single=True
            )
        return _get_terminal_station_name_for_export(m_train, project)


# 時刻表をCSVへエクスポートする処理の本体
def export_timetable_to_csv(parent_window):
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
        QMessageBox.warning(parent_window, "警告", "エクスポート対象の時刻表が表示されていません")
        return
        
    # 2. ファイル保存ダイアログを表示
    filepath, _ = QFileDialog.getSaveFileName(
        parent_window,
        "時刻表をCSVにエクスポート",
        "",
        "CSVファイル (*.csv)"
    )
    if not filepath:
        return
        
    # 3. エクスポート設定ダイアログを表示
    dialog = ExportCsvSettingsDialog(parent_window)
    if dialog.exec() != QDialog.Accepted:
        return
        
    # 4. エクスポート処理
    try:
        project = model.project
        route_id = model.route_id
        diagram_id = model.diagram_id
        direction = model.direction

        route = project.routes.get(route_id)
        tbd = route.get("trains_by_diagram", {}).get(diagram_id, {})
        train_key = "inbound_trains" if direction == "inbound" else "outbound_trains"
        d_trains = tbd.get(train_key, {})
        m_trains = route.get(train_key, {})

        # オプション読み取り
        export_non_in_service = dialog.chk_in_service_only.isChecked()
        split_station = dialog.chk_split_station.isChecked()
        resolve_dest = dialog.chk_resolve_destination.isChecked()
        include_pass = dialog.chk_include_pass.isChecked()
        show_seconds = dialog.chk_show_seconds.isChecked()
        use_over24 = dialog.chk_over24.isChecked()

        # 実データを持つ有効な列を抽出 (to_be_saved が True のもののみ)
        # 「営業列車以外も出力する」が未チェックの場合、is_in_service が True でない種別の列車を除外
        valid_cols = []
        for col, train_id in enumerate(model.train_ids):
            d_train = d_trains.get(train_id, {})
            if d_train.get("to_be_saved") is not True:
                continue
            if not export_non_in_service:
                # 列車種別の is_in_service を確認
                m_train = m_trains.get(train_id, {})
                type_id = m_train.get("train_type_id")
                train_type = project.train_types.get(type_id) if type_id else None
                if not (train_type and train_type.get("is_in_service") is True):
                    continue
            valid_cols.append((col, train_id))
                
        rows_to_export = []
        
        # ヘッダー行定義 (行インデックス、ラベル、出力フラグ)
        header_configs = [
            (0, "列車番号", dialog.chk_train_number.isChecked()),
            (1, "運転日", dialog.chk_operation_day.isChecked()),
            (2, "運用番号", dialog.chk_operation_number.isChecked()),
            (3, "両数", dialog.chk_car_count.isChecked()),
            (4, "種別・愛称", dialog.chk_train_type.isChecked()),
            (5, "号数", dialog.chk_named_number.isChecked()),
            (6, "行き先", dialog.chk_destination.isChecked()),
        ]
        
        # 1. 共通ヘッダー行の追加
        for row_idx, label, is_checked in header_configs:
            if is_checked:
                row_data = []
                if split_station:
                    row_data.extend([label, ""])
                else:
                    row_data.append(label)
                for col_idx, train_id in valid_cols:
                    if row_idx == 6 and resolve_dest:
                        # 行き先行：連続する列車の行き先を反映する
                        d_train = d_trains.get(train_id, {})
                        m_train = m_trains.get(train_id, {})
                        raw_dest = d_train.get("destination")
                        if raw_dest:
                            val = raw_dest
                        else:
                            val = _resolve_destination_for_export(d_train, m_train, project, diagram_id)
                    else:
                        val = model.data(model.index(row_idx, col_idx), Qt.DisplayRole) or ""
                    row_data.append(val)
                rows_to_export.append(row_data)
                
        # 2. 駅時刻行の追加
        num_headers = len(model.row_headers)
        num_stations = len(model.station_rows)
        for i in range(num_stations):
            station_row = model.station_rows[i]
            row_idx = num_headers + i
            
            row_data = []
            if split_station:
                # 1列目に駅名、2列目に「着」「発」または空欄
                raw_name = station_row["name"]
                if raw_name.endswith("[着]"):
                    name = raw_name[:-3].strip()
                    distinction = "着"
                elif raw_name.endswith("[発]"):
                    name = raw_name[:-3].strip()
                    distinction = "発"
                else:
                    name = raw_name
                    distinction = ""
                row_data.extend([name, distinction])
            else:
                row_data.append(station_row["name"])
                
            for col_idx, train_id in valid_cols:
                m_train = m_trains.get(train_id, {})

                # stop_map を使って stop を取得し stop_type を確認
                stop_map = m_train.get("_stop_map")
                if stop_map is not None:
                    stop = stop_map.get(station_row.get("stop_idx"))
                else:
                    stop = next(
                        (s for s in m_train.get("stops", []) if s.get("stop_idx") == station_row.get("stop_idx")),
                        None
                    )

                stop_type = stop.get("stop_type", 1) if stop else 1
                is_pass_or_op = (stop_type in (0, -1))

                # 時刻取得 (EditRole = hh:mm:ss 形式)
                raw_time = model.data(model.index(row_idx, col_idx), Qt.EditRole) or ""

                # 記号「ﾚ」「| |」「・・」は出力しない
                if raw_time in ("ﾚ", "| |", "・・"):
                    raw_time = ""

                if raw_time:
                    if is_pass_or_op:
                        if include_pass:
                            # 通過・運転停車の場合は時刻の前に「|」を付加
                            val = "|" + _format_time(raw_time, show_seconds, use_over24)
                        else:
                            # 通過・運転停車を出力しない場合は空文字列
                            val = ""
                    else:
                        val = _format_time(raw_time, show_seconds, use_over24)
                else:
                    val = ""

                row_data.append(val)
            rows_to_export.append(row_data)
            
        # 3. 連続する列車行の追加
        num_rows_before_footer = num_headers + num_stations
        if dialog.chk_subsequent.isChecked():
            row_data = []
            label = "連続する列車"
            if split_station:
                row_data.extend([label, ""])
            else:
                row_data.append(label)
            for col_idx, train_id in valid_cols:
                d_train = d_trains.get(train_id, {})
                subsequent_list = d_train.get("subsequent_trains") or []
                train_nums = []
                for item in subsequent_list:
                    s_rid, s_dir, s_tid = item.get("route_id"), item.get("direction"), item.get("train_id")
                    if s_tid:
                        s_route = model.project.routes.get(s_rid)
                        if s_route:
                            s_train_key = "inbound_trains" if s_dir == "inbound" else "outbound_trains"
                            s_m_train = s_route.get(s_train_key, {}).get(s_tid)
                            if s_m_train:
                                num = s_m_train.get("train_number") or "(番号なし)"
                                train_nums.append(num)
                row_data.append(" ".join(train_nums))
            rows_to_export.append(row_data)
            
        # 4. 備考行の追加
        if dialog.chk_note.isChecked():
            row_idx = num_rows_before_footer + 1
            row_data = []
            label = "備考"
            if split_station:
                row_data.extend([label, ""])
            else:
                row_data.append(label)
            for col_idx, _ in valid_cols:
                val = model.data(model.index(row_idx, col_idx), Qt.DisplayRole) or ""
                row_data.append(val.replace("\n", " "))
            rows_to_export.append(row_data)
            
        # CSVファイルへの書き出し (UTF-8 with BOM)
        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerows(rows_to_export)
            
        QMessageBox.information(parent_window, "情報", "CSVエクスポートが完了しました。")
    except Exception as e:
        QMessageBox.critical(parent_window, "エラー", f"CSVエクスポート中にエラーが発生しました:\n{e}")
