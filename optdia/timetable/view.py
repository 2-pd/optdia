import re
from PySide6.QtCore import Qt, QRect, QModelIndex
from PySide6.QtGui import QColor, QPainter, QFont, QFontMetrics
from PySide6.QtWidgets import QHeaderView, QStyleOptionHeader, QStyle, QTableView, QPushButton, QSizePolicy, QVBoxLayout, QLabel

# 時刻表テーブルの垂直ヘッダーのビュー
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
        super().setModel(model)
        # セルの選択（カレント）状態が変わったときに垂直ヘッダーを再描画して背景色を更新する
        self.selectionModel().currentChanged.connect(lambda: self.verticalHeader().update())

        # モデルのリセット時や行・列の変更時にボタンを再配置する
        model.modelReset.connect(self._update_footer_widgets)
        model.columnsInserted.connect(self._update_footer_widgets)
        model.columnsRemoved.connect(self._update_footer_widgets)
        model.rowsInserted.connect(self._update_footer_widgets)
        model.rowsRemoved.connect(self._update_footer_widgets)
        model.dataChanged.connect(self._update_footer_widgets)
        
        self._update_footer_widgets()
        self.setup_horizontal_header()

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

    def _update_footer_widgets(self):
        model = self.model()
        if not model or not hasattr(model, 'row_headers') or not hasattr(model, 'station_rows'):
            return
            
        footer_row = len(model.row_headers) + len(model.station_rows)
        if footer_row >= model.rowCount():
            return

        route = model.project.routes.get(model.route_id)
        if not route: return
        tbd = route.get("trains_by_diagram", {}).get(model.diagram_id, {})
        train_key = "inbound_trains" if model.direction == "inbound" else "outbound_trains"
        # 連続する列車情報はダイヤ側のオブジェクトを参照
        d_trains = tbd.get(train_key, {})
        # 列車番号や種別はマスタ側のオブジェクトを参照
        m_trains = route.get(train_key, {})

        for col in range(model.columnCount()):
            index = model.index(footer_row, col)
            if not index.isValid(): continue

            btn = self.indexWidget(index)
            if not btn:
                btn = QPushButton()
                btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                btn.setFocusPolicy(Qt.NoFocus)
                # 枠線を非表示にし、背景を透明に設定
                btn.setStyleSheet("QPushButton { border: none; background: transparent; margin: 0px; }")
                
                # 複数色のテキスト（HTML）を表示するために内部にラベルを配置
                layout = QVBoxLayout(btn)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(0)
                label = QLabel()
                label.setAlignment(Qt.AlignCenter)
                label.setAttribute(Qt.WA_TransparentForMouseEvents) # クリックを下のボタンに透過させる
                layout.addWidget(label)
                
                btn.clicked.connect(lambda _, c=col: self._on_footer_button_clicked(c))
                self.setIndexWidget(index, btn)

            label = btn.findChild(QLabel)

            # 連続する列車の列車番号を取得して表示（最大3つ）
            if col < len(model.train_ids):
                train_id = model.train_ids[col]
                d_train = d_trains.get(train_id, {})
                subsequent_list = d_train.get("subsequent_trains") or []
                
                html_parts = []
                for item in subsequent_list[:3]:
                    s_rid, s_dir, s_tid = item.get("route_id"), item.get("direction"), item.get("train_id")
                    if s_tid:
                        s_route = model.project.routes.get(s_rid)
                        if s_route:
                            s_train_key = "inbound_trains" if s_dir == "inbound" else "outbound_trains"
                            # マスタ側から列車番号等を取得
                            s_m_train = s_route.get(s_train_key, {}).get(s_tid)
                            if s_m_train:
                                num = s_m_train.get("train_number") or "(番号なし)"
                                # 種別の基本色を取得
                                tt_id = s_m_train.get("train_type_id")
                                tt = model.project.train_types.get(tt_id)
                                color = tt.get("main_color", "#333333") if tt else "#333333"
                                html_parts.append(f"<div style='color: {color};'>{num}</div>")
                
                if label:
                    label.setText("".join(html_parts))

    def _on_footer_button_clicked(self, col):
        from .dialogs import SubsequentTrainDialog
        model = self.model()
        if not model.route_id or not model.diagram_id:
            return
            
        route = model.project.routes.get(model.route_id)
        tbd = route.get("trains_by_diagram", {}).get(model.diagram_id, {})
        train_key = "inbound_trains" if model.direction == "inbound" else "outbound_trains"
        train_id = model.train_ids[col]
        
        d_train = tbd.get(train_key, {}).get(train_id)
        m_train = route.get(train_key, {}).get(train_id)
        
        if d_train:
            # ダイアログにはダイヤ側の情報とマスタ側の情報の両方が必要になる場合があるため
            dialog = SubsequentTrainDialog(self, model.project, d_train, m_train, model.diagram_id,
                                          model.route_id, model.direction)
            dialog.exec()

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
