from PySide6.QtCore import Qt, QEvent, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QStyledItemDelegate, QStyleOptionViewItem, QApplication, QStyle,
    QDialog, QLineEdit, QAbstractItemDelegate, QVBoxLayout, QListWidget, QListWidgetItem
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

        for tt_id in self.project.train_types_order:
            tt = self.project.train_types[tt_id]
            name, train_name = tt.get("train_type_name", ""), tt.get("train_name")
            color, bg_color = tt.get("main_color", "#333333"), tt.get("background_color", "#ffffff")
            display_name = f"{name} {train_name}" if train_name else name
            item = QListWidgetItem(f"<font color='{color}'>{display_name}</font>")
            item.setData(Qt.UserRole, tt_id)
            item.setBackground(QColor(bg_color))
            self.list_widget.addItem(item)

        if current_id:
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

class TimetableDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        row, model = index.row(), index.model()
        if row in (1, 3):
            options = QStyleOptionViewItem(option)
            self.initStyleOption(options, index)
            style = options.widget.style() if options.widget else QApplication.style()
            options.text = ""
            style.drawControl(QStyle.CE_ItemViewItem, options, painter)
            text = index.data(Qt.DisplayRole)
            color = index.data(Qt.ForegroundRole)
            if not isinstance(color, QColor): color = options.palette.text().color()
            painter.save()
            painter.setPen(color)
            painter.setFont(options.font)
            painter.drawText(options.rect, Qt.AlignCenter, text)
            painter.restore()
        else:
            super().paint(painter, option, index)

        painter.save()
        painter.setPen(QColor("#d0d0d0"))
        rect = option.rect
        painter.drawLine(rect.right(), rect.top(), rect.right(), rect.bottom())
        num_headers = len(model.row_headers) if hasattr(model, 'row_headers') else 0
        if row < num_headers:
            painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())
        painter.restore()

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        if index.row() in (1, 3): size.setHeight(max(size.height(), 32))
        return size

    def editorEvent(self, event, model, option, index):
        if event.type() == QEvent.MouseButtonRelease and index.row() == 3:
            self._show_train_type_menu(index, model, option.widget)
            return True
        return super().editorEvent(event, model, option, index)

    def _show_train_type_menu(self, index, model, widget):
        train_id = model.train_ids[index.column()]
        route = model.project.routes.get(model.route_id)
        trains = route.get("trains_by_diagram", {}).get(model.diagram_id, {}).get("inbound_trains" if model.direction == "inbound" else "outbound_trains", {})
        current_id = trains.get(train_id, {}).get("train_type_id")
        picker = TrainTypePicker(widget, model.project, current_id)
        pos = widget.viewport().mapToGlobal(widget.visualRect(index).bottomLeft())
        picker.move(pos)
        if picker.exec() == QDialog.Accepted: model.setData(index, picker.selected_id, Qt.EditRole)

    def setEditorData(self, editor, index):
        super().setEditorData(editor, index)
        if isinstance(editor, QLineEdit):
            editor.deselect()
            editor.setCursorPosition(len(editor.text()))

    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit): editor.installEventFilter(self)
        return editor

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter) and isinstance(obj, QLineEdit):
            view = self.parent()
            idx = view.currentIndex()
            r, c = idx.row(), idx.column()
            self.commitData.emit(obj)
            self.closeEditor.emit(obj, QAbstractItemDelegate.SubmitModelCache)
            QTimer.singleShot(0, lambda: view.move_to_next_cell_and_edit(r, c))
            return True
        return super().eventFilter(obj, event)
