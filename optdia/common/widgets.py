from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QIcon, QTransform
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QFrame, QColorDialog
)
from settings import AppSettings
from common.gui_utils import create_color_square_pixmap


# クリック可能なカラーラベル
class ClickableColorLabel(QLabel):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


# 色選択ウィジェット（正方形ピクスマップ、ボタン、色選択履歴QFrame）
class ColorPickerWidget(QWidget):
    colorChanged = Signal(str)

    def __init__(self, default_color: str = "#333333", parent=None):
        super().__init__(parent)
        self._current_color = default_color
        self._app_settings = AppSettings()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # 上部: 30pxの正方形ピクスマップと色コードボタン
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(6)

        self.color_square = ClickableColorLabel()
        self.color_square.setFixedSize(30, 30)
        self.color_square.setStyleSheet("border: 1px solid #cccccc;")
        self.color_square.clicked.connect(self._open_color_dialog)
        top_layout.addWidget(self.color_square)

        self.color_button = QPushButton(self._current_color)
        self.color_button.clicked.connect(self._open_color_dialog)
        top_layout.addWidget(self.color_button)
        top_layout.addStretch()

        main_layout.addLayout(top_layout)

        # 下部: 枠線付きQFrame（履歴表示）
        self.history_frame = QFrame()
        self.history_frame.setFrameShape(QFrame.StyledPanel)
        self.history_frame.setFrameShadow(QFrame.Plain)
        self.history_frame.setStyleSheet("QFrame { border: 1px solid #cccccc; border-radius: 4px; padding: 2px; }")

        self.history_layout = QHBoxLayout(self.history_frame)
        self.history_layout.setContentsMargins(2, 2, 2, 2)
        self.history_layout.setSpacing(2)

        history_label = QLabel("履歴:")
        history_label.setStyleSheet("border: none;")
        self.history_layout.addWidget(history_label)

        self.history_colors_layout = QHBoxLayout()
        self.history_colors_layout.setContentsMargins(0, 0, 0, 0)
        self.history_colors_layout.setSpacing(2)
        self.history_layout.addLayout(self.history_colors_layout)
        self.history_layout.addStretch()

        main_layout.addWidget(self.history_frame)

        self._update_display(self._current_color)
        self.refresh_history()

    def set_color(self, color_hex: str):
        """色を設定し、表示を更新する（シグナルは発火しない）"""
        self._current_color = color_hex
        self._update_display(color_hex)

    def get_color(self) -> str:
        """現在の色コードを取得する"""
        return self._current_color

    def setEnabled(self, enabled: bool):
        super().setEnabled(enabled)
        self.color_square.setEnabled(enabled)
        self.color_button.setEnabled(enabled)
        self.history_frame.setEnabled(enabled)

    def _update_display(self, color_hex: str):
        self.color_button.setText(color_hex)
        self.color_square.setPixmap(create_color_square_pixmap(color_hex, size=30))

    def _open_color_dialog(self):
        if not self.isEnabled():
            return
        initial_color = QColor(self._current_color if self._current_color else "#ffffff")
        color = QColorDialog.getColor(initial_color, self)
        if color.isValid():
            new_hex = color.name()
            self._apply_and_save_color(new_hex)

    def _on_history_color_clicked(self, color_hex: str):
        if not self.isEnabled():
            return
        self._apply_and_save_color(color_hex)

    def _apply_and_save_color(self, color_hex: str):
        self._app_settings.add_recent_color(color_hex)
        self.set_color(color_hex)
        self.refresh_history()
        self.colorChanged.emit(color_hex)

    def refresh_history(self):
        """履歴フレーム内の正方形ピクスマップを再描画する"""
        # 既存の履歴ウィジェットをクリア
        while self.history_colors_layout.count():
            item = self.history_colors_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        recent_colors = self._app_settings.load_recent_colors()
        for c_hex in recent_colors:
            label = ClickableColorLabel()
            label.setFixedSize(20, 20)
            label.setStyleSheet("border: 1px solid #cccccc;")
            label.setPixmap(create_color_square_pixmap(c_hex, size=20))
            label.setToolTip(c_hex)
            # クリックイベントのコールバック
            label.clicked.connect(lambda hex_val=c_hex: self._on_history_color_clicked(hex_val))
            self.history_colors_layout.addWidget(label)


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


# アコーディオンウィジェット
class AccordionWidget(QWidget):
    toggled = Signal(bool)

    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self._is_expanded = False

        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        # アイコンを読み込み、上下反転したアイコンを生成
        self.accordion_pixmap = QPixmap(":/assets/accordion.png")
        self.accordion_icon = QIcon(self.accordion_pixmap) # オリジナルのアイコン
        transform = QTransform().scale(1, -1)
        flipped_accordion_pixmap = self.accordion_pixmap.transformed(transform)
        self.flipped_accordion_icon = QIcon(flipped_accordion_pixmap) # 上下反転したアイコン

        # 見出しボタン (角丸なし、背景色は薄い灰色)
        self.header_button = QPushButton(title)
        self.header_button.setIcon(self.accordion_icon)
        self.header_button.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.header_button.setStyleSheet("""
            QPushButton {
                border: 1px solid #cccccc;
                border-radius: 0px;
                background-color: #eeeeee;
                text-align: left;
                padding: 6px 10px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #dddddd;
            }
        """)
        self.header_button.setCursor(Qt.PointingHandCursor)
        self.header_button.clicked.connect(self.toggle)
        self._main_layout.addWidget(self.header_button)

        # コンテンツウィジェット (初期状態は非表示)
        self.content_widget = QWidget()
        self.content_widget.setVisible(False)
        self._main_layout.addWidget(self.content_widget)

    def set_title(self, title: str):
        self.header_button.setText(title)

    def title(self) -> str:
        return self.header_button.text()

    def set_content_widget(self, widget: QWidget):
        self._main_layout.removeWidget(self.content_widget)
        self.content_widget.deleteLater()
        self.content_widget = widget
        self.content_widget.setVisible(self._is_expanded)
        self._main_layout.addWidget(self.content_widget)

    def set_content_layout(self, layout):
        self.content_widget.setLayout(layout)

    def toggle(self):
        self.set_expanded(not self._is_expanded)

    def set_expanded(self, expanded: bool):
        self._is_expanded = expanded
        self.content_widget.setVisible(self._is_expanded)
        self.toggled.emit(self._is_expanded)
        
        if expanded:
            self.header_button.setIcon(self.flipped_accordion_icon)
        else:
            self.header_button.setIcon(self.accordion_icon)

    def is_expanded(self) -> bool:
        return self._is_expanded