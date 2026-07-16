import csv
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton, QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt

class ExportCsvSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("エクスポート設定")
        self.resize(320, 360)
        
        layout = QVBoxLayout(self)
        
        # チェックボックスの定義
        self.chk_split_station = QCheckBox("発/着の区別を駅名とは別の列に出力", self)
        self.chk_train_number = QCheckBox("列車番号を出力", self)
        self.chk_operation_day = QCheckBox("運転日を出力", self)
        self.chk_operation_number = QCheckBox("運用番号を出力", self)
        self.chk_car_count = QCheckBox("両数を出力", self)
        self.chk_train_type = QCheckBox("種別・愛称を出力", self)
        self.chk_named_number = QCheckBox("号数を出力", self)
        self.chk_destination = QCheckBox("行き先を出力", self)
        self.chk_subsequent = QCheckBox("連続する列車を出力", self)
        self.chk_note = QCheckBox("備考を出力", self)
        
        # デフォルトのチェック状態
        self.chk_split_station.setChecked(False)
        self.chk_train_number.setChecked(True)
        self.chk_operation_day.setChecked(True)
        self.chk_operation_number.setChecked(True)
        self.chk_car_count.setChecked(True)
        self.chk_train_type.setChecked(True)
        self.chk_named_number.setChecked(True)
        self.chk_destination.setChecked(True)
        self.chk_subsequent.setChecked(True)
        self.chk_note.setChecked(True)
        
        # レイアウトへの追加
        layout.addWidget(self.chk_split_station)
        layout.addWidget(self.chk_train_number)
        layout.addWidget(self.chk_operation_day)
        layout.addWidget(self.chk_operation_number)
        layout.addWidget(self.chk_car_count)
        layout.addWidget(self.chk_train_type)
        layout.addWidget(self.chk_named_number)
        layout.addWidget(self.chk_destination)
        layout.addWidget(self.chk_subsequent)
        layout.addWidget(self.chk_note)
        
        # ボタン (OK / キャンセル)
        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton("OK", self)
        self.btn_cancel = QPushButton("キャンセル", self)
        
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(btn_layout)


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
        
        # 実データを持つ有効な列を抽出 (to_be_saved が True のもののみ)
        valid_cols = []
        for col, train_id in enumerate(model.train_ids):
            d_train = d_trains.get(train_id, {})
            if d_train.get("to_be_saved") is True:
                valid_cols.append((col, train_id))
                
        rows_to_export = []
        split_station = dialog.chk_split_station.isChecked()
        
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
                for col_idx, _ in valid_cols:
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
                
            for col_idx, _ in valid_cols:
                val = model.data(model.index(row_idx, col_idx), Qt.DisplayRole) or ""
                # 記号「ﾚ」「| |」「・・」は出力しない
                if val in ("ﾚ", "| |", "・・"):
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
