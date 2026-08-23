from PySide6.QtWidgets import (
    QGraphicsScene, QGraphicsRectItem, QGraphicsSimpleTextItem, QGraphicsLineItem, QMenu, QDialog
)
from PySide6.QtGui import QColor, QFont, QPen, QBrush
from PySide6.QtCore import Qt, QRectF
from .dialogs import TemporaryStablingDialog, AddDeadheadDialog, AddTrainToOperationDialog


# 一時入庫を表す矩形アイテム
class TemporaryStablingItem(QGraphicsRectItem):
    def __init__(self, x: float, y: float, w: float, h: float, event_data: dict, operation: dict, scene: "TimelineScene"):
        super().__init__(x, y, w, h)
        self.event_data = event_data
        self.operation = operation
        self.timeline_scene = scene

        # 塗りつぶし色は透明、輪郭線は灰色
        self.setPen(QPen(QColor("#888888"), 1))
        self.setBrush(QBrush(Qt.NoBrush))
        self.setZValue(1)

        # テキスト項目を配置
        stabled_location = event_data.get("stabled_location", "")
        self.text_item = QGraphicsSimpleTextItem(stabled_location, self)
        font = QFont()
        font.setPixelSize(12)
        self.text_item.setFont(font)

        # formations_can_changed が True の場合は赤文字、それ以外は黒文字
        if event_data.get("formations_can_changed", False):
            self.text_item.setBrush(QBrush(QColor("#ff0000")))
        else:
            self.text_item.setBrush(QBrush(QColor("#000000")))

        tn_rect = self.text_item.boundingRect()
        tn_y = (h - tn_rect.height()) / 2.0
        self.text_item.setPos(x + 2, y + tn_y)
        self.text_item.setZValue(2)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            parent_widget = self.timeline_scene.views()[0].window() if self.timeline_scene and self.timeline_scene.views() else None
            dialog = TemporaryStablingDialog(parent_widget, event_data=self.event_data)
            if dialog.exec() == QDialog.Accepted:
                new_data = dialog.get_data()
                self.event_data.update(new_data)
                # start_time順にソート
                events = self.operation.get("temporary_stabling_events", [])
                events.sort(key=lambda e: e.get("start_time", ""))
                self.timeline_scene.refresh()
                if parent_widget and hasattr(parent_widget, "set_modified"):
                    parent_widget.set_modified(True)
            event.accept()
        else:
            super().mousePressEvent(event)


