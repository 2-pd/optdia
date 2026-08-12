from PySide6.QtWidgets import QGraphicsScene, QGraphicsRectItem, QGraphicsSimpleTextItem, QGraphicsLineItem
from PySide6.QtGui import QColor, QFont, QPen, QBrush
from PySide6.QtCore import Qt, QRectF

class TimelineScene(QGraphicsScene):
    ROW_HEIGHT = 70
    BAR_HEIGHT = 24
    BAR_TOP_OFFSET = 16
    LABEL_TOP_OFFSET = 16
    TIMELINE_WIDTH = 2160  # 36 hours * 60 minutes/hour = 2160px

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project = None
        self.diagram_id = None
        self.operation_group_id = None

    def update_timeline(self, project, diagram_id: str, operation_group_id: str):
        self.project = project
        self.diagram_id = diagram_id
        self.operation_group_id = operation_group_id
        self.clear()

        if not self.project or not self.diagram_id or not self.operation_group_id:
            self.setSceneRect(0, 0, self.TIMELINE_WIDTH, 0)
            return

        diagram = self.project.diagrams.get(self.diagram_id, {})
        op_groups = diagram.get("operation_groups", {})
        operations = diagram.get("operations", {})

        og = op_groups.get(self.operation_group_id, {})
        op_ids = og.get("operations", [])

        total_rows = len(op_ids)
        scene_height = max(0, total_rows * self.ROW_HEIGHT)
        self.setSceneRect(0, 0, self.TIMELINE_WIDTH, scene_height)

        if total_rows == 0:
            return

        # 1. 毎時0分の縦破線と行間境界の実線を描画
        dot_pen = QPen(QColor("#cccccc"), 1, Qt.PenStyle.DashLine)
        solid_pen = QPen(QColor("#cccccc"), 1, Qt.PenStyle.SolidLine)

        for hour in range(37):
            x = hour * 60
            line = self.addLine(x, 0, x, scene_height, dot_pen)
            line.setZValue(0)

        for i in range(1, total_rows):
            y = i * self.ROW_HEIGHT
            line = self.addLine(0, y, self.TIMELINE_WIDTH, y, solid_pen)
            line.setZValue(0)

        # 2. 各運用のガントチャート要素を描画
        for row_idx, op_id in enumerate(op_ids):
            op = operations.get(op_id, {})
            y_base = row_idx * self.ROW_HEIGHT

            # 出庫・入庫テキスト
            self._draw_operation_start_end(op, y_base)

            # 運用に割り振られている列車の矩形描画
            self._draw_operation_trains(op_id, y_base)

    def _time_to_minutes(self, time_str: str):
        if not time_str:
            return None
        try:
            parts = time_str.split(":")
            h, m = int(parts[0]), int(parts[1])
            return h * 60 + m
        except (ValueError, IndexError):
            return None

    def _get_station_initial(self, station_id: str) -> str:
        if not station_id or not self.project:
            return ""
        st = self.project.stations.get(station_id, {})
        st_initial = st.get("station_initial")
        if st_initial:
            return str(st_initial)
        st_name = st.get("station_name", "")
        return st_name[0] if st_name else ""

    def _draw_operation_start_end(self, op: dict, y_base: float):
        start_time_str = op.get("start_time")
        if start_time_str:
            start_m = self._time_to_minutes(start_time_str)
            if start_m is not None:
                text_item = QGraphicsSimpleTextItem("○")
                font = QFont()
                font.setPixelSize(16)
                text_item.setFont(font)
                text_item.setBrush(QBrush(QColor("#000000")))
                rect = text_item.boundingRect()
                # テキストの右端が出庫時刻の位置
                text_item.setPos(start_m - rect.width(), y_base + self.LABEL_TOP_OFFSET)
                text_item.setZValue(2)
                self.addItem(text_item)

        end_time_str = op.get("end_time")
        if end_time_str:
            end_m = self._time_to_minutes(end_time_str)
            if end_m is not None:
                text_item = QGraphicsSimpleTextItem("△")
                font = QFont()
                font.setPixelSize(16)
                text_item.setFont(font)
                text_item.setBrush(QBrush(QColor("#000000")))
                # テキストの左端が入庫時刻の位置
                text_item.setPos(end_m, y_base + self.LABEL_TOP_OFFSET)
                text_item.setZValue(2)
                self.addItem(text_item)

    def _draw_operation_trains(self, target_op_id: str, y_base: float):
        # プロジェクト内の全列車を走査して、target_op_id を持つ列車（かつ現在の diagram_id に属するもの）を抽出
        matched_trains = []

        for route in self.project.routes.values():
            tbd = route.get("trains_by_diagram", {}).get(self.diagram_id, {})
            for direction in ["inbound_trains", "outbound_trains"]:
                m_trains = route.get(direction, {})
                d_trains = tbd.get(direction, {})
                for train_id, d_train in d_trains.items():
                    ops = d_train.get("operations", [])
                    op_ids = [op.get("operation_id") if isinstance(op, dict) else op for op in ops]
                    if target_op_id in op_ids:
                        m_train = m_trains.get(train_id)
                        if not m_train:
                            continue
                        stops = m_train.get("stops", [])
                        valid_times = []
                        for s in stops:
                            arr = self._time_to_minutes(s.get("arrival_time"))
                            dep = self._time_to_minutes(s.get("departure_time"))
                            if arr is not None:
                                valid_times.append(arr)
                            if dep is not None:
                                valid_times.append(dep)
                        if not valid_times:
                            continue

                        first_dep = min(valid_times)
                        last_arr = max(valid_times)

                        first_station_id = stops[0].get("station_id") if stops else None
                        last_station_id = stops[-1].get("station_id") if stops else None

                        matched_trains.append({
                            "train_number": m_train.get("train_number", ""),
                            "train_type_id": m_train.get("train_type_id"),
                            "first_dep": first_dep,
                            "last_arr": last_arr,
                            "first_station_id": first_station_id,
                            "last_station_id": last_station_id
                        })

        # 最初の発時刻順にソート
        matched_trains.sort(key=lambda x: x["first_dep"])

        prev_last_station_id = None

        font_tn = QFont()
        font_tn.setPixelSize(12)

        font_st = QFont()
        font_st.setPixelSize(14)

        for train in matched_trains:
            first_dep = train["first_dep"]
            last_arr = train["last_arr"]
            rect_w = max(1.0, float(last_arr - first_dep))
            rect_h = float(self.BAR_HEIGHT)
            rect_x = float(first_dep)
            rect_y = y_base + float(self.BAR_TOP_OFFSET)

            # 列車種別の基本色を取得
            tt = self.project.train_types.get(train["train_type_id"]) if train["train_type_id"] else None
            main_color_str = tt.get("main_color", "#333333") if tt else "#333333"
            bg_color = QColor(main_color_str)

            # 矩形描画
            rect_item = QGraphicsRectItem(rect_x, rect_y, rect_w, rect_h)
            rect_item.setBrush(QBrush(bg_color))
            rect_item.setPen(QPen(Qt.NoPen))
            rect_item.setZValue(1)
            self.addItem(rect_item)

            # 列車番号 (白文字・左寄せ)
            tn_text = QGraphicsSimpleTextItem(train["train_number"])
            tn_text.setFont(font_tn)
            tn_text.setBrush(QBrush(QColor("#ffffff")))
            # 左寄せ、縦中央付近または上端に配置（高さ24pxの中で上下中央）
            tn_rect = tn_text.boundingRect()
            tn_y = rect_y + (rect_h - tn_rect.height()) / 2.0
            tn_text.setPos(rect_x + 2, tn_y)
            tn_text.setZValue(2)
            self.addItem(tn_text)

            # 始発駅の1文字表記
            start_st_initial = self._get_station_initial(train["first_station_id"])
            if start_st_initial:
                st_text = QGraphicsSimpleTextItem(start_st_initial)
                st_text.setFont(font_st)
                
                # 直前列車の終着駅と一致しない場合赤文字
                is_mismatch = (prev_last_station_id is not None and train["first_station_id"] != prev_last_station_id)
                if is_mismatch:
                    st_text.setBrush(QBrush(QColor("#ff0000")))
                else:
                    st_text.setBrush(QBrush(QColor("#000000")))

                st_text.setPos(rect_x, rect_y + rect_h)
                st_text.setZValue(2)
                self.addItem(st_text)

            prev_last_station_id = train["last_station_id"]
