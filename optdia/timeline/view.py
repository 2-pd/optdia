from PySide6.QtWidgets import QGraphicsView
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from .scene import TimelineScene

class TimelineView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = TimelineScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setStyleSheet("border: none; background-color: #fafafa;")
