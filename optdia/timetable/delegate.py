from PySide6.QtCore import Qt, QEvent, QTimer, QRect
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QStyledItemDelegate, QStyleOptionViewItem, QApplication, QStyle,
    QDialog, QLineEdit, QAbstractItemDelegate, QVBoxLayout, QListWidget, QListWidgetItem,
    QWidget, QHBoxLayout, QPushButton
)
from common.gui_utils import HtmlDelegate
from project import OptDiaProject

class TrainTypePicker(QDialog):
    def __init__(self, parent, project: OptDiaProject, current_id=None):
        super().__init__(parent, Qt.Popup)
        self.project = project
        self.selected_id = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.list_widget = QListWidget(self)
        self.list_widget.setStyleSheet("border: 1px solid #dddddd;")
        self.list_widget.setItemDelegate(HtmlDelegate(self))

        # 「設定しない」アイテムの追加
        none_item = QListWidgetItem("<font color='#888888'>設定しない</font>")
        none_item.setData(Qt.UserRole, None)
        self.list_widget.addItem(none_item)

        for tt_id in self.project.train_types_order:
            tt = self.project.train_types[tt_id]
            name, train_name = tt.get("train_type_name", ""), tt.get("train_name")
            color, bg_color = tt.get("main_color", "#333333"), tt.get("background_color", "#ffffff")
            display_name = f"{name} {train_name}" if train_name else name
            item = QListWidgetItem(f"<font color='{color}'>{display_name}</font>")
            item.setData(Qt.UserRole, tt_id)
            item.setBackground(QColor(bg_color))
            self.list_widget.addItem(item)

        if current_id is None:
            self.list_widget.setCurrentItem(none_item)
        else:
            for i in range(self.list_widget.count()):
                if self.list_widget.item(i).data(Qt.UserRole) == current_id:
                    self.list_widget.setCurrentItem(self.list_widget.item(i))
                    self.list_widget.scrollToItem(self.list_widget.item(i))
                    break
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)
        self.setFixedSize(200, min(400, self.list_widget.count() * 32 + 2))

    def _on_item_clicked(self, item):
        self.selected_id = item.data(Qt.UserRole)
        self.accept()

class TrackPicker(QDialog):
    def __init__(self, parent, station_data, current_track_id=None):
        super().__init__(parent, Qt.Popup)
        self.selected_id = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.list_widget = QListWidget(self)
        self.list_widget.setStyleSheet("border: 1px solid #dddddd;")
        
        # 「設定しない」アイテムの追加
        none_item = QListWidgetItem("設定しない")
        none_item.setData(Qt.UserRole, None)
        self.list_widget.addItem(none_item)
        if current_track_id is None:
            self.list_widget.setCurrentItem(none_item)

        tracks = station_data.get("tracks", {})
        order = station_data.get("tracks_order", [])
        for tid in order:
            track = tracks.get(tid, {})
            track_name = track.get("track_name") or tid
            item = QListWidgetItem(track_name)
            item.setData(Qt.UserRole, tid)
            self.list_widget.addItem(item)
            if tid == current_track_id:
                self.list_widget.setCurrentItem(item)
                self.list_widget.scrollToItem(item)
        
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)
        self.setFixedSize(150, min(300, self.list_widget.count() * 28 + 2))

    def _on_item_clicked(self, item):
        self.selected_id = item.data(Qt.UserRole)
        self.accept()

