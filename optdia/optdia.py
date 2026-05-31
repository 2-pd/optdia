#!/usr/bin/env python3
# coding: utf-8

import sys
import os
import subprocess
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QMessageBox
from project import OptDiaProject, load_project

APP_NAME = "OptDia"
__version__ = "26.06-1"


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
        file_menu.addAction("プロジェクトを開く(&O)")
        file_menu.addSeparator()
        save_action = file_menu.addAction("上書き保存(&S)")
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._on_save_project)
        save_as_action = file_menu.addAction("名前を付けて保存(&A)")
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self._on_save_as_project)
        file_menu.addSeparator()
        exit_action = file_menu.addAction("終了(&Q)")
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)

        # 編集(E)、ヘルプ(H) を追加
        menu_bar.addMenu("編集(&E)")
        menu_bar.addMenu("ヘルプ(&H)")

    def _on_new_project(self):
        """新規プロジェクトとして、新しくアプリを起動する"""
        # 現在実行中の Python インタープリタとスクリプトパスを使用して、引数なしで新しいプロセスを開始
        subprocess.Popen([sys.executable, sys.argv[0]])

    def _on_save_project(self):
        """現在のファイルパスに上書き保存する。パスがない場合は名前を付けて保存を実行する"""
        if self.filepath:
            self.project.save_project(self.filepath)
            self.set_modified(False)
        else:
            self._on_save_as_project()

    def _on_save_as_project(self):
        """名前を付けて保存ダイアログを表示し、プロジェクトを保存する"""
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "名前を付けて保存",
            "",
            "OptDiaプロジェクトファイル (*.optdia)"
        )
        if filepath:
            # 拡張子が指定されていない場合に補完する
            if not filepath.lower().endswith(".optdia"):
                filepath += ".optdia"
            
            self.project.save_project(filepath)
            self.filepath = filepath
            self.set_modified(False)


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
