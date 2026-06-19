from PySide6.QtWidgets import QGraphicsScene, QGraphicsTextItem
from PySide6.QtGui import QColor, QFont
from PySide6.QtCore import Qt

class TimelineScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackgroundBrush(QColor("#fafafa"))
        
        # Add a placeholder text to confirm it's displaying
        self.placeholder_text = QGraphicsTextItem("運用表 (車両運用ガントチャート) 表示エリア")
        font = QFont("Sans-serif", 16)
        self.placeholder_text.setFont(font)
        self.placeholder_text.setDefaultTextColor(QColor("#888888"))
        self.addItem(self.placeholder_text)
        
        # Update scene rect or position of text
        self.placeholder_text.setPos(50, 50)
