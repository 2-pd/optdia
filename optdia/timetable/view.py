import re
from PySide6.QtCore import Qt, QRect, QModelIndex
from PySide6.QtGui import QColor, QPainter, QFont, QFontMetrics, QIcon
from PySide6.QtWidgets import QHeaderView, QStyleOptionHeader, QStyle, QTableView, QSizePolicy, QVBoxLayout, QLabel, QMenu
from PySide6.QtGui import QActionGroup
from .model import StopTypeRole

# 時刻表テーブルの垂直ヘッダーのビュー
class TimetableVerticalHeader(QHeaderView):
    def __init__(self, parent=None):
        super().__init__(Qt.Vertical, parent)

        # 各行の高さのデフォルト値を24pxに縮小
        self.setMinimumSectionSize(24)
        self.setDefaultSectionSize(24)

        # 行の高さは固定のため ResizeToContents は設定しない
        # padding: top right bottom left (左8px = 縦線6px + 余白2px、右4px)
        self.setStyleSheet("QHeaderView::section { padding: 0px 4px 0px 8px; margin: 0px; }")
        self.setDefaultAlignment(Qt.AlignRight | Qt.AlignVCenter)

    def paintSection(self, painter, rect, logicalIndex):
        model = self.model()
        if not model or not hasattr(model, 'row_headers') or not hasattr(model, 'station_rows'):
            super().paintSection(painter, rect, logicalIndex)
            return

        painter.save()
        option_header = QStyleOptionHeader()
        option_header.initFrom(self)
        option_header.rect = rect
        option_header.section = logicalIndex
        option_header.orientation = self.orientation()
        option_header.text = ""

        # フォーカスされている（カレントセルがある）行の背景色を #dddddd にする
        view = self.parent()
        is_current = view and view.currentIndex().isValid() and view.currentIndex().row() == logicalIndex
        bg_color = QColor("#dddddd") if is_current else option_header.palette.button().color()

        # 標準のヘッダー描画(CE_Header)を使うと上下に線が出るため、背景と右側の境界線を個別に描画する
        # これにより上下の枠線が非表示になる
        painter.fillRect(rect, bg_color)
        painter.setPen(QColor("#dddddd"))
        painter.drawLine(rect.right(), rect.top(), rect.right(), rect.bottom())

        is_station_row = logicalIndex >= len(model.row_headers)
        if is_station_row:
            row_idx = logicalIndex - len(model.row_headers)
            if 0 <= row_idx < len(model.station_rows):
                color_hex = model.station_rows[row_idx].get("line_color", "#333333")
                painter.fillRect(rect.left(), rect.top(), 6, rect.height(), QColor(color_hex))

        display_text = str(model.headerData(logicalIndex, Qt.Vertical, Qt.DisplayRole) or "").strip()
        text_alignment = model.headerData(logicalIndex, Qt.Vertical, Qt.TextAlignmentRole) or (Qt.AlignRight | Qt.AlignVCenter)

        base_font = painter.font()
        fm_normal = QFontMetrics(base_font)
        trailing_space_width = fm_normal.horizontalAdvance(" ")

        text_left_padding, text_right_padding = 8, 4
        text_draw_rect = QRect(rect.left() + text_left_padding, rect.top(),
                               rect.width() - text_left_padding - text_right_padding - trailing_space_width, rect.height())

        painter.setFont(base_font)
        painter.setPen(option_header.palette.buttonText().color())

        if is_station_row:
            row_idx = logicalIndex - len(model.row_headers)
            if 0 <= row_idx < len(model.station_rows):
                station_row_data = model.station_rows[row_idx]
                station_id = model.full_stop_sequence[station_row_data["stop_idx"]]
                station_data = model.project.stations.get(station_id, {})

                if station_data.get("is_signal_station", False):
                    painter.setPen(Qt.gray)

                if station_data.get("is_major_station", False):
                    match = re.match(r"^(.*?)\s*(\[発\]|\s*\[着\])?\s*$", display_text)
                    station_name_part = match.group(1).strip() if match else display_text.strip()
                    suffix_part = match.group(2).strip() if match and match.group(2) else ""
                    bold_font = QFont(base_font)
                    bold_font.setBold(True)
                    fm_bold = QFontMetrics(bold_font)
                    station_name_width = fm_bold.horizontalAdvance(station_name_part)
                    suffix_width = fm_normal.horizontalAdvance(suffix_part)
                    space_width = fm_normal.horizontalAdvance(" ") if station_name_part and suffix_part else 0
                    total_text_width = station_name_width + space_width + suffix_width
                    start_x = text_draw_rect.right() - total_text_width

                    painter.setFont(bold_font)
                    painter.drawText(start_x, text_draw_rect.top(), station_name_width, text_draw_rect.height(),
                                     Qt.AlignRight | Qt.AlignVCenter, station_name_part)
                    if suffix_part:
                        painter.setFont(base_font)
                        painter.drawText(start_x + station_name_width + space_width, text_draw_rect.top(), suffix_width, text_draw_rect.height(),
                                         Qt.AlignRight | Qt.AlignVCenter, suffix_part)
                else:
                    painter.drawText(text_draw_rect, text_alignment, display_text)
            else:
                # 駅行以外の行（フッター行など）
                painter.drawText(text_draw_rect, text_alignment, display_text)
        else:
            painter.drawText(text_draw_rect, text_alignment, display_text)
        painter.restore()

