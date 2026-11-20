import math
import html
from PySide6.QtWidgets import (
    QGraphicsScene, QGraphicsLineItem, QGraphicsSimpleTextItem,
    QGraphicsPathItem, QGraphicsTextItem, QGraphicsDropShadowEffect
)
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
            if seg_id is not None and not st.get("is_track_entry", False):
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

            if st.get("is_track_entry", False):
                # 発着番線占有表表示時:
                # 最初の発着番線: 「<駅名> <発着番線名の省略表記>」
                # 2つ目以降: 「<発着番線名の省略表記>」
                # 「発着番線名の省略表記」は常にフォント太さを標準で表示する
                track_short_name = st.get("track_short_name", "")
                if st.get("is_first_track", False):
                    # 駅名部分（主要駅なら太字）と発着番線名（常に標準）を分けて描画
                    is_major = st_obj.get("is_major_station", False)
                    # 2つのアイテムを作成、またはまとめて位置決め
                    # 駅名アイテム
                    st_name_item = QGraphicsSimpleTextItem(name + " ")
                    st_name_item.setFont(font_major if is_major else font)
                    st_name_item.setBrush(QBrush(QColor("#666666")))
                    # 番線名アイテム (常に標準フォント)
                    trk_item = QGraphicsSimpleTextItem(track_short_name)
                    trk_item.setFont(font)
                    trk_item.setBrush(QBrush(QColor("#666666")))

                    br_st = st_name_item.boundingRect()
                    br_trk = trk_item.boundingRect()
                    total_w = br_st.width() + br_trk.width()

                    tx_start = self.STATION_WIDTH - total_w - 5
                    ty_st = y - (br_st.height() / 2.0)
                    ty_trk = y - (br_trk.height() / 2.0)

                    st_name_item.setPos(tx_start, ty_st)
                    trk_item.setPos(tx_start + br_st.width(), ty_trk)

                    self.addItem(st_name_item)
                    self.addItem(trk_item)
                    continue
                else:
                    text_item = QGraphicsSimpleTextItem(track_short_name)
                    text_item.setFont(font) # 常に標準フォント
                    text_item.setBrush(QBrush(QColor("#666666")))
            else:
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
        self.filter_train_type_id = None
        self.scale_x = scale_x
        self.scale_y = scale_y
        self.show_track_allocation_chart = False
        self.rendered_trains = []
        self.stations_data = []
        self.current_highlight_train = None
        self.current_highlight_query = ""
        # 発着番線占有表エリアの水平線分・点線情報（右クリック当たり判定用）
        # 各要素: {
        #   "x1": float, "x2": float, "y": float,  # 線分の座標 (y は水平線分。点線の場合はy1,y2)
        #   "y1": float, "y2": float,               # 点線の場合のみ使用
        #   "is_dotted": bool,                       # Trueなら点線、Falseなら水平線分
        #   "station_id": str,                       # 始点の駅ID
        #   "operation_id": str,                     # 車両運用ID
        #   "diagram_id": str,                       # 運転ダイヤID
        # }
        self.track_allocation_segments = []

    def set_scales(self, scale_x: float, scale_y: float):
        if self.scale_x != scale_x or self.scale_y != scale_y:
            self.scale_x = scale_x
            self.scale_y = scale_y

    def get_total_time(self, project=None, selected_target=None, route_id=None) -> float | None:
        """
        現在の表示対象（または指定された対象）の起点から終点までの合計基準運転時分（秒）を計算して返す。
        駅が2つ未満の場合や基準時分が設定されていない場合は None を返す。
        """
        proj = project if project is not None else self.project
        target = selected_target if selected_target is not None else self.selected_target
        r_id = route_id if route_id is not None else self.route_id

        if not proj:
            return None

        if target == "route":
            if not r_id or r_id not in proj.routes:
                return None
            route = proj.routes[r_id]
            segments = route.get("line_segments", [])
            if not segments:
                return None

            accumulated_time = 0.0
            station_count = 0

            for seg in segments:
                line_id = seg.get("line_id")
                start_eid = seg.get("start_station_entry", seg.get("start_station"))
                end_eid = seg.get("end_station_entry", seg.get("end_station"))

                line = proj.lines.get(line_id)
                if not line:
                    continue

                line_station_entries = line.get("station_entries", [])
                line_eids = [s.get("station_entry_id") for s in line_station_entries]
                station_map = {s.get("station_entry_id"): s for s in line_station_entries}

                if start_eid not in line_eids or end_eid not in line_eids:
                    continue

                idx_start = line_eids.index(start_eid)
                idx_end = line_eids.index(end_eid)

                if idx_start <= idx_end:
                    seg_eids = line_eids[idx_start:idx_end + 1]
                else:
                    seg_eids = line_eids[idx_start:idx_end - 1:-1] if idx_end > 0 else line_eids[idx_start::-1]

                start_st_info = station_map.get(start_eid)
                if not start_st_info or start_st_info.get("absolute_standard_running_time") is None:
                    return None
                start_abs_time = start_st_info.get("absolute_standard_running_time")

                end_st_info = station_map.get(end_eid)
                if not end_st_info or end_st_info.get("absolute_standard_running_time") is None:
                    return None
                end_abs_time = end_st_info.get("absolute_standard_running_time")

                station_count += len(seg_eids)
                accumulated_time += abs(end_abs_time - start_abs_time)

            if station_count < 2 or accumulated_time <= 0:
                return None
            return accumulated_time
        else:
            line = proj.lines.get(target)
            if not line:
                return None
            station_entries = line.get("station_entries", [])
            if len(station_entries) < 2:
                return None

            start_abs_time = station_entries[0].get("absolute_standard_running_time")
            end_abs_time = station_entries[-1].get("absolute_standard_running_time")
            if start_abs_time is None or end_abs_time is None:
                return None

            total_diff = abs(end_abs_time - start_abs_time)
            if total_diff <= 0:
                return None
            return float(total_diff)

    def calculate_auto_scale_y(self, viewport_height: int, project=None, selected_target=None, route_id=None, show_track_allocation_chart: bool = False) -> float | None:
        """
        ビューの表示高さ（viewport_height）にシーンの上下サイズ（max_y + 40）がちょうど収まるような scale_y の値を計算して返す。
        """
        total_time = self.get_total_time(project, selected_target, route_id)
        if total_time is None or total_time <= 0:
            return None

        # show_track_allocation_chartがTrueの場合、各対象駅の発着番線分の追加高さを計算
        extra_track_height = 0.0
        if show_track_allocation_chart:
            proj = project if project is not None else self.project
            target = selected_target if selected_target is not None else self.selected_target
            r_id = route_id if route_id is not None else self.route_id
            if proj:
                if target == "route" and r_id and r_id in proj.routes:
                    route = proj.routes[r_id]
                    segments = route.get("line_segments", [])
                    for seg in segments:
                        line_id = seg.get("line_id")
                        line = proj.lines.get(line_id)
                        if not line:
                            continue
                        line_station_entries = line.get("station_entries", [])
                        line_eids = [s.get("station_entry_id") for s in line_station_entries]
                        station_map = {s.get("station_entry_id"): s for s in line_station_entries}
                        start_eid = seg.get("start_station_entry", seg.get("start_station"))
                        end_eid = seg.get("end_station_entry", seg.get("end_station"))
                        if start_eid not in line_eids or end_eid not in line_eids:
                            continue
                        idx_start = line_eids.index(start_eid)
                        idx_end = line_eids.index(end_eid)
                        if idx_start <= idx_end:
                            seg_eids = line_eids[idx_start:idx_end + 1]
                        else:
                            seg_eids = line_eids[idx_start:idx_end - 1:-1] if idx_end > 0 else line_eids[idx_start::-1]
                        for eid in seg_eids:
                            st_info = station_map.get(eid)
                            if st_info:
                                sid = st_info.get("station_id")
                                st_obj = proj.stations.get(sid, {})
                                if st_obj.get("show_track_allocation_chart", False):
                                    tracks = st_obj.get("tracks_order") or st_obj.get("tracks") or []
                                    num_tracks = len(tracks)
                                    if num_tracks > 0:
                                        extra_track_height += num_tracks * 10.0
                elif target != "route" and target in proj.lines:
                    line = proj.lines.get(target)
                    if line:
                        for s_entry in line.get("station_entries", []):
                            sid = s_entry.get("station_id")
                            st_obj = proj.stations.get(sid, {})
                            if st_obj.get("show_track_allocation_chart", False):
                                tracks = st_obj.get("tracks_order") or st_obj.get("tracks") or []
                                num_tracks = len(tracks)
                                if num_tracks > 0:
                                    extra_track_height += num_tracks * 10.0

        # シーン全体の高さ: scene_h = max_y + 40 = 40 + total_time * scale_y + extra_track_height + 40 = total_time * scale_y + extra_track_height + 80
        # viewport_height に収まるためには: total_time * scale_y + extra_track_height + 80 = viewport_height
        available_height = viewport_height - 80.0 - extra_track_height
        if available_height <= 0:
            return 1.0 / 6.0  # 画面が極端に小さい場合のフォールバック値

        return available_height / total_time

    def _is_train_visible(self, m_train, d_train) -> bool:
        """フィルタリング条件に基づいて列車が表示対象かを判定する"""
        if self.filter_train_type_id is not None:
            if m_train.get("train_type_id") != self.filter_train_type_id:
                return False
        if self.filter_train_type_ids is not None:
            if m_train.get("train_type_id") not in self.filter_train_type_ids:
                return False
        if self.filter_operation_ids is not None:
            # 列車に設定されている運用IDのいずれかがfilter_operation_idsに含まれているかを判定
            ops = d_train.get("operations", [])
            train_op_ids = set()
            for op_entry in ops:
                op_id = op_entry.get("operation_id") if isinstance(op_entry, dict) else op_entry
                if op_id:
                    train_op_ids.add(op_id)
            if not (train_op_ids & self.filter_operation_ids):
                return False
        return True

    def update_diagram(self, project, selected_target: str, route_id: str, diagram_id: str,
            filter_train_type_id: str = None,
            filter_train_type_ids: set = None,
            filter_operation_ids: set = None,
            show_track_allocation_chart: bool = False):
        """
        運行ダイヤグラムを更新描画する。
        selected_target: "route" または line_id (str)
        route_id: 運行系統リストで選択中のroute_id
        diagram_id: 運転ダイヤリストで選択中のdiagram_id
        filter_train_type_id: 表示する列車種別のID。Noneの場合は全種別を表示（後方互換用）
        filter_train_type_ids: 表示する列車種別IDの集合。Noneの場合は全種別を表示
        filter_operation_ids: 表示する車両運用IDの集合。Noneの場合は全運用を表示
        show_track_allocation_chart: 発着番線占有表を表示するか否か
        """
        self.project = project
        self.selected_target = selected_target
        self.route_id = route_id
        self.diagram_id = diagram_id
        self.filter_train_type_id = filter_train_type_id
        self.filter_train_type_ids = filter_train_type_ids
        self.filter_operation_ids = filter_operation_ids
        self.show_track_allocation_chart = show_track_allocation_chart
        self.rendered_trains = []
        self.current_highlight_train = None
        self.current_highlight_query = ""
        self.track_allocation_segments = []

        self.clear()

        if not self.project:
            self.setSceneRect(0, 0, 100, 100)
            return None

        # 1. 表示対象の駅リストを構築
        stations_data = self._collect_station_positions()
        self.stations_data = stations_data

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
        active_views = self.views()

        if active_views:
            view = active_views[0]
            view_rect = view.rect()

            view_width = view_rect.width()
            view_height = view_rect.height()
        else:
            view_width = 300
            view_height = 200

        self.setSceneRect(0, 0, view_width, view_height)

        text_item = QGraphicsSimpleTextItem(text)
        font = QFont()
        font.setPixelSize(18)
        text_item.setFont(font)
        text_item.setBrush(QBrush(QColor("#888888")))
        self.addItem(text_item)

        text_rect = text_item.boundingRect()
        text_width = text_rect.width() * text_item.scale()
        text_height = text_rect.height() * text_item.scale()

        pos_x = (view_width - text_width) / 2
        pos_y = (view_height - text_height) / 2
        text_item.setPos(pos_x, pos_y)

    def _collect_station_positions(self):
        """
        表示対象の駅リストを抽出し、それぞれのy座標を計算する。
        Noneが含まれる場合はNoneを返す。
        戻り値:
        [
            {
                "station_entry_id": str,
                "station_id": str,
                "station_name": str,
                "y": float,
                "segment_id": str (運行系統の場合) or None,
                "rel_time": float,
                "is_track_entry": bool,
                "track_id": str or None,
                "track_short_name": str or None,
                "is_first_track": bool,
                "station_y_top": float,
                "station_y_bottom": float,
                "tracks_count": int,
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
            cumulative_extra_y = 0.0

            for seg_idx, seg in enumerate(segments):
                line_id = seg.get("line_id")
                start_eid = seg.get("start_station_entry", seg.get("start_station"))
                end_eid = seg.get("end_station_entry", seg.get("end_station"))
                seg_id = seg.get("segment_id")

                line = self.project.lines.get(line_id)
                if not line:
                    continue

                line_station_entries = line.get("station_entries", [])
                line_eids = [s.get("station_entry_id") for s in line_station_entries]
                station_map = {s.get("station_entry_id"): s for s in line_station_entries}

                if start_eid not in line_eids or end_eid not in line_eids:
                    continue

                idx_start = line_eids.index(start_eid)
                idx_end = line_eids.index(end_eid)

                if idx_start <= idx_end:
                    seg_eids = line_eids[idx_start:idx_end + 1]
                else:
                    seg_eids = line_eids[idx_start:idx_end - 1:-1] if idx_end > 0 else line_eids[idx_start::-1]

                start_st_info = station_map.get(start_eid)
                if not start_st_info or start_st_info.get("absolute_standard_running_time") is None:
                    return None
                start_abs_time = start_st_info.get("absolute_standard_running_time")

                end_st_info = station_map.get(end_eid)
                if not end_st_info or end_st_info.get("absolute_standard_running_time") is None:
                    return None
                end_abs_time = end_st_info.get("absolute_standard_running_time")

                for eid in seg_eids:
                    st_info = station_map.get(eid)
                    if not st_info or st_info.get("absolute_standard_running_time") is None:
                        return None
                    abs_time = st_info.get("absolute_standard_running_time")

                    # その駅が属する部分区間の始点とのabsolute_standard_running_timeの差の絶対値 + それまでの部分区間の起点と終点の差の絶対値の合計
                    diff = abs(abs_time - start_abs_time)
                    rel_time = accumulated_time + diff

                    # 基準運転時分(秒)に対しscale_y (上部余白40px)
                    base_y = 40.0 + (rel_time * self.scale_y) + cumulative_extra_y

                    sid = st_info.get("station_id")
                    st_obj = self.project.stations.get(sid, {})
                    st_name = st_obj.get("station_name", sid)

                    if self.show_track_allocation_chart and st_obj.get("show_track_allocation_chart", False):
                        tracks_dict = st_obj.get("tracks", {})
                        tracks_order = st_obj.get("tracks_order", [])
                        if not tracks_order and isinstance(tracks_dict, dict):
                            tracks_order = list(tracks_dict.keys())
                        num_tracks = len(tracks_order)
                        if num_tracks > 0:
                            station_y_top = base_y
                            station_y_bottom = base_y + num_tracks * 10.0
                            for k, trk_id in enumerate(tracks_order):
                                trk_info = tracks_dict.get(trk_id, {}) if isinstance(tracks_dict, dict) else {}
                                trk_short = trk_info.get("track_short_name", trk_id)
                                track_center_y = base_y + k * 10.0 + 5.0
                                stations_data.append({
                                    "station_entry_id": eid,
                                    "station_id": sid,
                                    "station_name": st_name,
                                    "y": track_center_y,
                                    "segment_id": seg_id,
                                    "rel_time": rel_time,
                                    "is_track_entry": True,
                                    "track_id": trk_id,
                                    "track_short_name": trk_short,
                                    "is_first_track": (k == 0),
                                    "station_y_top": station_y_top,
                                    "station_y_bottom": station_y_bottom,
                                    "tracks_count": num_tracks,
                                })
                            cumulative_extra_y += num_tracks * 10.0
                            continue

                    stations_data.append({
                        "station_entry_id": eid,
                        "station_id": sid,
                        "station_name": st_name,
                        "y": base_y,
                        "segment_id": seg_id,
                        "rel_time": rel_time,
                        "is_track_entry": False,
                        "track_id": None,
                        "track_short_name": None,
                        "is_first_track": True,
                        "station_y_top": base_y,
                        "station_y_bottom": base_y,
                        "tracks_count": 0,
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

            station_entries = line.get("station_entries", [])
            if not station_entries:
                return []

            stations_data = []
            cumulative_extra_y = 0.0

            for s_entry in station_entries:
                eid = s_entry.get("station_entry_id")
                sid = s_entry.get("station_id")
                abs_time = s_entry.get("absolute_standard_running_time")
                if abs_time is None:
                    return None

                # 上部余白40px
                base_y = 40.0 + (abs_time * self.scale_y) + cumulative_extra_y
                st_obj = self.project.stations.get(sid, {})
                st_name = st_obj.get("station_name", sid)

                if self.show_track_allocation_chart and st_obj.get("show_track_allocation_chart", False):
                    tracks_dict = st_obj.get("tracks", {})
                    tracks_order = st_obj.get("tracks_order", [])
                    if not tracks_order and isinstance(tracks_dict, dict):
                        tracks_order = list(tracks_dict.keys())
                    num_tracks = len(tracks_order)
                    if num_tracks > 0:
                        station_y_top = base_y
                        station_y_bottom = base_y + num_tracks * 10.0
                        for k, trk_id in enumerate(tracks_order):
                            trk_info = tracks_dict.get(trk_id, {}) if isinstance(tracks_dict, dict) else {}
                            trk_short = trk_info.get("track_short_name", trk_id)
                            track_center_y = base_y + k * 10.0 + 5.0
                            stations_data.append({
                                "station_entry_id": eid,
                                "station_id": sid,
                                "station_name": st_name,
                                "y": track_center_y,
                                "segment_id": None,
                                "abs_time": abs_time,
                                "is_track_entry": True,
                                "track_id": trk_id,
                                "track_short_name": trk_short,
                                "is_first_track": (k == 0),
                                "station_y_top": station_y_top,
                                "station_y_bottom": station_y_bottom,
                                "tracks_count": num_tracks,
                            })
                        cumulative_extra_y += num_tracks * 10.0
                        continue

                stations_data.append({
                    "station_entry_id": eid,
                    "station_id": sid,
                    "station_name": st_name,
                    "y": base_y,
                    "segment_id": None,
                    "abs_time": abs_time,
                    "is_track_entry": False,
                    "track_id": None,
                    "track_short_name": None,
                    "is_first_track": True,
                    "station_y_top": base_y,
                    "station_y_bottom": base_y,
                    "tracks_count": 0,
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

            # 発着番線の線は細線、通常駅の主要駅は2px、それ以外は1px
            if st.get("is_track_entry", False):
                pen = pen_normal
            else:
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

        # 「全て表示」または「車両運用」フィルタリング時は接続パスおよび運用番号ラベルを描画する
        if self.filter_train_type_id is None and self.filter_train_type_ids is None:
            self._render_operations(stations_data)

    def _render_trains_for_route(self, stations_data):
        route = self.project.routes.get(self.route_id)
        if not route:
            return

        tbd = route.get("trains_by_diagram", {}).get(self.diagram_id, {})
        d_inbound = tbd.get("inbound_trains", {})
        d_outbound = tbd.get("outbound_trains", {})
        m_inbound = route.get("inbound_trains", {})
        m_outbound = route.get("outbound_trains", {})

        for d_dict, m_dict, direction in [
            (d_outbound, m_outbound, "outbound"),
            (d_inbound, m_inbound, "inbound"),
        ]:
            for tid, d_train in d_dict.items():
                if not d_train.get("to_be_saved", True):
                    continue
                m_train = m_dict.get(tid)
                if not m_train:
                    continue
                # 列車フィルタ
                if not self._is_train_visible(m_train, d_train):
                    continue
                self._draw_single_train_for_route(m_train, stations_data, route, tid, direction, self.route_id)

    def _build_train_subpaths(self, stops, stations_data, segment_indices=None, target_segment_ids=None):
        """
        列車の経由駅情報(stops)とstations_dataから、描画すべきサブパス群を生成する。
        発着番線占有表表示 (show_track_allocation_chart) が有効な駅の場合は、
        領域境界・発着番線への垂直・水平線分、通過時の垂直線分を適切に挿入する。
        戻り値:
        - subpaths: 通常の列車ペンのサブパス (QPointF/tupleのリストのリスト)
        - track_items_info: 発着番線占有表用の個別線分情報 (水平線: 2px, 垂直線: 0.5px)
        - full_subpaths: 列車番号ラベルや進行方向判定用の連続座標リスト
        - valid_stops_record: 各ポイントに対応する経由駅情報の記録
        """
        tt_id = None
        # target_segment_ids が指定されている場合（路線表示）はフィルタ
        # segment_indices が指定されている場合（運行系統表示）は連続性チェック

        subpaths = []
        track_horizontal_segments = [] # [(x1, x2, y)] 太さ2px
        track_vertical_segments = []   # [(x, y1, y2)] 太さ0.5px
        label_subpaths = []

        current_subpath = []
        current_label_subpath = []
        current_stops = []
        all_subpath_stops = []
        prev_seg_id = None

        # 連続する駅のY座標の推移を追跡するために、前回の駅位置(y)を保持
        last_y = None

        # stations_data 内の発着番線占有表表示の駅オカレンス一覧をあらかじめ抽出
        track_chart_stations = []
        seen_occ = set()
        for st in stations_data:
            if st.get("is_track_entry"):
                occ_key = (st.get("segment_id"), st.get("station_entry_id"), st.get("station_y_top"))
                if occ_key not in seen_occ:
                    seen_occ.add(occ_key)
                    track_chart_stations.append(st)

        for stop_idx, stop in enumerate(stops):

            seg_id = stop.get("segment_id")
            eid = stop.get("station_entry_id")
            arr_time_str = stop.get("arrival_time")
            dep_time_str = stop.get("departure_time")
            stop_type = stop.get("stop_type", 1)
            assigned_track_id = stop.get("track_id")

            arr_sec = self._time_to_seconds(arr_time_str)
            dep_sec = self._time_to_seconds(dep_time_str)

            # 路線表示で対象部分区間外、または有効な発着時刻がどちらもない場合
            if target_segment_ids is not None and seg_id not in target_segment_ids:
                if len(current_subpath) >= 2:
                    subpaths.append(current_subpath)
                if len(current_label_subpath) >= 2:
                    label_subpaths.append(current_label_subpath)
                if current_stops:
                    all_subpath_stops.append(current_stops)
                current_subpath = []
                current_label_subpath = []
                current_stops = []
                prev_seg_id = None
                last_y = None
                continue

            if arr_sec is None and dep_sec is None:
                if len(current_subpath) >= 2:
                    subpaths.append(current_subpath)
                if len(current_label_subpath) >= 2:
                    label_subpaths.append(current_label_subpath)
                if current_stops:
                    all_subpath_stops.append(current_stops)
                current_subpath = []
                current_label_subpath = []
                current_stops = []
                prev_seg_id = None
                last_y = None
                continue

            # 運行系統表示で部分区間が飛んでいるかチェック
            if segment_indices is not None and prev_seg_id is not None and seg_id != prev_seg_id:
                prev_idx = segment_indices.get(prev_seg_id)
                curr_idx = segment_indices.get(seg_id)
                if prev_idx is None or curr_idx is None or abs(curr_idx - prev_idx) != 1:
                    if len(current_subpath) >= 2:
                        subpaths.append(current_subpath)
                    if len(current_label_subpath) >= 2:
                        label_subpaths.append(current_label_subpath)
                    if current_stops:
                        all_subpath_stops.append(current_stops)
                    current_subpath = []
                    current_label_subpath = []
                    current_stops = []
                    last_y = None

            # stations_data 内で一致する駅を検索
            # 発着番線占有表表示の駅は同一駅が複数行(trackごと)に並んでいる
            # また同一駅が複数回登場する場合もあるため、マッチするエントリ群を抽出
            matching_entries = []
            for st in stations_data:
                # 運行系統表示では segment_id と station_entry_id
                # 路線表示では station_entry_id のみ (segment_id は None)
                if target_segment_ids is not None:
                    if st.get("station_entry_id") == eid:
                        matching_entries.append(st)
                else:
                    if st.get("segment_id") == seg_id and st.get("station_entry_id") == eid:
                        matching_entries.append(st)

            if not matching_entries:
                if len(current_subpath) >= 2:
                    subpaths.append(current_subpath)
                if len(current_label_subpath) >= 2:
                    label_subpaths.append(current_label_subpath)
                if current_stops:
                    all_subpath_stops.append(current_stops)
                current_subpath = []
                current_label_subpath = []
                current_stops = []
                prev_seg_id = None
                last_y = None
                continue

            # 同一駅が複数回描画されている場合の隣接オカレンス判定
            # last_y があればそれに最も近いオカレンスを選択
            first_entry = matching_entries[0]
            if len(matching_entries) > 1 and not first_entry.get("is_track_entry", False):
                # 通常駅で複数回登場
                if last_y is not None:
                    first_entry = min(matching_entries, key=lambda e: abs(e["y"] - last_y))
            elif first_entry.get("is_track_entry", False):
                # 発着番線占有駅の場合、オカレンスごとに tracks_count 個のエントリが連続している
                tracks_count = first_entry.get("tracks_count", len(matching_entries))
                if len(matching_entries) > tracks_count and last_y is not None:
                    # 複数オカレンスから last_y に最も近いオカレンスを選択
                    occurrences = [matching_entries[k:k+tracks_count] for k in range(0, len(matching_entries), tracks_count)]
                    best_occ = min(occurrences, key=lambda occ: abs(occ[0]["station_y_top"] - last_y))
                    matching_entries = best_occ
                    first_entry = matching_entries[0]

            is_track_chart = first_entry.get("is_track_entry", False)

            if not is_track_chart:
                # --- 通常の駅描画 ---
                y = first_entry["y"]
                pt_time_sec = arr_sec if arr_sec is not None else dep_sec
                pt_x = (pt_time_sec / 60.0) * self.scale_x

                # 前の駅(last_pt)から現在の駅(pt_x, y)へのパスが、
                # 途中の発着番線占有駅を跨いでいるかチェック
                if current_subpath:
                    last_pt = current_subpath[-1] # (x_prev, y_prev)
                    # last_pt と (pt_x, y) の間に位置する発着番線占有駅を検索
                    intervening_charts = []
                    # 進行方向 (下向きか上向きか)
                    if y > last_pt[1]:
                        # 下向き (y_prev -> y)
                        for occ in track_chart_stations:
                            # occ["station_y_top"] と occ["station_y_bottom"] が (last_pt[1], y) に含まれているか
                            if last_pt[1] <= occ["station_y_top"] and occ["station_y_bottom"] <= y:
                                intervening_charts.append((occ["station_y_top"], occ))
                        intervening_charts.sort(key=lambda item: item[0])
                    elif y < last_pt[1]:
                        # 上向き (y_prev -> y)
                        for occ in track_chart_stations:
                            if y <= occ["station_y_top"] and occ["station_y_bottom"] <= last_pt[1]:
                                intervening_charts.append((occ["station_y_bottom"], occ))
                        intervening_charts.sort(key=lambda item: item[0], reverse=True)

                    for _, occ in intervening_charts:
                        st_top = occ["station_y_top"]
                        st_bottom = occ["station_y_bottom"]
                        if y > last_pt[1]:
                            # 下向き進入: topから進入してbottomから出る
                            y_in = st_top
                            y_out = st_bottom
                        else:
                            # 上向き進入: bottomから進入してtopから出る
                            y_in = st_bottom
                            y_out = st_top

                        # 線形補間により通過時刻(X座標)を計算
                        # 直線: last_pt -> (pt_x, y)
                        dy_total = y - last_pt[1]
                        if dy_total != 0:
                            # y_in での時刻 (垂直線なので y_in の時刻で結ぶ)
                            frac_in = (y_in - last_pt[1]) / dy_total
                            x_cross = last_pt[0] + frac_in * (pt_x - last_pt[0])
                        else:
                            x_cross = last_pt[0]

                        # 前のパスを y_in で区切る
                        current_subpath.append((x_cross, y_in))
                        subpaths.append(current_subpath)

                        # 通過部分の垂直線分 (太さ0.5px)
                        track_vertical_segments.append((x_cross, y_in, y_out))
                        current_label_subpath.append((x_cross, (st_top + st_bottom) / 2.0))

                        # 次のパスを y_out から再開
                        current_subpath = [(x_cross, y_out)]
                        last_pt = current_subpath[-1]

                # 現在の駅の点を current_subpath に追加
                if arr_sec is not None and dep_sec is not None:
                    x_arr = (arr_sec / 60.0) * self.scale_x
                    x_dep = (dep_sec / 60.0) * self.scale_x
                    current_subpath.append((x_arr, y))
                    current_label_subpath.append((x_arr, y))
                    if x_arr != x_dep:
                        current_subpath.append((x_dep, y))
                        current_label_subpath.append((x_dep, y))
                elif arr_sec is not None:
                    x_arr = (arr_sec / 60.0) * self.scale_x
                    current_subpath.append((x_arr, y))
                    current_label_subpath.append((x_arr, y))
                elif dep_sec is not None:
                    x_dep = (dep_sec / 60.0) * self.scale_x
                    current_subpath.append((x_dep, y))
                    current_label_subpath.append((x_dep, y))

                last_y = y

            else:
                # --- 発着番線占有表の駅描画 ---
                # 駅の領域境界:
                station_top = first_entry["station_y_top"]
                station_bottom = first_entry["station_y_bottom"]

                # 進行方向を判定
                entering_from_top = True
                if last_y is not None:
                    entering_from_top = (last_y <= station_top)
                else:
                    # 次の駅を探して方向を推測
                    next_y = None
                    for next_s in stops[stop_idx + 1:]:
                        n_eid = next_s.get("station_entry_id")
                        for st in stations_data:
                            if st.get("station_entry_id") == n_eid:
                                next_y = st.get("station_y_top") if st.get("is_track_entry") else st.get("y")
                                break
                        if next_y is not None:
                            break
                    if next_y is not None:
                        entering_from_top = (next_y >= station_bottom)
                    else:
                        entering_from_top = True

                # 出る方向(exiting direction): 次の駅の位置から判定
                exiting_towards_bottom = True
                next_y = None
                for next_s in stops[stop_idx + 1:]:
                    n_eid = next_s.get("station_entry_id")
                    for st in stations_data:
                        if st.get("station_entry_id") == n_eid:
                            next_y = st.get("station_y_top") if st.get("is_track_entry") else st.get("y")
                            break
                    if next_y is not None:
                        break
                if next_y is not None:
                    exiting_towards_bottom = (next_y >= station_bottom)
                else:
                    exiting_towards_bottom = entering_from_top

                # 当該駅の発着番線 Y 座標
                track_y = None
                if assigned_track_id:
                    for me in matching_entries:
                        if me.get("track_id") == assigned_track_id:
                            track_y = me["y"]
                            break
                if track_y is None:
                    track_y = matching_entries[0]["y"]

                # 到着・出発の時刻とX座標
                t_arr_sec = arr_sec if arr_sec is not None else dep_sec
                t_dep_sec = dep_sec if dep_sec is not None else arr_sec
                x_arr = (t_arr_sec / 60.0) * self.scale_x
                x_dep = (t_dep_sec / 60.0) * self.scale_x

                is_passing = (stop_type == 0)

                # 外部パス（駅境界まで）の処理
                entry_boundary_y = station_top if entering_from_top else station_bottom
                exit_boundary_y = station_bottom if exiting_towards_bottom else station_top

                # 前の駅(last_pt)から entry_boundary_y までの間に
                # 別の発着番線占有駅が跨がれているかチェック
                if current_subpath:
                    last_pt = current_subpath[-1]
                    intervening_charts = []
                    if entry_boundary_y > last_pt[1]:
                        for occ in track_chart_stations:
                            # 自身 (first_entry) は除外
                            if occ["station_entry_id"] == eid and occ.get("segment_id") == seg_id:
                                continue
                            if last_pt[1] <= occ["station_y_top"] and occ["station_y_bottom"] <= entry_boundary_y:
                                intervening_charts.append((occ["station_y_top"], occ))
                        intervening_charts.sort(key=lambda item: item[0])
                    elif entry_boundary_y < last_pt[1]:
                        for occ in track_chart_stations:
                            if occ["station_entry_id"] == eid and occ.get("segment_id") == seg_id:
                                continue
                            if entry_boundary_y <= occ["station_y_top"] and occ["station_y_bottom"] <= last_pt[1]:
                                intervening_charts.append((occ["station_y_bottom"], occ))
                        intervening_charts.sort(key=lambda item: item[0], reverse=True)

                    for _, occ in intervening_charts:
                        st_top = occ["station_y_top"]
                        st_bottom = occ["station_y_bottom"]
                        if entry_boundary_y > last_pt[1]:
                            y_in = st_top
                            y_out = st_bottom
                        else:
                            y_in = st_bottom
                            y_out = st_top

                        dy_total = entry_boundary_y - last_pt[1]
                        if dy_total != 0:
                            frac_in = (y_in - last_pt[1]) / dy_total
                            x_cross = last_pt[0] + frac_in * (x_arr - last_pt[0])
                        else:
                            x_cross = last_pt[0]

                        current_subpath.append((x_cross, y_in))
                        subpaths.append(current_subpath)

                        track_vertical_segments.append((x_cross, y_in, y_out))
                        current_label_subpath.append((x_cross, (st_top + st_bottom) / 2.0))

                        current_subpath = [(x_cross, y_out)]
                        last_pt = current_subpath[-1]

                # もし始発駅で前にパスがない場合は entry_boundary に外部パスは不要
                # 前にパスがある場合: current_subpath に entry_boundary 点を追加してサブパスを区切る
                if current_subpath:
                    current_subpath.append((x_arr, entry_boundary_y))
                    subpaths.append(current_subpath)
                    current_subpath = []

                if is_passing:
                    # 通過列車:
                    # 当該駅の部分(発着番線用の領域の箇所)は垂直線で結ぶ
                    # 垂直線: (x_arr, entry_boundary_y) から (x_arr, exit_boundary_y)
                    # 太さ0.5px
                    track_vertical_segments.append((x_arr, entry_boundary_y, exit_boundary_y))
                    current_label_subpath.append((x_arr, (station_top + station_bottom) / 2.0))
                else:
                    # 停車列車:
                    # 発着番線に水平線分 (太さ2px実線)
                    track_horizontal_segments.append((x_arr, x_dep, track_y))
                    current_label_subpath.append((x_arr, track_y))
                    if x_arr != x_dep:
                        current_label_subpath.append((x_dep, track_y))

                    # 垂直線 (太さ0.5px実線):
                    # 前のパスと結ぶ: 始発駅でなく前がある場合、または到着がある場合
                    if last_y is not None:
                        track_vertical_segments.append((x_arr, entry_boundary_y, track_y))

                    # 後のパスと結ぶ: 次の駅がある場合
                    if next_y is not None:
                        track_vertical_segments.append((x_dep, track_y, exit_boundary_y))

                # 次の駅に向けて current_subpath を exit_boundary から開始
                if next_y is not None:
                    exit_x = x_arr if is_passing else x_dep
                    current_subpath = [(exit_x, exit_boundary_y)]

                last_y = exit_boundary_y

            current_stops.append(stop)
            prev_seg_id = seg_id

        if len(current_subpath) >= 2:
            subpaths.append(current_subpath)
        if len(current_label_subpath) >= 2:
            label_subpaths.append(current_label_subpath)
        if current_stops:
            all_subpath_stops.append(current_stops)


        # 全発着番線占有駅について、同一駅の全オカレンスに水平線分を描画する仕様:
        # 「show_track_allocation_chartがTrueの同一駅が運行ダイヤグラム上で複数回描画されるとき、
        # 発着番線部分の水平線はその全てに描画されるが、この水平線と列車のパスを結ぶ垂直線は、
        # 列車のパスと駅の領域が接している部分にしか描画しない。」
        # 停車列車で track_horizontal_segments に追加された各水平線について、
        # 同じ駅(station_id)かつ同じtrack_idの他のオカレンスがあれば、そこにも水平線分を追加する
        extra_horizontal_segments = []
        for (x1, x2, ty) in track_horizontal_segments:
            # ty に該当する station_data エントリを見つける
            source_entry = None
            for st in stations_data:
                if st.get("is_track_entry") and abs(st["y"] - ty) < 0.1:
                    source_entry = st
                    break
            if source_entry:
                sid = source_entry["station_id"]
                trkid = source_entry.get("track_id")
                # stations_data 内の他のオカレンスで同一 sid, trkid を探す
                for other_st in stations_data:
                    if other_st is not source_entry and other_st.get("station_id") == sid and other_st.get("track_id") == trkid:
                        extra_horizontal_segments.append((x1, x2, other_st["y"]))

        track_horizontal_segments.extend(extra_horizontal_segments)

        return subpaths, track_horizontal_segments, track_vertical_segments, label_subpaths, all_subpath_stops

    def _draw_single_train_for_route(self, train, stations_data, route, train_id: str, direction: str, route_id: str):
        stops = train.get("stops", [])
        if not stops:
            return

        tt_id = train.get("train_type_id")
        pen = self._create_train_pen(tt_id)

        segments = route.get("line_segments", [])
        segment_indices = {seg.get("segment_id"): idx for idx, seg in enumerate(segments)}

        subpaths, track_h_segs, track_v_segs, label_subpaths, all_subpath_stops = self._build_train_subpaths(
            stops, stations_data, segment_indices=segment_indices, target_segment_ids=None
        )

        path_items = []
        # 通常のサブパスを描画
        for sp in subpaths:
            p_item = self._draw_path(sp, pen)
            if p_item:
                path_items.append(p_item)

        # 発着番線占有表用の線分を描画
        tt = self.project.train_types.get(tt_id) if (self.project and tt_id) else None
        main_color = tt.get("main_color", "#333333") if tt else "#333333"

        # 水平線分: 2px実線 (列車の種別色)
        pen_horizontal = QPen(QColor(main_color), 2.0, Qt.SolidLine)
        for (x1, x2, y) in track_h_segs:
            p = QPainterPath()
            p.moveTo(x1, y)
            p.lineTo(x2, y)
            p_item = QGraphicsPathItem(p)
            p_item.setPen(pen_horizontal)
            p_item.setZValue(2)
            self.addItem(p_item)
            path_items.append(p_item)

        # 垂直線分: 0.5px実線 (列車の種別色)
        pen_vertical = QPen(QColor(main_color), 0.5, Qt.SolidLine)
        for (x, y1, y2) in track_v_segs:
            p = QPainterPath()
            p.moveTo(x, y1)
            p.lineTo(x, y2)
            p_item = QGraphicsPathItem(p)
            p_item.setPen(pen_vertical)
            p_item.setZValue(2)
            self.addItem(p_item)
            path_items.append(p_item)

        # 列車番号ラベルの描画 (ラベル用座標を使用)
        effective_subpaths = label_subpaths if label_subpaths else subpaths
        text_item = self._render_train_number_label(train, effective_subpaths)

        # 始発時刻（表示されている最初の有効な発着時刻）を取得
        sort_key = None
        for stop in stops:
            arr = self._time_to_seconds(stop.get("arrival_time"))
            dep = self._time_to_seconds(stop.get("departure_time"))
            if dep is not None:
                sort_key = dep
                break
            elif arr is not None:
                sort_key = arr
                break
        if sort_key is None:
            sort_key = 0

        p0 = effective_subpaths[0][0] if effective_subpaths and effective_subpaths[0] else (0, 0)

        self.rendered_trains.append({
            "train_id": train_id,
            "direction": direction,
            "route_id": route_id,
            "train_number": str(train.get("train_number", "")),
            "sort_key": sort_key,
            "path_items": path_items,
            "text_item": text_item,
            "main_color": main_color,
            "p0": p0,
        })

    def _render_trains_for_line(self, stations_data):
        target_line_id = self.selected_target

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

            for d_dict, m_dict, direction in [
                (d_outbound, m_outbound, "outbound"),
                (d_inbound, m_inbound, "inbound"),
            ]:
                for tid, d_train in d_dict.items():
                    if not d_train.get("to_be_saved", True):
                        continue
                    m_train = m_dict.get(tid)
                    if not m_train:
                        continue

                    # 列車フィルタ
                    if not self._is_train_visible(m_train, d_train):
                        continue

                    stops = m_train.get("stops", [])
                    tt_id = m_train.get("train_type_id")
                    pen = self._create_train_pen(tt_id)

                    subpaths, track_h_segs, track_v_segs, label_subpaths, all_subpath_stops = self._build_train_subpaths(
                        stops, stations_data, segment_indices=None, target_segment_ids=target_segment_ids
                    )

                    path_items = []
                    for sp in subpaths:
                        p_item = self._draw_path(sp, pen)
                        if p_item:
                            path_items.append(p_item)

                    tt = self.project.train_types.get(tt_id) if (self.project and tt_id) else None
                    main_color = tt.get("main_color", "#333333") if tt else "#333333"

                    # 水平線分: 2px実線 (列車の種別色)
                    pen_horizontal = QPen(QColor(main_color), 2.0, Qt.SolidLine)
                    for (x1, x2, y) in track_h_segs:
                        p = QPainterPath()
                        p.moveTo(x1, y)
                        p.lineTo(x2, y)
                        p_item = QGraphicsPathItem(p)
                        p_item.setPen(pen_horizontal)
                        p_item.setZValue(2)
                        self.addItem(p_item)
                        path_items.append(p_item)

                    # 垂直線分: 0.5px実線 (列車の種別色)
                    pen_vertical = QPen(QColor(main_color), 0.5, Qt.SolidLine)
                    for (x, y1, y2) in track_v_segs:
                        p = QPainterPath()
                        p.moveTo(x, y1)
                        p.lineTo(x, y2)
                        p_item = QGraphicsPathItem(p)
                        p_item.setPen(pen_vertical)
                        p_item.setZValue(2)
                        self.addItem(p_item)
                        path_items.append(p_item)

                    # 列車番号ラベルの描画
                    effective_subpaths = label_subpaths if label_subpaths else subpaths
                    text_item = self._render_train_number_label(m_train, effective_subpaths)

                    # 始発時刻（表示されている最初の有効な発着時刻）を取得
                    sort_key = None
                    for stop in stops:
                        arr = self._time_to_seconds(stop.get("arrival_time"))
                        dep = self._time_to_seconds(stop.get("departure_time"))
                        if dep is not None:
                            sort_key = dep
                            break
                        elif arr is not None:
                            sort_key = arr
                            break
                    if sort_key is None:
                        sort_key = 0

                    p0 = effective_subpaths[0][0] if effective_subpaths and effective_subpaths[0] else (0, 0)

                    self.rendered_trains.append({
                        "train_id": tid,
                        "direction": direction,
                        "route_id": rid,
                        "train_number": str(m_train.get("train_number", "")),
                        "sort_key": sort_key,
                        "path_items": path_items,
                        "text_item": text_item,
                        "main_color": main_color,
                        "p0": p0,
                    })


    def _render_train_number_label(self, train, subpaths):
        train_number = train.get("train_number", "")
        if not train_number or not subpaths:
            return None

        # 最初のサブパスを取得
        first_subpath = subpaths[0]
        if len(first_subpath) < 2:
            return None

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
            return None

        # 角度計算（度単位）
        angle_rad = math.atan2(dy, dx)
        angle_deg = math.degrees(angle_rad)

        # 文字色の取得
        tt_id = train.get("train_type_id")
        tt = self.project.train_types.get(tt_id) if (self.project and tt_id) else None
        main_color = tt.get("main_color", "#333333") if tt else "#333333"

        font = QFont()
        font.setPixelSize(12)

        text_item = QGraphicsTextItem()
        text_item.document().setDocumentMargin(0)
        text_item.setFont(font)
        text_item.setDefaultTextColor(QColor(main_color))
        text_item.setPlainText(train_number)

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
        return text_item

    def _draw_path(self, points, pen):
        if len(points) < 2:
            return None
        path = QPainterPath()
        path.moveTo(points[0][0], points[0][1])
        for pt in points[1:]:
            path.lineTo(pt[0], pt[1])

        path_item = QGraphicsPathItem(path)
        path_item.setPen(pen)
        path_item.setZValue(2)
        self.addItem(path_item)
        return path_item

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
            pen.setWidthF(0.6)
        elif weight_str == "bold":
            pen.setWidthF(1.8)
        else:
            pen.setWidthF(1.2)

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

    def get_matching_trains(self, query: str):
        """
        検索文字列に列車番号が部分一致する表示中の列車を、始発時刻順（同一時は列車番号順）にリストアップして返す。
        """
        query = query.strip()
        if not query:
            return []
        
        matches = [t for t in self.rendered_trains if query in t["train_number"]]
        # 始発時刻順、同一時刻の場合は列車番号順でソート
        matches.sort(key=lambda t: (t["sort_key"], t["train_number"]))
        return matches

    def clear_highlight(self):
        """現在ハイライトされている列車のハイライトを解除する"""
        if self.current_highlight_train:
            t_data = self.current_highlight_train
            for p_item in t_data.get("path_items", []):
                p_item.setGraphicsEffect(None)
                p_item.setZValue(2)
            
            text_item = t_data.get("text_item")
            if text_item:
                text_item.setPlainText(t_data.get("train_number", ""))
                text_item.setZValue(3)

            self.current_highlight_train = None
            self.current_highlight_query = ""

    def highlight_train(self, train_data, query: str):
        """
        指定された列車をハイライト表示する。
        - 列車パスに濃い黄色のドロップシャドウ効果を適用
        - 列車番号ラベルの一致部分を濃い黄色の背景色でハイライト
        - ZValueを上げて最前面に表示
        """
        self.clear_highlight()
        if not train_data:
            return

        self.current_highlight_train = train_data
        self.current_highlight_query = query

        # パスにドロップシャドウを適用
        for p_item in train_data.get("path_items", []):
            shadow = QGraphicsDropShadowEffect()
            shadow.setColor(QColor("#ffee00"))
            shadow.setBlurRadius(10)
            shadow.setOffset(0, 0)
            p_item.setGraphicsEffect(shadow)
            p_item.setZValue(10)

        # 列車番号テキストの一致部分をハイライト
        text_item = train_data.get("text_item")
        if text_item:
            num = train_data.get("train_number", "")
            main_color = train_data.get("main_color", "#333333")
            if query and query in num:
                # queryに一致する部分に背景色を設定
                escaped_num = html.escape(num)
                escaped_query = html.escape(query)
                highlighted_html = escaped_num.replace(
                    escaped_query,
                    f"<span style='background-color: #ffee00;'>{escaped_query}</span>"
                )
                html_text = f"<span style='color: {main_color}; font-size: 12px; font-family: sans-serif;'>{highlighted_html}</span>"
                text_item.setHtml(html_text)
            else:
                text_item.setPlainText(num)
            text_item.setZValue(11)

    def _render_operations(self, stations_data):
        """
        車両運用の列車間接続線および始発・終着運用番号ラベルを描画する。
        """
        if not self.project or not self.diagram_id or not stations_data:
            return

        lookup_dict = getattr(self.project, "operation_train_lookup", {})
        diag_lookup = lookup_dict.get(self.diagram_id, {})
        if not diag_lookup:
            return

        # 運用番号辞書の構築
        diag_ops = self.project.diagrams.get(self.diagram_id, {}).get("operations", {})

        # 始発駅・終着駅のラベル用集約辞書
        # key: (route_id, direction, train_id) -> {
        #     "symbols": {
        #         "○": [op_num_str, ...],
        #         "(○)": [op_num_str, ...],
        #     },
        #     "info": info,
        #     "m_train": m_train
        # }
        first_train_ops = {}
        last_train_ops = {}

        # 接続線描画用：すでに描画した接続パスの重複防止セット
        drawn_connections = set()

        for op_id, assigned_list in diag_lookup.items():
            if not assigned_list:
                continue

            if self.filter_operation_ids is not None and op_id not in self.filter_operation_ids:
                continue

            op_info = diag_ops.get(op_id, {})
            op_num = op_info.get("operation_number")
            op_num_str = str(op_num) if op_num is not None else str(op_id)

            # 1. 車両運用に属する列車および一時入庫イベントを収集し、時刻順にソート
            op_entries = []
            for item in assigned_list:
                r_id = item.get("route_id")
                d_dir = item.get("direction")
                t_id = item.get("train_id")

                route = self.project.routes.get(r_id)
                if not route:
                    continue

                train_key = "inbound_trains" if d_dir == "inbound" else "outbound_trains"
                m_train = route.get(train_key, {}).get(t_id)
                tbd = route.get("trains_by_diagram", {}).get(self.diagram_id, {})
                d_train = tbd.get(train_key, {}).get(t_id)

                if not m_train or not d_train:
                    continue

                # 始発時刻（ソート用）の算出
                stops = m_train.get("stops", [])
                if not stops:
                    continue

                first_stop = stops[0]
                first_dep_str = first_stop.get("departure_time") or first_stop.get("arrival_time") or ""
                first_dep_sec = self._time_to_seconds(first_dep_str)
                sort_key = first_dep_sec if first_dep_sec is not None else 24 * 3600 + 1

                op_entries.append({
                    "is_stabling": False,
                    "route_id": r_id,
                    "direction": d_dir,
                    "train_id": t_id,
                    "m_train": m_train,
                    "d_train": d_train,
                    "sort_key": sort_key,
                })

            # 一時入庫イベントの追加
            temp_stabling_events = op_info.get("temporary_stabling_events", []) or []
            for event in temp_stabling_events:
                start_time_str = event.get("start_time", "")
                start_sec = self._time_to_seconds(start_time_str)
                sort_key = start_sec if start_sec is not None else 24 * 3600 + 1
                op_entries.append({
                    "is_stabling": True,
                    "sort_key": sort_key,
                })

            op_entries.sort(key=lambda x: x["sort_key"])
            if not op_entries:
                continue

            # 2. 一時入庫イベントで区切られた列車のセグメント（サブ運用）に分割
            train_segments = []
            current_seg = []
            for entry in op_entries:
                if entry.get("is_stabling"):
                    if current_seg:
                        train_segments.append(current_seg)
                        current_seg = []
                else:
                    current_seg.append(entry)
            if current_seg:
                train_segments.append(current_seg)

            if not train_segments:
                continue

            num_segments = len(train_segments)

            # 3. 各セグメント内で表示対象列車を判定し、接続パスおよび運用番号ラベルを登録
            for seg_idx, seg_train_items in enumerate(train_segments):
                if not seg_train_items:
                    continue

                displayed_train_data = []
                for item in seg_train_items:
                    info = self._get_train_display_info(item, stations_data)
                    if info is not None:
                        displayed_train_data.append((item, info))

                if not displayed_train_data:
                    continue

                # セグメントの最初の列車がそのセグメント全体の最初の列車であり、かつ始発駅が表示対象の場合
                if displayed_train_data[0][0] is seg_train_items[0] and displayed_train_data[0][1]["origin_displayed"]:
                    first_item = displayed_train_data[0][0]
                    t_key = (first_item["route_id"], first_item["direction"], first_item["train_id"])
                    if t_key not in first_train_ops:
                        first_train_ops[t_key] = {"symbols": {}, "info": displayed_train_data[0][1], "m_train": first_item["m_train"]}
                    # 運用の完全な最初なら "○"、一時入庫直後なら "(○)"
                    sym = "○" if seg_idx == 0 else "(○)"
                    if sym not in first_train_ops[t_key]["symbols"]:
                        first_train_ops[t_key]["symbols"][sym] = []
                    if op_num_str not in first_train_ops[t_key]["symbols"][sym]:
                        first_train_ops[t_key]["symbols"][sym].append(op_num_str)

                # セグメントの最後の列車がそのセグメント全体の最後の列車であり、かつ終着駅が表示対象の場合
                if displayed_train_data[-1][0] is seg_train_items[-1] and displayed_train_data[-1][1]["terminal_displayed"]:
                    last_item = displayed_train_data[-1][0]
                    t_key = (last_item["route_id"], last_item["direction"], last_item["train_id"])
                    if t_key not in last_train_ops:
                        last_train_ops[t_key] = {"symbols": {}, "info": displayed_train_data[-1][1], "m_train": last_item["m_train"]}
                    # 運用の完全な最後なら "△"、一時入庫直前なら "(△)"
                    sym = "△" if seg_idx == num_segments - 1 else "(△)"
                    if sym not in last_train_ops[t_key]["symbols"]:
                        last_train_ops[t_key]["symbols"][sym] = []
                    if op_num_str not in last_train_ops[t_key]["symbols"][sym]:
                        last_train_ops[t_key]["symbols"][sym].append(op_num_str)

                # セグメント内で連続する列車の接続パスを描画
                for i in range(len(displayed_train_data) - 1):
                    item_prev, info_prev = displayed_train_data[i]
                    item_next, info_next = displayed_train_data[i + 1]

                    # 前の列車の終着駅と後の列車の始発駅がどちらも表示対象でない場合は接続パスを描画しない
                    if not info_prev["terminal_displayed"] or not info_next["origin_displayed"]:
                        continue

                    # 接続キー（重複描画防止）
                    conn_key = (
                        item_prev["route_id"], item_prev["direction"], item_prev["train_id"],
                        item_next["route_id"], item_next["direction"], item_next["train_id"],
                    )
                    if conn_key in drawn_connections:
                        continue
                    drawn_connections.add(conn_key)

                    self._draw_operation_connecting_path(info_prev, info_next, item_next["m_train"], op_info=op_info, op_id=op_id)

        # 4. 始発・終着運用番号ラベルの描画
        self._render_operation_start_end_labels(first_train_ops, last_train_ops)

    def _get_train_display_info(self, item, stations_data):
        """
        列車が現在のダイヤグラム表示条件に合致し、表示可能かを判定して発着座標および進行方向を返す。
        合致しない、または表示対象外の場合は None を返す。
        また、列車の本来の始発駅・終着駅がダイヤグラム上に表示対象となっているかのフラグを含める。
        """
        m_train = item["m_train"]
        d_train = item["d_train"]
        r_id = item["route_id"]

        # 有効判定
        if not d_train.get("to_be_saved", True):
            return None

        # フィルタ判定
        if not self._is_train_visible(m_train, d_train):
            return None

        stops = m_train.get("stops", [])
        if not stops:
            return None

        first_stop = stops[0]
        last_stop = stops[-1]

        # 表示対象判定（運行系統または路線）
        if self.selected_target == "route":
            if r_id != self.route_id:
                return None
            route = self.project.routes.get(r_id)
            if not route:
                return None
            segments = route.get("line_segments", [])
            segment_indices = {seg.get("segment_id"): idx for idx, seg in enumerate(segments)}

            subpaths, track_h_segs, track_v_segs, label_subpaths, all_subpath_stops = self._build_train_subpaths(
                stops, stations_data, segment_indices=segment_indices, target_segment_ids=None
            )

            if not subpaths and not track_h_segs and not label_subpaths:
                return None

            effective_subpaths = label_subpaths if label_subpaths else subpaths
            if not effective_subpaths:
                return None

            first_sp = effective_subpaths[0]
            last_sp = effective_subpaths[-1]
            origin_pt = first_sp[0]
            term_pt = last_sp[-1]

            # 始発位置での進行方向 dy
            origin_dy = 0.0
            for pt in first_sp[1:]:
                if pt[1] != origin_pt[1]:
                    origin_dy = pt[1] - origin_pt[1]
                    break
            if origin_dy == 0.0 and len(first_sp) > 1:
                origin_dy = first_sp[1][1] - origin_pt[1]

            # 終着位置での進行方向 dy
            term_dy = 0.0
            for pt in reversed(last_sp[:-1]):
                if pt[1] != term_pt[1]:
                    term_dy = term_pt[1] - pt[1]
                    break
            if term_dy == 0.0 and len(last_sp) > 1:
                term_dy = term_pt[1] - last_sp[-2][1]

            first_displayed_stop = all_subpath_stops[0][0] if all_subpath_stops and all_subpath_stops[0] else None
            last_displayed_stop = all_subpath_stops[-1][-1] if all_subpath_stops and all_subpath_stops[-1] else None

            origin_displayed = (
                first_displayed_stop is not None and
                first_displayed_stop.get("segment_id") == first_stop.get("segment_id") and
                first_displayed_stop.get("station_entry_id") == first_stop.get("station_entry_id")
            )
            terminal_displayed = (
                last_displayed_stop is not None and
                last_displayed_stop.get("segment_id") == last_stop.get("segment_id") and
                last_displayed_stop.get("station_entry_id") == last_stop.get("station_entry_id")
            )

            return {
                "origin": origin_pt,
                "terminal": term_pt,
                "origin_dy": origin_dy,
                "term_dy": term_dy,
                "origin_displayed": origin_displayed,
                "terminal_displayed": terminal_displayed,
                "first_stop": first_stop,
                "last_stop": last_stop,
                "first_displayed_stop": first_displayed_stop,
                "last_displayed_stop": last_displayed_stop,
            }

        else:
            # 路線表示
            target_line_id = self.selected_target
            route = self.project.routes.get(r_id)
            if not route:
                return None

            segments = route.get("line_segments", [])
            target_segment_ids = {seg["segment_id"] for seg in segments if seg.get("line_id") == target_line_id}
            if not target_segment_ids:
                return None

            subpaths, track_h_segs, track_v_segs, label_subpaths, all_subpath_stops = self._build_train_subpaths(
                stops, stations_data, segment_indices=None, target_segment_ids=target_segment_ids
            )

            if not subpaths and not track_h_segs and not label_subpaths:
                return None

            effective_subpaths = label_subpaths if label_subpaths else subpaths
            if not effective_subpaths:
                return None

            first_sp = effective_subpaths[0]
            last_sp = effective_subpaths[-1]
            origin_pt = first_sp[0]
            term_pt = last_sp[-1]

            # 始発位置での進行方向 dy
            origin_dy = 0.0
            for pt in first_sp[1:]:
                if pt[1] != origin_pt[1]:
                    origin_dy = pt[1] - origin_pt[1]
                    break
            if origin_dy == 0.0 and len(first_sp) > 1:
                origin_dy = first_sp[1][1] - origin_pt[1]

            # 終着位置での進行方向 dy
            term_dy = 0.0
            for pt in reversed(last_sp[:-1]):
                if pt[1] != term_pt[1]:
                    term_dy = term_pt[1] - pt[1]
                    break
            if term_dy == 0.0 and len(last_sp) > 1:
                term_dy = term_pt[1] - last_sp[-2][1]

            first_displayed_stop = all_subpath_stops[0][0] if all_subpath_stops and all_subpath_stops[0] else None
            last_displayed_stop = all_subpath_stops[-1][-1] if all_subpath_stops and all_subpath_stops[-1] else None

            origin_displayed = (
                first_displayed_stop is not None and
                first_displayed_stop.get("segment_id") == first_stop.get("segment_id") and
                first_displayed_stop.get("station_entry_id") == first_stop.get("station_entry_id")
            )
            terminal_displayed = (
                last_displayed_stop is not None and
                last_displayed_stop.get("segment_id") == last_stop.get("segment_id") and
                last_displayed_stop.get("station_entry_id") == last_stop.get("station_entry_id")
            )

            return {
                "origin": origin_pt,
                "terminal": term_pt,
                "origin_dy": origin_dy,
                "term_dy": term_dy,
                "origin_displayed": origin_displayed,
                "terminal_displayed": terminal_displayed,
                "first_stop": first_stop,
                "last_stop": last_stop,
                "first_displayed_stop": first_displayed_stop,
                "last_displayed_stop": last_displayed_stop,
            }

    def _get_station_id_for_stop(self, stop):
        """stop の station_entry_id または station_id から station_id を取得する"""
        if not stop or not self.project:
            return None
        sid = stop.get("station_id")
        if sid:
            return sid
        eid = stop.get("station_entry_id")
        if eid:
            return self.project.station_entry_to_station_id.get(eid)
        return None

    def _get_track_y(self, station_id, track_id, stations_data, ref_y=None):
        """指定された駅・番線のY座標を stations_data から検索して返す"""
        candidates = []
        for st in stations_data:
            if st.get("station_id") == station_id:
                if st.get("is_track_entry"):
                    if st.get("track_id") == track_id:
                        candidates.append(st["y"])
                else:
                    candidates.append(st["y"])
        if not candidates:
            return None
        if ref_y is not None:
            return min(candidates, key=lambda y_val: abs(y_val - ref_y))
        return candidates[0]

    def _draw_operation_connecting_path(self, info_prev, info_next, m_train_next, op_info=None, op_id=None):
        """
        前の列車の終着駅(x_arr, y_arr)と後の列車の始発駅(x_dep, y_dep)を結ぶパスを描画する。
        発着番線占有表有効時、番線一致判定および入換（shunting_operations）の描画を行う。
        線のスタイル・色は後の列車(m_train_next)の種別に従う。
        """
        p_prev = info_prev["terminal"]
        p_next = info_next["origin"]

        dy_prev = info_prev["term_dy"]
        dy_next = info_next["origin_dy"]

        tt_id = m_train_next.get("train_type_id")
        pen_default = self._create_train_pen(tt_id)
        tt = self.project.train_types.get(tt_id) if (self.project and tt_id) else None
        main_color = tt.get("main_color", "#333333") if tt else "#333333"

        # 始発駅の show_track_allocation_chart 判定
        stop_next_first = info_next.get("first_stop") or {}
        st_id_next = self._get_station_id_for_stop(stop_next_first)
        st_next_obj = self.project.stations.get(st_id_next, {}) if (self.project and st_id_next) else {}
        is_track_chart_active = self.show_track_allocation_chart and st_next_obj.get("show_track_allocation_chart", False)

        if not is_track_chart_active:
            # 発着番線占有表が無効な場合は従来通りの曲線/直線描画
            path = QPainterPath()
            path.moveTo(p_prev[0], p_prev[1])
            if dy_prev < 0 and dy_next > 0:
                ctrl_x = (p_prev[0] + p_next[0]) / 2.0
                ctrl_y = min(p_prev[1], p_next[1]) - 30.0
                path.quadTo(ctrl_x, ctrl_y, p_next[0], p_next[1])
            elif dy_prev > 0 and dy_next < 0:
                ctrl_x = (p_prev[0] + p_next[0]) / 2.0
                ctrl_y = max(p_prev[1], p_next[1]) + 30.0
                path.quadTo(ctrl_x, ctrl_y, p_next[0], p_next[1])
            else:
                path.lineTo(p_next[0], p_next[1])

            path_item = QGraphicsPathItem(path)
            path_item.setPen(pen_default)
            path_item.setZValue(2)
            self.addItem(path_item)
            return

        # --- 発着番線占有表がTrueの場合 ---
        # 仕様:
        # 「前の列車の終着駅と後の列車の始発駅とを結ぶ曲線については、その始発駅のshow_track_allocation_chartがTrueであるならば、
        # 曲線ではなく水平の線分として始発駅の経由駅情報に登録されている発着番線の位置に描画する(線のスタイルは前述の駅停車中の場合と同様)。
        # ただし、前の列車の終着駅・終着駅の発着番線と後の列車の始発駅・始発駅の発着番線が一致しない場合は、
        # 水平の線分ではなく、終着の発着番線の位置から始発の発着番線の位置まで点線で結ぶ。」
        # 「前の列車の終着駅と後の列車の始発駅との間に位置する時刻に同じ車両運用の駅構内入換が設定されている場合、
        # 水平の線分となるか点線となるか、それをどの位置に描画するかは、終着駅と駅構内入換の移動元番線の間、
        # 駅構内入換の移動先番線と始発駅の間でそれぞれ判定し、描画する。駅構内入換は連続して複数設定することもできるため、
        # その場合は終着駅と最初の駅構内入換の移動元番線の間、駅構内入換同士の移動先番線と移動元番線の間、
        # 最後の駅構内入換の移動先番線と始発駅の間で判定し、描画することになる。」

        stop_prev_last = info_prev.get("last_stop") or {}
        st_id_prev = self._get_station_id_for_stop(stop_prev_last)
        track_prev = stop_prev_last.get("track_id")
        track_next = stop_next_first.get("track_id")

        t_prev_sec = self._time_to_seconds(stop_prev_last.get("arrival_time") or stop_prev_last.get("departure_time"))
        t_next_sec = self._time_to_seconds(stop_next_first.get("departure_time") or stop_next_first.get("arrival_time"))

        if t_prev_sec is None or t_next_sec is None:
            t_prev_sec = (p_prev[0] / self.scale_x) * 60.0
            t_next_sec = (p_next[0] / self.scale_x) * 60.0

        # 駅構内入換 (shunting_operations) の抽出
        shunting_ops = []
        if op_info:
            all_shunts = op_info.get("shunting_operations", []) or []
            for sh in all_shunts:
                sh_time_str = sh.get("shunting_time")
                sh_sec = self._time_to_seconds(sh_time_str)
                if sh_sec is not None and t_prev_sec < sh_sec < t_next_sec:
                    shunting_ops.append((sh_sec, sh))
            shunting_ops.sort(key=lambda x: x[0])

        pen_solid = QPen(QColor(main_color), 2.0, Qt.SolidLine)
        pen_dotted = QPen(QColor(main_color), 1.0, Qt.DotLine)

        if not shunting_ops:
            # 入換なし
            # 終着駅と始発駅、番線がすべて一致するか判定
            stations_and_tracks_match = (st_id_prev == st_id_next and track_prev == track_next and track_next is not None)
            if stations_and_tracks_match:
                # 水平線分 (2px実線)
                x1 = (t_prev_sec / 60.0) * self.scale_x
                x2 = (t_next_sec / 60.0) * self.scale_x
                y = p_next[1]
                path = QPainterPath()
                path.moveTo(x1, y)
                path.lineTo(x2, y)
                item = QGraphicsPathItem(path)
                item.setPen(pen_solid)
                item.setZValue(2)
                self.addItem(item)
                # 当たり判定用メタデータを記録
                if op_id:
                    self.track_allocation_segments.append({
                        "x1": min(x1, x2), "x2": max(x1, x2),
                        "y1": y, "y2": y,
                        "is_dotted": False,
                        "station_id": st_id_next,
                        "operation_id": op_id,
                        "diagram_id": self.diagram_id,
                        "origin_track": track_prev,
                        "destination_track": track_next,
                    })
            else:
                # 点線で結ぶ
                path = QPainterPath()
                path.moveTo(p_prev[0], p_prev[1])
                path.lineTo(p_next[0], p_next[1])
                item = QGraphicsPathItem(path)
                item.setPen(pen_dotted)
                item.setZValue(2)
                self.addItem(item)
                # 当たり判定用メタデータを記録
                if op_id:
                    self.track_allocation_segments.append({
                        "x1": min(p_prev[0], p_next[0]), "x2": max(p_prev[0], p_next[0]),
                        "y1": min(p_prev[1], p_next[1]), "y2": max(p_prev[1], p_next[1]),
                        "is_dotted": True,
                        "station_id": st_id_next,
                        "operation_id": op_id,
                        "diagram_id": self.diagram_id,
                        "origin_track": track_prev,
                        "destination_track": track_next,
                    })
        else:
            # 入換あり
            # 区間ごとに判定:
            # 1. 終着駅 (t_prev, st_id_prev, track_prev, p_prev) -> 第1入換移動元番線 (sh_sec_1, sh_st_id_1, orig_track_1)
            # 2. 入換 k 移動先番線 (sh_sec_k, dest_track_k) -> 入換 k+1 移動元番線 (sh_sec_k+1, orig_track_k+1)
            # 3. 最終入換移動先番線 (sh_sec_last, dest_track_last) -> 始発駅 (t_next, st_id_next, track_next, p_next)
            # また、各入換自体の移動元番線から移動先番線へは時刻 sh_sec において点線で結ぶ
            stages = []
            # 最初の地点
            stages.append({
                "time_sec": t_prev_sec,
                "station_id": st_id_prev,
                "track_id": track_prev,
                "point": p_prev,
            })

            ref_y = p_prev[1]
            for sh_sec, sh in shunting_ops:
                sh_sid = sh.get("station_id") or st_id_next
                orig_trk = sh.get("origin_track")
                dest_trk = sh.get("destination_track")

                y_orig = self._get_track_y(sh_sid, orig_trk, self.stations_data, ref_y=ref_y) or ref_y
                x_sh = (sh_sec / 60.0) * self.scale_x
                pt_orig = (x_sh, y_orig)

                stages.append({
                    "time_sec": sh_sec,
                    "station_id": sh_sid,
                    "track_id": orig_trk,
                    "point": pt_orig,
                    "is_shunt_orig": True,
                    "dest_track_id": dest_trk,
                })

                y_dest = self._get_track_y(sh_sid, dest_trk, self.stations_data, ref_y=y_orig) or y_orig
                pt_dest = (x_sh, y_dest)
                ref_y = y_dest

                stages.append({
                    "time_sec": sh_sec,
                    "station_id": sh_sid,
                    "track_id": dest_trk,
                    "point": pt_dest,
                    "is_shunt_dest": True,
                })

            stages.append({
                "time_sec": t_next_sec,
                "station_id": st_id_next,
                "track_id": track_next,
                "point": p_next,
            })

            # stages のペアごとに描画
            i = 0
            while i < len(stages) - 1:
                stg_a = stages[i]
                stg_b = stages[i + 1]

                pt_a = stg_a["point"]
                pt_b = stg_b["point"]

                if stg_a.get("is_shunt_orig") and stg_b.get("is_shunt_dest") and stg_a["time_sec"] == stg_b["time_sec"]:
                    # 入換自体の移動元〜移動先: 時刻同一での垂直/点線移動
                    path = QPainterPath()
                    path.moveTo(pt_a[0], pt_a[1])
                    path.lineTo(pt_b[0], pt_b[1])
                    item = QGraphicsPathItem(path)
                    item.setPen(pen_dotted)
                    item.setZValue(2)
                    self.addItem(item)
                else:
                    # 時間間隔を伴う移動 (終着〜入換、入換間、入換〜始発)
                    match = (
                        stg_a["station_id"] == stg_b["station_id"] and
                        stg_a["track_id"] == stg_b["track_id"] and
                        stg_a["track_id"] is not None
                    )
                    if match:
                        path = QPainterPath()
                        path.moveTo(pt_a[0], pt_a[1])
                        path.lineTo(pt_b[0], pt_a[1])
                        item = QGraphicsPathItem(path)
                        item.setPen(pen_solid)
                        item.setZValue(2)
                        self.addItem(item)
                        # 当たり判定用メタデータを記録
                        if op_id:
                            seg_sid = stg_a.get("station_id") or st_id_next
                            self.track_allocation_segments.append({
                                "x1": min(pt_a[0], pt_b[0]), "x2": max(pt_a[0], pt_b[0]),
                                "y1": pt_a[1], "y2": pt_a[1],
                                "is_dotted": False,
                                "station_id": seg_sid,
                                "operation_id": op_id,
                                "diagram_id": self.diagram_id,
                                "origin_track": stg_a.get("track_id"),
                                "destination_track": stg_b.get("track_id"),
                            })
                    else:
                        path = QPainterPath()
                        path.moveTo(pt_a[0], pt_a[1])
                        path.lineTo(pt_b[0], pt_b[1])
                        item = QGraphicsPathItem(path)
                        item.setPen(pen_dotted)
                        item.setZValue(2)
                        self.addItem(item)
                        # 当たり判定用メタデータを記録
                        if op_id:
                            seg_sid = stg_b.get("station_id") or st_id_next
                            self.track_allocation_segments.append({
                                "x1": min(pt_a[0], pt_b[0]), "x2": max(pt_a[0], pt_b[0]),
                                "y1": min(pt_a[1], pt_b[1]), "y2": max(pt_a[1], pt_b[1]),
                                "is_dotted": True,
                                "station_id": seg_sid,
                                "operation_id": op_id,
                                "diagram_id": self.diagram_id,
                                "origin_track": stg_a.get("track_id"),
                                "destination_track": stg_b.get("track_id"),
                            })
                i += 1


    def _render_operation_start_end_labels(self, first_train_ops, last_train_ops):
        """
        始発・終着運用番号ラベルを描画する。
        - 始発: ○{op_nums} または (○){op_nums} 上方に向かう列車(dy < 0)はパスの下側、下方に向かう列車(dy > 0)はパスの上側
        - 終着: △{op_nums} または (△){op_nums} 上方に向かう列車(dy < 0)はパスの上側、下方に向かう列車(dy > 0)はパスの下側
        """
        font = QFont()
        font.setPixelSize(11)

        # 始発ラベル
        for t_key, data in first_train_ops.items():
            symbols_dict = data.get("symbols", {})
            label_parts = []
            for sym in ["○", "(○)"]:
                if sym in symbols_dict and symbols_dict[sym]:
                    op_nums_str = ",".join(symbols_dict[sym])
                    label_parts.append(f"{sym}{op_nums_str}")

            if not label_parts:
                continue

            label_text = " ".join(label_parts)

            m_train = data["m_train"]
            info = data["info"]
            p_origin = info["origin"]
            dy = info["origin_dy"]

            tt_id = m_train.get("train_type_id")
            tt = self.project.train_types.get(tt_id) if (self.project and tt_id) else None
            main_color = tt.get("main_color", "#333333") if tt else "#333333"

            text_item = QGraphicsSimpleTextItem(label_text)
            text_item.setFont(font)
            text_item.setBrush(QBrush(QColor(main_color)))

            br = text_item.boundingRect()
            pos_x = p_origin[0] - br.width() / 2.0

            if dy < 0:
                # 上方に向かう列車 -> パスの下側
                pos_y = p_origin[1] + 4.0
            else:
                # 下方に向かう列車 (dy >= 0) -> パスの上側
                pos_y = p_origin[1] - br.height() - 4.0

            text_item.setPos(pos_x, pos_y)
            text_item.setZValue(3)
            self.addItem(text_item)

        # 終着ラベル
        for t_key, data in last_train_ops.items():
            symbols_dict = data.get("symbols", {})
            label_parts = []
            for sym in ["△", "(△)"]:
                if sym in symbols_dict and symbols_dict[sym]:
                    op_nums_str = ",".join(symbols_dict[sym])
                    label_parts.append(f"{sym}{op_nums_str}")

            if not label_parts:
                continue

            label_text = " ".join(label_parts)

            m_train = data["m_train"]
            info = data["info"]
            p_term = info["terminal"]
            dy = info["term_dy"]

            tt_id = m_train.get("train_type_id")
            tt = self.project.train_types.get(tt_id) if (self.project and tt_id) else None
            main_color = tt.get("main_color", "#333333") if tt else "#333333"

            text_item = QGraphicsSimpleTextItem(label_text)
            text_item.setFont(font)
            text_item.setBrush(QBrush(QColor(main_color)))

            br = text_item.boundingRect()
            pos_x = p_term[0] - br.width() / 2.0

            if dy < 0:
                # 上方に向かう列車 -> パスの上側
                pos_y = p_term[1] - br.height() - 4.0
            else:
                # 下方に向かう列車 (dy >= 0) -> パスの下側
                pos_y = p_term[1] + 4.0

            text_item.setPos(pos_x, pos_y)
            text_item.setZValue(3)
            self.addItem(text_item)

    def get_track_allocation_segments_at(self, scene_x: float, scene_y: float, tolerance: float = 5.0) -> list:
        """
        指定されたシーン座標 (scene_x, scene_y) の近傍に存在する
        発着番線占有表エリアの水平線分・点線セグメントを返す。
        tolerance: 判定する距離の許容範囲（px）
        戻り値: マッチしたセグメント情報のリスト（track_allocation_segments の要素）。
        """
        result = []
        for seg in self.track_allocation_segments:
            x1, x2 = seg["x1"], seg["x2"]
            y1, y2 = seg["y1"], seg["y2"]
            is_dotted = seg["is_dotted"]
            if is_dotted:
                # 点線: 2点を結ぶ線分との距離を計算
                dx = x2 - x1
                dy = y2 - y1
                length_sq = dx * dx + dy * dy
                if length_sq < 1e-9:
                    dist = ((scene_x - x1) ** 2 + (scene_y - y1) ** 2) ** 0.5
                else:
                    t = max(0.0, min(1.0, ((scene_x - x1) * dx + (scene_y - y1) * dy) / length_sq))
                    proj_x = x1 + t * dx
                    proj_y = y1 + t * dy
                    dist = ((scene_x - proj_x) ** 2 + (scene_y - proj_y) ** 2) ** 0.5
                x_in_range = (min(x1, x2) - tolerance <= scene_x <= max(x1, x2) + tolerance)
                if dist <= tolerance and x_in_range:
                    result.append(seg)
            else:
                # 水平線分: X範囲内かつY距離が許容範囲内
                if (x1 - tolerance <= scene_x <= x2 + tolerance) and (abs(scene_y - y1) <= tolerance):
                    result.append(seg)
        return result
