import math
from PySide6.QtWidgets import QGraphicsScene, QGraphicsLineItem, QGraphicsSimpleTextItem, QGraphicsPathItem
from PySide6.QtGui import QColor, QPen, QBrush, QFont, QPainterPath
from PySide6.QtCore import Qt, QRectF

# 運行ダイヤグラム上部のシーン（時刻の値のみ）
class DiagramHeaderScene(QGraphicsScene):
    HEADER_HEIGHT = 20

    def __init__(self, parent=None, scale_x: float = 6.0):
        super().__init__(parent)
        self.scale_x = scale_x
        self.setBackgroundBrush(QBrush(QColor("#ffffff")))
        self.update_header()

    def set_scale_x(self, scale_x: float):
        if self.scale_x != scale_x:
            self.scale_x = scale_x
            self.update_header()

    def update_header(self):
        self.clear()
        scene_w = 36 * 60 * self.scale_x + 20 # うち20pxはメインシーンの上下スクロールバーの幅として確保
        self.setSceneRect(0, 0, scene_w, self.HEADER_HEIGHT)

        font_hour = QFont()
        font_hour.setPixelSize(14)

        for hour in range(36): # 36時は描画不要
            hour_x = hour * 60 * self.scale_x
            text_str = str(hour)
            t_item = QGraphicsSimpleTextItem(text_str)
            t_item.setFont(font_hour)
            t_item.setBrush(QBrush(QColor("#666666")))
            br = t_item.boundingRect()
            tx = hour_x
            ty = (self.HEADER_HEIGHT - br.height()) / 2.0
            t_item.setPos(tx, ty)
            self.addItem(t_item)


# 運行ダイヤグラム左側のシーン（駅名テキストのみ）
class DiagramStationScene(QGraphicsScene):
    STATION_WIDTH = 120

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackgroundBrush(QBrush(QColor("#ffffff")))

    def update_stations(self, project, stations_data):
        self.clear()
        if not stations_data:
            self.setSceneRect(0, 0, self.STATION_WIDTH, 100)
            return

        max_y = stations_data[-1]["y"]
        scene_h = max_y + 60 # メインシーンの左右スクロールバーの高さとして20pxの余裕を確保
        self.setSceneRect(0, 0, self.STATION_WIDTH, max(scene_h, 200))

        font = QFont()
        font.setPixelSize(12)
        font_major = QFont()
        font_major.setPixelSize(12)
        font_major.setBold(True)

        for i, st in enumerate(stations_data):
            y = st["y"]
            sid = st["station_id"]
            st_obj = project.stations.get(sid, {}) if project else {}
            name = st["station_name"]

            # 部分区間の境界で異なるIDの駅が隣接しているときのy座標オフセット処理
            seg_id = st.get("segment_id")
            if seg_id is not None:
                # 前の駅と異なる部分区間、かつ駅IDが異なる場合（下側の部分区間の上端の駅）
                if i > 0:
                    prev_st = stations_data[i - 1]

                    if prev_st.get("station_id") == sid: # 前の駅と同じ駅名は描画不要
                        continue

                    if prev_st.get("segment_id") != seg_id:
                        y += 10.0
                # 次の駅と異なる部分区間、かつ駅IDが異なる場合（上側の部分区間の下端の駅）
                if i < len(stations_data) - 1:
                    next_st = stations_data[i + 1]
                    if next_st.get("segment_id") != seg_id and next_st.get("station_id") != sid:
                        y -= 10.0

            text_item = QGraphicsSimpleTextItem(name)
            if st_obj.get("is_major_station", False):
                text_item.setFont(font_major)
            else:
                text_item.setFont(font)
            text_item.setBrush(QBrush(QColor("#666666")))

            br = text_item.boundingRect()
            tx = self.STATION_WIDTH - br.width() - 5
            ty = y - (br.height() / 2.0)
            text_item.setPos(tx, ty)
            self.addItem(text_item)


