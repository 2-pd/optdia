#!/usr/bin/env python3
# coding: utf-8

import sys
from PySide6.QtWidgets import QApplication, QMainWindow


APP_NAME = "ODia3"
__version__ = "26.06-1"


# メインウィンドウ
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # 初期タイトルと初期サイズ
        self.setWindowTitle(f"{APP_NAME} v{__version__}")
        self.resize(960, 640)


# アプリ起動処理
def main():
    app = QApplication(sys.argv)

    window = MainWindow()

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
