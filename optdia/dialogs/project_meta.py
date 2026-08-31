from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QTextEdit, QDialogButtonBox
from core.project import OptDiaProject

# プロジェクトのメタデータを編集するダイアログ
class ProjectPropertiesDialog(QDialog):
    def __init__(self, parent, project: OptDiaProject):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("プロジェクトのプロパティ")
        self.resize(480, 480)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("路線系統名:"))
        self.name_edit = QLineEdit(self.project.metadata.get("railroad_name", ""))
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel("説明:"))
        self.description_edit = QTextEdit(self.project.metadata.get("description", ""))
        layout.addWidget(self.description_edit)

        layout.addWidget(QLabel("ライセンス:"))
        self.license_edit = QTextEdit(self.project.metadata.get("license_text", ""))
        layout.addWidget(self.license_edit)

        # OK / Cancel ボタン
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        """メタデータを更新してダイアログを閉じる"""
        self.project.metadata["railroad_name"] = self.name_edit.text()
        self.project.metadata["description"] = self.description_edit.toPlainText()
        self.project.metadata["license_text"] = self.license_edit.toPlainText()
        super().accept()