# 時刻表テーブルの水平ヘッダーのビュー
class TimetableHorizontalHeader(QHeaderView):
    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self.setFixedHeight(12)
        self.setDefaultSectionSize(60)
        self.setSectionResizeMode(QHeaderView.Fixed)
        self.setSectionsMovable(True)

        self.draggable_icon = QIcon(":/assets/draggable.png")

    def paintSection(self, painter, rect, logicalIndex):
        painter.save()
        bg_color = QColor("#f7f7f7")
        painter.fillRect(rect, bg_color)
        painter.setPen(QColor("#dddddd"))
        painter.drawLine(rect.right(), rect.top(), rect.right(), rect.bottom())
        painter.restore()

        # ヘッダーセルの中央にアイコンを描画
        icon_width = 10 # アイコンの幅
        icon_height = 8 # アイコンの幅
        pixmap = self.draggable_icon.pixmap(icon_width, icon_height)

        icon_x = rect.left() + (rect.width() - icon_width) // 2
        icon_y = rect.top() + (rect.height() - icon_height) // 2
        target_rect = QRect(icon_x, icon_y, icon_width, icon_height)

        painter.drawPixmap(target_rect, pixmap)

# メインウィンドウの時刻表テーブルのビュー
class TimetableView(QTableView):
    def setModel(self, model):
        old_model = self.model()
        if old_model:
            try:
                old_model.modelReset.disconnect(self.update_row_heights)
                old_model.layoutChanged.disconnect(self.update_row_heights)
            except Exception:
                pass
        super().setModel(model)
        if model:
            model.modelReset.connect(self.update_row_heights)
            model.layoutChanged.connect(self.update_row_heights)

        # テーブルの外観設定
        self.setStyleSheet("QTableView, QHeaderView { font-size: 12px; }")
        self.setShowGrid(False)

        # セルの選択（カレント）状態が変わったときに垂直ヘッダーを再描画して背景色を更新する
        self.selectionModel().currentChanged.connect(lambda: self.verticalHeader().update())

        self.setup_horizontal_header()
        self.update_row_heights()

    def update_row_heights(self):
        """時刻表テーブルの各行の高さを設定する"""
        model = self.model()
        if not model or not hasattr(model, 'row_headers') or not hasattr(model, 'station_rows'):
            return
        v_header = self.verticalHeader()
        base_height = v_header.defaultSectionSize()

        num_headers = len(model.row_headers)
        num_stations = len(model.station_rows)
        total_rows = model.rowCount()

        # 全ての行（時刻表示行含む）をまずデフォルトの高さ（1行分）にリセット
        for r in range(total_rows):
            v_header.resizeSection(r, base_height)

        # 「行き先」行: 2行分の高さ
        if "行き先" in model.row_headers:
            dest_row = model.row_headers.index("行き先")
            if dest_row < total_rows:
                v_header.resizeSection(dest_row, base_height * 2)

        # 「連続する列車」行: 3行分の高さ
        subsequent_row = num_headers + num_stations
        if subsequent_row < total_rows:
            v_header.resizeSection(subsequent_row, base_height * 3)

        # 「備考」行: 4行分の高さ
        note_row = num_headers + num_stations + 1
        if note_row < total_rows:
            v_header.resizeSection(note_row, base_height * 4)

    def setup_horizontal_header(self):
        h_header = TimetableHorizontalHeader(self)
        h_header.sectionMoved.connect(self._on_section_moved)
        self.setHorizontalHeader(h_header)
        h_header.setVisible(True)

    def _on_section_moved(self, logicalIndex, oldVisualIndex, newVisualIndex):
        if oldVisualIndex == newVisualIndex:
            return
            
        from PySide6.QtCore import QTimer
        # sectionMovedイベントハンドラ実行中のオブジェクト自己破壊によるSegfaultを防ぐため遅延実行する
        QTimer.singleShot(0, lambda: self._perform_reorder(oldVisualIndex, newVisualIndex))

    def _perform_reorder(self, old_idx, new_idx):
        model = self.model()
        if not model:
            return
        model.move_train(old_idx, new_idx)
        self.setup_horizontal_header()

    def move_to_next_cell_and_edit(self, row=None, col=None):
        model = self.model()
        if row is None or col is None:
            current = self.currentIndex()
            if not current.isValid(): return False
            next_index = model._get_next_editable_index(current)
        else:
            next_index = model.index(row + 1, col)

        if next_index.isValid():
            self.setCurrentIndex(next_index)
            if hasattr(model, 'row_headers') and next_index.row() >= len(model.row_headers):
                self.edit(next_index)
            return True
        return False

    def keyPressEvent(self, event):
        model = self.model()
        if not model:
            super().keyPressEvent(event)
            return

        current = self.currentIndex()
        num_headers = len(model.row_headers) if hasattr(model, 'row_headers') else 0
        num_stations = len(model.station_rows) if hasattr(model, 'station_rows') else 0
        footer_subsequent_row = num_headers + num_stations
        footer_note_row = num_headers + num_stations + 1

        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if current.isValid():
                r = current.row()
                delegate = self.itemDelegate(current)
                if hasattr(delegate, "_show_diagram_picker_menu") and r == 1:
                    delegate._show_diagram_picker_menu(current, model, self)
                    return
                elif hasattr(delegate, "_show_operation_picker_menu") and r == 2:
                    delegate._show_operation_picker_menu(current, model, self)
                    return
                elif hasattr(delegate, "_show_train_type_menu") and r == 4:
                    delegate._show_train_type_menu(current, model, self)
                    return
                elif hasattr(delegate, "_show_subsequent_train_dialog") and r == footer_subsequent_row:
                    delegate._show_subsequent_train_dialog(current, model, self)
                    return
                elif hasattr(delegate, "_show_note_popup") and r == footer_note_row:
                    delegate._show_note_popup(current, model, self)
                    return

            if self.move_to_next_cell_and_edit():
                return

        elif event.key() == Qt.Key_Delete:
            if self.clear_selected_cells():
                return

        super().keyPressEvent(event)

    def clear_selected_cells(self):
        """選択されているセル（運転日行以外）のデータをクリアし、履歴イベントを登録する"""
        model = self.model()
        if not model or not hasattr(model, 'project') or not model.route_id or not model.diagram_id:
            return False

        indexes = self.selectedIndexes()
        if not indexes:
            return False

        from core.events import (
            ChangeTrainNumberEvent, RemoveTrainOperationEvent,
            ChangeTrainCarCountEvent, ChangeTrainTypeEvent,
            ChangeTrainNamedNumberEvent, ChangeTrainDestinationEvent,
            RemoveTrainStopEvent, ChangeTrainStopEvent,
            RemoveSubsequentTrainEvent, ChangeTrainNoteEvent
        )
        import copy

        num_headers = len(model.row_headers)
        num_stations = len(model.station_rows)
        footer_subsequent_row = num_headers + num_stations
        footer_note_row = num_headers + num_stations + 1

        route = model.project.routes.get(model.route_id, {})
        tbd = route.get("trains_by_diagram", {}).get(model.diagram_id, {})
        train_key = "inbound_trains" if model.direction == "inbound" else "outbound_trains"
        d_trains = tbd.get(train_key, {})
        m_trains = route.get(train_key, {})

        # 列ごとに選択されたインデックスを整理
        cols_map = {}
        for idx in indexes:
            cols_map.setdefault(idx.column(), []).append(idx)

        events_to_push = []
        affected_cols = set()

        for col, col_indexes in cols_map.items():
            if col >= len(model.train_ids):
                continue
            train_id = model.train_ids[col]
            d_train = d_trains.get(train_id)
            m_train = m_trains.get(train_id)
            if not d_train or not m_train:
                continue

            col_changed = False
            col_events = []

            # 行ごとにソート
            col_indexes.sort(key=lambda x: x.row())

            # ストップ変更処理用の事前スナップショット（駅行が含まれる場合）
            all_stops_before = {s["stop_idx"]: copy.deepcopy(s) for s in m_train.get("stops", []) if "stop_idx" in s}

            for idx in col_indexes:
                row = idx.row()
                if row == 1:
                    # 運転日行はクリア対象外
                    continue

                if row == 0:  # 列車番号
                    old_num = m_train.get("train_number", "")
                    if old_num != "":
                        m_train["train_number"] = ""
                        col_events.append(ChangeTrainNumberEvent(model.route_id, model.direction, train_id, old_num, ""))
                        col_changed = True

                elif row == 2:  # 運用番号
                    ops = d_train.get("operations", [])
                    if ops:
                        for i, op in reversed(list(enumerate(ops))):
                            col_events.append(RemoveTrainOperationEvent(model.route_id, model.direction, train_id, model.diagram_id, i, op))
                        d_train["operations"] = []
                        col_changed = True

                elif row == 3:  # 両数
                    old_val = d_train.get("car_count")
                    if old_val is not None:
                        d_train["car_count"] = None
                        col_events.append(ChangeTrainCarCountEvent(model.route_id, model.direction, train_id, model.diagram_id, old_val, None))
                        col_changed = True

                elif row == 4:  # 種別・愛称
                    old_val = m_train.get("train_type_id")
                    if old_val is not None:
                        m_train["train_type_id"] = None
                        col_events.append(ChangeTrainTypeEvent(model.route_id, model.direction, train_id, old_val, None))
                        col_changed = True

                elif row == 5:  # 号数
                    old_val = m_train.get("named_train_number")
                    if old_val is not None:
                        m_train["named_train_number"] = None
                        col_events.append(ChangeTrainNamedNumberEvent(model.route_id, model.direction, train_id, old_val, None))
                        col_changed = True

                elif row == 6:  # 行き先
                    old_val = d_train.get("destination")
                    if old_val is not None:
                        d_train["destination"] = None
                        col_events.append(ChangeTrainDestinationEvent(model.route_id, model.direction, train_id, model.diagram_id, old_val, None))
                        col_changed = True

                elif row == footer_subsequent_row:  # 連続する列車
                    subs = d_train.get("subsequent_trains", [])
                    if subs:
                        for i, sub in reversed(list(enumerate(subs))):
                            col_events.append(RemoveSubsequentTrainEvent(model.route_id, model.direction, train_id, model.diagram_id, i, sub))
                        d_train["subsequent_trains"] = []
                        col_changed = True

                elif row == footer_note_row:  # 備考
                    old_note = m_train.get("note", "")
                    if old_note != "":
                        m_train["note"] = ""
                        col_events.append(ChangeTrainNoteEvent(model.route_id, model.direction, train_id, old_note, ""))
                        col_changed = True

                elif num_headers <= row < footer_subsequent_row:  # 駅行
                    row_idx = row - num_headers
                    if 0 <= row_idx < len(model.station_rows):
                        row_def = model.station_rows[row_idx]
                        stop_idx = row_def["stop_idx"]
                        config = model.full_stop_configs[stop_idx]
                        station_data = model.project.stations.get(config["station_id"], {})
                        is_seg_boundary = config.get("is_segment_start") or config.get("is_segment_end")
                        show_arr = is_seg_boundary or station_data.get("show_arrival_time", False)

                        stop = next((s for s in m_train.get("stops", []) if s.get("stop_idx") == stop_idx), None)
                        if stop:
                            time_key = "arrival_time" if row_def["type"] == "arr" else "departure_time"
                            if stop.get(time_key) is not None:
                                stop[time_key] = None
                                col_changed = True
                                # 中間駅で着時刻非表示の場合、発時刻のクリアに合わせて着時刻もクリア
                                if row_def["type"] == "dep" and not is_seg_boundary and not show_arr:
                                    stop["arrival_time"] = None

            # 駅行の変更差分をイベント化
            if col_changed and "stops" in m_train:
                # 完全に発着時刻が空になったstopの整理
                new_stops = []
                for s in m_train["stops"]:
                    s_idx = s.get("stop_idx")
                    old_s = all_stops_before.get(s_idx)
                    arr = s.get("arrival_time")
                    dep = s.get("departure_time")
                    if arr is None and dep is None:
                        # 全時刻がNoneになった場合はリストから削除
                        if old_s is not None:
                            old_idx = list(all_stops_before.keys()).index(s_idx)
                            col_events.append(RemoveTrainStopEvent(model.route_id, model.direction, train_id, old_idx, old_s))
                    else:
                        new_stops.append(s)
                        if old_s != s:
                            col_events.append(ChangeTrainStopEvent(model.route_id, model.direction, train_id, s_idx, old_s, s))
                m_train["stops"] = new_stops

            if col_changed:
                events_to_push.extend(col_events)
                affected_cols.add(col)

        if events_to_push:
            if model.history_manager:
                model.history_manager.push_events(events_to_push)
            model.clear_destination_cache()
            for col in affected_cols:
                train_id = model.train_ids[col]
                m_train = m_trains.get(train_id)
                if m_train:
                    model._normalize_train_stops(m_train)
                model.dataChanged.emit(
                    model.index(0, col),
                    model.index(model.rowCount() - 1, col),
                    [Qt.DisplayRole, Qt.EditRole, Qt.ForegroundRole, Qt.BackgroundRole, StopTypeRole]
                )
            return True

        return False

    def contextMenuEvent(self, event):
        index = self.indexAt(event.pos())
        if not index.isValid():
            super().contextMenuEvent(event)
            return

        model = self.model()
        if not model or not hasattr(model, 'row_headers') or not hasattr(model, 'station_rows'):
            super().contextMenuEvent(event)
            return

        row, col = index.row(), index.column()
        # 各駅停車時刻のセル
        if row >= len(model.row_headers) and row < len(model.row_headers) + len(model.station_rows):
            menu = QMenu(self)
            
            # 客扱い情報 サブメニュー
            passenger_menu = QMenu("客扱い情報", menu)
            
            group = QActionGroup(self)
            
            current_value = index.data(StopTypeRole)
            if current_value is None:
                current_value = 1  # デフォルトは停車
                
            stop_action = passenger_menu.addAction("停車")
            stop_action.setCheckable(True)
            stop_action.setData(1)
            group.addAction(stop_action)
            if current_value == 1:
                stop_action.setChecked(True)
                
            pass_action = passenger_menu.addAction("通過")
            pass_action.setCheckable(True)
            pass_action.setData(0)
            group.addAction(pass_action)
            if current_value == 0:
                pass_action.setChecked(True)
                
            op_stop_action = passenger_menu.addAction("運転停車")
            op_stop_action.setCheckable(True)
            op_stop_action.setData(-1)
            group.addAction(op_stop_action)
            if current_value == -1:
                op_stop_action.setChecked(True)
                
            menu.addMenu(passenger_menu)
            
            split_action = menu.addAction("この駅で列車を分割")
            
            selected_action = menu.exec(event.globalPos())
            if selected_action and selected_action in (stop_action, pass_action, op_stop_action):
                new_val = selected_action.data()
                model.setData(index, new_val, StopTypeRole)
            elif selected_action == split_action:
                from .dialogs import split_train_at_cell
                split_train_at_cell(self, model, index)
        else:
            super().contextMenuEvent(event)

