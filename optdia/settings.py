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

    def save_auto_fill_enabled(self, enabled: bool):
        """同じ種別の列車から時刻を補完する設定を保存する"""
        self.settings.setValue("edit/auto_fill", enabled)

    def load_auto_fill_enabled(self) -> bool:
        """同じ種別の列車から時刻を補完する設定を読み込む"""
        val = self.settings.value("edit/auto_fill", False)
        if isinstance(val, str):
            return val.lower() in ("true", "1")
        return bool(val)

    def save_adjust_later_enabled(self, enabled: bool):
        """発着時刻の変更時に後の駅の発着時刻も増減する設定を保存する"""
        self.settings.setValue("edit/adjust_later", enabled)

    def load_adjust_later_enabled(self) -> bool:
        """発着時刻の変更時に後の駅の発着時刻も増減する設定を読み込む"""
        val = self.settings.value("edit/adjust_later", False)
        if isinstance(val, str):
            return val.lower() in ("true", "1")
        return bool(val)

    MAX_RECENT_COLORS = 10 # 最大で10個の色選択履歴を保持

    def add_recent_color(self, color_hex: str):
        """色選択履歴に色コードを追加する"""
        recent_colors = self.load_recent_colors()
        if color_hex in recent_colors:
            recent_colors.remove(color_hex)
        recent_colors.insert(0, color_hex)
        while len(recent_colors) > self.MAX_RECENT_COLORS:
            recent_colors.pop()
        self.settings.setValue("color_history/list", recent_colors)

    def load_recent_colors(self) -> list[str]:
        """色選択履歴を読み込む"""
        colors = self.settings.value("color_history/list", [])
        if isinstance(colors, str):
            return [colors]
        return list(colors) if colors is not None else []