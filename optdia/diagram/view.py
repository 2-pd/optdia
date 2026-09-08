from PySide6.QtWidgets import QGraphicsView
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from .scene import DiagramScene, DiagramHeaderScene, DiagramStationScene

# 運行ダイヤグラムの上部ビュー（時刻ヘッダー）
class DiagramHeaderView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = DiagramHeaderScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setStyleSheet("border: none; background-color: #ffffff;")
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setFixedHeight(20)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def update_header(self):
        self.scene.update_header()


# 運行ダイヤグラムの左側ビュー（駅名）
class DiagramStationView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = DiagramStationScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setStyleSheet("border: none; background-color: #ffffff;")
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setFixedWidth(120)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def update_stations(self, project, stations_data):
        self.scene.update_stations(project, stations_data)


# 運行ダイヤグラムのメインビュー（右下）
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
        return self.scene.update_diagram(project, selected_target, route_id, diagram_id)

