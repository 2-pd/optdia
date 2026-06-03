#!/usr/bin/env python3
# coding: utf-8

import sys
import os
import subprocess
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QMessageBox, QDialog, QLabel,
    QLineEdit, QTextEdit, QDialogButtonBox
)
from project import OptDiaProject, load_project

# アプリケーション名とバージョン番号
APP_NAME = "OptDia"
__version__ = "26.06-1"


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


# アプリケーション情報ダイアログ
class AboutDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} について")
        self.setFixedSize(480, 320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 20)

        # アプリケーション名
        name_label = QLabel(APP_NAME)
        name_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        name_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(name_label)

        # バージョン番号
        version_label = QLabel(f"Version {__version__}")
        version_label.setStyleSheet("font-size: 16px; color: #555555;")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)

        # 将来的な拡張用のスペース
        layout.addStretch()

        # ボタンエリア (情報のコピー / OK)
        button_layout = QHBoxLayout()
        copy_btn = QPushButton("コピー(&C)")
        copy_btn.clicked.connect(self._copy_to_clipboard)
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)

        button_layout.addStretch()
        button_layout.addWidget(copy_btn)
        button_layout.addWidget(ok_btn)
        layout.addLayout(button_layout)

    def _copy_to_clipboard(self):
        """アプリ名とバージョン番号をクリップボードにコピーする"""
        clipboard = QApplication.clipboard()
        clipboard.setText(f"{APP_NAME} v{__version__}")


