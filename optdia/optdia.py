#!/usr/bin/env python3
# coding: utf-8

import sys
import os
import subprocess
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QMessageBox, QDialog, QLabel,
    QListWidget, QListWidgetItem, QStackedWidget,
    QTabBar, QHeaderView, QMenu
)
import assets_rc
from version import APP_NAME, __version__
from project import OptDiaProject, load_project
from settings import AppSettings
from common.gui_utils import HtmlDelegate, create_color_square_pixmap
from common.widgets import LineSampleWidget
from dialogs.route import AddRouteDialog, SelectSegmentDialog, SplitSegmentDialog, RouteEditorDialog
from dialogs.diagram import AddDiagramDialog, DiagramEditorDialog
from dialogs.line_station import LineStationEditorDialog
from dialogs.train_type import AddTrainTypeDialog, TrainTypeEditorDialog
from dialogs.project_meta import ProjectPropertiesDialog
from dialogs.about import AboutDialog
from timetable.model import TimetableModel
from timetable.view import TimetableView, TimetableVerticalHeader
from timetable.delegate import TimetableDelegate

# メインウィンドウ
class MainWindow(QMainWindow):
    def __init__(self, project: OptDiaProject, filepath: str = None):
        super().__init__()
        self.project = project
        self.filepath = filepath
        self.is_modified = False

        # 設定管理クラスの初期化
        self.app_settings = AppSettings()

        # 初期タイトルと初期サイズ
        self._update_window_title()
        self.resize(960, 640)
        self.app_settings.load_window_settings(self)

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
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet("#sidebar { background-color: #f7f7f7; border-right: 1px solid #dddddd; }")
        
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
        self.btn_lines.clicked.connect(self._on_edit_lines_stations)
        self.btn_lines.setStyleSheet(button_style)
        sidebar_layout.addWidget(self.btn_lines)

        # 2つ目のボタン: 種別情報
        self.btn_types = QPushButton("種別情報")
        self.btn_types.setFixedHeight(50)
        self.btn_types.clicked.connect(self._on_edit_train_types)
        self.btn_types.setStyleSheet(button_style)
        sidebar_layout.addWidget(self.btn_types)

        # 運行系統セクション
        route_section = QWidget()
        route_layout = QVBoxLayout(route_section)
        route_layout.setContentsMargins(10, 0, 10, 5)
        route_layout.addSpacing(10)

        route_header_layout = QHBoxLayout()
        lbl_route = QLabel("運行系統")
        lbl_route.setStyleSheet("font-size: 14px; border: none;")
        route_header_layout.addWidget(lbl_route)
        self.btn_edit_routes = QPushButton("編集")
        self.btn_edit_routes.setFixedWidth(60)
        self.btn_edit_routes.setStyleSheet("QPushButton { border: none; text-decoration: underline; background-color: transparent; }")
        self.btn_edit_routes.clicked.connect(self._on_edit_routes)
        route_header_layout.addWidget(self.btn_edit_routes)
        route_layout.addLayout(route_header_layout)

        self.route_list_widget = QListWidget()
        self.route_list_widget.setStyleSheet("font-size: 14px;")
        self.route_list_widget.setDragDropMode(QListWidget.InternalMove)
        self.route_list_widget.model().rowsMoved.connect(self._on_routes_reordered)
        self.route_list_widget.itemSelectionChanged.connect(self._on_timetable_settings_changed)
        route_layout.addWidget(self.route_list_widget)

        # サイドバーの残りスペースを2等分するため、stretch=1 を指定
        sidebar_layout.addWidget(route_section, 1)

        # ダイヤセクション
        diagram_section = QWidget()
        diagram_layout = QVBoxLayout(diagram_section)
        diagram_layout.setContentsMargins(10, 0, 10, 10)
        diagram_layout.addSpacing(10)

        diagram_header_layout = QHBoxLayout()
        lbl_diagram = QLabel("ダイヤ")
        lbl_diagram.setStyleSheet("font-size: 14px; border: none;")
        diagram_header_layout.addWidget(lbl_diagram)
        self.btn_edit_diagrams = QPushButton("編集")
        self.btn_edit_diagrams.setFixedWidth(60)
        self.btn_edit_diagrams.setStyleSheet("QPushButton { border: none; text-decoration: underline; background-color: transparent; }")
        self.btn_edit_diagrams.clicked.connect(self._on_edit_diagrams)
        diagram_header_layout.addWidget(self.btn_edit_diagrams)
        diagram_layout.addLayout(diagram_header_layout)

        self.diagram_list_widget = QListWidget()
        self.diagram_list_widget.setDragDropMode(QListWidget.InternalMove)
        self.diagram_list_widget.model().rowsMoved.connect(self._on_diagrams_reordered)
        self.diagram_list_widget.itemSelectionChanged.connect(self._on_diagram_selected_in_main_window)
        self.diagram_list_widget.setStyleSheet("font-size: 14px;")
        diagram_layout.addWidget(self.diagram_list_widget)

        # サイドバーの残りスペースを2等分するため、stretch=1 を指定
        sidebar_layout.addWidget(diagram_section, 1)

        # レイアウトにサイドバーを追加
        main_layout.addWidget(sidebar)
        
        # 右側のコンテンツ表示エリア (スタックドウィジェット)
        self.right_stack = QStackedWidget()

        # --- コンテンツありのページ ---
        self.timetable_page = QWidget()
        self.timetable_layout = QVBoxLayout(self.timetable_page)
        self.timetable_layout.setContentsMargins(0, 0, 0, 0)
        self.timetable_layout.setSpacing(0)

        # 方面選択用タブバー
        self.direction_tab_bar = QTabBar()
        self.direction_tab_bar.addTab("下り時刻表")
        self.direction_tab_bar.addTab("上り時刻表")
        self.direction_tab_bar.currentChanged.connect(self._on_timetable_settings_changed)
        self.timetable_layout.addWidget(self.direction_tab_bar)

        # 時刻表テーブル
        self.timetable_model = TimetableModel(self.project)
        self.timetable_model.dataChanged.connect(lambda: self.set_modified(True))
        self.timetable_view = TimetableView()
        self.timetable_view.setModel(self.timetable_model)
        
        # テーブルの外観設定
        self.timetable_view.setStyleSheet("QTableView, QHeaderView { font-size: 12px; }")
        self.timetable_view.setShowGrid(False)
        h_header = self.timetable_view.horizontalHeader()
        h_header.setVisible(False)
        h_header.setDefaultSectionSize(60)
        h_header.setSectionResizeMode(QHeaderView.Fixed)
        
        v_header = TimetableVerticalHeader(self.timetable_view)
        # padding: top right bottom left (左8px = 縦線6px + 余白2px、右4px)
        v_header.setStyleSheet("QHeaderView::section { padding: 0px 4px 0px 8px; margin: 0px; }")
        v_header.setDefaultAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.timetable_view.setVerticalHeader(v_header)
        v_header.setSectionResizeMode(QHeaderView.ResizeToContents)
        
        # ボタン用デリゲートの適用
        self.timetable_delegate = TimetableDelegate(self.timetable_view)
        self.timetable_view.setItemDelegate(self.timetable_delegate)

        self.timetable_layout.addWidget(self.timetable_view)
        
        self.right_stack.addWidget(self.timetable_page)

        # --- コンテンツなしのプレースホルダーページ ---
        self.placeholder_page = QWidget()
        placeholder_layout = QVBoxLayout(self.placeholder_page)
        placeholder_label = QLabel("時刻表を編集するには、路線情報・運行系統・ダイヤの設定を完了してください")
        placeholder_label.setAlignment(Qt.AlignCenter)
        placeholder_label.setStyleSheet("color: #888888; font-size: 18px;")
        placeholder_layout.addWidget(placeholder_label)
        
        self.right_stack.addWidget(self.placeholder_page)

        main_layout.addWidget(self.right_stack, stretch=1)

        # 初期リストの構築
        self._populate_route_list()
        self._populate_diagram_list()

        # 初期選択の設定
        if self.route_list_widget.count() > 0:
            self.route_list_widget.setCurrentRow(0)
        if self.diagram_list_widget.count() > 0:
            self.diagram_list_widget.setCurrentRow(0)
            
        self._on_timetable_settings_changed()

    def _populate_route_list(self):
        """プロジェクトに登録されている運行系統をサイドバーのリストに表示する"""
        self.route_list_widget.clear()
        for rid in self.project.routes_order:
            route = self.project.routes[rid]
            item = QListWidgetItem(route.get("route_name", rid))
            item.setData(Qt.UserRole, rid)
            self.route_list_widget.addItem(item)

    def _populate_diagram_list(self):
        """プロジェクトに登録されている運転ダイヤをサイドバーのリストに表示する"""
        self.diagram_list_widget.clear()
        for did in self.project.diagrams_order:
            diag = self.project.diagrams[did]
            item = QListWidgetItem(diag.get("diagram_name", did))
            item.setData(Qt.UserRole, did)
            self.diagram_list_widget.addItem(item)

    def closeEvent(self, event):
        """閉じるイベントを捕捉し、未保存の変更がある場合に確認する"""
        if not self.is_modified:
            self.app_settings.save_window_settings(self)
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
                self.app_settings.save_window_settings(self)
                event.accept()
            else:  # 保存ダイアログでキャンセルされた場合は閉じない
                event.ignore()
        elif reply == QMessageBox.StandardButton.Discard:
            self.app_settings.save_window_settings(self)
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
        self.recent_files_menu = file_menu.addMenu("最近開いたプロジェクト(&R)")
        self._update_recent_files_menu() # メニューを初期化
        file_menu.addSeparator()
        exit_action = file_menu.addAction("終了(&Q)")
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)

        # 編集(E)
        menu_bar.addMenu("編集(&E)")

        # ヘルプ(H)
        help_menu = menu_bar.addMenu("ヘルプ(&H)")
        about_action = help_menu.addAction(f"{APP_NAME}について(&A)")
        about_action.triggered.connect(self._on_about)

    def _update_recent_files_menu(self):
        """最近開いたプロジェクトメニューを更新する"""
        self.recent_files_menu.clear()
        recent_files = self.app_settings.load_recent_files()

        if not recent_files:
            no_recent_action = self.recent_files_menu.addAction("最近開いたプロジェクトはありません")
            no_recent_action.setEnabled(False)
            return

        for i, filepath in enumerate(recent_files):
            # ファイル名のみを表示し、ツールチップにフルパスを表示
            filename = os.path.basename(filepath)
            action = self.recent_files_menu.addAction(f"&{i+1} {filename}")
            action.setToolTip(filepath)
            action.setData(filepath) # アクションにファイルパスを紐付け
            action.triggered.connect(self._open_recent_file)

    def _open_recent_file(self):
        """最近開いたプロジェクトメニューから選択されたファイルを開く"""
        action = self.sender() # シグナルを送信したアクションを取得
        if action:
            filepath = action.data()
            # 現在のプロジェクトが変更されている場合は別プロセスで開く
            if self.is_modified:
                subprocess.Popen([sys.executable, sys.argv[0], filepath])
            else:
                self._load_project_in_current_window(filepath)

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
            self._load_project_in_current_window(filepath)
        else:
            # それ以外（既にファイルを開いているか、変更がある場合）は別プロセスで開く
            subprocess.Popen([sys.executable, sys.argv[0], filepath])

    def _on_save_project(self):
        """現在のファイルパスに上書き保存する。パスがない場合は名前を付けて保存を実行する"""
        if self.filepath:
            # save_projectが成功した場合のみrecent_filesに追加
            if self._save_project_to_path(self.filepath):
                self.app_settings.add_recent_file(self.filepath)
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
            
            if self._save_project_to_path(filepath):
                self.filepath = filepath
                self.set_modified(False)
                self._update_window_title()
                self.app_settings.add_recent_file(filepath)
                self._update_recent_files_menu()

    def _save_project_to_path(self, filepath: str) -> bool:
        """指定されたパスにプロジェクトを保存する。成功したらTrueを返す。"""
        try:
            self.project.save_project(filepath)
            return True
        except Exception as e:
            QMessageBox.critical(self, "保存エラー", f"プロジェクトの保存中にエラーが発生しました:\n{e}")
            return False

    def _load_project_in_current_window(self, filepath: str):
        """現在のウィンドウでプロジェクトをロードする"""
        try:
            self.project = load_project(filepath)
            self.timetable_model.project = self.project
            self.filepath = filepath
            self.set_modified(False)
            self._update_window_title()
            self._populate_route_list()
            self._populate_diagram_list()
            
            # 初期選択の設定
            if self.route_list_widget.count() > 0:
                self.route_list_widget.setCurrentRow(0)
            if self.diagram_list_widget.count() > 0:
                self.diagram_list_widget.setCurrentRow(0)
            self._on_timetable_settings_changed()
            self.app_settings.add_recent_file(filepath) # 成功したら最近開いたファイルに追加
            self._update_recent_files_menu()
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"プロジェクトファイルの読み込み中にエラーが発生しました:\n{e}\nファイルが破損している可能性があります。")

    def _on_project_properties(self):
        """プロジェクトのプロパティダイアログを表示する"""
        dialog = ProjectPropertiesDialog(self, self.project)
        if dialog.exec() == QDialog.Accepted:
            self.set_modified(True)

    def _on_about(self):
        """バージョン情報を表示する"""
        dialog = AboutDialog(self)
        dialog.exec()

    def _on_edit_lines_stations(self):
        """路線・駅情報編集ダイアログを表示する"""
        dialog = LineStationEditorDialog(self, self.project)
        dialog.exec()
        self._on_timetable_settings_changed()

    def _on_edit_train_types(self):
        """種別情報編集ダイアログを表示する"""
        dialog = TrainTypeEditorDialog(self, self.project)
        dialog.exec()

    def _on_edit_routes(self):
        """運行系統編集ウィンドウを表示する"""
        selected_items = self.route_list_widget.selectedItems()
        initial_route_id = selected_items[0].data(Qt.UserRole) if selected_items else None

        dialog = RouteEditorDialog(self, self.project, initial_route_id)
        dialog.exec()
        self._populate_route_list()
        
        # 運行系統が存在し、かつ何も選択されていない場合は最初の運行系統を選択する
        if self.route_list_widget.count() > 0 and not self.route_list_widget.selectedItems():
            self.route_list_widget.setCurrentRow(0)

        self._on_timetable_settings_changed()

    def _on_edit_diagrams(self):
        """運転ダイヤ情報編集ウィンドウを表示する"""
        selected_items = self.diagram_list_widget.selectedItems()
        initial_diagram_id = selected_items[0].data(Qt.UserRole) if selected_items else None

        dialog = DiagramEditorDialog(self, self.project, initial_diagram_id)
        dialog.exec()
        self._populate_diagram_list()
        
        # ダイヤが存在し、かつ何も選択されていない場合は最初のダイヤを選択する
        if self.diagram_list_widget.count() > 0 and not self.diagram_list_widget.selectedItems():
            self.diagram_list_widget.setCurrentRow(0)

        self._on_timetable_settings_changed()

    def _on_diagram_selected_in_main_window(self):
        """メインウィンドウのダイヤリストで選択が変更されたときに表示を更新する"""
        self._on_timetable_settings_changed()

    def _on_timetable_settings_changed(self):
        """サイドバーの選択やタブの切り替え時に、時刻表テーブルの表示内容を更新する"""
        if not self.project.routes or not self.project.diagrams:
            self.right_stack.setCurrentIndex(1)
        else:
            self.right_stack.setCurrentIndex(0)

        route_item = self.route_list_widget.currentItem()
        diagram_item = self.diagram_list_widget.currentItem()
        
        route_id = route_item.data(Qt.UserRole) if route_item else None
        diagram_id = diagram_item.data(Qt.UserRole) if diagram_item else None
        direction = "inbound" if self.direction_tab_bar.currentIndex() == 1 else "outbound"
        
        self.timetable_model.update_data(route_id, diagram_id, direction)

    def _on_diagrams_reordered(self, parent, start, end, destination, row):
        """サイドバーでの運転ダイヤの並び替えをプロジェクトデータに反映する"""
        new_order = []
        for i in range(self.diagram_list_widget.count()):
            item = self.diagram_list_widget.item(i)
            new_order.append(item.data(Qt.UserRole))
        
        self.project.diagrams_order = new_order
        self.set_modified(True)
        self._on_timetable_settings_changed()


    def _on_routes_reordered(self, parent, start, end, destination, row):
        """サイドバーでの運行系統の並び替えをプロジェクトデータに反映する"""
        new_order = []
        for i in range(self.route_list_widget.count()):
            item = self.route_list_widget.item(i)
            new_order.append(item.data(Qt.UserRole))
        
        self.project.routes_order = new_order
        self.set_modified(True)
        self._on_timetable_settings_changed()


# アプリ起動処理
def main():
    app = QApplication(sys.argv)

    # アプリケーションアイコンの設定
    app.setWindowIcon(QIcon(":/assets/app_icon.ico"))

    # コマンドライン引数でファイルパスが指定されている場合はロード、
    # そうでない場合は新規プロジェクトを生成
    filepath = sys.argv[1] if len(sys.argv) > 1 else None
    if filepath:
        try:
            project = load_project(filepath)
        except Exception:
            QMessageBox.critical(None, "エラー", "このファイルは破損しています")
            project = OptDiaProject()
            filepath = None
    else:
        project = OptDiaProject()

    window = MainWindow(project, filepath)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
