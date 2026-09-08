from PySide6.QtWidgets import QGraphicsView
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from .scene import TimelineScene, TimelineHeaderScene

# 運用ガントチャートのビュー
class TimelineView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = TimelineScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setStyleSheet("""
        QGraphicsView {
            border: none;
            background-color: #ffffff;
        }
        """)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self._is_rubber_banding = False

    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())
        from .scene import TimelineRectItem
        if not item or not isinstance(item, TimelineRectItem):
            if not (event.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier)):
                self.scene.clear_timeline_selection()
            self._is_rubber_banding = True
            self._rubber_band_origin = event.pos()
            super().mousePressEvent(event)
        else:
            self._is_rubber_banding = False
            self._rubber_band_origin = None
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self._is_rubber_banding and self._rubber_band_origin is not None:
            self._is_rubber_banding = False
            p1 = self._rubber_band_origin
            p2 = event.pos()
            self._rubber_band_origin = None
            
            # 矩形領域の作成 (viewport coordinates -> scene coordinates)
            from PySide6.QtCore import QRect
            rect = QRect(p1, p2).normalized()
            if rect.width() > 3 and rect.height() > 3:
                scene_poly = self.mapToScene(rect)
                scene_rect = scene_poly.boundingRect()
                items_in_rect = self.scene.items(scene_rect)
                self.scene.handle_rubber_band_selection(items_in_rect)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            self.scene.delete_selected_items()
            event.accept()
        else:
            super().keyPressEvent(event)

    def update_timeline(self, project, diagram_id: str, operation_group_id: str):
        self.scene.update_timeline(project, diagram_id, operation_group_id)


# 運用ガントチャートの見出しのビュー
class TimelineHeaderView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = TimelineHeaderScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setStyleSheet("border: none; background-color: #f7f7f7;")
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def update_header(self, right_margin: int = 0):
        self.scene.update_header(right_margin)