# メインウィンドウ
class MainWindow(QMainWindow):
    def __init__(self, project: OptDiaProject, filepath: str = None):
        super().__init__()
        self.project = project
        self.filepath = filepath
        self.is_modified = False

        # 初期タイトルと初期サイズ
        self._update_window_title()
        self.resize(960, 640)

        # メニューバーの設定
        self._init_menu_bar()

        # セントラルウィジェットの設定
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # メインとなる水平レイアウト
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 左側のサイドバーウィジェット (幅240px固定)
        sidebar = QWidget()
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet("background-color: #f7f7f7; border-right: 1px solid #dddddd;")
        
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # ボタンの共通スタイル定義
        button_style = """
            QPushButton {
                border: none;
                text-align: left;
                text-decoration: underline;
                padding-left: 15px;
                font-size: 14px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: #eeeeee;
            }
        """

        # 1つ目のボタン: 路線・駅情報
        self.btn_lines = QPushButton("路線・駅情報")
        self.btn_lines.setFixedHeight(50)
        self.btn_lines.setStyleSheet(button_style)
        sidebar_layout.addWidget(self.btn_lines)

        # 2つ目のボタン: 種別情報
        self.btn_types = QPushButton("種別情報")
        self.btn_types.setFixedHeight(50)
        self.btn_types.setStyleSheet(button_style)
        sidebar_layout.addWidget(self.btn_types)

        # 下部に伸縮スペースを入れてボタンを上部に寄せる
        sidebar_layout.addStretch()

        # レイアウトにサイドバーを追加
        main_layout.addWidget(sidebar)
        
        # 右側のコンテンツ表示エリア (将来の拡張用)
        self.content_container = QWidget()
        main_layout.addWidget(self.content_container, stretch=1)

    def closeEvent(self, event):
        """閉じるイベントを捕捉し、未保存の変更がある場合に確認する"""
        if not self.is_modified:
            event.accept()
            return

        reply = QMessageBox.question(
            self,
            "プロジェクトを保存しますか？",
            f"{APP_NAME}を閉じる前に現在のプロジェクトへの変更を保存しますか？",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save
        )

        if reply == QMessageBox.StandardButton.Save:
            self._on_save_project()
            if not self.is_modified:  # 保存が完了（フラグがクリア）したなら閉じる
                event.accept()
            else:  # 保存ダイアログでキャンセルされた場合は閉じない
                event.ignore()
        elif reply == QMessageBox.StandardButton.Discard:
            event.accept()
        else:
            event.ignore()

    def set_modified(self, modified: bool):
        """変更フラグを更新し、タイトルバーに反映させる"""
        if self.is_modified != modified:
            self.is_modified = modified
            self._update_window_title()

    def _update_window_title(self):
        """ファイル名を含めてウィンドウタイトルを更新する"""
        base_app_title = f"{APP_NAME} v{__version__}"
        
        # railroad_name が設定されていればそれを優先
        if self.project.metadata.get("railroad_name"):
            project_display_name = self.project.metadata["railroad_name"]
        else:
            project_display_name = os.path.basename(self.filepath) if self.filepath else "路線系統名未設定"
        
        status_mark = "*" if self.is_modified else ""
        self.setWindowTitle(f"{project_display_name}{status_mark} - {base_app_title}")

    def _init_menu_bar(self):
        """メニューバーを初期化し、基本項目を追加する"""
        menu_bar = self.menuBar()

        # ファイル(F)
        file_menu = menu_bar.addMenu("ファイル(&F)")
        new_project_action = file_menu.addAction("新規プロジェクト(&N)")
        new_project_action.setShortcut("Ctrl+N")
        new_project_action.triggered.connect(self._on_new_project)
        open_project_action = file_menu.addAction("プロジェクトを開く(&O)")
        open_project_action.setShortcut("Ctrl+O")
        open_project_action.triggered.connect(self._on_open_project)
        file_menu.addSeparator()
        save_action = file_menu.addAction("上書き保存(&S)")
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._on_save_project)
        save_as_action = file_menu.addAction("名前を付けて保存(&A)")
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self._on_save_as_project)
        file_menu.addSeparator()
        properties_action = file_menu.addAction("プロジェクトのプロパティ")
        file_menu.addSeparator()
        properties_action.triggered.connect(self._on_project_properties)
        exit_action = file_menu.addAction("終了(&Q)")
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)

        # 編集(E)
        menu_bar.addMenu("編集(&E)")

        # ヘルプ(H)
        help_menu = menu_bar.addMenu("ヘルプ(&H)")
        about_action = help_menu.addAction(f"{APP_NAME}について(&A)")
        about_action.triggered.connect(self._on_about)

    def _on_new_project(self):
        """新規プロジェクトとして、新しくアプリを起動する"""
        # 現在実行中の Python インタープリタとスクリプトパスを使用して、引数なしで新しいプロセスを開始
        subprocess.Popen([sys.executable, sys.argv[0]])

    def _on_open_project(self):
        """プロジェクトを開くダイアログを表示し、条件に応じて現在のプロセスまたは別プロセスで開く"""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "プロジェクトを開く",
            "",
            "OptDiaプロジェクトファイル (*.optdia *.optd)"
        )
        if not filepath:
            return

        # 現在のプロジェクトが「編集されていない新規状態」であれば、現在のプロセスでロードする
        if self.filepath is None and not self.is_modified:
            self.project = load_project(filepath)
            self.filepath = filepath
            self.set_modified(False)
            self._update_window_title()
        else:
            # それ以外（既にファイルを開いているか、変更がある場合）は別プロセスで開く
            subprocess.Popen([sys.executable, sys.argv[0], filepath])

    def _on_save_project(self):
        """現在のファイルパスに上書き保存する。パスがない場合は名前を付けて保存を実行する"""
        if self.filepath:
            self.project.save_project(self.filepath)
            self.set_modified(False)
        else:
            self._on_save_as_project()

    def _on_save_as_project(self):
        """名前を付けて保存ダイアログを表示し、プロジェクトを保存する"""
        filepath, selected_filter = QFileDialog.getSaveFileName(
            self,
            "名前を付けて保存",
            "",
            "OptDiaプロジェクトファイル (*.optd);;非圧縮OptDiaプロジェクトファイル (*.optdia)"
        )
        if filepath:
            # 拡張子が指定されていない場合に補完する
            if not (filepath.lower().endswith(".optdia") or filepath.lower().endswith(".optd")):
                if ".optd" in selected_filter:
                    filepath += ".optd"
                else:
                    filepath += ".optdia"
            
            self.project.save_project(filepath)
            self.filepath = filepath
            self.set_modified(False)

    def _on_project_properties(self):
        """プロジェクトのプロパティダイアログを表示する"""
        dialog = ProjectPropertiesDialog(self, self.project)
        if dialog.exec() == QDialog.Accepted:
            self.set_modified(True)

    def _on_about(self):
        """バージョン情報を表示する"""
        dialog = AboutDialog(self)
        dialog.exec()


# アプリ起動処理
def main():
    app = QApplication(sys.argv)

    # コマンドライン引数でファイルパスが指定されている場合はロード、
    # そうでない場合は新規プロジェクトを生成
    filepath = sys.argv[1] if len(sys.argv) > 1 else None
    if filepath:
        project = load_project(filepath)
    else:
        project = OptDiaProject()

    window = MainWindow(project, filepath)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
