import copy
from PySide6.QtWidgets import (
    QGraphicsScene, QGraphicsRectItem, QGraphicsSimpleTextItem, QGraphicsLineItem, QMenu, QDialog, QMessageBox
)
from PySide6.QtGui import QColor, QFont, QPen, QBrush
from PySide6.QtCore import Qt, QRectF
from .dialogs import TemporaryStablingDialog, AddDeadheadDialog, AddTrainToOperationDialog


# ガントチャート上の矩形アイテムの基底クラス
class TimelineRectItem(QGraphicsRectItem):
    def __init__(self, x: float, y: float, w: float, h: float, operation_id: str, scene: "TimelineScene"):
        super().__init__(x, y, w, h)
        self.operation_id = operation_id
        self.timeline_scene = scene
        self._is_selected = False
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemClipsChildrenToShape, True)

    def is_timeline_selected(self) -> bool:
        return self._is_selected

    def set_timeline_selected(self, selected: bool):
        if self._is_selected != selected:
            self._is_selected = selected
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.timeline_scene:
                self.timeline_scene.handle_item_mouse_press(self, event)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.timeline_scene and self.timeline_scene.drag_controller:
            self.timeline_scene.drag_controller.handle_mouse_move(event)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.timeline_scene and self.timeline_scene.drag_controller:
                self.timeline_scene.drag_controller.handle_mouse_release(event)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def paint_selection_pattern(self, painter, option, widget=None):
        if self._is_selected:
            pattern_pen = QPen(QColor("#eeeeee"), 1)
            pattern_pen.setStyle(Qt.PenStyle.CustomDashLine)
            brush = QBrush(QColor("#eeeeee"), Qt.DiagCrossPattern)
            painter.fillRect(self.rect(), brush)


