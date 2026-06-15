from PySide6.QtCore import QSettings
from version import APP_NAME, ORGANIZATION_NAME

class AppSettings:
    """
    アプリケーションの設定を管理するクラス。
    """
    MAX_RECENT_FILES = 10 # 最大で10個の最近開いたファイルを保持

    def __init__(self):
        # 組織名とアプリケーション名を使用してQSettingsを初期化
        self.settings = QSettings(ORGANIZATION_NAME, APP_NAME)

    def save_window_settings(self, window):
        """メインウィンドウのサイズ、位置、最大化状態などを保存する"""
        self.settings.setValue("main_window/geometry", window.saveGeometry())
        self.settings.setValue("main_window/windowState", window.saveState())

    def load_window_settings(self, window):
        """メインウィンドウの状態を復元する"""
        geometry = self.settings.value("main_window/geometry")
        if geometry:
            window.restoreGeometry(geometry)
        
        state = self.settings.value("main_window/windowState")
        if state:
            window.restoreState(state)

    def add_recent_file(self, filepath: str):
        """最近開いたファイルリストにファイルパスを追加する"""
        recent_files = self.load_recent_files()
        if filepath in recent_files:
            recent_files.remove(filepath) # 既存の場合は一度削除して先頭に移動
        recent_files.insert(0, filepath)
        # 最大数を超えたら古いものを削除
        while len(recent_files) > self.MAX_RECENT_FILES:
            recent_files.pop()
        self.settings.setValue("recent_files/list", recent_files)

    def load_recent_files(self) -> list[str]:
        """最近開いたファイルリストを読み込む"""
        files = self.settings.value("recent_files/list", [])
        # QSettings(INI形式)は要素が1つの場合にリストではなく文字列を返すことがあるため補正
        if isinstance(files, str):
            return [files]
        return files if files is not None else []