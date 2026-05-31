#!/usr/bin/env python3
# coding: utf-8

import sys
import subprocess
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton
from project import OptDiaProject, load_project

APP_NAME = "OptDia"
__version__ = "26.06-1"


# メインウィンドウ
class MainWindow(QMainWindow):
    def __init__(self, project: OptDiaProject):
        super().__init__()
        self.project = project

        # 初期タイトルと初期サイズ
        self.setWindowTitle(f"{APP_NAME} v{__version__}")
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

    def _init_menu_bar(self):
        """メニューバーを初期化し、基本項目を追加する"""
        menu_bar = self.menuBar()

        # ファイル(F)
        file_menu = menu_bar.addMenu("ファイル(&F)")
        new_project_action = file_menu.addAction("新規プロジェクト(&N)")
        new_project_action.triggered.connect(self._on_new_project)
        file_menu.addAction("プロジェクトを開く(&O)")
        file_menu.addSeparator()
        file_menu.addAction("上書き保存(&S)")
        file_menu.addAction("名前を付けて保存(&A)")
        file_menu.addSeparator()
        file_menu.addAction("終了(&Q)")

        # 編集(E)、ヘルプ(H) を追加
        menu_bar.addMenu("編集(&E)")
        menu_bar.addMenu("ヘルプ(&H)")

    def _on_new_project(self):
        """新規プロジェクトとして、新しくアプリを起動する"""
        # 現在実行中の Python インタープリタとスクリプトパスを使用して、引数なしで新しいプロセスを開始
        subprocess.Popen([sys.executable, sys.argv[0]])


# アプリ起動処理
def main():
    app = QApplication(sys.argv)

    # コマンドライン引数でファイルパスが指定されている場合はロード、
    # そうでない場合は新規プロジェクトを生成
    if len(sys.argv) > 1:
        project = load_project(sys.argv[1])
    else:
        project = OptDiaProject()

    window = MainWindow(project)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