# 列車を表す矩形アイテム
class TrainTimelineItem(TimelineRectItem):
    def __init__(self, x: float, y: float, w: float, h: float, bg_color: QColor, train_number: str,
                 route_id: str, direction_key: str, train_id: str, operation_id: str, scene: "TimelineScene",
                 train_type: str = "", first_station_initial: str = "", last_station_initial: str = "",
                 first_dep_str: str = "", last_arr_str: str = "", all_op_ids: list = None,
                 first_dep_m: float = 0, last_arr_m: float = 0):
        super().__init__(x, y, w, h, operation_id, scene)
        self.route_id = route_id
        self.direction_key = direction_key
        self.train_id = train_id
        self.bg_color = bg_color
        self.first_dep_m = first_dep_m
        self.last_arr_m = last_arr_m
        self.station_text_item = None

        self.setBrush(QBrush(bg_color))
        self.setPen(QPen(Qt.NoPen))
        self.setZValue(1)

        # 列車番号 (白文字・左寄せ)
        font_tn = QFont()
        font_tn.setPixelSize(12)
        self.tn_text = QGraphicsSimpleTextItem(train_number, self)
        self.tn_text.setFont(font_tn)
        self.tn_text.setBrush(QBrush(QColor("#ffffff")))
        tn_rect = self.tn_text.boundingRect()
        tn_y = y + (h - tn_rect.height()) / 2.0
        self.tn_text.setPos(x + 2, tn_y)
        self.tn_text.setZValue(2)

        # ツールチップ設定
        self.setToolTip(self._build_tooltip(
            train_number, train_type, operation_id, all_op_ids or [],
            first_station_initial, last_station_initial, first_dep_str, last_arr_str, scene
        ))

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        self.paint_selection_pattern(painter, option, widget)

    def _build_tooltip(self, train_number: str, train_type: str, operation_id: str, all_op_ids: list,
                       first_station_initial: str, last_station_initial: str,
                       first_dep_str: str, last_arr_str: str, scene: "TimelineScene") -> str:
        # 担当運用の運用番号リストを構築（自運用は太字）
        op_parts = []
        if scene and scene.project:
            ops_dict = {}
            for diag in scene.project.diagrams.values():
                ops_dict.update(diag.get("operations", {}))
            for oid in all_op_ids:
                op = ops_dict.get(oid, {})
                op_number = op.get("operation_number", oid)
                if oid == operation_id:
                    op_parts.append(f"<b>{op_number}</b>")
                else:
                    op_parts.append(op_number)
        train_line = f"{train_type} {train_number}"
        op_line = "+".join(op_parts) if op_parts else ""
        route_line = f"{first_station_initial} {first_dep_str} → {last_arr_str} {last_station_initial}"
        return f"{train_line}<br>{op_line}<br>{route_line}"

    def contextMenuEvent(self, event):
        menu = QMenu()
        act_remove = menu.addAction("この列車を除外")
        selected_act = menu.exec(event.screenPos())

        if selected_act == act_remove:
            parent_widget = self.timeline_scene.views()[0].window() if self.timeline_scene and self.timeline_scene.views() else None
            reply = QMessageBox.question(
                parent_widget,
                "確認",
                "この列車を運用から除外しますか？\nこの操作で列車そのものが削除されることはありません。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                route = self.timeline_scene.project.routes.get(self.route_id, {})
                tbd = route.get("trains_by_diagram", {}).get(self.timeline_scene.diagram_id, {})
                d_trains = tbd.get(self.direction_key, {})
                d_train = d_trains.get(self.train_id)
                if d_train and "operations" in d_train:
                    old_ops = copy.deepcopy(d_train["operations"])
                    # 削除対象のインデックスと内容を探す
                    target_idx = -1
                    target_op = None
                    for i, op in enumerate(d_train["operations"]):
                        oid = op.get("operation_id") if isinstance(op, dict) else op
                        if oid == self.operation_id:
                            target_idx = i
                            target_op = copy.deepcopy(op)
                            break

                    d_train["operations"] = [
                        op for op in d_train["operations"]
                        if (op.get("operation_id") if isinstance(op, dict) else op) != self.operation_id
                    ]
                    d_train["to_be_saved"] = True

                    if self.timeline_scene.history_manager and target_idx != -1 and target_op is not None:
                        from core.events import RemoveTrainOperationEvent
                        ev = RemoveTrainOperationEvent(
                            route_id=self.route_id,
                            direction=self.direction_key.replace("_trains", ""),
                            train_id=self.train_id,
                            diagram_id=self.timeline_scene.diagram_id,
                            index=target_idx,
                            operation=target_op
                        )
                        self.timeline_scene.history_manager.push_events([ev])

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


# 一時入庫を表す矩形アイテム
class TemporaryStablingItem(TimelineRectItem):
    def __init__(self, x: float, y: float, w: float, h: float, event_data: dict, operation: dict, operation_id: str, scene: "TimelineScene",
                 start_m: float = 0, end_m: float = 0):
        super().__init__(x, y, w, h, operation_id, scene)
        self.event_data = event_data
        self.operation = operation
        self.start_m = start_m
        self.end_m = end_m

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
        tn_y = y + (h - tn_rect.height()) / 2.0
        self.text_item.setPos(x + 2, tn_y)
        self.text_item.setZValue(2)

        # ツールチップ設定
        self.setToolTip(self._build_tooltip(event_data))

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        self.paint_selection_pattern(painter, option, widget)

    def _build_tooltip(self, event_data: dict) -> str:
        stabled_location = event_data.get("stabled_location", "")
        start_time = event_data.get("start_time", "")
        end_time = event_data.get("end_time", "")
        note = event_data.get("note", "")

        def fmt_time(t: str) -> str:
            if not t:
                return ""
            parts = t.split(":")
            if len(parts) >= 2:
                return f"{parts[0]}:{parts[1]}"
            return t

        start_str = fmt_time(start_time)
        end_str = fmt_time(end_time)
        time_line = f"{start_str} - {end_str}"

        lines = [stabled_location, time_line]
        if note:
            lines.append(note)
        return "\n".join(lines)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.open_stabling_dialog()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def open_stabling_dialog(self):
        parent_widget = self.timeline_scene.views()[0].window() if self.timeline_scene and self.timeline_scene.views() else None
        dialog = TemporaryStablingDialog(parent_widget, event_data=self.event_data)
        if dialog.exec() == QDialog.Accepted:
            old_event_data = copy.deepcopy(self.event_data)
            new_data = dialog.get_data()
            
            events = self.operation.get("temporary_stabling_events", [])
            event_idx = events.index(self.event_data) if self.event_data in events else -1

            self.event_data.update(new_data)
            # start_time順にソート
            events.sort(key=lambda e: e.get("start_time", ""))

            if self.timeline_scene.history_manager and event_idx != -1:
                from core.events import ChangeTemporaryStablingEvent
                ev = ChangeTemporaryStablingEvent(
                    diagram_id=self.timeline_scene.diagram_id,
                    operation_id=self.operation_id,
                    index=event_idx,
                    old_stabling_event=old_event_data,
                    new_stabling_event=new_data
                )
                self.timeline_scene.history_manager.push_events([ev])

            self.timeline_scene.refresh()
            if parent_widget and hasattr(parent_widget, "set_modified"):
                parent_widget.set_modified(True)

    def contextMenuEvent(self, event):
        menu = QMenu()
        act_edit = menu.addAction("一時入庫の設定を変更")
        act_delete = menu.addAction("この一時入庫を削除")
        selected_act = menu.exec(event.screenPos())

        if selected_act == act_edit:
            self.open_stabling_dialog()
        elif selected_act == act_delete:
            stabled_location = self.event_data.get("stabled_location", "")
            parent_widget = self.timeline_scene.views()[0].window() if self.timeline_scene and self.timeline_scene.views() else None
            reply = QMessageBox.question(
                parent_widget,
                "確認",
                f"この一時入庫({stabled_location})を削除しますか？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                events = self.operation.get("temporary_stabling_events", [])
                if self.event_data in events:
                    del_idx = events.index(self.event_data)
                    del_data = copy.deepcopy(self.event_data)
                    events.remove(self.event_data)

                    if self.timeline_scene.history_manager:
                        from core.events import RemoveTemporaryStablingEvent
                        ev = RemoveTemporaryStablingEvent(
                            diagram_id=self.timeline_scene.diagram_id,
                            operation_id=self.operation_id,
                            index=del_idx,
                            stabling_event=del_data
                        )
                        self.timeline_scene.history_manager.push_events([ev])

                self.timeline_scene.refresh()
                if parent_widget and hasattr(parent_widget, "set_modified"):
                    parent_widget.set_modified(True)


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
                prev_last_station_id=prev_last_station_id,
                history_manager=self.timeline_scene.history_manager
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
                default_end_m=self.end_m,
                history_manager=self.timeline_scene.history_manager
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

                insert_idx = self.operation["temporary_stabling_events"].index(new_data)
                if self.timeline_scene.history_manager:
                    from core.events import AddTemporaryStablingEvent
                    ev = AddTemporaryStablingEvent(
                        diagram_id=self.timeline_scene.diagram_id,
                        operation_id=self.operation_id,
                        index=insert_idx,
                        stabling_event=new_data
                    )
                    self.timeline_scene.history_manager.push_events([ev])

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



# 運用ガントチャートのドラッグ移動管理クラス
class TimelineDragController:
    def __init__(self, scene: "TimelineScene"):
        self.scene = scene
        self.is_dragging = False
        self.mouse_press_pos = None
        self.dragged_items = []
        self.initial_positions = {}
        self.current_dy = 0.0

    def handle_mouse_press(self, item: TimelineRectItem, event):
        self.mouse_press_pos = event.scenePos()
        self.is_dragging = False
        self.dragged_items = []
        self.initial_positions = {}
        self.current_dy = 0.0

    def handle_mouse_move(self, event):
        if not self.mouse_press_pos:
            return
        
        pos = event.scenePos()
        dy = pos.y() - self.mouse_press_pos.y()
        dx = pos.x() - self.mouse_press_pos.x()

        if not self.is_dragging:
            if abs(dy) >= 5 or abs(dx) >= 5:
                self.is_dragging = True
                self.dragged_items = list(self.scene.selected_items)
                self.initial_positions = {}
                for it in self.dragged_items:
                    self.initial_positions[it] = (it.pos().x(), it.pos().y())
                    it.setZValue(10)
                    if isinstance(it, TrainTimelineItem) and it.station_text_item:
                        self.initial_positions[it.station_text_item] = (
                            it.station_text_item.pos().x(), it.station_text_item.pos().y()
                        )
                        it.station_text_item.setZValue(11)

        if self.is_dragging:
            self.current_dy = dy
            for it in self.dragged_items:
                orig_x, orig_y = self.initial_positions[it]
                it.setPos(orig_x, orig_y + dy)
                if isinstance(it, TrainTimelineItem) and it.station_text_item:
                    st_orig_x, st_orig_y = self.initial_positions[it.station_text_item]
                    it.station_text_item.setPos(st_orig_x, st_orig_y + dy)

    def handle_mouse_release(self, event):
        if not self.is_dragging:
            self.mouse_press_pos = None
            return

        self.is_dragging = False
        self.mouse_press_pos = None

        # 元の位置・ZValueを復元
        for it in self.dragged_items:
            orig_x, orig_y = self.initial_positions.get(it, (0, 0))
            it.setPos(orig_x, orig_y)
            it.setZValue(1)
            if isinstance(it, TrainTimelineItem) and it.station_text_item:
                st_orig_x, st_orig_y = self.initial_positions.get(it.station_text_item, (0, 0))
                it.station_text_item.setPos(st_orig_x, st_orig_y)
                it.station_text_item.setZValue(2)

        # 移動先の行を計算
        row_delta = round(self.current_dy / self.scene.ROW_HEIGHT)
        if row_delta == 0:
            return

        self.scene.move_selected_items(row_delta)


# 運用ガントチャートのシーン
class TimelineScene(QGraphicsScene):
    ROW_HEIGHT = 70
    BAR_HEIGHT = 24
    BAR_TOP_OFFSET = 16
    LABEL_TOP_OFFSET = 16
    TIMELINE_WIDTH = 2160  # 36 hours * 60 minutes/hour = 2160px

    def __init__(self, parent=None, history_manager=None):
        super().__init__(parent)
        self.project = None
        self.diagram_id = None
        self.operation_group_id = None
        self.history_manager = history_manager
        self.row_items = {}  # op_id -> list of QGraphicsItem
        self.selected_items = []  # list of TimelineRectItem
        self.drag_controller = TimelineDragController(self)

        if self.history_manager:
            self.history_manager.undone.connect(self._on_history_changed)
            self.history_manager.redone.connect(self._on_history_changed)

    def set_history_manager(self, history_manager):
        if self.history_manager:
            try:
                self.history_manager.undone.disconnect(self._on_history_changed)
                self.history_manager.redone.disconnect(self._on_history_changed)
            except Exception:
                pass
        self.history_manager = history_manager
        if self.history_manager:
            self.history_manager.undone.connect(self._on_history_changed)
            self.history_manager.redone.connect(self._on_history_changed)

    def _on_history_changed(self, events: list):
        """Undo/Redo 実行時に変更のあった運用の行のみを差分更新する"""
        if not self.project or not self.diagram_id or not self.operation_group_id:
            return

        diagram = self.project.diagrams.get(self.diagram_id, {})
        op_groups = diagram.get("operation_groups", {})
        og = op_groups.get(self.operation_group_id, {})
        current_op_ids = set(og.get("operations", []))

        # イベントに関連する op_id または train_id を収集
        affected_op_ids = set()
        for ev in events:
            if hasattr(ev, "operation_id") and ev.operation_id in current_op_ids:
                affected_op_ids.add(ev.operation_id)
            elif hasattr(ev, "old_operations") and hasattr(ev, "new_operations"):
                for op in ev.old_operations:
                    if "operation_id" in op and op["operation_id"] in current_op_ids:
                        affected_op_ids.add(op["operation_id"])
                for op in ev.new_operations:
                    if "operation_id" in op and op["operation_id"] in current_op_ids:
                        affected_op_ids.add(op["operation_id"])
            elif hasattr(ev, "train_id"):
                # プロジェクト全体からこの列車に割り当てられている op_id を探索
                for did, d_train_id, target_op_id in self._find_op_ids_for_train(ev.train_id):
                    if did == self.diagram_id and target_op_id in current_op_ids:
                        affected_op_ids.add(target_op_id)

        # 影響を受けた運用行のみ再描画
        if affected_op_ids:
            for op_id in affected_op_ids:
                self._redraw_operation_row(op_id)
        else:
            # 念のため該当行が特定できなかった場合は全更新
            self.refresh()

    def _find_op_ids_for_train(self, train_id: str):
        """列車IDが割り当てられている運用のリストを返す (diagram_id, train_id, op_id)"""
        results = []
        if not self.project:
            return results
        for route in self.project.routes.values():
            tbd = route.get("trains_by_diagram", {})
            for did, dt in tbd.items():
                for dkey in ["inbound_trains", "outbound_trains"]:
                    d_train = dt.get(dkey, {}).get(train_id)
                    if d_train:
                        for op in d_train.get("operations", []):
                            op_id = op.get("operation_id") if isinstance(op, dict) else op
                            if op_id:
                                results.append((did, train_id, op_id))
        return results

    def refresh(self):
        if self.project and self.diagram_id and self.operation_group_id:
            self.update_timeline(self.project, self.diagram_id, self.operation_group_id)

    def clear_timeline_selection(self):
        for it in self.selected_items:
            it.set_timeline_selected(False)
        self.selected_items.clear()

    def get_row_rect_items(self, op_id: str):
        items = self.row_items.get(op_id, [])
        rect_items = [it for it in items if isinstance(it, TimelineRectItem)]
        def item_time(it):
            if isinstance(it, TrainTimelineItem):
                return (it.first_dep_m, it.last_arr_m)
            elif isinstance(it, TemporaryStablingItem):
                return (it.start_m, it.end_m)
            return (0, 0)
        return sorted(rect_items, key=item_time)

    def handle_item_mouse_press(self, item: TimelineRectItem, event):
        modifiers = event.modifiers()
        if modifiers & Qt.ControlModifier:
            if item.is_timeline_selected():
                item.set_timeline_selected(False)
                if item in self.selected_items:
                    self.selected_items.remove(item)
            else:
                if self.selected_items:
                    first_op_id = self.selected_items[0].operation_id
                    if item.operation_id != first_op_id:
                        parent_widget = self.views()[0].window() if self.views() else None
                        QMessageBox.information(
                            parent_widget,
                            "情報",
                            "複数の車両運用に跨って選択することはできません"
                        )
                        self.clear_timeline_selection()
                        return
                item.set_timeline_selected(True)
                if item not in self.selected_items:
                    self.selected_items.append(item)

        elif modifiers & Qt.ShiftModifier:
            if not self.selected_items:
                item.set_timeline_selected(True)
                self.selected_items.append(item)
            else:
                first_op_id = self.selected_items[0].operation_id
                if item.operation_id != first_op_id:
                    parent_widget = self.views()[0].window() if self.views() else None
                    QMessageBox.information(
                        parent_widget,
                        "情報",
                        "複数の車両運用に跨って選択することはできません"
                    )
                    self.clear_timeline_selection()
                    return

                row_items = self.get_row_rect_items(first_op_id)
                cur_indices = [row_items.index(it) for it in self.selected_items if it in row_items]
                if cur_indices and item in row_items:
                    target_idx = row_items.index(item)
                    min_idx = min(min(cur_indices), target_idx)
                    max_idx = max(max(cur_indices), target_idx)
                    for i in range(min_idx, max_idx + 1):
                        it = row_items[i]
                        it.set_timeline_selected(True)
                        if it not in self.selected_items:
                            self.selected_items.append(it)
                else:
                    item.set_timeline_selected(True)
                    if item not in self.selected_items:
                        self.selected_items.append(item)
        else:
            if not item.is_timeline_selected():
                self.clear_timeline_selection()
                item.set_timeline_selected(True)
                self.selected_items.append(item)

        self.drag_controller.handle_mouse_press(item, event)

    def handle_rubber_band_selection(self, selected_items: list):
        valid_items = [it for it in selected_items if isinstance(it, TimelineRectItem)]
        if not valid_items:
            self.clear_timeline_selection()
            return

        op_ids = set(it.operation_id for it in valid_items)
        if len(op_ids) > 1:
            self.clear_timeline_selection()
            parent_widget = self.views()[0].window() if self.views() else None
            QMessageBox.information(
                parent_widget,
                "情報",
                "複数の車両運用に跨って選択することはできません"
            )
            return

        self.clear_timeline_selection()
        for it in valid_items:
            it.set_timeline_selected(True)
            self.selected_items.append(it)

    def delete_selected_items(self):
        if not self.selected_items or not self.project or not self.diagram_id:
            return

        count = len(self.selected_items)
        parent_widget = self.views()[0].window() if self.views() else None
        reply = QMessageBox.question(
            parent_widget,
            "確認",
            f"選択されている {count} 件の列車・一時入庫を運用表から除外しますか？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        events_to_push = []
        items_to_delete = list(self.selected_items)

        for it in items_to_delete:
            if isinstance(it, TrainTimelineItem):
                route = self.project.routes.get(it.route_id, {})
                tbd = route.get("trains_by_diagram", {}).get(self.diagram_id, {})
                d_trains = tbd.get(it.direction_key, {})
                d_train = d_trains.get(it.train_id)
                if d_train and "operations" in d_train:
                    target_idx = -1
                    target_op = None
                    for i, op in enumerate(d_train["operations"]):
                        oid = op.get("operation_id") if isinstance(op, dict) else op
                        if oid == it.operation_id:
                            target_idx = i
                            target_op = copy.deepcopy(op)
                            break

                    d_train["operations"] = [
                        op for op in d_train["operations"]
                        if (op.get("operation_id") if isinstance(op, dict) else op) != it.operation_id
                    ]
                    d_train["to_be_saved"] = True

                    if target_idx != -1 and target_op is not None:
                        from core.events import RemoveTrainOperationEvent
                        ev = RemoveTrainOperationEvent(
                            route_id=it.route_id,
                            direction=it.direction_key.replace("_trains", ""),
                            train_id=it.train_id,
                            diagram_id=self.diagram_id,
                            index=target_idx,
                            operation=target_op
                        )
                        events_to_push.append(ev)

            elif isinstance(it, TemporaryStablingItem):
                events = it.operation.get("temporary_stabling_events", [])
                if it.event_data in events:
                    del_idx = events.index(it.event_data)
                    del_data = copy.deepcopy(it.event_data)
                    events.remove(it.event_data)

                    from core.events import RemoveTemporaryStablingEvent
                    ev = RemoveTemporaryStablingEvent(
                        diagram_id=self.diagram_id,
                        operation_id=it.operation_id,
                        index=del_idx,
                        stabling_event=del_data
                    )
                    events_to_push.append(ev)

        if self.history_manager and events_to_push:
            self.history_manager.push_events(events_to_push)

        self.clear_timeline_selection()
        self.refresh()
        if parent_widget:
            if hasattr(parent_widget, "timetable_model") and parent_widget.timetable_model:
                parent_widget.timetable_model.update_data(
                    parent_widget.timetable_model.route_id,
                    parent_widget.timetable_model.diagram_id,
                    parent_widget.timetable_model.direction
                )
            if hasattr(parent_widget, "set_modified"):
                parent_widget.set_modified(True)

    def move_selected_items(self, row_delta: int):
        if not self.selected_items or not self.project or not self.diagram_id or not self.operation_group_id:
            return

        diagram = self.project.diagrams.get(self.diagram_id, {})
        op_groups = diagram.get("operation_groups", {})
        og = op_groups.get(self.operation_group_id, {})
        op_ids = og.get("operations", [])

        src_op_id = self.selected_items[0].operation_id
        if src_op_id not in op_ids:
            return
        src_row_idx = op_ids.index(src_op_id)
        target_row_idx = src_row_idx + row_delta

        if target_row_idx < 0 or target_row_idx >= len(op_ids) or target_row_idx == src_row_idx:
            return

        target_op_id = op_ids[target_row_idx]
        target_op = diagram.get("operations", {}).get(target_op_id, {})
        src_op = diagram.get("operations", {}).get(src_op_id, {})

        # 移動元・移動先で選択中のアイテムと移動先にあるアイテムを取得
        moving_items = list(self.selected_items)
        target_row_all_items = self.get_row_rect_items(target_op_id)

        # 重なり判定
        overlapping_target_items = []
        for m_it in moving_items:
            if isinstance(m_it, TrainTimelineItem):
                m_s, m_e = m_it.first_dep_m, m_it.last_arr_m
            else:
                m_s, m_e = m_it.start_m, m_it.end_m

            for t_it in target_row_all_items:
                if isinstance(t_it, TrainTimelineItem):
                    t_s, t_e = t_it.first_dep_m, t_it.last_arr_m
                else:
                    t_s, t_e = t_it.start_m, t_it.end_m

                if max(m_s, t_s) < min(m_e, t_e):
                    if t_it not in overlapping_target_items:
                        overlapping_target_items.append(t_it)

        if overlapping_target_items:
            parent_widget = self.views()[0].window() if self.views() else None
            reply = QMessageBox.question(
                parent_widget,
                "確認",
                "移動先の運用には同じ時間に別の列車・一時入庫が登録されています。\n移動元の運用と列車・一時入庫を入れ替えますか？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        events_to_push = []
        from core.events import (
            ChangeTrainOperationEvent,
            AddTemporaryStablingEvent,
            RemoveTemporaryStablingEvent
        )

        # 1. moving_items を src_op_id -> target_op_id へ移動
        for it in moving_items:
            if isinstance(it, TrainTimelineItem):
                route = self.project.routes.get(it.route_id, {})
                tbd = route.get("trains_by_diagram", {}).get(self.diagram_id, {})
                d_train = tbd.get(it.direction_key, {}).get(it.train_id)
                if d_train and "operations" in d_train:
                    old_ops = copy.deepcopy(d_train["operations"])
                    new_ops = []
                    for op in d_train["operations"]:
                        oid = op.get("operation_id") if isinstance(op, dict) else op
                        if oid == src_op_id:
                            if isinstance(op, dict):
                                new_op_entry = copy.deepcopy(op)
                                new_op_entry["operation_id"] = target_op_id
                                new_ops.append(new_op_entry)
                            else:
                                new_ops.append(target_op_id)
                        else:
                            new_ops.append(copy.deepcopy(op))
                    d_train["operations"] = new_ops
                    d_train["to_be_saved"] = True
                    ev = ChangeTrainOperationEvent(
                        route_id=it.route_id,
                        direction=it.direction_key.replace("_trains", ""),
                        train_id=it.train_id,
                        diagram_id=self.diagram_id,
                        old_operations=old_ops,
                        new_operations=new_ops
                    )
                    events_to_push.append(ev)

            elif isinstance(it, TemporaryStablingItem):
                src_events = src_op.get("temporary_stabling_events", [])
                if it.event_data in src_events:
                    del_idx = src_events.index(it.event_data)
                    del_data = copy.deepcopy(it.event_data)
                    src_events.remove(it.event_data)
                    ev_rem = RemoveTemporaryStablingEvent(
                        diagram_id=self.diagram_id,
                        operation_id=src_op_id,
                        index=del_idx,
                        stabling_event=del_data
                    )
                    events_to_push.append(ev_rem)

                tgt_events = target_op.setdefault("temporary_stabling_events", [])
                new_stabling = copy.deepcopy(it.event_data)
                tgt_events.append(new_stabling)
                tgt_events.sort(key=lambda e: e.get("start_time", ""))
                ins_idx = tgt_events.index(new_stabling)
                ev_add = AddTemporaryStablingEvent(
                    diagram_id=self.diagram_id,
                    operation_id=target_op_id,
                    index=ins_idx,
                    stabling_event=new_stabling
                )
                events_to_push.append(ev_add)

        # 2. overlapping_target_items を target_op_id -> src_op_id へ移動
        for it in overlapping_target_items:
            if isinstance(it, TrainTimelineItem):
                route = self.project.routes.get(it.route_id, {})
                tbd = route.get("trains_by_diagram", {}).get(self.diagram_id, {})
                d_train = tbd.get(it.direction_key, {}).get(it.train_id)
                if d_train and "operations" in d_train:
                    old_ops = copy.deepcopy(d_train["operations"])
                    new_ops = []
                    for op in d_train["operations"]:
                        oid = op.get("operation_id") if isinstance(op, dict) else op
                        if oid == target_op_id:
                            if isinstance(op, dict):
                                new_op_entry = copy.deepcopy(op)
                                new_op_entry["operation_id"] = src_op_id
                                new_ops.append(new_op_entry)
                            else:
                                new_ops.append(src_op_id)
                        else:
                            new_ops.append(copy.deepcopy(op))
                    d_train["operations"] = new_ops
                    d_train["to_be_saved"] = True
                    ev = ChangeTrainOperationEvent(
                        route_id=it.route_id,
                        direction=it.direction_key.replace("_trains", ""),
                        train_id=it.train_id,
                        diagram_id=self.diagram_id,
                        old_operations=old_ops,
                        new_operations=new_ops
                    )
                    events_to_push.append(ev)

            elif isinstance(it, TemporaryStablingItem):
                tgt_events = target_op.get("temporary_stabling_events", [])
                if it.event_data in tgt_events:
                    del_idx = tgt_events.index(it.event_data)
                    del_data = copy.deepcopy(it.event_data)
                    tgt_events.remove(it.event_data)
                    ev_rem = RemoveTemporaryStablingEvent(
                        diagram_id=self.diagram_id,
                        operation_id=target_op_id,
                        index=del_idx,
                        stabling_event=del_data
                    )
                    events_to_push.append(ev_rem)

                src_events = src_op.setdefault("temporary_stabling_events", [])
                new_stabling = copy.deepcopy(it.event_data)
                src_events.append(new_stabling)
                src_events.sort(key=lambda e: e.get("start_time", ""))
                ins_idx = src_events.index(new_stabling)
                ev_add = AddTemporaryStablingEvent(
                    diagram_id=self.diagram_id,
                    operation_id=src_op_id,
                    index=ins_idx,
                    stabling_event=new_stabling
                )
                events_to_push.append(ev_add)

        if self.history_manager and events_to_push:
            self.history_manager.push_events(events_to_push)

        self.clear_timeline_selection()
        self.refresh()
        parent_widget = self.views()[0].window() if self.views() else None
        if parent_widget:
            if hasattr(parent_widget, "timetable_model") and parent_widget.timetable_model:
                parent_widget.timetable_model.update_data(
                    parent_widget.timetable_model.route_id,
                    parent_widget.timetable_model.diagram_id,
                    parent_widget.timetable_model.direction
                )
            if hasattr(parent_widget, "set_modified"):
                parent_widget.set_modified(True)

    def update_timeline(self, project, diagram_id: str, operation_group_id: str):
        self.project = project
        self.diagram_id = diagram_id
        self.operation_group_id = operation_group_id
        self.clear()
        self.row_items.clear()

        if not self.project or not self.diagram_id or not self.operation_group_id:
            self.setSceneRect(0, 0, self.TIMELINE_WIDTH, 0)
            return

        diagram = self.project.diagrams.get(self.diagram_id, {})
        op_groups = diagram.get("operation_groups", {})
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
            self._draw_operation_row(op_id, row_idx)

    def _draw_operation_row(self, op_id: str, row_idx: int):
        diagram = self.project.diagrams.get(self.diagram_id, {})
        operations = diagram.get("operations", {})
        op = operations.get(op_id, {})
        y_base = row_idx * self.ROW_HEIGHT

        created_items = []

        # 出庫・入庫テキストを描画
        start_end_items = self._draw_operation_start_end(op, y_base)
        created_items.extend(start_end_items)

        # 出庫・入庫時刻が未設定の場合はそれぞれ0分(0時0分)、2160分(36時0分)とみなして範囲を設定
        start_m = self._time_to_minutes(op.get("start_time"))
        eff_start = start_m if start_m is not None else 0
        end_m = self._time_to_minutes(op.get("end_time"))
        eff_end = end_m if end_m is not None else 2160

        elements = [(eff_start, eff_start)]

        # 運用に割り振られている列車の矩形を描画し要素範囲を記録
        train_elems, train_items = self._draw_operation_trains(op_id, y_base)
        elements.extend(train_elems)
        created_items.extend(train_items)

        # 一時入庫の矩形を描画し要素範囲を記録
        stabling_elems, stabling_items = self._draw_operation_stabling(op, op_id, y_base)
        elements.extend(stabling_elems)
        created_items.extend(stabling_items)

        elements.append((eff_end, eff_end))

        # 各要素間の空白部分に透明な矩形を配置
        max_end = None
        for s, e in sorted(elements, key=lambda x: (x[0], x[1])):
            if max_end is not None:
                if s > max_end:
                    blank_item = BlankSpaceItem(max_end, s, y_base, self.BAR_TOP_OFFSET, self.BAR_HEIGHT, op, op_id, self)
                    self.addItem(blank_item)
                    created_items.append(blank_item)
                    max_end = max(max_end, e)
                else:
                    max_end = max(max_end, e)
            else:
                max_end = e

        self.row_items[op_id] = created_items

    def _redraw_operation_row(self, op_id: str):
        """指定された運用の行のみ既存アイテムを削除し再描画する"""
        if not self.project or not self.diagram_id or not self.operation_group_id:
            return
        diagram = self.project.diagrams.get(self.diagram_id, {})
        op_groups = diagram.get("operation_groups", {})
        og = op_groups.get(self.operation_group_id, {})
        op_ids = og.get("operations", [])
        if op_id not in op_ids:
            return

        # 既存アイテムの削除
        if op_id in self.row_items:
            for item in self.row_items[op_id]:
                self.removeItem(item)
            del self.row_items[op_id]

        row_idx = op_ids.index(op_id)
        self._draw_operation_row(op_id, row_idx)


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

    def _draw_operation_start_end(self, op: dict, y_base: float) -> list:
        items = []
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
                items.append(text_item)

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
                items.append(text_item)
        return items

    def _draw_operation_stabling(self, op: dict, op_id: str, y_base: float) -> tuple:
        elements = []
        items = []
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
                    op_id,
                    self,
                    start_m=float(start_m),
                    end_m=float(end_m)
                )
                self.addItem(stabling_item)
                items.append(stabling_item)
                elements.append((start_m, end_m))
        return elements, items

    def _draw_operation_trains(self, target_op_id: str, y_base: float) -> tuple:
        elements = []
        items = []
        matched_trains = []

        for route_id, route in self.project.routes.items():
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

                        # 始発駅発車時刻文字列 (stops[0]のdeparture_time、なければarrival_time)
                        first_stop = stops[0] if stops else {}
                        first_dep_time = first_stop.get("departure_time") or first_stop.get("arrival_time") or ""
                        # 終着駅到着時刻文字列 (stops[-1]のarrival_time、なければdeparture_time)
                        last_stop = stops[-1] if stops else {}
                        last_arr_time = last_stop.get("arrival_time") or last_stop.get("departure_time") or ""

                        def fmt_hhmm(t: str) -> str:
                            if not t:
                                return ""
                            parts = t.split(":")
                            if len(parts) >= 2:
                                return f"{parts[0]}:{parts[1]}"
                            return t

                        matched_trains.append({
                            "route_id": route_id,
                            "direction_key": direction,
                            "train_id": train_id,
                            "train_number": m_train.get("train_number", ""),
                            "train_type_id": m_train.get("train_type_id"),
                            "first_dep": first_dep,
                            "last_arr": last_arr,
                            "first_station_id": first_station_id,
                            "last_station_id": last_station_id,
                            "all_op_ids": op_ids,
                            "first_dep_str": fmt_hhmm(first_dep_time),
                            "last_arr_str": fmt_hhmm(last_arr_time),
                        })

        matched_trains.sort(key=lambda x: x["first_dep"])

        prev_last_station_id = None

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

            # 列車種別の短縮名と基本色を取得
            tt = self.project.train_types.get(train["train_type_id"]) if train["train_type_id"] else None
            train_type_short_name = tt.get("train_type_short_name", "") if tt else ""
            main_color_str = tt.get("main_color", "#333333") if tt else "#333333"
            bg_color = QColor(main_color_str)

            # 始発・終着駅の1文字表記
            first_station_initial = self._get_station_initial(train["first_station_id"])
            last_station_initial = self._get_station_initial(train["last_station_id"])

            # 列車矩形描画 (コンテクストメニュー・テキストトリミング付き)
            rect_item = TrainTimelineItem(
                rect_x, rect_y, rect_w, rect_h,
                bg_color,
                train["train_number"],
                train["route_id"],
                train["direction_key"],
                train["train_id"],
                target_op_id,
                self,
                train_type=train_type_short_name,
                first_station_initial=first_station_initial,
                last_station_initial=last_station_initial,
                first_dep_str=train["first_dep_str"],
                last_arr_str=train["last_arr_str"],
                all_op_ids=train["all_op_ids"],
                first_dep_m=float(first_dep),
                last_arr_m=float(last_arr)
            )
            self.addItem(rect_item)
            items.append(rect_item)

            # 始発駅の1文字表記
            start_st_initial = first_station_initial
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
                items.append(st_text)
                rect_item.station_text_item = st_text

            prev_last_station_id = train["last_station_id"]

        return elements, items



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


