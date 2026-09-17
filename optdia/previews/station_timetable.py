import html
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QRadioButton,
    QButtonGroup, QComboBox, QCheckBox, QTabBar, QTextBrowser
)
from core.project import OptDiaProject
from previews.train_detail import TrainDetailPreviewDialog


def is_station_in_route(project: OptDiaProject, route_id: str, station_id: str) -> bool:
    """運行系統のいずれかの区間に指定した駅が含まれているかを判定する"""
    route = project.routes.get(route_id)
    if not route:
        return False
    for seg in route.get("line_segments", []):
        line_id = seg.get("line_id")
        line = project.lines.get(line_id)
        if not line:
            continue
        line_entries = line.get("station_list", [])
        entry_ids = [e.get("station_entry_id") for e in line_entries]
        start_entry = seg.get("start_station_entry")
        end_entry = seg.get("end_station_entry")
        try:
            i_start = entry_ids.index(start_entry)
            i_end = entry_ids.index(end_entry)
        except ValueError:
            st_ids = [e.get("station_id") for e in line_entries]
            try:
                i_start = st_ids.index(start_entry)
                i_end = st_ids.index(end_entry)
            except ValueError:
                continue

        low = min(i_start, i_end)
        high = max(i_start, i_end)
        for i in range(low, high + 1):
            if line_entries[i].get("station_id") == station_id:
                return True
    return False


def is_station_in_line(project: OptDiaProject, line_id: str, station_id: str) -> bool:
    """指定した路線に指定した駅が含まれているかを判定する"""
    line = project.lines.get(line_id)
    if not line:
        return False
    for entry in line.get("station_list", []):
        if entry.get("station_id") == station_id:
            return True
    return False


def get_train_destination_char(project: OptDiaProject, route_id: str, direction: str, train_id: str, diagram_id: str, visited=None) -> str:
    """
    列車の行き先1文字を解決する。
    1. destinationが設定されていればその1文字目。
    2. destinationがNoneで連続する列車がある場合は再帰的に探査。
    3. destinationが設定されている列車か連続する列車のない列車に行き着いたとき、その列車のdestinationの1文字目または終着駅のstation_initialを使用。
    """
    if visited is None:
        visited = set()
    key = (route_id, direction, train_id)
    if key in visited:
        return ""
    visited.add(key)

    route = project.routes.get(route_id)
    if not route:
        return ""

    tbd = route.get("trains_by_diagram", {}).get(diagram_id, {})
    train_key = "inbound_trains" if direction == "inbound" else "outbound_trains"
    d_train = tbd.get(train_key, {}).get(train_id, {})
    m_train = route.get(train_key, {}).get(train_id, {})

    # 1. destination が存在するか
    dest = d_train.get("destination")
    if dest:
        return dest[0]

    # 2. 連続する列車が存在するか
    subsequent_trains = d_train.get("subsequent_trains", [])
    if subsequent_trains:
        first_sub = subsequent_trains[0]
        sub_route_id = first_sub.get("route_id")
        sub_direction = first_sub.get("direction")
        sub_train_id = first_sub.get("train_id")
        if sub_route_id and sub_direction and sub_train_id:
            res = get_train_destination_char(project, sub_route_id, sub_direction, sub_train_id, diagram_id, visited)
            if res:
                return res

    # 3. 終着駅の station_initial
    stops = m_train.get("stops", []) if m_train else []
    if stops:
        timed_stops = [s for s in stops if s.get("arrival_time") or s.get("departure_time")]
        last_stop = timed_stops[-1] if timed_stops else stops[-1]
        seid = last_stop.get("station_entry_id")
        sid = project.station_entry_to_station_id.get(seid, last_stop.get("station_id"))
        st_data = project.stations.get(sid, {})
        st_initial = st_data.get("station_initial")
        if st_initial:
            return str(st_initial)[0]
        st_name = st_data.get("station_name", "")
        if st_name:
            return st_name[0]

    return ""


