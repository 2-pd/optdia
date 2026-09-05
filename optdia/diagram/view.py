from PySide6.QtWidgets import QGraphicsView
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from .scene import DiagramScene

class DiagramView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = DiagramScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setStyleSheet("""
        QGraphicsView {
            border: none;
            background-color: #ffffff;
        }
        """)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    def update_diagram(self, project, selected_target: str, route_id: str, diagram_id: str):
        self.scene.update_diagram(project, selected_target, route_id, diagram_id)
