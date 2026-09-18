import html
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QWidget, QCheckBox, QTextBrowser
from PySide6.QtCore import Qt, QUrl
from core.project import OptDiaProject


def _time_to_seconds(text: str):
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
        pass
    return None


class TrainDetailPreviewDialog(QDialog):
    """列車詳細プレビューダイアログ"""
    def __init__(self, parent, project: OptDiaProject, route_id: str, direction: str, train_id: str):
        super().__init__(parent)
        self.project = project
        self.route_id = route_id
        self.direction = direction
        self.train_id = train_id

        # 列車番号の取得
        route = self.project.routes.get(route_id, {})
        train_key = "inbound_trains" if direction == "inbound" else "outbound_trains"
        m_train = route.get(train_key, {}).get(train_id, {})
        train_number = m_train.get("train_number", "")

        self.setWindowTitle(f"列車 {train_number} の詳細")
        self.setFixedSize(480, 640)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 上の領域(高さ40px): 横並びになった2つのチェックボックス
        top_widget = QWidget()
        top_widget.setFixedHeight(40)
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(10, 0, 10, 0)
        top_layout.setSpacing(15)

        self.chk_show_seconds = QCheckBox("秒まで表示")
        self.chk_show_pass = QCheckBox("通過時刻も表示")
        top_layout.addWidget(self.chk_show_seconds)
        top_layout.addWidget(self.chk_show_pass)
        top_layout.addStretch()

        main_layout.addWidget(top_widget)

        # 下の領域: QTextBrowser
        self.text_browser = QTextBrowser()
        self.text_browser.setOpenLinks(False)
        self.text_browser.anchorClicked.connect(self._on_anchor_clicked)
        main_layout.addWidget(self.text_browser, 1)

        self.chk_show_seconds.toggled.connect(self._update_content)
        self.chk_show_pass.toggled.connect(self._update_content)

        self._update_content()

    def _on_anchor_clicked(self, url: QUrl):
        anchor_name = url.fragment() or url.toString().lstrip("#")
        if anchor_name:
            self.text_browser.scrollToAnchor(anchor_name)

    def _collect_related_trains(self):
        """
        コンストラクタで指定された列車と、
        その列車から連続する列車（5階層まで再帰的に辿る）や、
        その列車に連続する列車（逆引き情報から5階層まで辿る）の情報を収集する。
        """
        collected = set()

        # 1. 順方向（subsequent_trains）を最大5階層探索
        def traverse_forward(r_id, d_dir, t_id, depth):
            if depth > 5:
                return
            key = (r_id, d_dir, t_id)
            if key not in collected:
                collected.add(key)
            if depth == 5:
                return

            route = self.project.routes.get(r_id, {})
            # すべてのダイヤから subsequent_trains を集める
            subsequents = []
            for diag_id in self.project.diagrams_order:
                tbd = route.get("trains_by_diagram", {}).get(diag_id, {})
                t_key = "inbound_trains" if d_dir == "inbound" else "outbound_trains"
                d_train = tbd.get(t_key, {}).get(t_id)
                if d_train:
                    for sub in d_train.get("subsequent_trains", []):
                        sub_key = (sub.get("route_id"), sub.get("direction"), sub.get("train_id"))
                        if all(sub_key) and sub_key not in subsequents:
                            subsequents.append(sub_key)

            for sub_r, sub_d, sub_t in subsequents:
                traverse_forward(sub_r, sub_d, sub_t, depth + 1)

        # 2. 逆方向（_preceding_trains）を最大5階層探索
        def traverse_backward(r_id, d_dir, t_id, depth):
            if depth > 5:
                return
            key = (r_id, d_dir, t_id)
            if key not in collected:
                collected.add(key)
            if depth == 5:
                return

            route = self.project.routes.get(r_id, {})
            t_key = "inbound_trains" if d_dir == "inbound" else "outbound_trains"
            m_train = route.get(t_key, {}).get(t_id)
            precedings = []
            if m_train:
                for prec in m_train.get("_preceding_trains", []):
                    prec_key = (prec.get("route_id"), prec.get("direction"), prec.get("train_id"))
                    if all(prec_key) and prec_key not in precedings:
                        precedings.append(prec_key)

            for prec_r, prec_d, prec_t in precedings:
                traverse_backward(prec_r, prec_d, prec_t, depth + 1)

        traverse_forward(self.route_id, self.direction, self.train_id, 0)
        traverse_backward(self.route_id, self.direction, self.train_id, 0)

        # 始発時刻順にソート
        train_items = []
        for r_id, d_dir, t_id in collected:
            route = self.project.routes.get(r_id, {})
            t_key = "inbound_trains" if d_dir == "inbound" else "outbound_trains"
            m_tr = route.get(t_key, {}).get(t_id)
            if not m_tr:
                continue

            # 始発時刻の取得 (departure_time または arrival_time の最初の有効値)
            first_time_sec = 24 * 3600 + 1
            stops = m_tr.get("stops", [])
            for s in stops:
                t_str = s.get("departure_time") or s.get("arrival_time")
                sec = _time_to_seconds(t_str)
                if sec is not None:
                    first_time_sec = sec
                    break

            train_items.append({
                "route_id": r_id,
                "direction": d_dir,
                "train_id": t_id,
                "first_time_sec": first_time_sec,
                "train_number": m_tr.get("train_number", ""),
                "train_type_id": m_tr.get("train_type_id", ""),
                "named_train_number" : m_tr.get("named_train_number")
            })

        train_items.sort(key=lambda item: (item["first_time_sec"], item["train_number"]))
        return train_items

    def _format_time(self, time_str: str, show_seconds: bool) -> str:
        if not time_str:
            return ""
        parts = time_str.split(":")
        if show_seconds:
            if len(parts) == 3:
                return f"{int(parts[0]):02d}:{int(parts[1]):02d}:{int(parts[2]):02d}"
            elif len(parts) == 2:
                return f"{int(parts[0]):02d}:{int(parts[1]):02d}:00"
            return time_str
        else:
            if len(parts) >= 2:
                return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
            return time_str

    def _get_segment_line_color(self, route_id: str, segment_id: str) -> str:
        route = self.project.routes.get(route_id, {})
        for seg in route.get("line_segments", []):
            if seg.get("segment_id") == segment_id:
                line_id = seg.get("line_id")
                line_data = self.project.lines.get(line_id, {})
                return line_data.get("line_color", "#333333")
        return "#333333"

    def _update_content(self):
        show_seconds = self.chk_show_seconds.isChecked()
        show_pass = self.chk_show_pass.isChecked()

        train_list = self._collect_related_trains()
        if not train_list:
            self.text_browser.setHtml("")
            return

        # 運行系統・路線の segment_id -> line_color マッピング用
        # 各列車の Table HTML を構築
        tables_html = []

        for idx, t_info in enumerate(train_list):
            r_id = t_info["route_id"]
            d_dir = t_info["direction"]
            t_id = t_info["train_id"]
            nt_num = t_info["named_train_number"]

            if t_info["train_type_id"]:
                train_type = self.project.train_types.get(t_info["train_type_id"], {})
                train_color = train_type.get("main_color", "#333333")
                train_type_short_name = html.escape(train_type.get("train_type_short_name", ""))
            else:
                train_color = "#333333"
                train_type_short_name = "種別未設定"

            route = self.project.routes.get(r_id, {})
            t_key = "inbound_trains" if d_dir == "inbound" else "outbound_trains"
            m_train = route.get(t_key, {}).get(t_id, {})

            # 1. 1行目: <列車番号>列車 <列車の担当運用の運用番号を半角プラス記号で連結した文字列> (<列車の両数(Noneの場合は担当運用の所定両数の合計値)>両)
            train_num = html.escape(m_train.get("train_number", ""))

            # 担当運用情報および両数情報の収集（運転ダイヤから）
            # 各ダイヤで定義されている運用の番号と両数を取得（最初に見つかった有効なダイヤ別列車情報を使用）
            operations_str = ""
            car_count_str = ""

            for diag_id in self.project.diagrams_order:
                tbd = route.get("trains_by_diagram", {}).get(diag_id, {})
                d_train = tbd.get(t_key, {}).get(t_id)
                if d_train:
                    diag_operations = self.project.diagrams.get(diag_id, {}).get("operations", {})
                    op_nums = []
                    sum_cars = 0
                    for op_item in d_train.get("operations", []):
                        op_id = op_item.get("operation_id") if isinstance(op_item, dict) else op_item
                        if op_id and op_id in diag_operations:
                            op_data = diag_operations[op_id]
                            op_nums.append(str(op_data.get("operation_number", op_id)))
                            sum_cars += op_data.get("car_count", 0)
                        elif op_id:
                            op_nums.append(str(op_id))
                    
                    if op_nums:
                        operations_str = "+".join(op_nums)

                    cc = d_train.get("car_count")
                    if cc is None:
                        cc = sum_cars if sum_cars > 0 else None
                    if cc is not None:
                        car_count_str = f"({cc}両)"
                    break

            header_parts = [f'<span style="color: {train_color};">{train_type_short_name}']
            if nt_num:
                header_parts.append(str(nt_num) + "号")
            header_parts.append(f'{train_num}列車</span>')
            if operations_str:
                header_parts.append('<span style="color: #666666; font-size: 14px;">' + html.escape(operations_str) + '</span>')
            if car_count_str:
                header_parts.append('<span style="color: #666666; font-size: 14px;">' + html.escape(car_count_str) + '</span>')
            header_html = " ".join(header_parts)

            # 2. 2行目以降: 経由駅情報
            # まず stops をグループ化（同一駅が連続している場合は1駅分に統合）
            raw_stops = m_train.get("stops", [])
            grouped_stations = []
            i = 0
            while i < len(raw_stops):
                s1 = raw_stops[i]
                s1_eid = s1.get("station_entry_id")
                s1_sid = getattr(self.project, "station_entry_to_station_id", {}).get(s1_eid, s1.get("station_id"))

                if i + 1 < len(raw_stops):
                    s2 = raw_stops[i + 1]
                    s2_eid = s2.get("station_entry_id")
                    s2_sid = getattr(self.project, "station_entry_to_station_id", {}).get(s2_eid, s2.get("station_id"))
                    if s1_sid and s2_sid and s1_sid == s2_sid:
                        grouped_stations.append({
                            "is_double": True,
                            "station_id": s1_sid,
                            "stop1": s1,
                            "stop2": s2
                        })
                        i += 2
                        continue

                grouped_stations.append({
                    "is_double": False,
                    "station_id": s1_sid,
                    "stop1": s1,
                    "stop2": None
                })
                i += 1

            # フィルタリング & 行HTML生成
            station_rows_html = []
            for i, g in enumerate(grouped_stations):
                st_id = g["station_id"]
                st_data = self.project.stations.get(st_id, {})
                st_name = st_data.get("station_name", st_id or "")

                bg_color = "#ffffff" if i % 2 == 0 else "#f7f7f7"

                if g["is_double"]:
                    stop1 = g["stop1"]
                    stop2 = g["stop2"]
                    # 通過駅チェック: 「通過時刻も表示」がチェックされていない時、stop_typeが1でない駅は除外
                    # double の場合はいずれかが stop_type == 1 であれば停車扱いとするか、stop_type を判定
                    # 通常 stop2(発車側) または stop1(到着側) の stop_type を確認
                    effective_stop_type = stop2.get("stop_type", stop1.get("stop_type", 1))
                    if not show_pass and effective_stop_type != 1:
                        continue

                    arr_raw = stop1.get("arrival_time")
                    dep_raw = stop2.get("departure_time")

                    arr_formatted = self._format_time(arr_raw, show_seconds)
                    dep_formatted = self._format_time(dep_raw, show_seconds)

                    seg1_color = self._get_segment_line_color(r_id, stop1.get("segment_id"))
                    seg2_color = self._get_segment_line_color(r_id, stop2.get("segment_id"))

                    row_color = " color: #888888;" if effective_stop_type != 1 else ""
                    row_style = f'background-color: {bg_color};{row_color}'

                    if effective_stop_type == 0:
                        # stop_typeが0の駅では到着時刻を表示せずに発車時刻は半角丸括弧で囲んで表示
                        dep_display = f"({dep_formatted})" if dep_formatted else ""
                        station_rows_html.append(f"""
                            <tr style="{row_style}">
                                <td width="30" rowspan="2"></td>
                                <td width="20" style="background-color: {seg1_color};" padding: 0;></td>
                                <td width="70" rowspan="2" align="center">{html.escape(dep_display)}</td>
                                <td width="350" rowspan="2">{html.escape(st_name)}</td>
                            </tr>
                            <tr style="{row_style}">
                                <td width="20" style="background-color: {seg2_color}; padding: 0;"></td>
                            </tr>
                        """)
                    else:
                        # 2つの経由駅情報で表示している場合は1列目は行を結合せず、1行目は1つ目の経由駅情報、2行目は2つ目の経由駅情報のsegment_idの路線のline_color
                        # 2列目は、到着時刻と発車時刻で表示する値が同一となる場合や一方がNoneの場合は上下の行を結合して発車時刻(発車時刻がNoneの場合は到着時刻)のみ表示
                        if arr_formatted == dep_formatted or not arr_formatted or not dep_formatted:
                            single_time = dep_formatted if dep_formatted else arr_formatted
                            station_rows_html.append(f"""
                                <tr style="{row_style}">
                                    <td width="30" rowspan="2"></td>
                                    <td width="30" style="background-color: {seg1_color}; padding: 0;"></td>
                                    <td width="70" rowspan="2" align="center">{html.escape(single_time)}</td>
                                    <td width="350" rowspan="2">{html.escape(st_name)}</td>
                                </tr>
                                <tr style="{row_style}">
                                    <td width="20" style="background-color: {seg2_color}; padding: 0;"></td>
                                </tr>
                            """)
                        else:
                            station_rows_html.append(f"""
                                <tr style="{row_style}">
                                    <td width="30" rowspan="2"></td>
                                    <td width="20" style="background-color: {seg1_color}; padding: 0;"></td>
                                    <td width="70" align="center" style="padding: 0 5px;">{html.escape(arr_formatted)}</td>
                                    <td width="350" rowspan="2">{html.escape(st_name)}</td>
                                </tr>
                                <tr style="{row_style}">
                                    <td width="20" style="background-color: {seg2_color}; padding: 0;"></td>
                                    <td width="70" align="center" style="padding: 0 5px;">{html.escape(dep_formatted)}</td>
                                </tr>
                            """)
                else:
                    stop1 = g["stop1"]
                    stop_type = stop1.get("stop_type", 1)
                    if not show_pass and stop_type != 1:
                        continue

                    arr_raw = stop1.get("arrival_time")
                    dep_raw = stop1.get("departure_time")

                    arr_formatted = self._format_time(arr_raw, show_seconds)
                    dep_formatted = self._format_time(dep_raw, show_seconds)

                    seg_color = self._get_segment_line_color(r_id, stop1.get("segment_id"))
                    row_color = " color: #888888;" if stop_type != 1 else ""
                    row_style = f'background-color: {bg_color};{row_color}'

                    if stop_type == 0:
                        dep_display = f"({dep_formatted})" if dep_formatted else ""
                        station_rows_html.append(f"""
                            <tr style="{row_style}">
                                <td width="30"></td>
                                <td width="20" style="background-color: {seg_color};"></td>
                                <td width="70" align="center">{html.escape(dep_display)}</td>
                                <td width="350">{html.escape(st_name)}</td>
                            </tr>
                        """)
                    else:
                        if arr_formatted == dep_formatted or not arr_formatted or not dep_formatted:
                            single_time = dep_formatted if dep_formatted else arr_formatted
                            station_rows_html.append(f"""
                                <tr style="{row_style}">
                                    <td width="30"></td>
                                    <td width="20" style="background-color: {seg_color};"></td>
                                    <td width="70" align="center">{html.escape(single_time)}</td>
                                    <td width="350">{html.escape(st_name)}</td>
                                </tr>
                            """)
                        else:
                            station_rows_html.append(f"""
                                <tr style="{row_style}">
                                    <td width="30" rowspan="2"></td>
                                    <td width="20" rowspan="2" style="background-color: {seg_color};"></td>
                                    <td width="70" align="center" style="padding: 0 5px;">{html.escape(arr_formatted)}</td>
                                    <td width="350" rowspan="2">{html.escape(st_name)}</td>
                                </tr>
                                <tr style="{row_style}">
                                    <td width="70" align="center" style="padding: 0 5px;">{html.escape(dep_formatted)}</td>
                                </tr>
                            """)

            # 3. 連続する列車のリンク行
            # 列車に連続する列車が設定されている場合(ただし、連続する列車に指定されている列車が1つのみで、かつ、次のTableに表示される列車がその列車である場合を除く)
            # は、「連続する列車:」というテキストに続けて、連続する列車の列車番号をリンクテキストとした内部リンク(クリックすると当該列車のTableの位置までスクロール)を最後の行(列は全て結合)に並べる。
            subsequent_links = []
            all_subs = []
            for diag_id in self.project.diagrams_order:
                tbd = route.get("trains_by_diagram", {}).get(diag_id, {})
                d_train = tbd.get(t_key, {}).get(t_id)
                if d_train:
                    for sub in d_train.get("subsequent_trains", []):
                        sub_tuple = (sub.get("route_id"), sub.get("direction"), sub.get("train_id"))
                        if all(sub_tuple) and sub_tuple not in all_subs:
                            all_subs.append(sub_tuple)

            # 条件チェック: 連続する列車に指定されている列車が1つのみで、かつ、次のTableに表示される列車がその列車である場合を除く
            skip_sub_row = False
            if len(all_subs) == 1 and idx + 1 < len(train_list):
                next_t = train_list[idx + 1]
                next_tuple = (next_t["route_id"], next_t["direction"], next_t["train_id"])
                if all_subs[0] == next_tuple:
                    skip_sub_row = True

            if all_subs and not skip_sub_row:
                for sub_r, sub_d, sub_t in all_subs:
                    s_route = self.project.routes.get(sub_r, {})
                    s_key = "inbound_trains" if sub_d == "inbound" else "outbound_trains"
                    s_m_train = s_route.get(s_key, {}).get(sub_t, {})
                    s_num = s_m_train.get("train_number") or "(番号なし)"
                    target_anchor = f"train_{sub_r}_{sub_d}_{sub_t}"
                    subsequent_links.append(f'<a href="#{target_anchor}">{html.escape(s_num)}</a>')

            if subsequent_links:
                links_html_str = " ".join(subsequent_links)
                sub_row_html = f"""
                    <tr class="subsequent_links_row">
                        <td colspan="4">連続する列車: {links_html_str}</td>
                    </tr>
                """
            else:
                sub_row_html = ""

            table_id = f"train_{r_id}_{d_dir}_{t_id}"
            table_html = f"""
                <a name="{table_id}"></a>
                <table id="{table_id}" cellpadding="0" cellspacing="0">
                    <tr>
                        <th colspan="4">{header_html}</th>
                    </tr>
                    {"".join(station_rows_html)}
                    {sub_row_html}
                </table>
            """
            tables_html.append(table_html)

        full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{
    margin: 0;
    padding: 0;
    font-family: sans-serif;
    line-height: 0;
}}
table {{
    border-collapse: collapse;
    margin: 0;
    border: none;
    font-size: 14px;
    line-height: 20px;
}}
th {{
    border: 2px solid #efefef;
    border-bottom-width: 4px;
    padding: 10px 8px;
    font-size: 16px;
    font-weight: normal;
    text-align: left;
}}
td {{
    border: none;
    padding: 10px 5px;
}}
.subsequent_links_row td {{
    padding-left: 20px;
}}
a {{
    color: #666666;
    text-decoration: underline;
}}
</style>
</head>
<body>
{"".join(tables_html)}
</body>
</html>"""

        self.text_browser.setHtml(full_html)
