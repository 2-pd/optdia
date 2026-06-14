import re
from PySide6.QtCore import Qt, QRect, QModelIndex
from PySide6.QtGui import QColor, QPainter, QFont, QFontMetrics
from PySide6.QtWidgets import QHeaderView, QStyleOptionHeader, QStyle, QTableView

class TimetableVerticalHeader(QHeaderView):
    def __init__(self, parent=None):
        super().__init__(Qt.Vertical, parent)

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
        self.style().drawControl(QStyle.CE_Header, option_header, painter, self)

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
            painter.drawText(text_draw_rect, text_alignment, display_text)
        painter.restore()

class TimetableView(QTableView):
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
