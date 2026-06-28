from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QLabel, QListWidget, QStackedWidget, QTabWidget, QWidget
)
from project import OptDiaProject

class VehicleOperationEditorDialog(QDialog):
    def __init__(self, parent, project: OptDiaProject):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("車両運用情報")
        self.resize(960, 640)

        # 水平レイアウト
        main_layout = QHBoxLayout(self)

        # 左側の垂直レイアウト (幅240px固定)
        left_panel = QWidget()
        left_panel.setFixedWidth(240)
        left_panel.setStyleSheet("background-color: #f7f7f7;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(5)
        
        group_label = QLabel("<b>運用グループ</b>")
        left_layout.addWidget(group_label)
        
        self.group_list = QListWidget()
        left_layout.addWidget(self.group_list)
        
        # Populate list widget with operation group names
        for og_id in self.project.operation_groups_order:
            og = self.project.operation_groups[og_id]
            self.group_list.addItem(og.get("operation_group_name", ""))
            
        main_layout.addWidget(left_panel, stretch=1)

        # 右側: スタックドウィジェット
        self.stacked_widget = QStackedWidget()
        
        # 1. 運用グループが登録されているときに表示するタブウィジェット
        self.tab_widget = QTabWidget()
        self.tab_operation = QWidget()
        self.tab_group = QWidget()
        self.tab_widget.addTab(self.tab_operation, "運用情報")
        self.tab_widget.addTab(self.tab_group, "運用グループ情報")
        self.stacked_widget.addWidget(self.tab_widget)

        # 2. 運用グループが登録されていないときに表示するラベル
        self.placeholder_page = QWidget()
        placeholder_layout = QVBoxLayout(self.placeholder_page)
        placeholder_label = QLabel("運用グループを追加してください")
        placeholder_label.setAlignment(Qt.AlignCenter)
        placeholder_label.setStyleSheet("color: #888888; font-size: 18px;")
        placeholder_layout.addWidget(placeholder_label)
        self.stacked_widget.addWidget(self.placeholder_page)

        main_layout.addWidget(self.stacked_widget, stretch=3)

        # 表示の切り替え
        if len(self.project.operation_groups_order) > 0:
            self.stacked_widget.setCurrentIndex(0)
            self.group_list.setCurrentRow(0)
        else:
            self.stacked_widget.setCurrentIndex(1)