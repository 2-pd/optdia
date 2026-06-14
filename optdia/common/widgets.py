from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

# 線のサンプルを表示するためのカスタムウィジェット
class LineSampleWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(120, 30)
        self.line_color = QColor("#333333")
        self.line_weight = "normal"
        self.line_style = "solid"

    def set_line_properties(self, color_hex, weight, style):
        self.line_color = QColor(color_hex)
        self.line_weight = weight
        self.line_style = style
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        # 背景
        painter.fillRect(self.rect(), Qt.white)
        painter.setPen(QColor("#cccccc"))
        painter.drawRect(0, 0, self.width() - 1, self.height() - 1)

        # ペンの設定
        pen = QPen(self.line_color)
        
        # 太さのマッピング
        if self.line_weight == "thin":
            pen.setWidth(1)
        elif self.line_weight == "bold":
            pen.setWidth(3)
        else: # normal
            pen.setWidth(2)

        # スタイルのマッピング
        if self.line_style == "dashed":
            pen.setStyle(Qt.DashLine)
        elif self.line_style == "dotted":
            pen.setStyle(Qt.DotLine)
        else: # solid
            pen.setStyle(Qt.SolidLine)

        painter.setPen(pen)
        y = self.height() / 2
        painter.drawLine(10, y, self.width() - 10, y)