class StationTimetablePreviewDialog(QDialog):
    """駅時刻表プレビューダイアログ"""

    def __init__(self, parent, project: OptDiaProject, station_id: str, diagram_id: str = None,
                 initial_route_id: str = None, initial_direction: str = "outbound"):
        super().__init__(parent)
        self.project = project
        self.station_id = station_id
        self.diagram_id = diagram_id or (self.project.diagrams_order[0] if self.project.diagrams_order else "")

        station_data = self.project.stations.get(station_id, {})
        station_name = station_data.get("station_name", station_id)
        station_name_kana = station_data.get("station_name_kana", "")

        # ウィンドウ設定
        self.setWindowTitle(f"{station_name}の時刻表")
        self.setFixedSize(720, 720)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(5)

        # 1. 駅名のひらがな表記
        self.lbl_kana = QLabel(station_name_kana)
        self.lbl_kana.setAlignment(Qt.AlignCenter)
        self.lbl_kana.setStyleSheet("font-size: 14px; color: #555555;")
        main_layout.addWidget(self.lbl_kana)

        # 2. 駅名
        self.lbl_name = QLabel(station_name)
        self.lbl_name.setAlignment(Qt.AlignCenter)
        self.lbl_name.setStyleSheet("font-size: 24px; font-weight: bold;")
        main_layout.addWidget(self.lbl_name)

        # 3. トグルボックス (選択肢は「運行系統」と「路線」)
        toggle_layout = QHBoxLayout()
        self.radio_route = QRadioButton("運行系統")
        self.radio_line = QRadioButton("路線")
        self.btn_group = QButtonGroup(self)
        self.btn_group.addButton(self.radio_route)
        self.btn_group.addButton(self.radio_line)

        toggle_layout.addStretch()
        toggle_layout.addWidget(self.radio_route)
        toggle_layout.addSpacing(20)
        toggle_layout.addWidget(self.radio_line)
        toggle_layout.addStretch()
        main_layout.addLayout(toggle_layout)

        # 4. 運行系統または路線を選択するためのコンボボックス
        self.combo_target = QComboBox()
        main_layout.addWidget(self.combo_target)
        
        main_layout.addSpacing(5)

        # 5. 「営業列車以外も表示」というチェックボックス
        self.chk_non_in_service = QCheckBox("営業列車以外も表示")
        self.chk_non_in_service.setChecked(False)
        main_layout.addWidget(self.chk_non_in_service)
        
        main_layout.addStretch()

        # 6. 「下り」と「上り」というタブを持つタブバー
        self.tab_bar = QTabBar()
        self.tab_bar.addTab("下り")
        self.tab_bar.addTab("上り")
        if initial_direction == "inbound":
            self.tab_bar.setCurrentIndex(1)
        else:
            self.tab_bar.setCurrentIndex(0)
        main_layout.addWidget(self.tab_bar)

        # 7. 駅時刻表プレビューを表示するためのQTextBrowser
        self.text_browser = QTextBrowser()
        self.text_browser.setFixedHeight(500)
        self.text_browser.setOpenLinks(False)
        self.text_browser.anchorClicked.connect(self._on_anchor_clicked)
        main_layout.addWidget(self.text_browser)

        # シグナル接続
        self.radio_route.toggled.connect(self._on_mode_changed)
        self.combo_target.currentIndexChanged.connect(self._update_preview)
        self.chk_non_in_service.toggled.connect(self._update_preview)
        self.tab_bar.currentChanged.connect(self._update_preview)

        # 初期選択状態の設定
        # 指定された駅を含む運行系統が存在するか確認
        has_route = any(is_station_in_route(self.project, rid, self.station_id) for rid in self.project.routes_order)
        has_line = any(is_station_in_line(self.project, lid, self.station_id) for lid in self.project.lines_order)

        if initial_route_id and is_station_in_route(self.project, initial_route_id, self.station_id):
            self.initial_target_id = initial_route_id
            self.radio_route.setChecked(True)
        elif has_route:
            self.initial_target_id = None
            self.radio_route.setChecked(True)
        elif has_line:
            self.initial_target_id = None
            self.radio_line.setChecked(True)
        else:
            self.initial_target_id = None
            self.radio_route.setChecked(True)

        self._populate_target_combo()

    def _on_mode_changed(self):
        self._populate_target_combo()

    def _populate_target_combo(self):
        self.combo_target.blockSignals(True)
        self.combo_target.clear()

        if self.radio_route.isChecked():
            # 運行系統の候補を追加
            for rid in self.project.routes_order:
                if is_station_in_route(self.project, rid, self.station_id):
                    r_name = self.project.routes[rid].get("route_name", rid)
                    self.combo_target.addItem(r_name, rid)
        else:
            # 路線の候補を追加
            for lid in self.project.lines_order:
                if is_station_in_line(self.project, lid, self.station_id):
                    l_name = self.project.lines[lid].get("line_name", lid)
                    self.combo_target.addItem(l_name, lid)

        # 初期ターゲットがあれば選択を試みる
        if getattr(self, "initial_target_id", None):
            idx = self.combo_target.findData(self.initial_target_id)
            if idx >= 0:
                self.combo_target.setCurrentIndex(idx)
            self.initial_target_id = None

        self.combo_target.blockSignals(False)
        self._update_preview()

    def _collect_trains(self) -> list:
        """条件に合致する列車を収集してソートしたリストを返す"""
        target_id = self.combo_target.currentData()
        if not target_id or not self.diagram_id:
            return []

        is_route_mode = self.radio_route.isChecked()
        direction_tab = "inbound" if self.tab_bar.currentIndex() == 1 else "outbound"
        include_non_in_service = self.chk_non_in_service.isChecked()

        train_records = []
        seen_keys = set()

        if is_route_mode:
            route = self.project.routes.get(target_id)
            if not route:
                return []
            route_direction = direction_tab
            train_key = "inbound_trains" if route_direction == "inbound" else "outbound_trains"
            tbd = route.get("trains_by_diagram", {}).get(self.diagram_id, {})
            d_trains = tbd.get(train_key, {})
            m_trains = route.get(train_key, {})

            for train_id, d_train in d_trains.items():
                if d_train.get("to_be_saved") is False:
                    continue
                m_train = m_trains.get(train_id)
                if not m_train:
                    continue

                if not include_non_in_service:
                    ttid = m_train.get("train_type_id")
                    tt = self.project.train_types.get(ttid) if ttid else None
                    if not (tt and tt.get("is_in_service") is True):
                        continue

                # 停車駅の発車時刻を探す
                for stop in m_train.get("stops", []):
                    seid = stop.get("station_entry_id")
                    sid = self.project.station_entry_to_station_id.get(seid, stop.get("station_id"))
                    if sid == self.station_id:
                        dep_time = stop.get("departure_time")
                        if dep_time and dep_time.strip():
                            record_key = (target_id, route_direction, train_id, dep_time)
                            if record_key not in seen_keys:
                                seen_keys.add(record_key)
                                train_records.append({
                                    "route_id": target_id,
                                    "direction": route_direction,
                                    "train_id": train_id,
                                    "m_train": m_train,
                                    "departure_time": dep_time.strip()
                                })
        else:
            # 路線モード
            line = self.project.lines.get(target_id)
            if not line:
                return []
            line_entries = line.get("station_list", [])
            entry_ids = [e.get("station_entry_id") for e in line_entries]

            for route in self.project.routes.values():
                route_id = route.get("route_id")
                for seg in route.get("line_segments", []):
                    if seg.get("line_id") != target_id:
                        continue
                    start_entry = seg.get("start_station_entry")
                    end_entry = seg.get("end_station_entry")
                    try:
                        idx_start = entry_ids.index(start_entry)
                        idx_end = entry_ids.index(end_entry)
                    except ValueError:
                        st_ids = [e.get("station_id") for e in line_entries]
                        try:
                            idx_start = st_ids.index(start_entry)
                            idx_end = st_ids.index(end_entry)
                        except ValueError:
                            continue

                    low = min(idx_start, idx_end)
                    high = max(idx_start, idx_end)
                    seg_station_ids = [line_entries[i].get("station_id") for i in range(low, high + 1)]
                    if self.station_id not in seg_station_ids:
                        continue

                    is_forward = (idx_start <= idx_end)
                    if direction_tab == "outbound":
                        route_direction = "outbound" if is_forward else "inbound"
                    else:
                        route_direction = "inbound" if is_forward else "outbound"

                    train_key = "inbound_trains" if route_direction == "inbound" else "outbound_trains"
                    tbd = route.get("trains_by_diagram", {}).get(self.diagram_id, {})
                    d_trains = tbd.get(train_key, {})
                    m_trains = route.get(train_key, {})

                    for train_id, d_train in d_trains.items():
                        if d_train.get("to_be_saved") is False:
                            continue
                        m_train = m_trains.get(train_id)
                        if not m_train:
                            continue

                        if not include_non_in_service:
                            ttid = m_train.get("train_type_id")
                            tt = self.project.train_types.get(ttid) if ttid else None
                            if not (tt and tt.get("is_in_service") is True):
                                continue

                        for stop in m_train.get("stops", []):
                            if stop.get("segment_id") and stop.get("segment_id") != seg.get("segment_id"):
                                continue
                            seid = stop.get("station_entry_id")
                            sid = self.project.station_entry_to_station_id.get(seid, stop.get("station_id"))
                            if sid == self.station_id:
                                dep_time = stop.get("departure_time")
                                if dep_time and dep_time.strip():
                                    record_key = (route_id, route_direction, train_id, dep_time)
                                    if record_key not in seen_keys:
                                        seen_keys.add(record_key)
                                        train_records.append({
                                            "route_id": route_id,
                                            "direction": route_direction,
                                            "train_id": train_id,
                                            "m_train": m_train,
                                            "departure_time": dep_time.strip()
                                        })

        # 時刻をパースしてソート
        parsed_trains = []
        for item in train_records:
            parts = item["departure_time"].split(":")
            try:
                hour = int(parts[0])
                minute = int(parts[1])
                second = int(parts[2]) if len(parts) > 2 else 0
            except (ValueError, IndexError):
                continue

            m_train = item["m_train"]
            ttid = m_train.get("train_type_id")
            tt = self.project.train_types.get(ttid) if ttid else None
            main_color = tt.get("main_color", "#333333") if tt else "#333333"

            dest_char = get_train_destination_char(
                self.project, item["route_id"], item["direction"], item["train_id"], self.diagram_id
            )

            parsed_trains.append({
                "hour": hour,
                "minute": minute,
                "second": second,
                "route_id": item["route_id"],
                "direction": item["direction"],
                "train_id": item["train_id"],
                "train_number": m_train.get("train_number", ""),
                "main_color": main_color,
                "dest_char": dest_char
            })

        parsed_trains.sort(key=lambda t: (t["hour"], t["minute"], t["second"], t["train_number"]))
        return parsed_trains

    def _update_preview(self):
        """駅時刻表プレビューの HTML を生成して QTextBrowser に設定する"""
        trains = self._collect_trains()

        if not trains:
            empty_html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body { margin: 0; font-family: sans-serif; text-align: center; color: #888888; font-size: 18px; }
p { line-height: 250px; }
</style>
</head>
<body>
<p>該当する列車はありません</p>
</body>
</html>"""
            self.text_browser.setHtml(empty_html)
            return

        min_hour = min(t["hour"] for t in trains)
        max_hour = max(t["hour"] for t in trains)

        trains_by_hour = {}
        for t in trains:
            trains_by_hour.setdefault(t["hour"], []).append(t)

        diagram_data = self.project.diagrams.get(self.diagram_id, {})
        diagram_bg_color = diagram_data.get("background_color", "#cccccc")

        html_lines = [
            '<!DOCTYPE html>',
            '<html>',
            '<head>',
            '<meta charset="utf-8">',
            '<style>',
            'body { margin: 0; font-family: sans-serif; }',
            'table { width: 100%; border-collapse: collapse; font-size: 18px; }',
            '.hour_col { background-color: #888888; color: #ffffff; font-weight: bold; text-align: center; vertical-align: top; padding: 4px 0; }',
            '.train_col { vertical-align: middle; padding: 4px 8px; }',
            'a { text-decoration: none; white-space: nowrap; }',
            '</style>',
            '</head>',
            '<body>',
            '<table cellpadding="0" cellspacing="0" width="100%">'
        ]

        for h in range(min_hour, max_hour + 1):
            bg_color = "#ffffff" if (h % 2 == 1) else diagram_bg_color
            h_trains = trains_by_hour.get(h, [])
            links = []
            for t in h_trains:
                url = f"{t['route_id']}/{t['direction']}/{t['train_id']}"
                dest_char_escaped = html.escape(t["dest_char"])
                link_html = (
                    f'<a href="{url}" style="color: {t["main_color"]};">'
                    f'{t["minute"]:02d}'
                    f'<span style="font-size: 12px;">{dest_char_escaped}</span>'
                    f'</a>'
                )
                links.append(link_html)

            links_str = "&nbsp; ".join(links)
            row_html = (
                f'<tr>'
                f'<td width="40" class="hour_col">{h}</td>'
                f'<td class="train_col" style="background-color: {bg_color};">{links_str}</td>'
                f'</tr>'
            )
            html_lines.append(row_html)

        html_lines.append('</table>')
        html_lines.append('</body>')
        html_lines.append('</html>')

        self.text_browser.setHtml("\n".join(html_lines))

    def _on_anchor_clicked(self, url: QUrl):
        """リンククリック時に列車詳細プレビューを開く"""
        url_str = url.toString()
        parts = url_str.split("/")
        if len(parts) == 3:
            route_id, direction, train_id = parts
            dialog = TrainDetailPreviewDialog(self, self.project, route_id, direction, train_id)
            dialog.exec()
