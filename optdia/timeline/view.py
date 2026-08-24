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



