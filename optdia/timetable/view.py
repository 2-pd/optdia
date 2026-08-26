import re
from PySide6.QtCore import Qt, QRect, QModelIndex
from PySide6.QtGui import QColor, QPainter, QFont, QFontMetrics
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

        # フォーカスされている（カレントセルがある）行の背景色を #cccccc にする
        view = self.parent()
        is_current = view and view.currentIndex().isValid() and view.currentIndex().row() == logicalIndex
        bg_color = QColor("#eeeeee") if is_current else option_header.palette.button().color()

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

    def paintSection(self, painter, rect, logicalIndex):
        painter.save()
        bg_color = QColor("#eeeeee")
        painter.fillRect(rect, bg_color)
        painter.setPen(QColor("#dddddd"))
        painter.drawLine(rect.right(), rect.top(), rect.right(), rect.bottom())
        painter.restore()

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
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self.move_to_next_cell_and_edit(): return
        super().keyPressEvent(event)

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