# 運行ダイヤグラムのメインシーン（右下）
class DiagramScene(QGraphicsScene):
    def __init__(self, parent=None, scale_x: float = 6.0, scale_y: float = 1.0 / 3.0):
        super().__init__(parent)
        self.setBackgroundBrush(QBrush(QColor("#ffffff")))
        self.project = None
        self.selected_target = "route"  # "route" or line_id
        self.route_id = None
        self.diagram_id = None
        self.scale_x = scale_x
        self.scale_y = scale_y

    def set_scales(self, scale_x: float, scale_y: float):
        if self.scale_x != scale_x or self.scale_y != scale_y:
            self.scale_x = scale_x
            self.scale_y = scale_y

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
            return None

        # 1. 表示対象の駅リストを構築
        stations_data = self._collect_station_positions()

        # エラー（基準運転時分の設定されていない駅がある場合、または駅が存在しない等）の判定
        if stations_data is None:
            # エラー文描画
            self._render_error_message(
                "表示対象の路線に基準運転時分の設定されていない駅が含まれます。\n"
                "ダイヤグラムを表示するには基準運転時分の設定を完了してください。"
            )
            return None

        if not stations_data:
            self.setSceneRect(0, 0, 100, 100)
            return []

        # 2. 軸とグリッドの描画
        # 横軸: 0時から36時まで1分をscale_x px
        # 全体幅 = 36 * 60 * scale_x
        max_y = stations_data[-1]["y"]
        scene_h = max_y + 40
        scene_w = 36 * 60 * self.scale_x

        self.setSceneRect(0, 0, scene_w, max(scene_h, 200))

        # 縦線（時間）の描画
        self._render_time_lines(max_y, max(scene_h, 200))

        # 横線（駅）の描画
        self._render_station_lines(stations_data, scene_w)

        # 3. 列車のプロット描画
        self._render_trains(stations_data)

        return stations_data

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

                    # 基準運転時分(秒)に対しscale_y (上部余白40px)
                    y = 40.0 + (rel_time * self.scale_y)

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

                # 上部余白40px
                y = 40.0 + (abs_time * self.scale_y)
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

    def _render_station_lines(self, stations_data, line_end_x):
        pen_normal = QPen(QColor("#dddddd"), 1)
        pen_major = QPen(QColor("#aaaaaa"), 2)

        for st in stations_data:
            y = st["y"]
            sid = st["station_id"]
            st_obj = self.project.stations.get(sid, {}) if self.project else {}
            is_major = st_obj.get("is_major_station", False)

            pen = pen_major if is_major else pen_normal
            line_item = self.addLine(0, y, line_end_x, y, pen)
            line_item.setZValue(0)

    def _render_time_lines(self, max_y, total_scene_h):
        pen_5min = QPen(QColor("#dddddd"), 1)
        pen_5min.setStyle(Qt.DotLine)

        pen_10min = QPen(QColor("#dddddd"), 1)
        pen_hour = QPen(QColor("#aaaaaa"), 2)

        # 毎時5分〜55分: 上下40pxの余白を空ける (top_y=40.0, bottom_y=max_y)
        top_y_grid = 40.0
        bottom_y_grid = max_y

        # 毎時0分の縦線: ビューの上端から下端まで (0 から total_scene_h)
        for hour in range(37):  # 0時から36時
            hour_x = hour * 60 * self.scale_x

            # 毎時0分の縦線 (上端から下端まで)
            line_item = self.addLine(hour_x, 0, hour_x, total_scene_h, pen_hour)
            line_item.setZValue(0)

            # hour 36は0分のみ
            if hour < 36:
                # 毎時5、15、25、35、45、55分（点線）
                for minute_step in [5, 15, 25, 35, 45, 55]:
                    min_x = hour_x + minute_step * self.scale_x
                    m_line = self.addLine(min_x, top_y_grid, min_x, bottom_y_grid, pen_5min)
                    m_line.setZValue(0)

                # 毎時10分、20分、30分、40分、50分（実線）
                for minute_step in [10, 20, 30, 40, 50]:
                    min_x = hour_x + minute_step * self.scale_x
                    m_line = self.addLine(min_x, top_y_grid, min_x, bottom_y_grid, pen_10min)
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
                self._draw_single_train_for_route(m_train, stations_data, route)

    def _draw_single_train_for_route(self, train, stations_data, route):
        stops = train.get("stops", [])
        if not stops:
            return

        tt_id = train.get("train_type_id")
        pen = self._create_train_pen(tt_id)

        # 運行系統の部分区間の順序とインデックスのマップを作成
        segments = route.get("line_segments", [])
        segment_indices = {seg.get("segment_id"): idx for idx, seg in enumerate(segments)}

        # 連続する有効な区間ごとにパスを分割
        subpaths = []
        current_subpath = []
        prev_seg_id = None

        for stop in stops:
            seg_id = stop.get("segment_id")
            sid = stop.get("station_id")
            arr_time_str = stop.get("arrival_time")
            dep_time_str = stop.get("departure_time")

            arr_sec = self._time_to_seconds(arr_time_str)
            dep_sec = self._time_to_seconds(dep_time_str)

            # 有効な発着時刻がどちらもない場合は区間が途切れる
            if arr_sec is None and dep_sec is None:
                if len(current_subpath) >= 2:
                    subpaths.append(current_subpath)
                current_subpath = []
                prev_seg_id = None
                continue

            # 部分区間が飛んでいるか（連続していないか）チェック
            if prev_seg_id is not None and seg_id != prev_seg_id:
                prev_idx = segment_indices.get(prev_seg_id)
                curr_idx = segment_indices.get(seg_id)
                if prev_idx is None or curr_idx is None or abs(curr_idx - prev_idx) != 1:
                    if len(current_subpath) >= 2:
                        subpaths.append(current_subpath)
                    current_subpath = []

            # stations_data 内で一致する駅を検索
            target_entry = None
            for idx in range(len(stations_data)):
                st = stations_data[idx]
                if st.get("segment_id") == seg_id and st.get("station_id") == sid:
                    target_entry = st
                    break

            if not target_entry:
                if len(current_subpath) >= 2:
                    subpaths.append(current_subpath)
                current_subpath = []
                prev_seg_id = None
                continue

            y = target_entry["y"]

            if arr_sec is not None and dep_sec is not None:
                x_arr = (arr_sec / 60.0) * self.scale_x
                x_dep = (dep_sec / 60.0) * self.scale_x
                current_subpath.append((x_arr, y))
                if x_arr != x_dep:
                    current_subpath.append((x_dep, y))
            elif arr_sec is not None:
                x_arr = (arr_sec / 60.0) * self.scale_x
                current_subpath.append((x_arr, y))
            elif dep_sec is not None:
                x_dep = (dep_sec / 60.0) * self.scale_x
                current_subpath.append((x_dep, y))

            prev_seg_id = seg_id

        if len(current_subpath) >= 2:
            subpaths.append(current_subpath)

        for sp in subpaths:
            self._draw_path(sp, pen)

        # 列車番号ラベルの描画
        self._render_train_number_label(train, subpaths)

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
                    subpaths = []
                    current_subpath = []

                    tt_id = m_train.get("train_type_id")
                    pen = self._create_train_pen(tt_id)

                    for stop in stops:
                        seg_id = stop.get("segment_id")
                        arr_sec = self._time_to_seconds(stop.get("arrival_time"))
                        dep_sec = self._time_to_seconds(stop.get("departure_time"))

                        if seg_id not in target_segment_ids or (arr_sec is None and dep_sec is None):
                            if len(current_subpath) >= 2:
                                subpaths.append(current_subpath)
                            current_subpath = []
                            continue

                        sid = stop.get("station_id")
                        if sid not in station_y_map:
                            if len(current_subpath) >= 2:
                                subpaths.append(current_subpath)
                            current_subpath = []
                            continue

                        y = station_y_map[sid]

                        if arr_sec is not None and dep_sec is not None:
                            x_arr = (arr_sec / 60.0) * self.scale_x
                            x_dep = (dep_sec / 60.0) * self.scale_x
                            current_subpath.append((x_arr, y))
                            if x_arr != x_dep:
                                current_subpath.append((x_dep, y))
                        elif arr_sec is not None:
                            x_arr = (arr_sec / 60.0) * self.scale_x
                            current_subpath.append((x_arr, y))
                        elif dep_sec is not None:
                            x_dep = (dep_sec / 60.0) * self.scale_x
                            current_subpath.append((x_dep, y))

                    if len(current_subpath) >= 2:
                        subpaths.append(current_subpath)

                    for sp in subpaths:
                        self._draw_path(sp, pen)

                    # 列車番号ラベルの描画
                    self._render_train_number_label(m_train, subpaths)

    def _render_train_number_label(self, train, subpaths):
        train_number = train.get("train_number", "")
        if not train_number or not subpaths:
            return

        # 最初のサブパスを取得
        first_subpath = subpaths[0]
        if len(first_subpath) < 2:
            return

        p0 = first_subpath[0]
        # p0とy座標が異なる最初の点（次の経由駅での点）を探す
        p_next = None
        for pt in first_subpath[1:]:
            if pt[1] != p0[1]:
                p_next = pt
                break

        if p_next is None:
            # 異なるy座標の点がなければ2番目の点を採用
            p_next = first_subpath[1]

        dx = p_next[0] - p0[0]
        dy = p_next[1] - p0[1]

        # dy > 0: 上から下に向かう列車
        # dy < 0: 下から上に向かう列車
        if dy == 0 and dx == 0:
            return

        # 角度計算（度単位）
        angle_rad = math.atan2(dy, dx)
        angle_deg = math.degrees(angle_rad)

        # 文字色の取得
        tt_id = train.get("train_type_id")
        tt = self.project.train_types.get(tt_id) if (self.project and tt_id) else None
        main_color = tt.get("main_color", "#333333") if tt else "#333333"

        font = QFont()
        font.setPixelSize(12)

        text_item = QGraphicsSimpleTextItem(train_number)
        text_item.setFont(font)
        text_item.setBrush(QBrush(QColor(main_color)))

        # 回転中心をテキストの左上(0,0)にして回転
        text_item.setRotation(angle_deg)

        # 進行方向単位ベクトル
        length = math.hypot(dx, dy)
        ux = dx / length
        uy = dy / length

        if dy >= 0:
            # 画面上から下に向かう列車: 始点の右下側
            forward_dist = 4.0
            perp_dist = 4.0
            nx = uy
            ny = -ux
            pos_x = p0[0] + forward_dist * ux + perp_dist * nx + 15 # 列車のパスと重ならないように右へ15pxずらす
            pos_y = p0[1] + forward_dist * uy + perp_dist * ny
        else:
            # 画面下から上に向かう列車: 始点の左上側
            forward_dist = 4.0
            perp_dist = 4.0
            nx = -uy
            ny = ux
            pos_x = p0[0] + forward_dist * ux + perp_dist * nx - 25 # 列車のパスと重ならないように左へ25pxずらす
            pos_y = p0[1] + forward_dist * uy + perp_dist * ny

        text_item.setPos(pos_x, pos_y)
        text_item.setZValue(3)
        self.addItem(text_item)

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