# ガントチャート要素間の空白を埋める透明の矩形アイテム
class BlankSpaceItem(QGraphicsRectItem):
    def __init__(self, start_m: float, end_m: float, y_base: float, bar_top_offset: float, bar_height: float, operation: dict, operation_id: str, scene: "TimelineScene"):
        x = float(start_m)
        y = float(y_base + bar_top_offset)
        w = max(1.0, float(end_m - start_m))
        h = float(bar_height)
        super().__init__(x, y, w, h)
        self.start_m = start_m
        self.end_m = end_m
        self.operation = operation
        self.operation_id = operation_id
        self.timeline_scene = scene

        self.setAcceptHoverEvents(True)
        # 透明な領域でホバーイベントが拾えるようにアルファ0のブラシをセット
        self.setBrush(QBrush(QColor(0, 0, 0, 0)))
        self.setPen(QPen(Qt.NoPen))
        self.setZValue(1)

    def hoverEnterEvent(self, event):
        # 薄い灰色の左下がりの斜線模様
        hatch_brush = QBrush(QColor("#cccccc"), Qt.BDiagPattern)
        self.setBrush(hatch_brush)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setBrush(QBrush(QColor(0, 0, 0, 0)))
        super().hoverLeaveEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu()
        act_train = menu.addAction("ここへ列車を登録")
        act_deadhead = menu.addAction("ここへ時刻表にない回送を追加")
        act_stabling = menu.addAction("ここへ一時入庫を追加")

        screen_pos = event.screenPos()
        selected_act = menu.exec(screen_pos)

        if selected_act == act_train:
            parent_widget = self.timeline_scene.views()[0].window() if self.timeline_scene and self.timeline_scene.views() else None
            # 直前列車の終着駅IDを計算
            prev_last_station_id = self._get_prev_last_station_id()
            dialog = AddTrainToOperationDialog(
                parent_widget,
                project=self.timeline_scene.project,
                diagram_id=self.timeline_scene.diagram_id,
                target_op_id=self.operation_id,
                start_m=self.start_m,
                prev_last_station_id=prev_last_station_id
            )
            if dialog.exec() == QDialog.Accepted:
                self.timeline_scene.refresh()
                if parent_widget:
                    if hasattr(parent_widget, "timetable_model") and parent_widget.timetable_model:
                        parent_widget.timetable_model.update_data(
                            parent_widget.timetable_model.route_id,
                            parent_widget.timetable_model.diagram_id,
                            parent_widget.timetable_model.direction
                        )
                    if hasattr(parent_widget, "set_modified"):
                        parent_widget.set_modified(True)

        elif selected_act == act_deadhead:
            parent_widget = self.timeline_scene.views()[0].window() if self.timeline_scene and self.timeline_scene.views() else None
            dialog = AddDeadheadDialog(
                parent_widget,
                project=self.timeline_scene.project,
                diagram_id=self.timeline_scene.diagram_id,
                operation_id=self.operation_id,
                default_start_m=self.start_m,
                default_end_m=self.end_m
            )
            if dialog.exec() == QDialog.Accepted:
                self.timeline_scene.refresh()
                if parent_widget:
                    if hasattr(parent_widget, "timetable_model") and parent_widget.timetable_model:
                        parent_widget.timetable_model.update_data(
                            parent_widget.timetable_model.route_id,
                            parent_widget.timetable_model.diagram_id,
                            parent_widget.timetable_model.direction
                        )
                    if hasattr(parent_widget, "set_modified"):
                        parent_widget.set_modified(True)

        elif selected_act == act_stabling:
            sh = int(self.start_m // 60)
            sm = int(self.start_m % 60)
            eh = int(self.end_m // 60)
            em = int(self.end_m % 60)
            default_start_time = f"{sh:02d}:{sm:02d}:00"
            default_end_time = f"{eh:02d}:{em:02d}:00"

            parent_widget = self.timeline_scene.views()[0].window() if self.timeline_scene and self.timeline_scene.views() else None
            dialog = TemporaryStablingDialog(
                parent_widget,
                default_start_time=default_start_time,
                default_end_time=default_end_time
            )
            if dialog.exec() == QDialog.Accepted:
                new_data = dialog.get_data()
                if "temporary_stabling_events" not in self.operation:
                    self.operation["temporary_stabling_events"] = []
                self.operation["temporary_stabling_events"].append(new_data)
                self.operation["temporary_stabling_events"].sort(key=lambda e: e.get("start_time", ""))
                self.timeline_scene.refresh()
                if parent_widget and hasattr(parent_widget, "set_modified"):
                    parent_widget.set_modified(True)

    def _get_prev_last_station_id(self) -> str:
        if not self.timeline_scene or not self.timeline_scene.project:
            return None
        diagram_id = self.timeline_scene.diagram_id
        target_op_id = self.operation_id
        prev_trains = []

        for route in self.timeline_scene.project.routes.values():
            tbd = route.get("trains_by_diagram", {}).get(diagram_id, {})
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
                            arr = self.timeline_scene._time_to_minutes(s.get("arrival_time"))
                            dep = self.timeline_scene._time_to_minutes(s.get("departure_time"))
                            if arr is not None:
                                valid_times.append(arr)
                            if dep is not None:
                                valid_times.append(dep)
                        if not valid_times:
                            continue
                        first_dep = min(valid_times)
                        last_arr = max(valid_times)
                        if last_arr <= self.start_m:
                            last_station_id = stops[-1].get("station_id") if stops else None
                            prev_trains.append((last_arr, last_station_id))

        if prev_trains:
            prev_trains.sort(key=lambda x: x[0])
            return prev_trains[-1][1]
        return None



# 運用ガントチャートのシーン
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

    def refresh(self):
        if self.project and self.diagram_id and self.operation_group_id:
            self.update_timeline(self.project, self.diagram_id, self.operation_group_id)

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

            # 出庫・入庫テキストを描画
            self._draw_operation_start_end(op, y_base)

            # 出庫・入庫時刻が未設定の場合はそれぞれ0分(0時0分)、2160分(36時0分)とみなして範囲を設定
            start_m = self._time_to_minutes(op.get("start_time"))
            eff_start = start_m if start_m is not None else 0
            end_m = self._time_to_minutes(op.get("end_time"))
            eff_end = end_m if end_m is not None else 2160

            elements = [(eff_start, eff_start)]

            # 運用に割り振られている列車の矩形を描画し要素範囲を記録
            train_elems = self._draw_operation_trains(op_id, y_base)
            elements.extend(train_elems)

            # 一時入庫の矩形を描画し要素範囲を記録
            stabling_elems = self._draw_operation_stabling(op, y_base)
            elements.extend(stabling_elems)

            elements.append((eff_end, eff_end))

            # 各要素間の空白部分に透明な矩形を配置
            max_end = None
            for s, e in sorted(elements, key=lambda x: (x[0], x[1])):
                if max_end is not None:
                    if s > max_end:
                        blank_item = BlankSpaceItem(max_end, s, y_base, self.BAR_TOP_OFFSET, self.BAR_HEIGHT, op, op_id, self)
                        self.addItem(blank_item)
                        max_end = max(max_end, e)
                    else:
                        max_end = max(max_end, e)
                else:
                    max_end = e

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

    def _draw_operation_stabling(self, op: dict, y_base: float) -> list:
        elements = []
        events = op.get("temporary_stabling_events", [])
        for ev in events:
            start_m = self._time_to_minutes(ev.get("start_time"))
            end_m = self._time_to_minutes(ev.get("end_time"))
            if start_m is not None and end_m is not None:
                w = max(1.0, float(end_m - start_m))
                stabling_item = TemporaryStablingItem(
                    float(start_m),
                    y_base + float(self.BAR_TOP_OFFSET),
                    w,
                    float(self.BAR_HEIGHT),
                    ev,
                    op,
                    self
                )
                self.addItem(stabling_item)
                elements.append((start_m, end_m))
        return elements

    def _draw_operation_trains(self, target_op_id: str, y_base: float) -> list:
        elements = []
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

            elements.append((first_dep, last_arr))

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

                rect = st_text.boundingRect()
                st_text.setPos(rect_x - (rect.width() / 2), rect_y + rect_h)
                st_text.setZValue(2)
                self.addItem(st_text)

            prev_last_station_id = train["last_station_id"]

        return elements


# 運用ガントチャートの見出しのシーン
class TimelineHeaderScene(QGraphicsScene):
    TIMELINE_WIDTH = 2160  # 36 hours * 60 minutes/hour = 2160px
    HEADER_HEIGHT = 40

    def __init__(self, parent=None):
        super().__init__(parent)
        self.right_margin = 0
        self.update_header(0)

    def update_header(self, right_margin: int = 0):
        self.right_margin = right_margin
        self.clear()
        scene_w = self.TIMELINE_WIDTH + self.right_margin
        self.setSceneRect(0, 0, scene_w, self.HEADER_HEIGHT)

        solid_pen = QPen(QColor("#cccccc"), 1, Qt.PenStyle.SolidLine)
        font = QFont()
        font.setPixelSize(14)

        for hour in range(37):
            x = hour * 60
            # 縦線描画
            line = self.addLine(x, 0, x, self.HEADER_HEIGHT, solid_pen)
            line.setZValue(0)

            # 時刻文字の描画（36時は表示しない）
            if hour < 36:
                text_item = QGraphicsSimpleTextItem(str(hour))
                text_item.setFont(font)
                text_item.setBrush(QBrush(QColor("#333333")))
                text_item.setPos(x + 4, 10)
                text_item.setZValue(1)
                self.addItem(text_item)

        # 下部の枠線を描画 (y = HEADER_HEIGHT - 1)
        bottom_line = self.addLine(0, self.HEADER_HEIGHT - 1, scene_w, self.HEADER_HEIGHT - 1, solid_pen)
        bottom_line.setZValue(2)