# メインウィンドウの時刻表テーブルで使用するデリゲート
class TimetableDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        row, model = index.row(), index.model()
        num_headers = len(model.row_headers) if hasattr(model, 'row_headers') else 0

        # 番線表示の設定確認
        draw_track_box = False
        track_short_name = ""
        track_box_width = 15
        
        # フッター行（連続する列車）の判定
        num_stations = len(model.station_rows) if hasattr(model, 'station_rows') else 0
        footer_row_idx = num_headers + num_stations

        # 未入力セルの記号判定
        placeholder_symbol = None
        if row >= num_headers and row < footer_row_idx:
            display_text = index.data(Qt.DisplayRole)
            if not display_text:
                # フォーカスや選択がない場合のみプレースホルダーを表示
                if not (option.state & (QStyle.State_HasFocus | QStyle.State_Selected)):
                    placeholder_symbol = self._get_placeholder_symbol(index)
        
        if row == footer_row_idx:
            # セル内のボタンは TimetableView で setIndexWidget により配置されるため、
            # デリゲートでは境界線のみ描画する
            painter.save()
            painter.setPen(QColor("#dddddd"))
            painter.drawLine(option.rect.right(), option.rect.top(), option.rect.right(), option.rect.bottom())
            painter.restore()
            return

        if row >= num_headers:
            row_idx = row - num_headers
            if 0 <= row_idx < len(model.station_rows):
                row_def = model.station_rows[row_idx]
                config = model.full_stop_configs[row_def["stop_idx"]]
                station_data = model.project.stations.get(config["station_id"], {})
                if station_data.get("show_track_name", False):
                    draw_track_box = True
                    # 時刻情報に対応する番線名を取得
                    train_id = model.train_ids[index.column()]
                    route = model.project.routes.get(model.route_id)
                    if route:
                        train_key = "inbound_trains" if model.direction == "inbound" else "outbound_trains"
                        # 停車駅(stops)は運行系統が持つマスタ列車情報を参照する
                        m_train = route.get(train_key, {}).get(train_id, {})
                        stop = next((s for s in m_train.get("stops", []) if s.get("stop_idx") == row_def["stop_idx"]), None)
                        if stop:
                            track_id = stop.get("track_id")
                            track_data = station_data.get("tracks", {}).get(track_id)
                            if track_data:
                                track_short_name = track_data.get("track_short_name") or ""

        # 描画用オプションの作成（番線ボックスがある場合は右にずらす）
        text_option = QStyleOptionViewItem(option)
        self.initStyleOption(text_option, index)
        if draw_track_box:
            # 番線ボックスの描画（編集時のボタンと同じ外観）
            track_rect = QRect(option.rect.left(), option.rect.top(), track_box_width, option.rect.height())
            painter.save() # 変更開始
            painter.fillRect(track_rect, QColor("#f7f7f7")) # 背景色を #f7f7f7 に変更
            
            painter.setPen(QColor("#333333"))
            font = painter.font()
            font.setPointSize(10)
            painter.setFont(font)
            painter.drawText(track_rect, Qt.AlignCenter, track_short_name)
            painter.restore()
            
            # 時刻テキストの描画範囲を右へオフセット
            text_option.rect.setLeft(option.rect.left() + track_box_width)

        if row < num_headers:
            style = text_option.widget.style() if text_option.widget else QApplication.style()
            text_option.text = ""
            style.drawControl(QStyle.CE_ItemViewItem, text_option, painter)
            text = index.data(Qt.DisplayRole)
            color = index.data(Qt.ForegroundRole)
            if not isinstance(color, QColor): color = text_option.palette.text().color()
            alignment = index.data(Qt.TextAlignmentRole) or Qt.AlignCenter
            if row == 5:
                alignment |= Qt.TextWordWrap
            painter.save()
            painter.setPen(color)
            painter.setFont(text_option.font)
            painter.drawText(text_option.rect, alignment, text)
            painter.restore()
        else:
            # セルの背景（選択ハイライトなど）を描画
            style = text_option.widget.style() if text_option.widget else QApplication.style()
            text_option.text = "" # テキストは後で手動描画する
            style.drawControl(QStyle.CE_ItemViewItem, text_option, painter)

            painter.save()
            if placeholder_symbol:
                painter.setPen(Qt.gray)
                alignment = Qt.AlignCenter
                # 番線ボックスの有無にかかわらず、セル本体の中央に描画する
                painter.drawText(option.rect, alignment, placeholder_symbol)
            else:
                text = index.data(Qt.DisplayRole)
                if text:
                    color = index.data(Qt.ForegroundRole)
                    if not isinstance(color, QColor): color = text_option.palette.text().color()
                    alignment = index.data(Qt.TextAlignmentRole) or (Qt.AlignRight | Qt.AlignVCenter)
                    painter.setPen(color)
                    painter.setFont(text_option.font)
                    painter.drawText(text_option.rect, alignment, text)
            painter.restore()

        painter.save()
        painter.setPen(QColor("#dddddd"))
        rect = option.rect
        painter.drawLine(rect.right(), rect.top(), rect.right(), rect.bottom())
        # 下部の枠線を描画
        if row == num_headers - 1 or row == footer_row_idx - 1:
            painter.setPen(QColor("#999999")) # 境界（行き先の下、または最後の駅の下）を少し濃い色で強調
            painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())
        elif row < num_headers:
            painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())
        painter.restore()

    def sizeHint(self, option, index):
        # 1行あたりの標準的な高さを計算（フォント高さ＋上下パディングの目安）
        line_height = option.fontMetrics.height() + 8
        size = super().sizeHint(option, index)
        row = index.row()

        if row in (1, 3):
            size.setHeight(max(line_height, 32))
        elif row == 5:
            # 入力内容（折り返し数）に関わらず、高さを1行分の2倍に固定します
            size.setHeight(line_height * 2)
        
        model = index.model()
        num_headers = len(model.row_headers) if hasattr(model, 'row_headers') else 0
        num_stations = len(model.station_rows) if hasattr(model, 'station_rows') else 0
        if row == num_headers + num_stations:
            # フッターも同様に3行分に固定します
            size.setHeight(line_height * 3)
        return size

    def editorEvent(self, event, model, option, index):
        row, model = index.row(), index.model()
        num_headers = len(model.row_headers) if hasattr(model, 'row_headers') else 0
        
        # 番線表示エリア (左側15px) のクリック検知
        if event.type() == QEvent.MouseButtonRelease and row >= num_headers:
            if event.position().x() < option.rect.left() + 15:
                if self._is_track_editable(index, model):
                    self._show_track_menu(index, model, option.widget)
                    return True

        if event.type() == QEvent.MouseButtonRelease and index.row() == 3:
            self._show_train_type_menu(index, model, option.widget)
            return True
        return super().editorEvent(event, model, option, index)

    def _show_train_type_menu(self, index, model, widget):
        train_id = model.train_ids[index.column()]
        route = model.project.routes.get(model.route_id)
        # 列車種別(train_type_id)は運行系統が持つマスタ列車情報を参照する
        train_key = "inbound_trains" if model.direction == "inbound" else "outbound_trains"
        current_id = route.get(train_key, {}).get(train_id, {}).get("train_type_id")
        picker = TrainTypePicker(widget, model.project, current_id)
        pos = widget.viewport().mapToGlobal(widget.visualRect(index).bottomLeft())
        picker.move(pos)
        if picker.exec() == QDialog.Accepted: model.setData(index, picker.selected_id, Qt.EditRole)

    def _is_track_editable(self, index, model):
        row_idx = index.row() - len(model.row_headers)
        row_def = model.station_rows[row_idx]
        config = model.full_stop_configs[row_def["stop_idx"]]
        station_data = model.project.stations.get(config["station_id"], {})
        return station_data.get("show_track_name", False)

    def _show_track_menu(self, index, model, widget):
        from timetable.model import TrackIdRole
        row, col = index.row(), index.column()
        num_headers = len(model.row_headers)
        row_def = model.station_rows[row - num_headers]
        config = model.full_stop_configs[row_def["stop_idx"]]
        station_data = model.project.stations.get(config["station_id"], {})
        
        # 現在の番線IDを取得
        train_id = model.train_ids[col]
        route = model.project.routes.get(model.route_id)
        train_key = "inbound_trains" if model.direction == "inbound" else "outbound_trains"
        # 停車駅(stops)は運行系統が持つマスタ列車情報を参照する
        m_train = route.get(train_key, {}).get(train_id, {})
        stop = next((s for s in m_train.get("stops", []) if s.get("stop_idx") == row_def["stop_idx"]), None)
        current_track_id = stop.get("track_id") if stop else None
        
        picker = TrackPicker(widget, station_data, current_track_id)
        # 表示位置をセルの左下に合わせる
        rect = widget.visualRect(index)
        pos = widget.viewport().mapToGlobal(rect.bottomLeft())
        picker.move(pos)
        if picker.exec() == QDialog.Accepted: model.setData(index, picker.selected_id, TrackIdRole)

    def setEditorData(self, editor, index):
        super().setEditorData(editor, index)
        if isinstance(editor, QLineEdit):
            editor.deselect()
            editor.setCursorPosition(len(editor.text()))

    def setModelData(self, editor, model, index):
        super().setModelData(editor, model, index)

    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit):
            # モデルに定義されたアライメントをエディタにも適用
            alignment = index.data(Qt.TextAlignmentRole)
            if alignment:
                editor.setAlignment(alignment)

            editor.installEventFilter(self)
            model = index.model()
            if hasattr(model, 'row_headers') and index.row() >= len(model.row_headers):
                if self._is_track_editable(index, model):
                    # 編集開始時に番線表示エリアを隠すため、入力テキストの開始位置を右にずらす
                    editor.setTextMargins(15, 0, 0, 0)
        return editor

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter) and isinstance(obj, QLineEdit):
            editor = obj
            view = self.parent()
            idx = view.currentIndex()
            r, c = idx.row(), idx.column()
            self.commitData.emit(editor)
            self.closeEditor.emit(editor, QAbstractItemDelegate.SubmitModelCache)
            QTimer.singleShot(0, lambda: view.move_to_next_cell_and_edit(r, c))
            return True
        return super().eventFilter(obj, event)

    def _get_placeholder_symbol(self, index):
        model = index.model()
        row, col = index.row(), index.column()
        num_headers = len(model.row_headers)
        row_idx = row - num_headers
        if not (0 <= row_idx < len(model.station_rows)):
            return None
        
        row_def = model.station_rows[row_idx]
        stop_idx = row_def["stop_idx"]
        
        train_id = model.train_ids[col]
        route = model.project.routes.get(model.route_id)
        if not route: return None
        train_key = "inbound_trains" if model.direction == "inbound" else "outbound_trains"
        # stops はマスタ情報を参照
        m_train = route.get(train_key, {}).get(train_id)
        if not m_train: return None
        
        stops = m_train.get("stops", [])
        # 時刻が入っている(未入力でない)stop_idxの集合を取得
        timed_indices = {s["stop_idx"] for s in stops if s.get("arrival_time") or s.get("departure_time")}
        
        if not timed_indices:
            return "・・"
            
        first_idx = min(timed_indices)
        last_idx = max(timed_indices)
        
        if stop_idx < first_idx or stop_idx > last_idx:
            return "・・"
            
        # 始発から終着の間にある駅。セグメントの範囲を特定する
        seg_start = stop_idx
        while seg_start > 0 and not model.full_stop_configs[seg_start].get("is_segment_start"):
            seg_start -= 1
        seg_end = stop_idx
        while seg_end < len(model.full_stop_configs) - 1 and not model.full_stop_configs[seg_end].get("is_segment_end"):
            seg_end += 1
            
        # セグメント内のいずれかの駅に時刻が入っているか
        any_in_segment = any(seg_start <= idx <= seg_end for idx in timed_indices)
        return "ﾚ" if any_in_segment else "| |"
