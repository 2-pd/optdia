from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QPainter, QPixmap, QTextDocument, QAbstractTextDocumentLayout
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QStyle

# リストボックス内の HTML (Rich Text) をレンダリングするためのデリゲート
class HtmlDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options, index)

        painter.save()
        doc = QTextDocument()
        doc.setDefaultFont(options.font)
        doc.setHtml(options.text)
        
        # 背景（選択状態など）の描画
        options.text = ""
        style = options.widget.style()
        style.drawControl(QStyle.CE_ItemViewItem, options, painter)
        
        # テキストの描画位置調整（垂直中央揃え）
        text_rect = style.subElementRect(QStyle.SE_ItemViewItemText, options, options.widget)
        painter.translate(text_rect.left(), text_rect.top() + (text_rect.height() - doc.size().height()) / 2)
        doc.documentLayout().draw(painter, QAbstractTextDocumentLayout.PaintContext())
        painter.restore()

    def sizeHint(self, option, index):
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options, index)
        doc = QTextDocument()
        doc.setDefaultFont(options.font)
        doc.setHtml(options.text)
        return QSize(doc.idealWidth(), doc.size().height() + 4)  # 少し余白を追加


# 指定した色で塗りつぶされた正方形のピクスマップを作成するヘルパー関数
def create_color_square_pixmap(color_hex: str, size: int = 20):
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(color_hex))
    return pixmap