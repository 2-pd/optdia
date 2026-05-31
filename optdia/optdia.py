#!/usr/bin/env python3
# coding: utf-8

import sys
from PySide6.QtWidgets import QApplication, QMainWindow
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
