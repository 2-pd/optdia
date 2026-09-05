from PySide6.QtWidgets import QGraphicsScene, QGraphicsLineItem, QGraphicsSimpleTextItem, QGraphicsPathItem
from PySide6.QtGui import QColor, QPen, QBrush, QFont, QPainterPath
from PySide6.QtCore import Qt, QRectF

class DiagramScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackgroundBrush(QBrush(QColor("#ffffff")))
        self.project = None
        self.selected_target = "route"  # "route" or line_id
        self.route_id = None
        self.diagram_id = None

    def update_diagram(self, project, selected_target: str, route_id: str, diagram_id: str):
        """
        運行ダイヤグラムを更新描画する。
        selected_target: "route" または line_id (str)
        route_id: 運行系統リストで選択中のroute_id
        diagram_id: 運転ダイヤリストで選択中のdiagram_id
        """
        self.project = project
        self.selected_target = selected_target
        self.route_id = route_id
        self.diagram_id = diagram_id

        self.clear()

        if not self.project:
            self.setSceneRect(0, 0, 100, 100)
            return

        # 1. 表示対象の駅リストを構築
        stations_data = self._collect_station_positions()

        # エラー（基準運転時分がNoneの駅がある場合、または駅が存在しない等）の判定
        if stations_data is None:
            # エラー文描画
            self._render_error_message(
                "表示対象の路線に基準運転時分の設定されていない駅が含まれます。\n"
                "ダイヤグラムを表示するには基準運転時分の設定を完了してください。"
            )
            return

        if not stations_data:
            self.setSceneRect(0, 0, 100, 100)
            return

        # 2. 軸とグリッドの描画
        # 横軸: 左から120pxの位置から、0時から36時まで1分を6px
        # 全体幅 = 120 + 36 * 60 * 6 = 120 + 12960 = 13080px (+ 余白)
        max_y = stations_data[-1]["y"]
        scene_h = max_y + 60 + 20
        scene_w = 120 + 36 * 60 * 6 + 120

        self.setSceneRect(0, 0, scene_w, max(scene_h, 300))

        # 横線（駅）の描画
        self._render_station_lines(stations_data)

        # 縦線（時間）の描画
        self._render_time_lines(max_y)

        # 3. 列車のプロット描画
        self._render_trains(stations_data)

    def _render_error_message(self, text: str):
        self.setSceneRect(0, 0, 600, 300)
        error_item = QGraphicsSimpleTextItem(text)
        font = QFont()
        font.setPixelSize(14)
        error_item.setFont(font)
        error_item.setBrush(QBrush(QColor("#cc3333")))
        error_item.setPos(50, 100)
        self.addItem(error_item)

    def _collect_station_positions(self):
        """
        表示対象の駅リストを抽出し、それぞれのy座標を計算する。
        Noneが含まれる場合はNoneを返す。
        戻り値:
        [
            {
                "station_id": str,
                "station_name": str,
                "y": float,
                "segment_id": str (運行系統の場合) or None,
                "rel_time": float
            }, ...
        ]
        """
        if self.selected_target == "route":
            if not self.route_id or self.route_id not in self.project.routes:
                return []
            route = self.project.routes[self.route_id]
            segments = route.get("line_segments", [])
            if not segments:
                return []

            stations_data = []
            accumulated_time = 0.0

            for seg_idx, seg in enumerate(segments):
                line_id = seg.get("line_id")
                start_sid = seg.get("start_station")
                end_sid = seg.get("end_station")
                seg_id = seg.get("segment_id")

                line = self.project.lines.get(line_id)
                if not line:
                    continue

                line_station_list = line.get("station_list", [])
                line_sids = [s.get("station_id") for s in line_station_list]
                station_map = {s.get("station_id"): s for s in line_station_list}

                if start_sid not in line_sids or end_sid not in line_sids:
                    continue

                idx_start = line_sids.index(start_sid)
                idx_end = line_sids.index(end_sid)

                if idx_start <= idx_end:
                    seg_sids = line_sids[idx_start:idx_end + 1]
                else:
                    seg_sids = line_sids[idx_start:idx_end - 1:-1] if idx_end > 0 else line_sids[idx_start::-1]

                start_st_info = station_map.get(start_sid)
                if not start_st_info or start_st_info.get("absolute_standard_running_time") is None:
                    return None
                start_abs_time = start_st_info.get("absolute_standard_running_time")

                end_st_info = station_map.get(end_sid)
                if not end_st_info or end_st_info.get("absolute_standard_running_time") is None:
                    return None
                end_abs_time = end_st_info.get("absolute_standard_running_time")

                for sid in seg_sids:
                    st_info = station_map.get(sid)
                    if not st_info or st_info.get("absolute_standard_running_time") is None:
                        return None
                    abs_time = st_info.get("absolute_standard_running_time")

                    # その駅が属する部分区間の始点とのabsolute_standard_running_timeの差の絶対値 + それまでの部分区間の起点と終点の差の絶対値の合計
                    diff = abs(abs_time - start_abs_time)
                    rel_time = accumulated_time + diff

                    # 3秒を1px
                    y = 60.0 + (rel_time / 3.0)

                    st_obj = self.project.stations.get(sid, {})
                    st_name = st_obj.get("station_name", sid)

                    stations_data.append({
                        "station_id": sid,
                        "station_name": st_name,
                        "y": y,
                        "segment_id": seg_id,
                        "rel_time": rel_time
                    })

                # 2つ目以降の部分区間に備えて累積時間を加算
                seg_total_diff = abs(end_abs_time - start_abs_time)
                accumulated_time += seg_total_diff

            return stations_data

        else:
            # 路線が選択されている場合
            line_id = self.selected_target
            line = self.project.lines.get(line_id)
            if not line:
                return []

            station_list = line.get("station_list", [])
            if not station_list:
                return []

            stations_data = []
            for s_entry in station_list:
                sid = s_entry.get("station_id")
                abs_time = s_entry.get("absolute_standard_running_time")
                if abs_time is None:
                    return None

                y = 60.0 + (abs_time / 3.0)
                st_obj = self.project.stations.get(sid, {})
                st_name = st_obj.get("station_name", sid)

                stations_data.append({
                    "station_id": sid,
                    "station_name": st_name,
                    "y": y,
                    "segment_id": None,
                    "abs_time": abs_time
                })

            return stations_data

    def _render_station_lines(self, stations_data):
        # 120pxの余白を空けて色コード#ccccccで高さ1pxの横線
        # 横線の始点の左側に横線と同じ色で駅名を表示
        pen_station = QPen(QColor("#cccccc"), 1)
        font = QFont()
        font.setPixelSize(12)
        font_major = QFont()
        font_major.setPixelSize(12)
        font_major.setBold(True)

        line_end_x = 120 + 36 * 60 * 6

        for st in stations_data:
            y = st["y"]
            sid = st["station_id"]
            st_obj = self.project.stations.get(sid, {})
            name = st["station_name"]

            # 横線
            line_item = self.addLine(120, y, line_end_x, y, pen_station)
            line_item.setZValue(0)

            # 駅名テキスト（横線の始点の左側に表記）
            text_item = QGraphicsSimpleTextItem(name)
            if st_obj.get("is_major_station", False):
                text_item.setFont(font_major)
            else:
                text_item.setFont(font)
            text_item.setBrush(QBrush(QColor("#666666")))

            # テキストの配置: 始点(x=120)の左側、yは中央揃え
            br = text_item.boundingRect()
            tx = 120 - br.width() - 5
            ty = y - (br.height() / 2.0)
            text_item.setPos(tx, ty)
            text_item.setZValue(1)
            self.addItem(text_item)

    def _render_time_lines(self, max_y):
        # 横軸に時間(左から120pxの位置から、0時から36時まで1分を6pxで描画。
        # 毎時10分、20分、30分、40分、50分の位置には色コード#ddddddで幅1pxの縦線を上下60pxの余白を空けて表示する。
        # 毎時0分の位置には色コード#aaaaaaで幅2pxの縦線を上下60pxの余白を空けて表示し、
        # 縦線の始点の上と終点の下には時の値を線と同じ縦色で表記する。)
        pen_10min = QPen(QColor("#dddddd"), 1)
        pen_hour = QPen(QColor("#aaaaaa"), 2)

        font_hour = QFont()
        font_hour.setPixelSize(13)

        top_y = 60.0
        bottom_y = max_y

        for hour in range(37):  # 0時から36時
            hour_x = 120 + hour * 60 * 6

            # 毎時0分の縦線
            line_item = self.addLine(hour_x, top_y, hour_x, bottom_y, pen_hour)
            line_item.setZValue(0)

            # 縦線の始点の上と終点の下に時の値を表記
            text_str = str(hour)
            # 始点の上
            t_top = QGraphicsSimpleTextItem(text_str)
            t_top.setFont(font_hour)
            t_top.setBrush(QBrush(QColor("#666666")))
            br_top = t_top.boundingRect()
            t_top.setPos(hour_x - (br_top.width() / 2.0), top_y - br_top.height() - 5)
            t_top.setZValue(1)
            self.addItem(t_top)

            # 終点の下
            t_bottom = QGraphicsSimpleTextItem(text_str)
            t_bottom.setFont(font_hour)
            t_bottom.setBrush(QBrush(QColor("#666666")))
            br_bottom = t_bottom.boundingRect()
            t_bottom.setPos(hour_x - (br_bottom.width() / 2.0), bottom_y + 5)
            t_bottom.setZValue(1)
            self.addItem(t_bottom)

            # 毎時10分、20分、30分、40分、50分 (hour 36は0分のみ)
            if hour < 36:
                for minute_step in [10, 20, 30, 40, 50]:
                    min_x = hour_x + minute_step * 6
                    m_line = self.addLine(min_x, top_y, min_x, bottom_y, pen_10min)
                    m_line.setZValue(0)

    def _render_trains(self, stations_data):
        if not self.diagram_id:
            return

        if self.selected_target == "route":
            self._render_trains_for_route(stations_data)
        else:
            self._render_trains_for_line(stations_data)

    def _render_trains_for_route(self, stations_data):
        route = self.project.routes.get(self.route_id)
        if not route:
            return

        tbd = route.get("trains_by_diagram", {}).get(self.diagram_id, {})
        d_inbound = tbd.get("inbound_trains", {})
        d_outbound = tbd.get("outbound_trains", {})
        m_inbound = route.get("inbound_trains", {})
        m_outbound = route.get("outbound_trains", {})

        for d_dict, m_dict in [(d_outbound, m_outbound), (d_inbound, m_inbound)]:
            for tid, d_train in d_dict.items():
                if not d_train.get("to_be_saved", True):
                    continue
                m_train = m_dict.get(tid)
                if not m_train:
                    continue
                self._draw_single_train_for_route(m_train, stations_data)

    def _draw_single_train_for_route(self, train, stations_data):
        stops = train.get("stops", [])
        if not stops:
            return

        tt_id = train.get("train_type_id")
        pen = self._create_train_pen(tt_id)

        # stopsの各stopについて (segment_id, station_id) で stations_data 内を照合
        points = []

        for stop in stops:
            seg_id = stop.get("segment_id")
            sid = stop.get("station_id")
            arr_time_str = stop.get("arrival_time")
            dep_time_str = stop.get("departure_time")

            # stations_data 内で一致する駅を検索
            target_entry = None
            for idx in range(len(stations_data)):
                st = stations_data[idx]
                if st.get("segment_id") == seg_id and st.get("station_id") == sid:
                    target_entry = st
                    break

            if not target_entry:
                continue

            y = target_entry["y"]

            arr_sec = self._time_to_seconds(arr_time_str)
            dep_sec = self._time_to_seconds(dep_time_str)

            if arr_sec is not None and dep_sec is not None:
                x_arr = 120 + (arr_sec / 60.0) * 6.0
                x_dep = 120 + (dep_sec / 60.0) * 6.0
                points.append((x_arr, y))
                if x_arr != x_dep:
                    points.append((x_dep, y))
            elif arr_sec is not None:
                x_arr = 120 + (arr_sec / 60.0) * 6.0
                points.append((x_arr, y))
            elif dep_sec is not None:
                x_dep = 120 + (dep_sec / 60.0) * 6.0
                points.append((x_dep, y))

        if len(points) >= 2:
            self._draw_path(points, pen)

    def _render_trains_for_line(self, stations_data):
        target_line_id = self.selected_target
        # プロジェクトデータに存在する全運行系統を走査して、
        # 選択されている路線に属する部分区間を経由する列車を抽出し、
        # 各列車について選択されている路線に属する部分区間の発着時刻のみをプロット
        station_y_map = {st["station_id"]: st["y"] for st in stations_data}

        for rid in self.project.routes_order:
            route = self.project.routes.get(rid)
            if not route:
                continue

            segments = route.get("line_segments", [])
            target_segment_ids = {seg["segment_id"] for seg in segments if seg.get("line_id") == target_line_id}
            if not target_segment_ids:
                continue

            tbd = route.get("trains_by_diagram", {}).get(self.diagram_id, {})
            d_inbound = tbd.get("inbound_trains", {})
            d_outbound = tbd.get("outbound_trains", {})
            m_inbound = route.get("inbound_trains", {})
            m_outbound = route.get("outbound_trains", {})

            for d_dict, m_dict in [(d_outbound, m_outbound), (d_inbound, m_inbound)]:
                for tid, d_train in d_dict.items():
                    if not d_train.get("to_be_saved", True):
                        continue
                    m_train = m_dict.get(tid)
                    if not m_train:
                        continue

                    stops = m_train.get("stops", [])
                    current_subpath_points = []

                    tt_id = m_train.get("train_type_id")
                    pen = self._create_train_pen(tt_id)

                    for stop in stops:
                        seg_id = stop.get("segment_id")
                        if seg_id not in target_segment_ids:
                            if len(current_subpath_points) >= 2:
                                self._draw_path(current_subpath_points, pen)
                            current_subpath_points = []
                            continue

                        sid = stop.get("station_id")
                        if sid not in station_y_map:
                            continue

                        y = station_y_map[sid]
                        arr_sec = self._time_to_seconds(stop.get("arrival_time"))
                        dep_sec = self._time_to_seconds(stop.get("departure_time"))

                        if arr_sec is not None and dep_sec is not None:
                            x_arr = 120 + (arr_sec / 60.0) * 6.0
                            x_dep = 120 + (dep_sec / 60.0) * 6.0
                            current_subpath_points.append((x_arr, y))
                            if x_arr != x_dep:
                                current_subpath_points.append((x_dep, y))
                        elif arr_sec is not None:
                            x_arr = 120 + (arr_sec / 60.0) * 6.0
                            current_subpath_points.append((x_arr, y))
                        elif dep_sec is not None:
                            x_dep = 120 + (dep_sec / 60.0) * 6.0
                            current_subpath_points.append((x_dep, y))

                    if len(current_subpath_points) >= 2:
                        self._draw_path(current_subpath_points, pen)

    def _draw_path(self, points, pen):
        if len(points) < 2:
            return
        path = QPainterPath()
        path.moveTo(points[0][0], points[0][1])
        for pt in points[1:]:
            path.lineTo(pt[0], pt[1])

        path_item = QGraphicsPathItem(path)
        path_item.setPen(pen)
        path_item.setZValue(2)
        self.addItem(path_item)

    def _create_train_pen(self, train_type_id):
        tt = self.project.train_types.get(train_type_id) if (self.project and train_type_id) else None
        if tt:
            color_str = tt.get("main_color", "#333333")
            weight_str = tt.get("line_weight", "normal")
            style_str = tt.get("line_style", "solid")
        else:
            color_str = "#333333"
            weight_str = "normal"
            style_str = "solid"

        pen = QPen(QColor(color_str))

        if weight_str == "thin":
            pen.setWidth(1)
        elif weight_str == "bold":
            pen.setWidth(3)
        else:
            pen.setWidth(2)

        if style_str == "dashed":
            pen.setStyle(Qt.DashLine)
        elif style_str == "dotted":
            pen.setStyle(Qt.DotLine)
        else:
            pen.setStyle(Qt.SolidLine)

        return pen

    def _time_to_seconds(self, time_str: str):
        if not time_str:
            return None
        try:
            parts = time_str.split(":")
            if len(parts) >= 2:
                hh = int(parts[0])
                mm = int(parts[1])
                ss = int(parts[2]) if len(parts) >= 3 else 0
                return hh * 3600 + mm * 60 + ss
        except (ValueError, IndexError):
            pass
        return None
