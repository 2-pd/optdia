from PySide6.QtWidgets import QDialog, QVBoxLayout
from PySide6.QtCore import Qt
from core.project import OptDiaProject


class TrainDetailPreviewDialog(QDialog):
    """列車詳細プレビューダイアログ"""
    def __init__(self, parent, project: OptDiaProject, route_id: str, direction: str, train_id: str):
        super().__init__(parent)
        self.project = project
        self.route_id = route_id
        self.direction = direction
        self.train_id = train_id

        # 列車番号の取得
        route = self.project.routes.get(route_id, {})
        train_key = "inbound_trains" if direction == "inbound" else "outbound_trains"
        m_train = route.get(train_key, {}).get(train_id, {})
        train_number = m_train.get("train_number", "")

        self.setWindowTitle(f"列車 {train_number} の詳細")
        self.setFixedSize(480, 680)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        # 表示内容はまだ実装しない
