#!/usr/bin/env python3
# coding: utf-8

import sys
import os
import random
import string
import re
import subprocess
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QColor, QPainter, QPixmap, QFont, QTextDocument, QAbstractTextDocumentLayout, QPen
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QMessageBox, QDialog, QLabel,
    QLineEdit, QTextEdit, QDialogButtonBox, QListWidget, QTabWidget,
    QListWidgetItem, QCheckBox, QColorDialog, QStackedWidget,
    QRadioButton, QComboBox, QGroupBox, QFormLayout, QSpinBox,
    QStyledItemDelegate, QStyleOptionViewItem, QStyle, QScrollArea,
    QSizePolicy
)
import assets_rc
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


# リストボックス内の HTML (Rich Text) をレンダリングするためのデリゲート
class HtmlDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options, index)

        painter.save()
        doc = QTextDocument()
        doc.setDefaultFont(options.font)
        doc.setHtml(options.text)
        
        # 背景（選択状態など）の描画
        options.text = ""
        style = options.widget.style()
        style.drawControl(QStyle.CE_ItemViewItem, options, painter)
        
        # テキストの描画位置調整（垂直中央揃え）
        text_rect = style.subElementRect(QStyle.SE_ItemViewItemText, options, options.widget)
        painter.translate(text_rect.left(), text_rect.top() + (text_rect.height() - doc.size().height()) / 2)
        doc.documentLayout().draw(painter, QAbstractTextDocumentLayout.PaintContext())
        painter.restore()

    def sizeHint(self, option, index):
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options, index)
        doc = QTextDocument()
        doc.setDefaultFont(options.font)
        doc.setHtml(options.text)
        return QSize(doc.idealWidth(), doc.size().height() + 4)  # 少し余白を追加


# 指定した色で塗りつぶされた正方形のピクスマップを作成するヘルパー関数
def create_color_square_pixmap(color_hex: str, size: int = 20):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setBrush(QColor(color_hex))
    painter.drawRect(0, 0, size - 1, size - 1)
    painter.end()
    return pixmap


# 路線の追加ダイアログ
class AddLineDialog(QDialog):
    def __init__(self, parent, project: OptDiaProject):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("路線の追加")
        self.setFixedSize(480, 240)

        layout = QVBoxLayout(self)

        # 路線ID
        layout.addWidget(QLabel("路線ID:"))
        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("例) osaka_loop_line")
        self.id_edit.textChanged.connect(self._clear_id_error)
        layout.addWidget(self.id_edit)

        # 警告表示スペース
        self.warning_label = QLabel("")
        self.warning_label.setStyleSheet("color: red; padding-left: 5px;")
        layout.addWidget(self.warning_label)

        # 路線名
        layout.addWidget(QLabel("路線名:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例) 大阪環状線")
        layout.addWidget(self.name_edit)

        layout.addStretch()

        # ボタンエリア (追加 / キャンセル)
        button_layout = QHBoxLayout()
        self.add_button = QPushButton("追加")
        self.cancel_button = QPushButton("キャンセル")

        button_layout.addStretch()
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.add_button.clicked.connect(self._on_add_clicked)
        self.cancel_button.clicked.connect(self.reject)

    def _clear_id_error(self):
        """ID入力欄のエラー表示状態をクリアする"""
        self.id_edit.setStyleSheet("")
        self.warning_label.setText("")

    def _on_add_clicked(self):
        """入力内容を検証し、問題なければ accept する"""
        line_id = self.id_edit.text().strip()

        # スタイルをリセット
        self.id_edit.setStyleSheet("")

        if not line_id:
            self.warning_label.setText("IDを指定してください")
            self.id_edit.setStyleSheet("background-color: #ffeeee;")
            return

        if not re.match(r"^[a-zA-Z0-9_]+$", line_id):
            self.warning_label.setText("IDには半角英数字とアンダーバーのみが使用可能です")
            self.id_edit.setStyleSheet("background-color: #ffeeee;")
            return

        if line_id in self.project.lines:
            self.warning_label.setText("既に使用されているIDです")
            self.id_edit.setStyleSheet("background-color: #ffeeee;")
            return

        self.accept()


# 駅の追加ダイアログ
class AddStationDialog(QDialog):
    def __init__(self, parent, project: OptDiaProject, exclude_line_id: str = None):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("駅の追加")
        self.setFixedSize(480, 480)

        layout = QVBoxLayout(self)

        # 選択肢
        self.new_station_radio = QRadioButton("このプロジェクトでは未登録の駅を追加する")
        self.existing_station_radio = QRadioButton("既に別路線に登録済みの駅を追加する")
        self.new_station_radio.setChecked(True)
        layout.addWidget(self.new_station_radio)
        layout.addWidget(self.existing_station_radio)

        # 入力エリアのスタックウィジェット
        self.input_stack = QStackedWidget()
        layout.addWidget(self.input_stack)

        # --- 選択肢1: 新規駅 ---
        new_station_page = QWidget()
        new_layout = QVBoxLayout(new_station_page)
        new_layout.addWidget(QLabel("駅ID:"))
        self.station_id_edit = QLineEdit()
        self.station_id_edit.setPlaceholderText("例) osaka")
        self.station_id_edit.textChanged.connect(self._clear_id_error)
        new_layout.addWidget(self.station_id_edit)

        # 警告表示スペース
        self.warning_label = QLabel("")
        self.warning_label.setStyleSheet("color: red; padding-left: 5px;")
        new_layout.addWidget(self.warning_label)

        new_layout.addWidget(QLabel("駅名:"))
        self.station_name_edit = QLineEdit()
        self.station_name_edit.setPlaceholderText("例) 大阪")
        new_layout.addWidget(self.station_name_edit)

        # 駅名(ひらがな)
        new_layout.addWidget(QLabel("駅名(ひらがな):"))
        self.station_name_kana_edit = QLineEdit()
        self.station_name_kana_edit.setPlaceholderText("例) おおさか")
        new_layout.addWidget(self.station_name_kana_edit)
        new_layout.addStretch()
        self.input_stack.addWidget(new_station_page)

        # --- 選択肢2: 既存駅 ---
        existing_station_page = QWidget()
        existing_layout = QVBoxLayout(existing_station_page)
        existing_layout.addWidget(QLabel("路線の選択:"))
        self.line_combo = QComboBox()
        existing_layout.addWidget(self.line_combo)

        existing_layout.addWidget(QLabel("駅の選択:"))
        self.station_combo = QComboBox()
        existing_layout.addWidget(self.station_combo)
        existing_layout.addStretch()
        self.input_stack.addWidget(existing_station_page)

        # ラジオボタンの切り替えイベント
        self.new_station_radio.toggled.connect(self._on_radio_toggled)
        self.existing_station_radio.toggled.connect(self._on_radio_toggled)

        # 既存駅ページ用のデータ投入
        for line_id in self.project.lines_order:
            if line_id == exclude_line_id:
                continue
            line_name = self.project.lines[line_id].get("line_name", line_id)
            self.line_combo.addItem(line_name, line_id)
        
        # 他の路線が存在しない場合は、既存駅からの追加を選択不可にする
        if self.line_combo.count() == 0:
            self.existing_station_radio.setEnabled(False)

        self.line_combo.currentIndexChanged.connect(self._on_line_combo_changed)
        self._on_line_combo_changed() # 初期化

        layout.addStretch()

        # ボタンエリア
        button_layout = QHBoxLayout()
        self.add_button = QPushButton("追加")
        self.cancel_button = QPushButton("キャンセル")
        button_layout.addStretch()
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.add_button.clicked.connect(self._on_add_clicked)
        self.cancel_button.clicked.connect(self.reject)

    def _clear_id_error(self):
        """ID入力欄のエラー表示状態をクリアする"""
        self.station_id_edit.setStyleSheet("")
        self.warning_label.setText("")

    def _on_radio_toggled(self):
        """ラジオボタンの選択に合わせて表示を切り替える"""
        if self.new_station_radio.isChecked():
            self.input_stack.setCurrentIndex(0)
        else:
            self.input_stack.setCurrentIndex(1)

    def _on_line_combo_changed(self):
        """選択された路線の駅リストをコンボボックスに反映する"""
        self.station_combo.clear()
        line_id = self.line_combo.currentData()
        if not line_id:
            return
        line_data = self.project.lines.get(line_id)
        for station_item in line_data.get("station_list", []):
            sid = station_item.get("station_id")
            s_data = self.project.stations.get(sid)
            name = s_data.get("station_name", sid) if s_data else sid
            self.station_combo.addItem(name, sid)

    def _on_add_clicked(self):
        """入力内容の検証"""
        if self.new_station_radio.isChecked():
            station_id = self.station_id_edit.text().strip()
            station_name = self.station_name_edit.text().strip()

            self._clear_id_error()

            if not station_id:
                self.warning_label.setText("駅IDを入力してください。")
                self.station_id_edit.setStyleSheet("background-color: #ffeeee;")
                return
            if not re.match(r"^[a-zA-Z0-9_]+$", station_id):
                self.warning_label.setText("IDには半角英数字とアンダーバーのみ使用可能です。")
                self.station_id_edit.setStyleSheet("background-color: #ffeeee;")
                return
            if station_id in self.project.stations:
                self.warning_label.setText("この駅IDは既に使用されています。")
                self.station_id_edit.setStyleSheet("background-color: #ffeeee;")
                return
        else:
            if self.station_combo.currentIndex() < 0:
                QMessageBox.warning(self, "エラー", "追加する駅を選択してください。")
                return
            # 既にリストに存在するかのチェックなどは呼び出し側で行う

        self.accept()


# 乗り場の追加ダイアログ
class AddTrackDialog(QDialog):
    def __init__(self, parent, station_data: dict):
        super().__init__(parent)
        self.station_data = station_data
        self.setWindowTitle("乗り場の追加")
        self.setFixedSize(400, 240)
        self._is_track_number_manually_edited = False

        layout = QVBoxLayout(self)

        # 乗り場ID
        layout.addWidget(QLabel("乗り場ID:"))
        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("例) 1")
        self.id_edit.textChanged.connect(self._on_id_changed)
        layout.addWidget(self.id_edit)

        # 警告表示
        self.warning_label = QLabel("")
        self.warning_label.setStyleSheet("color: red; padding-left: 5px;")
        layout.addWidget(self.warning_label)

        # 乗り場番号
        layout.addWidget(QLabel("乗り場番号:"))
        self.number_edit = QLineEdit()
        self.number_edit.setPlaceholderText("例) 1番")
        self.number_edit.textEdited.connect(self._on_number_edited)
        layout.addWidget(self.number_edit)

        layout.addStretch()

        # ボタンエリア
        button_layout = QHBoxLayout()
        self.add_button = QPushButton("追加")
        self.cancel_button = QPushButton("キャンセル")
        button_layout.addStretch()
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.add_button.clicked.connect(self._on_add_clicked)
        self.cancel_button.clicked.connect(self.reject)

    def _on_id_changed(self, text: str):
        """IDが変更されたとき、番号が未編集なら同期させる"""
        self.id_edit.setStyleSheet("")
        self.warning_label.setText("")
        if not self._is_track_number_manually_edited:
            self.number_edit.setText(text)

    def _on_number_edited(self):
        """ユーザーが手動で番号を編集したことを記録する"""
        self._is_track_number_manually_edited = True

    def _on_add_clicked(self):
        """入力内容の検証"""
        track_id = self.id_edit.text().strip()

        if not track_id:
            self.warning_label.setText("乗り場IDを入力してください")
            self.id_edit.setStyleSheet("background-color: #ffeeee;")
            return

        if not re.match(r"^[a-zA-Z0-9_]+$", track_id):
            self.warning_label.setText("IDには半角英数字とアンダーバーのみ使用可能です")
            self.id_edit.setStyleSheet("background-color: #ffeeee;")
            return

        # 重複チェック (stations[station_id]["tracks"] 内でチェック)
        existing_tracks = self.station_data.get("tracks", {})
        if track_id in existing_tracks:
            self.warning_label.setText("乗り場IDが既に現在の駅で使用されています")
            self.id_edit.setStyleSheet("background-color: #ffeeee;")
            return

        self.accept()


# 乗り場の編集ダイアログ
class EditTrackDialog(QDialog):
    def __init__(self, parent, track_id: str, track_number: str):
        super().__init__(parent)
        self.setWindowTitle("乗り場の編集")
        self.setFixedSize(400, 200)

        layout = QVBoxLayout(self)

        # 乗り場ID (編集不可)
        layout.addWidget(QLabel("乗り場ID(変更不可):"))
        self.id_edit = QLineEdit(track_id)
        self.id_edit.setReadOnly(True)
        self.id_edit.setStyleSheet("background-color: #eeeeee; color: #888888;")
        layout.addWidget(self.id_edit)

        # 乗り場番号
        layout.addWidget(QLabel("乗り場番号:"))
        self.number_edit = QLineEdit(track_number)
        layout.addWidget(self.number_edit)

        layout.addStretch()

        # ボタンエリア
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("キャンセル")
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)


# 路線・駅情報編集ダイアログ
class LineStationEditorDialog(QDialog):
    def __init__(self, parent, project: OptDiaProject):
        super().__init__(parent)
        self.project = project
        # 現在選択されている路線のIDとデータ
        self.current_selected_line_id = None
        self.current_selected_line_data = None
        self.setWindowTitle("路線・駅情報")
        self.setFixedSize(960, 640)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 左側の垂直レイアウト (幅200px固定)
        left_panel = QWidget()
        left_panel.setFixedWidth(200)
        left_panel.setStyleSheet("background-color: #f7f7f7;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(5)

        left_layout.addWidget(QLabel("<b>路線の一覧</b>"))
        
        # 路線リスト
        self.line_list_widget = QListWidget()
        self.line_list_widget.setStyleSheet("font-size: 14px;")
        self.line_list_widget.setItemDelegate(HtmlDelegate(self))
        self.line_list_widget.setDragDropMode(QListWidget.InternalMove)
        self.line_list_widget.itemSelectionChanged.connect(self._on_line_selected)
        self.line_list_widget.model().rowsMoved.connect(self._on_lines_reordered)
        left_layout.addWidget(self.line_list_widget)
        
        # 路線追加ボタン
        self.add_line_button = QPushButton("路線の追加")
        self.add_line_button.clicked.connect(self._on_add_line)
        left_layout.addWidget(self.add_line_button)

        # 並び替えに関する説明文を追加
        left_layout.addSpacing(10)
        drag_info_label = QLabel("路線や駅はドラッグ操作で並び替え可能です")
        drag_info_label.setWordWrap(True)
        drag_info_label.setStyleSheet("color: #888888; font-size: 12px;")
        left_layout.addWidget(drag_info_label)

        main_layout.addWidget(left_panel)

        # 右側のコンテンツエリア (スタックウィジェットで表示を切り替え)
        self.right_stack = QStackedWidget()
        main_layout.addWidget(self.right_stack)

        # プレースホルダー (路線がない場合)
        self.placeholder_widget = QWidget()
        placeholder_layout = QVBoxLayout(self.placeholder_widget)
        placeholder_label = QLabel("まずは路線を追加してください")
        placeholder_label.setAlignment(Qt.AlignCenter)
        placeholder_label.setStyleSheet("color: #888888; font-size: 18px;")
        placeholder_layout.addWidget(placeholder_label)
        self.right_stack.addWidget(self.placeholder_widget)

        # タブウィジェット (路線がある場合)
        self.right_panel_tabs = QTabWidget()
        self.right_stack.addWidget(self.right_panel_tabs)

        # --- 「駅情報」タブの内容 ---
        self.station_info_tab = QWidget()
        station_tab_main_layout = QHBoxLayout(self.station_info_tab)
        station_tab_main_layout.setContentsMargins(0, 0, 0, 0)
        station_tab_main_layout.setSpacing(0)

        # 左側の垂直レイアウト (幅180px固定)
        station_left_panel = QWidget()
        station_left_panel.setObjectName("station_left_panel")
        station_left_panel.setFixedWidth(180)
        station_left_panel.setStyleSheet("#station_left_panel { background-color: #f7f7f7; border-right: 1px solid #dddddd; }")
        station_left_layout = QVBoxLayout(station_left_panel)
        station_left_layout.setContentsMargins(10, 10, 10, 10)
        station_left_layout.setSpacing(5)

        self.station_list_label = QLabel("<b>駅</b>")
        station_left_layout.addWidget(self.station_list_label)

        # 駅リスト
        self.station_list_widget = QListWidget()
        self.station_list_widget.setDragDropMode(QListWidget.InternalMove)
        self.station_list_widget.itemSelectionChanged.connect(self._on_station_selected)
        self.station_list_widget.model().rowsMoved.connect(self._on_stations_reordered)
        station_left_layout.addWidget(self.station_list_widget)

        # 駅追加ボタン
        self.add_station_button = QPushButton("駅の追加")
        self.add_station_button.clicked.connect(self._on_add_station)
        station_left_layout.addWidget(self.add_station_button)

        station_tab_main_layout.addWidget(station_left_panel)

        # 右側の駅情報入力フォーム
        self.station_editor_form_widget = QWidget()
        station_form_layout = QVBoxLayout(self.station_editor_form_widget)
        station_form_layout.setContentsMargins(20, 20, 20, 20)
        station_form_layout.setSpacing(15)

        # 1つ目のQGroupBox: 駅基本情報
        self.base_info_group = QGroupBox("駅基本情報")
        base_info_layout = QFormLayout(self.base_info_group)
        self.station_id_edit = QLineEdit()
        self.station_id_edit.setReadOnly(True)
        self.station_id_edit.setStyleSheet("background-color: #eeeeee; color: #888888;")
        base_info_layout.addRow("駅ID(変更不可):", self.station_id_edit)

        self.station_name_edit = QLineEdit()
        self.station_name_edit.textChanged.connect(self._on_station_base_info_changed)
        base_info_layout.addRow("駅名:", self.station_name_edit)

        self.station_kana_edit = QLineEdit()
        self.station_kana_edit.textChanged.connect(self._on_station_base_info_changed)
        base_info_layout.addRow("駅名(ひらがな):", self.station_kana_edit)

        # 垂直配置レイアウト2つを含む水平レイアウト
        bottom_base_info_layout = QHBoxLayout()

        # 1つ目の垂直配置レイアウト
        left_vertical_layout = QVBoxLayout()
        
        # 駅の1文字表記入力欄
        station_initial_layout = QHBoxLayout()
        station_initial_layout.addWidget(QLabel("駅の1文字表記:"))
        self.station_initial_edit = QLineEdit()
        self.station_initial_edit.setFixedWidth(80)
        self.station_initial_edit.textChanged.connect(self._on_station_base_info_changed)
        self.station_initial_edit.editingFinished.connect(self._on_station_initial_editing_finished)
        station_initial_layout.addWidget(self.station_initial_edit)
        station_initial_layout.addStretch()
        left_vertical_layout.addLayout(station_initial_layout)

        # 1文字表記に関する説明文
        initial_info_label = QLabel("1文字表記はその駅を始発・終着とする列車が設定されている駅と路線の分岐駅で必須です")
        initial_info_label.setWordWrap(True)
        initial_info_label.setStyleSheet("color: #888888; font-size: 12px;")
        left_vertical_layout.addWidget(initial_info_label)

        # 各種チェックボックス
        left_vertical_layout.addSpacing(20)
        self.is_major_station_checkbox = QCheckBox("主要駅")
        self.is_major_station_checkbox.stateChanged.connect(self._on_station_base_info_changed)
        left_vertical_layout.addWidget(self.is_major_station_checkbox)
        self.is_signal_station_checkbox = QCheckBox("信号場")
        self.is_signal_station_checkbox.stateChanged.connect(self._on_station_base_info_changed)
        left_vertical_layout.addWidget(self.is_signal_station_checkbox)
        self.show_arrival_time_checkbox = QCheckBox("着時刻を表示")
        self.show_arrival_time_checkbox.stateChanged.connect(self._on_station_base_info_changed)
        left_vertical_layout.addWidget(self.show_arrival_time_checkbox)
        self.show_track_number_checkbox = QCheckBox("乗り場を表示")
        self.show_track_number_checkbox.stateChanged.connect(self._on_station_base_info_changed)
        left_vertical_layout.addWidget(self.show_track_number_checkbox)
        left_vertical_layout.addStretch()
        bottom_base_info_layout.addLayout(left_vertical_layout)

        # 2つ目の垂直配置レイアウト
        right_vertical_layout = QVBoxLayout()
        right_vertical_layout.addWidget(QLabel("乗り場:"))
        self.track_list_widget = QListWidget()
        self.track_list_widget.setDragDropMode(QListWidget.InternalMove)
        self.track_list_widget.itemDoubleClicked.connect(self._on_edit_track)
        self.track_list_widget.model().rowsMoved.connect(self._on_tracks_reordered)
        right_vertical_layout.addWidget(self.track_list_widget)

        track_btn_layout = QHBoxLayout()
        self.edit_track_button = QPushButton("編集")
        self.edit_track_button.clicked.connect(self._on_edit_track)
        track_btn_layout.addWidget(self.edit_track_button)
        self.add_track_button = QPushButton("追加")
        self.add_track_button.clicked.connect(self._on_add_track)
        track_btn_layout.addWidget(self.add_track_button)
        right_vertical_layout.addLayout(track_btn_layout)
        bottom_base_info_layout.addLayout(right_vertical_layout)

        base_info_layout.addRow(bottom_base_info_layout)
        station_form_layout.addWidget(self.base_info_group)

        # 2つ目のQGroupBox: <路線名>に関連する駅情報
        self.line_station_group = QGroupBox("路線に関連する駅情報")
        line_station_main_layout = QVBoxLayout(self.line_station_group)

        # フォーム要素を横に並べるためのサブレイアウト
        line_station_forms_layout = QHBoxLayout()

        # 1つ目の垂直レイアウト (駅番号、基準運転時分)
        ls_left_form = QFormLayout()
        self.station_number_edit = QLineEdit()
        self.station_number_edit.setFixedWidth(80)
        self.station_number_edit.textChanged.connect(self._on_line_station_info_changed)
        ls_left_form.addRow("駅番号:", self.station_number_edit)
        self.running_time_spin = QSpinBox()
        self.running_time_spin.setRange(-1, 86400)
        self.running_time_spin.setSpecialValueText("未設定")
        self.running_time_spin.setSuffix(" 秒")
        self.running_time_spin.valueChanged.connect(self._on_line_station_info_changed)
        ls_left_form.addRow("起点駅からの基準運転時分:", self.running_time_spin)
        line_station_forms_layout.addLayout(ls_left_form)

        # 2つ目の垂直レイアウト (上下本線)
        ls_right_form = QFormLayout()
        self.inbound_track_combo = QComboBox()
        self.inbound_track_combo.currentIndexChanged.connect(self._on_line_station_info_changed)
        ls_right_form.addRow("上り本線:", self.inbound_track_combo)
        self.outbound_track_combo = QComboBox()
        self.outbound_track_combo.currentIndexChanged.connect(self._on_line_station_info_changed)
        ls_right_form.addRow("下り本線:", self.outbound_track_combo)
        line_station_forms_layout.addLayout(ls_right_form)

        line_station_main_layout.addLayout(line_station_forms_layout)

        # 説明文の追加
        calc_info_label = QLabel("基準運転時分は入力済みの時刻表から自動算出することもできます")
        calc_info_label.setStyleSheet("color: #888888; font-size: 12px;")
        line_station_main_layout.addWidget(calc_info_label)

        station_form_layout.addWidget(self.line_station_group)

        station_form_layout.addStretch()

        # 駅情報タブの右側をスタックウィジェット化（フォームとプレースホルダーの切り替え）
        self.station_right_stack = QStackedWidget()
        self.station_right_stack.addWidget(self.station_editor_form_widget)

        # 駅未登録時のプレースホルダー
        self.station_empty_placeholder = QWidget()
        empty_layout = QVBoxLayout(self.station_empty_placeholder)
        empty_layout.setAlignment(Qt.AlignCenter)

        label_main = QLabel("駅を追加してください")
        label_main.setStyleSheet("font-size: 18px; color: #888888;")
        label_main.setAlignment(Qt.AlignCenter)

        label_sub = QLabel("路線情報は路線情報タブで編集できます")
        label_sub.setStyleSheet("font-size: 14px; color: #aaaaaa;")
        label_sub.setAlignment(Qt.AlignCenter)

        empty_layout.addStretch()
        empty_layout.addWidget(label_main)
        empty_layout.addWidget(label_sub)
        empty_layout.addStretch()

        self.station_right_stack.addWidget(self.station_empty_placeholder)
        station_tab_main_layout.addWidget(self.station_right_stack, stretch=1)

        self.right_panel_tabs.addTab(self.station_info_tab, "駅情報")

        # --- 「路線情報」タブの内容 ---
        self.line_info_tab = QWidget()
        self.line_info_layout = QVBoxLayout(self.line_info_tab)
        self.line_info_layout.setContentsMargins(20, 20, 20, 20)
        self.line_info_layout.setSpacing(10)

        # 路線ID (表示のみ、編集不可)
        self.line_info_layout.addWidget(QLabel("路線ID(変更不可):"))
        self.line_id_display = QLineEdit()
        self.line_id_display.setReadOnly(True)
        self.line_id_display.setStyleSheet("background-color: #eeeeee; color: #888888;")
        self.line_info_layout.addWidget(self.line_id_display)

        # 路線名
        self.line_info_layout.addWidget(QLabel("路線名:"))
        self.line_name_edit = QLineEdit()
        self.line_name_edit.textChanged.connect(self._on_line_name_changed)
        self.line_info_layout.addWidget(self.line_name_edit)

        # 路線の色
        self.line_info_layout.addWidget(QLabel("路線の色:"))
        color_picker_layout = QHBoxLayout()
        self.color_square_label = QLabel()
        self.color_square_label.setFixedSize(20, 20)
        self.color_square_label.setStyleSheet("border: 1px solid #cccccc;") # 枠線で視認性を向上
        color_picker_layout.addWidget(self.color_square_label)
        self.color_button = QPushButton("#333333") # 初期色コード
        self.color_button.clicked.connect(self._on_pick_color)
        color_picker_layout.addWidget(self.color_button)
        color_picker_layout.addStretch()
        self.line_info_layout.addLayout(color_picker_layout)

        # 路線記号
        self.line_info_layout.addWidget(QLabel("路線記号等:"))
        self.line_symbol_edit = QLineEdit()
        self.line_symbol_edit.setFixedWidth(80)
        self.line_symbol_edit.textChanged.connect(self._on_line_symbol_changed)
        self.line_info_layout.addWidget(self.line_symbol_edit)

        # 編成の前位向きと列車の上り向きが一致するチェックボックス
        self.line_info_layout.addSpacing(20)
        self.inbound_direction_checkbox = QCheckBox("編成の前位向きと列車の上り向きが一致する")
        self.inbound_direction_checkbox.stateChanged.connect(self._on_inbound_direction_changed)
        self.line_info_layout.addWidget(self.inbound_direction_checkbox)

        self.line_info_layout.addStretch() # 内容を上部に寄せる

        self.right_panel_tabs.addTab(self.line_info_tab, "路線情報")

        # 初期リストの構築
        self._populate_line_list()

        # 初期状態では路線情報編集フォームを無効化
        self._set_line_editing_enabled(False)
        # 初期状態では駅情報編集フォームを無効化
        self._set_station_editing_enabled(False)

        # 路線が登録されていれば最初の項目を選択状態にする
        if self.line_list_widget.count() > 0:
            self.line_list_widget.setCurrentRow(0)

    def _set_line_editing_enabled(self, enabled: bool):
        """路線情報編集フォームのウィジェットの有効/無効を切り替える"""
        self.line_name_edit.setEnabled(enabled)
        self.color_button.setEnabled(enabled)
        self.line_symbol_edit.setEnabled(enabled)
        self.inbound_direction_checkbox.setEnabled(enabled)
        self.station_list_widget.setEnabled(enabled)
        self.add_station_button.setEnabled(enabled)
        
        if not enabled:
            self.line_name_edit.blockSignals(True)
            self.line_symbol_edit.blockSignals(True)
            self.inbound_direction_checkbox.blockSignals(True)
            self.line_id_display.clear()
            self.line_name_edit.clear()
            self.color_button.setText("#000000")
            self.color_square_label.setPixmap(create_color_square_pixmap("#000000"))
            self.line_symbol_edit.clear()
            self.station_list_widget.clear()
            self.station_list_label.setText("<b>駅</b>")
            self.inbound_direction_checkbox.setChecked(False)
            self.line_name_edit.blockSignals(False)
            self.line_symbol_edit.blockSignals(False)
            self.inbound_direction_checkbox.blockSignals(False)

    def _set_station_editing_enabled(self, enabled: bool):
        """駅情報編集フォームの有効/無効を切り替える"""
        self.station_editor_form_widget.setEnabled(enabled)
        # 信号を一時的にブロックし、クリア操作がデータ更新ハンドラを呼び出さないようにする
        self.station_name_edit.blockSignals(True)
        self.station_kana_edit.blockSignals(True)
        self.station_number_edit.blockSignals(True)
        self.running_time_spin.blockSignals(True)
        self.inbound_track_combo.blockSignals(True)
        self.outbound_track_combo.blockSignals(True)

        if not enabled:
            self.station_id_edit.clear()
            self.station_name_edit.clear()
            self.station_kana_edit.clear()
            self.station_initial_edit.clear()
            self.is_major_station_checkbox.setChecked(False)
            self.is_signal_station_checkbox.setChecked(False)
            self.show_arrival_time_checkbox.setChecked(False)
            self.show_track_number_checkbox.setChecked(False)
            self.station_number_edit.clear()
            self.running_time_spin.setValue(-1)
            self.inbound_track_combo.clear()
            self.outbound_track_combo.clear()

        self.station_name_edit.blockSignals(False)
        self.station_kana_edit.blockSignals(False)
        self.station_number_edit.blockSignals(False)
        self.running_time_spin.blockSignals(False)
        self.station_initial_edit.blockSignals(False)
        self.is_major_station_checkbox.blockSignals(False)
        self.is_signal_station_checkbox.blockSignals(False)
        self.show_arrival_time_checkbox.blockSignals(False)
        self.show_track_number_checkbox.blockSignals(False)
        self.inbound_track_combo.blockSignals(False)
        self.outbound_track_combo.blockSignals(False)

    def _populate_line_list(self):
        """プロジェクトに登録されている路線をリストに表示する"""
        self.line_list_widget.clear()
        for line_id in self.project.lines_order:
            line = self.project.lines[line_id]
            symbol = line.get("line_symbol") or ""
            name = line.get("line_name", "")
            color = line.get("line_color", "#333333")
            # 記号部分を路線の色で着色するHTML
            display_text = f"<font color='{color}'><b>[{symbol}]</b></font> {name}" if symbol else name
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, line_id)
            self.line_list_widget.addItem(item)

        # 路線が一つもない場合はプレースホルダーを表示
        if self.line_list_widget.count() > 0:
            self.right_stack.setCurrentWidget(self.right_panel_tabs)
        else:
            self.right_stack.setCurrentWidget(self.placeholder_widget)

    def _on_lines_reordered(self, parent, start, end, destination, row):
        """並び替えられたリストの状態をプロジェクトデータに反映する"""
        new_order = []
        for i in range(self.line_list_widget.count()):
            item = self.line_list_widget.item(i)
            new_order.append(item.data(Qt.UserRole))
        
        self.project.lines_order = new_order
        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)

    def _on_stations_reordered(self, parent, start, end, destination, row):
        """並び替えられた駅リストの状態をプロジェクトデータに反映する"""
        if not self.current_selected_line_data:
            return

        # 現在の駅データ（辞書のリスト）を取得
        old_station_list = self.current_selected_line_data.get("station_list", [])
        # IDをキーにした辞書に変換して、既存の属性（駅ナンバリング等）を保持できるようにする
        station_map = {s["station_id"]: s for s in old_station_list}
        
        new_station_list = []
        for i in range(self.station_list_widget.count()):
            item = self.station_list_widget.item(i)
            sid = item.data(Qt.UserRole)
            if sid in station_map:
                new_station_list.append(station_map[sid])
        
        self.current_selected_line_data["station_list"] = new_station_list
        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)

    def _on_line_selected(self):
        """路線リストの選択が変更されたときに呼び出される"""
        selected_items = self.line_list_widget.selectedItems()
        if not selected_items:
            self.current_selected_line_id = None
            self.current_selected_line_data = None
            self._set_line_editing_enabled(False)
            return

        self.current_selected_line_id = selected_items[0].data(Qt.UserRole)
        self.current_selected_line_data = self.project.lines[self.current_selected_line_id]
        
        # UI更新中のシグナルをブロックして不要なデータ更新を防ぐ
        self.line_name_edit.blockSignals(True)
        self.line_symbol_edit.blockSignals(True)
        self.inbound_direction_checkbox.blockSignals(True)

        self._set_line_editing_enabled(True)
        self.line_id_display.setText(self.current_selected_line_id)
        line_name = self.current_selected_line_data.get("line_name", "")
        self.line_name_edit.setText(line_name)
        self.line_station_group.setTitle(f"{line_name}に関連する駅情報")
        self._update_station_list_label(line_name)
        
        current_color = self.current_selected_line_data.get("line_color", "#333333")
        self.color_button.setText(current_color)
        self.color_square_label.setPixmap(create_color_square_pixmap(current_color))

        self.line_symbol_edit.setText(self.current_selected_line_data.get("line_symbol") or "")
        self.inbound_direction_checkbox.setChecked(self.current_selected_line_data.get("inbound_direction_is_forward_direction", True))

        # 選択された路線に紐づく駅をリストに表示
        self._populate_station_list(self.current_selected_line_data)

        # シグナルブロックを解除
        self.line_name_edit.blockSignals(False)
        self.line_symbol_edit.blockSignals(False)
        self.inbound_direction_checkbox.blockSignals(False)

    def _on_line_name_changed(self, text: str):
        """路線名が変更されたときにプロジェクトデータを更新する"""
        line_id = self.line_id_display.text()
        line_data = self.project.lines.get(line_id)
        if line_data:
            line_data["line_name"] = text
            self.line_station_group.setTitle(f"{text}に関連する駅情報")
            self._update_station_list_label(text)
            if hasattr(self.parent(), "set_modified"):
                self.parent().set_modified(True)
            # リストウィジェットの表示も更新
            selected_items = self.line_list_widget.selectedItems()
            if selected_items and selected_items[0].data(Qt.UserRole) == line_id:
                symbol = line_data.get("line_symbol") or ""
                name = line_data.get("line_name", "")
                color = line_data.get("line_color", "#333333")
                display_text = f"<font color='{color}'><b>[{symbol}]</b></font> {name}" if symbol else name
                selected_items[0].setText(display_text)

    def _on_line_symbol_changed(self, text: str):
        """路線記号が変更されたときにプロジェクトデータを更新する"""
        line_id = self.line_id_display.text()
        line_data = self.project.lines.get(line_id)
        if line_data:
            line_data["line_symbol"] = text if text else None
            if hasattr(self.parent(), "set_modified"):
                self.parent().set_modified(True)
            # リストウィジェットの表示も更新
            selected_items = self.line_list_widget.selectedItems()
            if selected_items and selected_items[0].data(Qt.UserRole) == line_id:
                symbol = line_data.get("line_symbol") or ""
                name = line_data.get("line_name", "")
                color = line_data.get("line_color", "#333333")
                display_text = f"<font color='{color}'><b>[{symbol}]</b></font> {name}" if symbol else name
                selected_items[0].setText(display_text)

    def _on_inbound_direction_changed(self, state: int):
        """編成の前位向きと列車の上り向きが一致するチェックボックスの状態が変更されたときにプロジェクトデータを更新する"""
        line_id = self.line_id_display.text()
        line_data = self.project.lines.get(line_id)
        if line_data:
            # state引数との比較よりもisChecked()を直接参照する方が確実
            line_data["inbound_direction_is_forward_direction"] = self.inbound_direction_checkbox.isChecked()
            if hasattr(self.parent(), "set_modified"):
                self.parent().set_modified(True)

    def _on_pick_color(self):
        """色選択ダイアログを表示し、選択された色をプロジェクトデータに反映する"""
        if self.current_selected_line_data:
            initial_color = QColor(self.current_selected_line_data.get("line_color", "#333333"))
            color = QColorDialog.getColor(initial_color, self)
            if color.isValid():
                new_color_hex = color.name()
                self.current_selected_line_data["line_color"] = new_color_hex
                self.color_button.setText(new_color_hex)
                self.color_square_label.setPixmap(create_color_square_pixmap(new_color_hex))
                
                # リスト側の色表示も更新する
                selected_items = self.line_list_widget.selectedItems()
                if selected_items:
                    symbol = self.current_selected_line_data.get("line_symbol") or ""
                    name = self.current_selected_line_data.get("line_name", "")
                    display_text = f"<font color='{new_color_hex}'><b>[{symbol}]</b></font> {name}" if symbol else name
                    selected_items[0].setText(display_text)

                if hasattr(self.parent(), "set_modified"):
                    self.parent().set_modified(True)

    def _on_add_line(self):
        """路線の追加ダイアログを表示する"""
        dialog = AddLineDialog(self, self.project)
        if dialog.exec() == QDialog.Accepted:
            line_id = dialog.id_edit.text().strip()
            line_name = dialog.name_edit.text().strip()

            # プロジェクトデータに新規路線を追加
            self.project.lines[line_id] = {
                "line_id": line_id,
                "line_name": line_name,
                "line_color": "#333333",
                "line_symbol": None,
                "inbound_direction_is_forward_direction": True,
                "station_list": []
            }
            self.project.lines_order.append(line_id)

            # リスト表示を更新
            self._populate_line_list()
            
            # 変更フラグを立てる
            if hasattr(self.parent(), "set_modified"):
                self.parent().set_modified(True)
            # 新しく追加された路線を選択状態にする
            if self.line_list_widget.count() > 0:
                self.line_list_widget.setCurrentRow(self.line_list_widget.count() - 1)

    def _populate_station_list(self, line_data: dict):
        """選択された路線に紐づく駅をリストに表示する"""
        self.station_list_widget.clear()
        station_list = line_data.get("station_list", [])
        for station_item in station_list:
            station_id = station_item.get("station_id")
            # QListWidgetItemの作成とIDの紐付け
            item = QListWidgetItem()
            item.setData(Qt.UserRole, station_id)
            self.station_list_widget.addItem(item)
            # 表示文字列とスタイルの更新
            self._update_station_list_item_display(item, station_id)

        # 駅の有無に応じて右側の表示を切り替え、あれば最初の駅を選択
        if self.station_list_widget.count() > 0:
            self.station_right_stack.setCurrentWidget(self.station_editor_form_widget)
            self.station_list_widget.setCurrentRow(0)
        else:
            self.station_right_stack.setCurrentWidget(self.station_empty_placeholder)
            self._set_station_editing_enabled(False)

    def _update_station_list_label(self, line_name: str):
        """駅リストのラベルを路線名に合わせて更新する（9文字以上の場合は切り詰め）"""
        if not line_name:
            self.station_list_label.setText("<b>駅</b>")
            return

        display_name = (line_name[:8] + "..") if len(line_name) >= 9 else line_name
        self.station_list_label.setText(f"<b>{display_name}の駅</b>")

    def _on_station_selected(self):
        """駅リストの選択が変更されたとき、右側のフォームを更新する"""
        selected_items = self.station_list_widget.selectedItems()
        if not selected_items or not self.current_selected_line_data:
            self._set_station_editing_enabled(False)
            return

        station_id = selected_items[0].data(Qt.UserRole)
        station_data = self.project.stations.get(station_id)
        line_station_item = next((s for s in self.current_selected_line_data.get("station_list", []) 
                                  if s.get("station_id") == station_id), None)
        
        if not station_data or not line_station_item:
            self._set_station_editing_enabled(False)
            return

        self._set_station_editing_enabled(True)
        
        self.station_id_edit.setText(station_id)
        
        # UI更新中のシグナルをブロック
        self.station_name_edit.blockSignals(True)
        self.station_kana_edit.blockSignals(True)
        self.station_number_edit.blockSignals(True)
        self.running_time_spin.blockSignals(True)
        self.station_initial_edit.blockSignals(True)
        self.is_major_station_checkbox.blockSignals(True)
        self.is_signal_station_checkbox.blockSignals(True)
        self.show_arrival_time_checkbox.blockSignals(True)
        self.show_track_number_checkbox.blockSignals(True)

        self.station_name_edit.setText(station_data.get("station_name", ""))
        self.station_kana_edit.setText(station_data.get("station_name_kana", ""))
        self.station_number_edit.setText(line_station_item.get("station_number") or "")
        rt = line_station_item.get("absolute_standard_running_time")
        self.running_time_spin.setValue(rt if rt is not None else -1)

        # 乗り場コンボボックスの更新
        self.inbound_track_combo.blockSignals(True)
        self.outbound_track_combo.blockSignals(True)
        self.inbound_track_combo.clear()
        self.outbound_track_combo.clear()
        self.inbound_track_combo.addItem("未設定", None)
        self.outbound_track_combo.addItem("未設定", None)

        tracks = station_data.get("tracks", {})
        tracks_order = station_data.get("tracks_order", [])
        for tid in tracks_order:
            t_data = tracks.get(tid)
            if t_data:
                t_name = t_data.get("track_number") or tid
                self.inbound_track_combo.addItem(t_name, tid)
                self.outbound_track_combo.addItem(t_name, tid)

        # 保存されている値を設定
        idx_in = self.inbound_track_combo.findData(line_station_item.get("inbound_main_track"))
        self.inbound_track_combo.setCurrentIndex(idx_in if idx_in >= 0 else 0)
        idx_out = self.outbound_track_combo.findData(line_station_item.get("outbound_main_track"))
        self.outbound_track_combo.setCurrentIndex(idx_out if idx_out >= 0 else 0)

        self.inbound_track_combo.blockSignals(False)
        self.outbound_track_combo.blockSignals(False)

        self.station_initial_edit.setText(station_data.get("station_initial", "") or "")
        self.is_major_station_checkbox.setChecked(station_data.get("is_major_station", False))
        self.is_signal_station_checkbox.setChecked(station_data.get("is_signal_station", False))
        self.show_arrival_time_checkbox.setChecked(station_data.get("show_arrival_time", False))
        self.show_track_number_checkbox.setChecked(station_data.get("show_track_number", False))

        self._populate_track_list(station_data)

        self.station_name_edit.blockSignals(False)
        self.station_kana_edit.blockSignals(False)
        self.station_number_edit.blockSignals(False)
        self.running_time_spin.blockSignals(False)
        self.station_initial_edit.blockSignals(False)
        self.is_major_station_checkbox.blockSignals(False)
        self.is_signal_station_checkbox.blockSignals(False)
        self.show_arrival_time_checkbox.blockSignals(False)
        self.show_track_number_checkbox.blockSignals(False)

    def _on_station_initial_editing_finished(self):
        # _on_station_base_info_changed が呼ばれるため、ここでは modified フラグは立てない
        # (textChanged で既にフラグが立つか、editingFinished で再度立つため)
        """駅の1文字表記入力欄のフォーカスが外れたときに、2文字目以降を削除する"""
        text = self.station_initial_edit.text()
        if len(text) > 1:
            self.station_initial_edit.setText(text[0])
        # textChangedシグナルが発火するので、別途_on_station_base_info_changedを呼ぶ必要はない


    def _on_station_base_info_changed(self):
        """駅の基本情報が変更されたとき、プロジェクトデータを更新する"""
        station_id = self.station_id_edit.text()
        if not station_id: return
        station_data = self.project.stations.get(station_id)
        if not station_data: return
        
        station_data["station_name"] = self.station_name_edit.text()
        station_data["station_name_kana"] = self.station_kana_edit.text()
        
        initial_text = self.station_initial_edit.text().strip()
        station_data["station_initial"] = initial_text if initial_text else None
        station_data["is_major_station"] = self.is_major_station_checkbox.isChecked()
        station_data["is_signal_station"] = self.is_signal_station_checkbox.isChecked()
        station_data["show_arrival_time"] = self.show_arrival_time_checkbox.isChecked()
        station_data["show_track_number"] = self.show_track_number_checkbox.isChecked()
        
        # リストの表示更新は、該当する項目が選択されている場合のみ行う
        selected_items = self.station_list_widget.selectedItems()
        if selected_items and selected_items[0].data(Qt.UserRole) == station_id:
            self._update_station_list_item_display(selected_items[0], station_id)

        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)

    def _on_line_station_info_changed(self):
        """特定の路線に関連する駅情報が変更されたとき、プロジェクトデータを更新する"""
        station_id = self.station_id_edit.text()
        if not station_id or not self.current_selected_line_data: return

        line_station_item = next((s for s in self.current_selected_line_data.get("station_list", []) 
                                  if s.get("station_id") == station_id), None)
        if not line_station_item: return
        
        num = self.station_number_edit.text().strip()
        line_station_item["station_number"] = num if num else None
        
        val = self.running_time_spin.value()
        line_station_item["absolute_standard_running_time"] = val if val != -1 else None

        line_station_item["inbound_main_track"] = self.inbound_track_combo.currentData()
        line_station_item["outbound_main_track"] = self.outbound_track_combo.currentData()
        
        selected_items = self.station_list_widget.selectedItems()
        if selected_items and selected_items[0].data(Qt.UserRole) == station_id:
            self._update_station_list_item_display(selected_items[0], station_id)

        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)

    def _populate_track_list(self, station_data: dict):
        """駅の乗り場リストを表示する"""
        self.track_list_widget.clear()
        tracks = station_data.get("tracks", {})
        tracks_order = station_data.get("tracks_order", [])
        for tid in tracks_order:
            track = tracks.get(tid)
            if track:
                display_name = track.get("track_number") or tid
                item = QListWidgetItem(display_name)
                item.setData(Qt.UserRole, tid)
                self.track_list_widget.addItem(item)

    def _on_add_track(self):
        """乗り場の追加ダイアログを表示し、プロジェクトデータに反映する"""
        station_id = self.station_id_edit.text()
        if not station_id:
            return
        station_data = self.project.stations.get(station_id)
        if not station_data:
            return

        dialog = AddTrackDialog(self, station_data)
        if dialog.exec() == QDialog.Accepted:
            track_id = dialog.id_edit.text().strip()
            track_number = dialog.number_edit.text().strip()

            if "tracks" not in station_data: station_data["tracks"] = {}
            if "tracks_order" not in station_data: station_data["tracks_order"] = []

            station_data["tracks"][track_id] = {
                "track_id": track_id,
                "track_number": track_number
            }
            station_data["tracks_order"].append(track_id)

            self._populate_track_list(station_data)
            self._on_station_selected()
            if hasattr(self.parent(), "set_modified"):
                self.parent().set_modified(True)

    def _on_edit_track(self):
        """選択中の乗り場の情報を編集するダイアログを表示する"""
        selected_items = self.track_list_widget.selectedItems()
        if not selected_items:
            return

        track_id = selected_items[0].data(Qt.UserRole)
        station_id = self.station_id_edit.text()
        station_data = self.project.stations.get(station_id)
        if not station_data:
            return

        track_data = station_data.get("tracks", {}).get(track_id)
        if not track_data:
            return

        dialog = EditTrackDialog(self, track_id, track_data.get("track_number", ""))
        if dialog.exec() == QDialog.Accepted:
            track_data["track_number"] = dialog.number_edit.text().strip()
            
            self._populate_track_list(station_data)
            self._on_station_selected()
            
            # 編集していた項目を再選択する
            for i in range(self.track_list_widget.count()):
                if self.track_list_widget.item(i).data(Qt.UserRole) == track_id:
                    self.track_list_widget.setCurrentRow(i)
                    break

            if hasattr(self.parent(), "set_modified"):
                self.parent().set_modified(True)

    def _on_tracks_reordered(self, parent, start, end, destination, row):
        """並び替えられた乗り場リストの状態をプロジェクトデータに反映する"""
        station_id = self.station_id_edit.text()
        if not station_id:
            return
        station_data = self.project.stations.get(station_id)
        if not station_data:
            return

        new_tracks_order = []
        for i in range(self.track_list_widget.count()):
            item = self.track_list_widget.item(i)
            tid = item.data(Qt.UserRole)
            new_tracks_order.append(tid)
        
        station_data["tracks_order"] = new_tracks_order
        self._on_station_selected()
        
        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)


    def _update_station_list_item_display(self, item, station_id):
        """駅リストの表示文字列とスタイルを最新の状態に更新する"""
        station_data = self.project.stations.get(station_id)
        line_station_item = next((s for s in self.current_selected_line_data.get("station_list", []) 
                                  if s.get("station_id") == station_id), None)
        if not station_data or not line_station_item: return

        name = station_data.get("station_name", station_id)
        number = line_station_item.get("station_number")
        item.setText(f"[{number}] {name}" if number else name)

        # スタイルの設定
        is_major = station_data.get("is_major_station", False)
        is_signal = station_data.get("is_signal_station", False)
        
        font = item.font()
        if is_signal:
            # 信号場は灰色、太字解除
            item.setForeground(Qt.gray)
            font.setBold(False)
        elif is_major:
            # 主要駅は太字、文字色はデフォルト
            item.setForeground(Qt.black)
            font.setBold(True)
        else:
            # それ以外は標準
            item.setForeground(Qt.black)
            font.setBold(False)
        item.setFont(font)

    def _on_add_station(self):
        """駅の追加ダイアログを表示し、プロジェクトデータに反映する"""
        if not self.current_selected_line_id:
            return

        dialog = AddStationDialog(self, self.project, self.current_selected_line_id)
        if dialog.exec() == QDialog.Accepted:
            if dialog.new_station_radio.isChecked():
                # 新規駅の作成
                station_id = dialog.station_id_edit.text().strip()
                station_name = dialog.station_name_edit.text().strip()
                
                self.project.stations[station_id] = {
                    "station_id": station_id,
                    "station_name": station_name, # 駅名
                    "station_name_kana": dialog.station_name_kana_edit.text().strip(), # 駅名(かな)
                    "station_initial": None,
                    "is_major_station": False,
                    "is_signal_station": False,
                    "show_arrival_time": False,
                    "show_track_number": False,
                    "tracks": {},
                    "tracks_order": []
                }
                new_station_id = station_id
            else:
                # 既存駅の参照
                new_station_id = dialog.station_combo.currentData()

            # 選択中の路線の駅リストに追加
            station_list = self.current_selected_line_data.get("station_list", [])
            # 重複チェック
            if any(s.get("station_id") == new_station_id for s in station_list):
                QMessageBox.warning(self, "エラー", "選択された駅は編集中の路線に登録済みです。")
                return
            
            station_list.append({
                "station_id": new_station_id,
                "station_number": None,
                "inbound_main_track": None,
                "outbound_main_track": None,
                "absolute_standard_running_time": None
            })
            self.current_selected_line_data["station_list"] = station_list
            
            # UI更新
            self._populate_station_list(self.current_selected_line_data)
            if hasattr(self.parent(), "set_modified"):
                self.parent().set_modified(True)


# 線のサンプルを表示するためのカスタムウィジェット
class LineSampleWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(120, 30)
        self.line_color = QColor("#333333")
        self.line_weight = "normal"
        self.line_style = "solid"

    def set_line_properties(self, color_hex, weight, style):
        self.line_color = QColor(color_hex)
        self.line_weight = weight
        self.line_style = style
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        # 背景
        painter.fillRect(self.rect(), Qt.white)
        painter.setPen(QColor("#cccccc"))
        painter.drawRect(0, 0, self.width() - 1, self.height() - 1)

        # ペンの設定
        pen = QPen(self.line_color)
        
        # 太さのマッピング
        if self.line_weight == "thin":
            pen.setWidth(1)
        elif self.line_weight == "bold":
            pen.setWidth(3)
        else: # normal
            pen.setWidth(2)

        # スタイルのマッピング
        if self.line_style == "dashed":
            pen.setStyle(Qt.DashLine)
        elif self.line_style == "dotted":
            pen.setStyle(Qt.DotLine)
        else: # solid
            pen.setStyle(Qt.SolidLine)

        painter.setPen(pen)
        y = self.height() / 2
        painter.drawLine(10, y, self.width() - 10, y)


# 列車種別の追加ダイアログ
class AddTrainTypeDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("種別の追加")
        self.setFixedSize(480, 240)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例) 区間急行")
        form_layout.addRow("列車種別名:", self.name_edit)

        self.nickname_edit = QLineEdit()
        self.nickname_edit.setPlaceholderText("例) ラピート")
        form_layout.addRow("列車愛称(なければ空欄):", self.nickname_edit)

        self.short_name_edit = QLineEdit()
        self.short_name_edit.setPlaceholderText("例) 区急")
        self.short_name_edit.setFixedWidth(100)
        form_layout.addRow("短縮表記:", self.short_name_edit)

        layout.addLayout(form_layout)
        layout.addStretch()

        # ボタンエリア
        button_layout = QHBoxLayout()
        self.add_button = QPushButton("追加")
        self.cancel_button = QPushButton("キャンセル")
        button_layout.addStretch()
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.add_button.clicked.connect(self._on_add_clicked)
        self.cancel_button.clicked.connect(self.reject)

    def _on_add_clicked(self):
        """入力チェック"""
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "エラー", "列車種別名を入力してください。")
            return
        if not self.short_name_edit.text().strip():
            QMessageBox.warning(self, "エラー", "短縮表記を入力してください。")
            return
        self.accept()


# 列車種別情報編集ダイアログ
class TrainTypeEditorDialog(QDialog):
    def __init__(self, parent, project: OptDiaProject):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("種別情報")
        self.setFixedSize(720, 480)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 左側の垂直レイアウト (幅180px固定)
        left_panel = QWidget()
        left_panel.setObjectName("train_type_left_panel")
        left_panel.setFixedWidth(180)
        left_panel.setStyleSheet("#train_type_left_panel { background-color: #f7f7f7; border-right: 1px solid #dddddd; }")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(5)

        left_layout.addWidget(QLabel("<b>種別の一覧</b>"))
        
        self.train_type_list_widget = QListWidget()
        self.train_type_list_widget.setStyleSheet("font-size: 12px;")
        self.train_type_list_widget.setItemDelegate(HtmlDelegate(self))
        self.train_type_list_widget.setDragDropMode(QListWidget.InternalMove)
        self.train_type_list_widget.itemSelectionChanged.connect(self._on_train_type_selected)
        self.train_type_list_widget.model().rowsMoved.connect(self._on_train_types_reordered)
        left_layout.addWidget(self.train_type_list_widget)
        
        self.add_train_type_button = QPushButton("種別の追加")
        self.add_train_type_button.clicked.connect(self._on_add_train_type)
        left_layout.addWidget(self.add_train_type_button)

        main_layout.addWidget(left_panel)

        # 右側の編集用フォームエリア
        self.tt_right_stack = QStackedWidget()
        main_layout.addWidget(self.tt_right_stack, stretch=1)

        # --- 編集フォームページ ---
        self.tt_editor_page = QWidget()
        self.tt_editor_layout = QVBoxLayout(self.tt_editor_page)
        self.tt_editor_layout.setContentsMargins(20, 20, 20, 20)
        
        # フォームコンテナ
        self.tt_form_container = QWidget()
        self.tt_form_layout = QFormLayout(self.tt_form_container)
        
        self.tt_name_edit = QLineEdit()
        self.tt_name_edit.textChanged.connect(self._on_train_type_form_changed)
        self.tt_form_layout.addRow("列車種別名:", self.tt_name_edit)
        
        self.tt_nickname_edit = QLineEdit()
        self.tt_nickname_edit.textChanged.connect(self._on_train_type_form_changed)
        self.tt_form_layout.addRow("列車愛称:", self.tt_nickname_edit)
        
        self.tt_short_name_edit = QLineEdit()
        self.tt_short_name_edit.setFixedWidth(100)
        self.tt_short_name_edit.textChanged.connect(self._on_train_type_form_changed)
        self.tt_form_layout.addRow("短縮表記:", self.tt_short_name_edit)
        
        spacer_tt_1 = QWidget()
        spacer_tt_1.setFixedHeight(10)
        self.tt_form_layout.addRow(spacer_tt_1)

        self.tt_in_service_check = QCheckBox("営業列車")
        self.tt_in_service_check.stateChanged.connect(self._on_train_type_form_changed)
        self.tt_form_layout.addRow("", self.tt_in_service_check)
        
        spacer_tt_2 = QWidget()
        spacer_tt_2.setFixedHeight(10)
        self.tt_form_layout.addRow(spacer_tt_2)

        # 種別の基本色
        self.tt_main_color_layout = QHBoxLayout()
        self.tt_main_color_square = QLabel()
        self.tt_main_color_square.setFixedSize(20, 20)
        self.tt_main_color_square.setStyleSheet("border: 1px solid #cccccc;")
        self.tt_main_color_btn = QPushButton()
        self.tt_main_color_btn.clicked.connect(self._on_pick_tt_main_color)
        self.tt_main_color_layout.addWidget(self.tt_main_color_square)
        self.tt_main_color_layout.addWidget(self.tt_main_color_btn)
        self.tt_main_color_layout.addStretch()
        self.tt_form_layout.addRow("種別の基本色:", self.tt_main_color_layout)
        
        # 時刻表背景色
        self.tt_bg_color_layout = QHBoxLayout()
        self.tt_bg_color_square = QLabel()
        self.tt_bg_color_square.setFixedSize(20, 20)
        self.tt_bg_color_square.setStyleSheet("border: 1px solid #cccccc;")
        self.tt_bg_color_btn = QPushButton()
        self.tt_bg_color_btn.clicked.connect(self._on_pick_tt_bg_color)
        self.tt_bg_color_layout.addWidget(self.tt_bg_color_square)
        self.tt_bg_color_layout.addWidget(self.tt_bg_color_btn)
        self.tt_bg_color_layout.addStretch()
        self.tt_form_layout.addRow("時刻表での背景色:", self.tt_bg_color_layout)
        
        # ダイアグラム表示設定
        spacer_tt_3 = QWidget()
        spacer_tt_3.setFixedHeight(20)
        self.tt_form_layout.addRow(spacer_tt_3)

        tt_diagram_label = QLabel("<b>ダイアグラムでの表示</b>")
        tt_diagram_label.setStyleSheet("font-size: 14px;")
        self.tt_form_layout.addRow(tt_diagram_label)
        
        self.tt_line_style_layout = QHBoxLayout()
        self.tt_weight_combo = QComboBox()
        self.tt_weight_combo.addItem("標準", "normal")
        self.tt_weight_combo.addItem("太", "bold")
        self.tt_weight_combo.addItem("細", "thin")
        self.tt_weight_combo.currentIndexChanged.connect(self._on_train_type_form_changed)
        
        self.tt_style_combo = QComboBox()
        self.tt_style_combo.addItem("実線", "solid")
        self.tt_style_combo.addItem("破線", "dashed")
        self.tt_style_combo.addItem("点線", "dotted")
        self.tt_style_combo.currentIndexChanged.connect(self._on_train_type_form_changed)
        
        self.tt_line_style_layout.addWidget(self.tt_weight_combo)
        self.tt_line_style_layout.addWidget(self.tt_style_combo)
        self.tt_form_layout.addRow("線のスタイル:", self.tt_line_style_layout)

        self.line_sample_widget = LineSampleWidget()
        self.tt_form_layout.addRow("プレビュー", self.line_sample_widget)
        
        self.tt_editor_layout.addWidget(self.tt_form_container)
        self.tt_editor_layout.addStretch()

        # 最下部に複製ボタンを追加
        self.duplicate_tt_button = QPushButton("この種別のコピーを作成")
        self.duplicate_tt_button.setFixedWidth(200)
        self.duplicate_tt_button.clicked.connect(self._on_duplicate_train_type)
        self.tt_editor_layout.addWidget(self.duplicate_tt_button, alignment=Qt.AlignRight)

        self.tt_right_stack.addWidget(self.tt_editor_page)

        # プレースホルダー
        self.tt_placeholder_page = QWidget()
        self.tt_placeholder_layout = QVBoxLayout(self.tt_placeholder_page)
        self.tt_empty_label = QLabel("種別を追加してください")
        self.tt_empty_label.setAlignment(Qt.AlignCenter)
        self.tt_empty_label.setStyleSheet("color: #888888; font-size: 18px;")
        self.tt_placeholder_layout.addWidget(self.tt_empty_label)
        
        self.tt_right_stack.addWidget(self.tt_placeholder_page)

        # 初期状態の設定
        self._set_tt_form_enabled(False)

        # 初期リスト表示
        self._populate_train_type_list()

        # 種別があれば最初を選択
        # 種別があれば最初を選択
        if self.train_type_list_widget.count() > 0:
            self.train_type_list_widget.setCurrentRow(0)

    def _on_train_types_reordered(self, parent, start, end, destination, row):
        """並び替えられた列車種別リストの状態をプロジェクトデータに反映する"""
        new_order = []
        for i in range(self.train_type_list_widget.count()):
            item = self.train_type_list_widget.item(i)
            new_order.append(item.data(Qt.UserRole))
        
        self.project.train_types_order = new_order
        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)

    def _on_train_type_selected(self):
        """リストで種別が選択された際にフォームの内容を更新する"""
        selected_items = self.train_type_list_widget.selectedItems()
        if not selected_items:
            self._set_tt_form_enabled(False)
            return

        tt_id = selected_items[0].data(Qt.UserRole)
        tt_data = self.project.train_types.get(tt_id)
        if not tt_data:
            self._set_tt_form_enabled(False)
            return

        self._set_tt_form_enabled(True)
        
        # UI更新中のシグナルをブロック
        self.tt_name_edit.blockSignals(True)
        self.tt_nickname_edit.blockSignals(True)
        self.tt_short_name_edit.blockSignals(True)
        self.tt_in_service_check.blockSignals(True)
        self.tt_weight_combo.blockSignals(True)
        self.tt_style_combo.blockSignals(True)
        self.duplicate_tt_button.setEnabled(True)

        self.tt_name_edit.setText(tt_data.get("train_type_name", ""))
        self.tt_nickname_edit.setText(tt_data.get("train_name") or "")
        self.tt_short_name_edit.setText(tt_data.get("train_type_short_name", ""))
        self.tt_in_service_check.setChecked(tt_data.get("is_in_service", True))
        
        main_color = tt_data.get("main_color", "#333333")
        self.tt_main_color_btn.setText(main_color)
        self.tt_main_color_square.setPixmap(create_color_square_pixmap(main_color))
        
        bg_color = tt_data.get("background_color", "#ffffff")
        self.tt_bg_color_btn.setText(bg_color)
        self.tt_bg_color_square.setPixmap(create_color_square_pixmap(bg_color))
        
        weight = tt_data.get("line_weight", "normal")
        idx_w = self.tt_weight_combo.findData(weight)
        self.tt_weight_combo.setCurrentIndex(idx_w if idx_w >= 0 else 0)
        
        style = tt_data.get("line_style", "solid")
        idx_s = self.tt_style_combo.findData(style)
        self.tt_style_combo.setCurrentIndex(idx_s if idx_s >= 0 else 0)

        self.tt_name_edit.blockSignals(False)
        self.tt_nickname_edit.blockSignals(False)
        self.tt_short_name_edit.blockSignals(False)
        self.tt_in_service_check.blockSignals(False)
        self.tt_weight_combo.blockSignals(False)
        self.tt_style_combo.blockSignals(False)
        self.duplicate_tt_button.setEnabled(True)
        
        self._update_line_sample()

    def _on_train_type_form_changed(self):
        """フォームの内容が変更された際にプロジェクトデータとリスト表示を更新する"""
        selected_items = self.train_type_list_widget.selectedItems()
        if not selected_items: return
        tt_id = selected_items[0].data(Qt.UserRole)
        tt_data = self.project.train_types.get(tt_id)
        if not tt_data: return
        
        tt_data["train_type_name"] = self.tt_name_edit.text()
        nickname = self.tt_nickname_edit.text().strip()
        tt_data["train_name"] = nickname if nickname else None
        tt_data["train_type_short_name"] = self.tt_short_name_edit.text()
        tt_data["is_in_service"] = self.tt_in_service_check.isChecked()
        tt_data["line_weight"] = self.tt_weight_combo.currentData()
        tt_data["line_style"] = self.tt_style_combo.currentData()
        
        self._update_line_sample()
        
        # リストの再描画のためにアイテムのテキストを再セット
        name = tt_data["train_type_name"]
        train_name = tt_data["train_name"]
        display_name = f"{name} {train_name}" if train_name else name
        main_color = tt_data.get("main_color", "#333333")
        html_text = f"<font color='{main_color}'>{display_name}</font>"
        selected_items[0].setText(html_text)
        
        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)

    def _on_pick_tt_main_color(self):
        """基本色の選択ダイアログを表示する"""
        selected_items = self.train_type_list_widget.selectedItems()
        if not selected_items: return
        tt_id = selected_items[0].data(Qt.UserRole)
        tt_data = self.project.train_types.get(tt_id)
        
        color = QColorDialog.getColor(QColor(tt_data.get("main_color", "#333333")), self)
        if color.isValid():
            new_hex = color.name()
            tt_data["main_color"] = new_hex
            self.tt_main_color_btn.setText(new_hex)
            self.tt_main_color_square.setPixmap(create_color_square_pixmap(new_hex))
            self._on_train_type_form_changed()

    def _on_pick_tt_bg_color(self):
        """背景色の選択ダイアログを表示する"""
        selected_items = self.train_type_list_widget.selectedItems()
        if not selected_items: return
        tt_id = selected_items[0].data(Qt.UserRole)
        tt_data = self.project.train_types.get(tt_id)
        
        color = QColorDialog.getColor(QColor(tt_data.get("background_color", "#ffffff")), self)
        if color.isValid():
            new_hex = color.name()
            tt_data["background_color"] = new_hex
            self.tt_bg_color_btn.setText(new_hex)
            self.tt_bg_color_square.setPixmap(create_color_square_pixmap(new_hex))
            selected_items[0].setBackground(QColor(new_hex))
            self._on_train_type_form_changed()

    def _populate_train_type_list(self):
        """列車種別の一覧をリストに表示する"""
        self.train_type_list_widget.clear()
        for tt_id in self.project.train_types_order:
            tt = self.project.train_types[tt_id]
            name = tt.get("train_type_name", "")
            train_name = tt.get("train_name")
            display_name = f"{name} {train_name}" if train_name else name

            main_color = tt.get("main_color", "#333333")
            bg_color = tt.get("background_color", "#ffffff")

            # 文字色を反映したHTMLテキストを生成
            html_text = f"<font color='{main_color}'>{display_name}</font>"
            
            item = QListWidgetItem(html_text)
            item.setData(Qt.UserRole, tt_id)
            item.setBackground(QColor(bg_color))
            self.train_type_list_widget.addItem(item)

    def _on_add_train_type(self):
        """「種別の追加」ダイアログを表示し、データを生成する"""
        dialog = AddTrainTypeDialog(self)
        if dialog.exec() == QDialog.Accepted:
            # ランダムな10文字のIDを生成
            chars = string.ascii_letters + string.digits
            while True:
                new_id = ''.join(random.choices(chars, k=10))
                if new_id not in self.project.train_types:
                    break

            nickname = dialog.nickname_edit.text().strip()
            new_type = {
                "train_type_id": new_id,
                "train_type_name": dialog.name_edit.text().strip(),
                "train_type_short_name": dialog.short_name_edit.text().strip(),
                "train_name": nickname if nickname else None,
                "is_in_service": True,
                "main_color": "#333333",
                "background_color": "#ffffff",
                "line_weight": "normal",
                "line_style": "solid"
            }
            
            self.project.train_types[new_id] = new_type
            self.project.train_types_order.append(new_id)
            
            self._populate_train_type_list()
            
            # 新しく追加された種別を選択
            for i in range(self.train_type_list_widget.count()):
                if self.train_type_list_widget.item(i).data(Qt.UserRole) == new_id:
                    self.train_type_list_widget.setCurrentRow(i)
                    break

            if hasattr(self.parent(), "set_modified"):
                self.parent().set_modified(True)

    def _on_duplicate_train_type(self):
        """現在選択中の列車種別のコピーを作成する"""
        selected_items = self.train_type_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "エラー", "複製する列車種別を選択してください。")
            return

        original_tt_id = selected_items[0].data(Qt.UserRole)
        original_tt_data = self.project.train_types.get(original_tt_id)
        if not original_tt_data:
            QMessageBox.warning(self, "エラー", "選択された列車種別データが見つかりません。")
            return

        # 新しいIDを生成
        chars = string.ascii_letters + string.digits
        while True:
            new_id = ''.join(random.choices(chars, k=10))
            if new_id not in self.project.train_types:
                break

        # データを複製し、IDと名前を更新
        new_type = original_tt_data.copy()
        new_type["train_type_id"] = new_id
        new_type["train_type_name"] = f"(コピー) {original_tt_data.get('train_type_name', '')}"

        self.project.train_types[new_id] = new_type
        self.project.train_types_order.append(new_id)

        self._populate_train_type_list()
        self.train_type_list_widget.setCurrentRow(self.train_type_list_widget.count() - 1) # 新しい項目を選択
        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)

    def _update_line_sample(self):
        """線のサンプルウィジェットを現在の設定で更新する"""
        selected_items = self.train_type_list_widget.selectedItems()
        if not selected_items: return
        tt_id = selected_items[0].data(Qt.UserRole)
        tt_data = self.project.train_types.get(tt_id)
        
        self.line_sample_widget.set_line_properties(
            tt_data.get("main_color", "#333333"),
            tt_data.get("line_weight", "normal"),
            tt_data.get("line_style", "solid")
        )

    def _set_tt_form_enabled(self, enabled):
        """右側フォームの表示・非表示を切り替える"""
        if enabled:
            self.tt_right_stack.setCurrentWidget(self.tt_editor_page)
        else:
            self.tt_right_stack.setCurrentWidget(self.tt_placeholder_page)


# 運行系統の追加ダイアログ
class AddRouteDialog(QDialog):
    def __init__(self, parent, project: OptDiaProject):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("運行系統の追加")
        self.setFixedSize(400, 240)

        layout = QVBoxLayout(self)

        # 運行系統ID
        layout.addWidget(QLabel("運行系統ID:"))
        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("例) midosuji_namboku")
        self.id_edit.textChanged.connect(self._clear_id_error)
        layout.addWidget(self.id_edit)

        # 警告表示スペース
        self.warning_label = QLabel("")
        self.warning_label.setStyleSheet("color: red; padding-left: 5px;")
        layout.addWidget(self.warning_label)

        # 運行系統名
        layout.addWidget(QLabel("運行系統名:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例) 御堂筋線・南北線系統")
        layout.addWidget(self.name_edit)

        layout.addStretch()

        # ボタンエリア
        button_layout = QHBoxLayout()
        self.add_button = QPushButton("追加")
        self.cancel_button = QPushButton("キャンセル")
        button_layout.addStretch()
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.add_button.clicked.connect(self._on_add_clicked)
        self.cancel_button.clicked.connect(self.reject)

    def _clear_id_error(self):
        self.id_edit.setStyleSheet("")
        self.warning_label.setText("")

    def _on_add_clicked(self):
        route_id = self.id_edit.text().strip()
        if not route_id:
            self.warning_label.setText("IDを指定してください")
            self.id_edit.setStyleSheet("background-color: #ffeeee;")
            return
        if not re.match(r"^[a-zA-Z0-9_]+$", route_id):
            self.warning_label.setText("IDには半角英数字とアンダーバーのみが使用可能です")
            self.id_edit.setStyleSheet("background-color: #ffeeee;")
            return
        if route_id in self.project.routes:
            self.warning_label.setText("既に使用されているIDです")
            self.id_edit.setStyleSheet("background-color: #ffeeee;")
            return
        self.accept()


# 路線と区間の選択ダイアログ
class SelectSegmentDialog(QDialog):
    def __init__(self, parent, project: OptDiaProject, is_add=True, 
                 initial_line=None, initial_start=None, initial_end=None):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("路線と区間の選択")
        self.setFixedSize(480, 240)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # 路線選択
        self.line_combo = QComboBox()
        self.line_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for lid in self.project.lines_order:
            line = self.project.lines[lid]
            if len(line.get("station_list", [])) >= 2:
                self.line_combo.addItem(line.get("line_name", lid), lid)
        
        form_layout.addRow("路線:", self.line_combo)

        # 区間選択 (始点 〜 終点)
        station_layout = QHBoxLayout()
        station_layout.setContentsMargins(0, 0, 0, 0)
        self.start_combo = QComboBox()
        self.end_combo = QComboBox()
        station_layout.addWidget(self.start_combo, 1)
        station_layout.addWidget(QLabel("〜"))
        station_layout.addWidget(self.end_combo, 1)
        form_layout.addRow("区間:", station_layout)

        # 起点と終点の反転
        self.invert_btn = QPushButton("起点と終点の反転")
        self.invert_btn.setStyleSheet("QPushButton { border: none; text-decoration: underline; background-color: transparent; }")
        self.invert_btn.setCursor(Qt.PointingHandCursor)
        self.invert_btn.clicked.connect(self._invert_stations)

        invert_container = QHBoxLayout()
        invert_container.setContentsMargins(0, 10, 0, 10)
        invert_container.addStretch()
        invert_container.addWidget(self.invert_btn)
        invert_container.addStretch()
        form_layout.addRow("", invert_container)

        layout.addLayout(form_layout)

        # 説明文
        desc_label = QLabel("区間を逆向きに設定することで、上り列車が別路線に下り列車として直通するような運行系統を設定できます")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(desc_label)

        layout.addStretch()

        # ボタンエリア
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.ok_button = QPushButton("追加" if is_add else "決定")
        self.cancel_button = QPushButton("キャンセル")
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.ok_button.clicked.connect(self._on_ok_clicked)
        self.cancel_button.clicked.connect(self.reject)

        self.line_combo.currentIndexChanged.connect(self._on_line_changed)

        # 初期値の設定
        if initial_line:
            idx = self.line_combo.findData(initial_line)
            if idx >= 0:
                self.line_combo.setCurrentIndex(idx)
        
        self._on_line_changed()

        if initial_start:
            idx = self.start_combo.findData(initial_start)
            if idx >= 0: self.start_combo.setCurrentIndex(idx)
        if initial_end:
            idx = self.end_combo.findData(initial_end)
            if idx >= 0: self.end_combo.setCurrentIndex(idx)

    def _on_line_changed(self):
        self.start_combo.clear()
        self.end_combo.clear()
        line_id = self.line_combo.currentData()
        if not line_id: return
        
        line_data = self.project.lines.get(line_id)
        for s_item in line_data.get("station_list", []):
            sid = s_item["station_id"]
            s_name = self.project.stations.get(sid, {}).get("station_name", sid)
            self.start_combo.addItem(s_name, sid)
            self.end_combo.addItem(s_name, sid)
        
        if self.start_combo.count() >= 2:
            self.end_combo.setCurrentIndex(self.end_combo.count() - 1)

    def _invert_stations(self):
        s_idx = self.start_combo.currentIndex()
        e_idx = self.end_combo.currentIndex()
        self.start_combo.setCurrentIndex(e_idx)
        self.end_combo.setCurrentIndex(s_idx)

    def get_data(self):
        return {
            "line_id": self.line_combo.currentData(),
            "start_station": self.start_combo.currentData(),
            "end_station": self.end_combo.currentData()
        }

    def _on_ok_clicked(self):
        """OK/追加ボタンが押された際のバリデーションと処理"""
        if self.start_combo.currentData() == self.end_combo.currentData():
            QMessageBox.warning(self, "エラー", "区間の起点と終点に同じ駅を設定することはできません。")
            return
        
        self.accept()


# 区間の分割ダイアログ
class SplitSegmentDialog(QDialog):
    def __init__(self, parent, project: OptDiaProject, line_id: str, start_sid: str, end_sid: str):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("区間の分割")
        self.setFixedSize(400, 150)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.station_combo = QComboBox()

        # 中間駅のリストアップ
        line_data = self.project.lines.get(line_id, {})
        station_ids = [s["station_id"] for s in line_data.get("station_list", [])]

        try:
            idx_start = station_ids.index(start_sid)
            idx_end = station_ids.index(end_sid)
        except ValueError:
            self.reject()
            return

        # 順方向か逆方向かでスライスを調整して中間駅を抽出
        if idx_start < idx_end:
            intermediate_ids = station_ids[idx_start + 1 : idx_end]
        else:
            intermediate_ids = station_ids[idx_start - 1 : idx_end : -1]

        for sid in intermediate_ids:
            s_name = self.project.stations.get(sid, {}).get("station_name", sid)
            self.station_combo.addItem(s_name, sid)

        form_layout.addRow("分割点とする駅:", self.station_combo)
        layout.addLayout(form_layout)
        layout.addStretch()

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.split_button = QPushButton("分割")
        self.cancel_button = QPushButton("キャンセル")
        button_layout.addWidget(self.split_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.split_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def get_selected_station_id(self):
        return self.station_combo.currentData()


# 運行系統編集ダイアログ
class RouteEditorDialog(QDialog):
    def __init__(self, parent, project: OptDiaProject, initial_route_id=None):
        super().__init__(parent)
        self.project = project
        self.initial_route_id = initial_route_id
        self.setWindowTitle("運行系統情報")
        self.setFixedSize(960, 640)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 左側のサイドバー (幅200px固定)
        sidebar = QWidget()
        sidebar.setObjectName("route_editor_sidebar")
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet("#route_editor_sidebar { background-color: #f7f7f7; border-right: 1px solid #dddddd; }")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        sidebar_layout.setSpacing(5)

        sidebar_layout.addWidget(QLabel("<b>運行系統一覧</b>"))

        # 運行系統リスト
        self.route_list_widget = QListWidget()
        self.route_list_widget.setStyleSheet("font-size: 14px;")
        self.route_list_widget.setDragDropMode(QListWidget.InternalMove)
        self.route_list_widget.model().rowsMoved.connect(self._on_routes_reordered)
        self.route_list_widget.itemSelectionChanged.connect(self._on_route_selected)
        sidebar_layout.addWidget(self.route_list_widget)

        # 運行系統追加ボタン
        self.add_route_button = QPushButton("運行系統の追加")
        self.add_route_button.clicked.connect(self._on_add_route)
        sidebar_layout.addWidget(self.add_route_button)

        sidebar_layout.addSpacing(10)
        desc_label = QLabel("運行系統や路線の区間はドラッグ操作で並び替え可能です")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #888888; font-size: 12px;")
        sidebar_layout.addWidget(desc_label)

        main_layout.addWidget(sidebar)

        # 右側のスタックドウィジェット
        self.right_stack = QStackedWidget()
        main_layout.addWidget(self.right_stack)

        # 1. プレースホルダーページ (データなし)
        self.placeholder_page = QWidget()
        placeholder_layout = QVBoxLayout(self.placeholder_page)
        placeholder_label = QLabel("運行系統を追加してください")
        placeholder_label.setAlignment(Qt.AlignCenter)
        placeholder_label.setStyleSheet("color: #888888; font-size: 18px;")
        placeholder_layout.addWidget(placeholder_label)
        self.right_stack.addWidget(self.placeholder_page)

        # 2. 運行系統編集フォームページ
        self.edit_form_page = QWidget()
        edit_form_layout = QHBoxLayout(self.edit_form_page)
        edit_form_layout.setContentsMargins(0, 0, 0, 0)
        edit_form_layout.setSpacing(0)

        # メイン編集エリア (左側)
        self.form_main_area = QWidget()
        self.form_main_layout = QVBoxLayout(self.form_main_area)
        self.form_main_layout.setContentsMargins(20, 20, 20, 20)
        self.form_main_layout.setSpacing(10)

        # 運行系統基本情報 (IDと名称)
        route_info_form = QFormLayout()
        self.route_id_edit = QLineEdit()
        self.route_id_edit.setReadOnly(True)
        self.route_id_edit.setStyleSheet("background-color: #eeeeee; color: #888888;")
        route_info_form.addRow("運行系統ID(変更不可):", self.route_id_edit)

        self.route_name_edit = QLineEdit()
        self.route_name_edit.textChanged.connect(self._on_route_name_changed)
        route_info_form.addRow("運行系統名:", self.route_name_edit)
        self.form_main_layout.addLayout(route_info_form)

        # 含まれる路線とその区間
        self.form_main_layout.addSpacing(10)
        self.form_main_layout.addWidget(QLabel("<b>含まれる路線とその区間</b>"))

        # カラムヘッダー
        seg_header_layout = QHBoxLayout()
        # 余白を削除
        seg_header_layout.setContentsMargins(0, 0, 0, 0)
        # 色バー用のスペース（アラインメント維持用）
        header_spacer = QWidget()
        header_spacer.setFixedWidth(10)
        seg_header_layout.addWidget(header_spacer)
        line_header = QLabel("路線名")
        line_header.setFixedWidth(140)
        line_header.setAlignment(Qt.AlignCenter)
        seg_header_layout.addWidget(line_header)
        segment_header = QLabel("区間")
        segment_header.setAlignment(Qt.AlignCenter)
        seg_header_layout.addWidget(segment_header, stretch=1)
        operation_header = QLabel("操作")
        operation_header.setFixedWidth(154) # ボタン3つ(50*3) + 間隔(2*2)
        operation_header.setAlignment(Qt.AlignCenter)
        seg_header_layout.addWidget(operation_header)
        self.form_main_layout.addLayout(seg_header_layout)

        # ヘッダー下部の境界線
        header_border = QWidget()
        header_border.setFixedHeight(1)
        header_border.setStyleSheet("background-color: #cccccc;")
        self.form_main_layout.addWidget(header_border)

        # 部分区間リスト
        self.segment_list_widget = QListWidget()
        self.segment_list_widget.setDragDropMode(QListWidget.InternalMove)
        # 並び替え操作を維持しつつ、選択ハイライトを無効化し、ホバー時のみ背景色を表示する
        self.segment_list_widget.setFocusPolicy(Qt.NoFocus)
        self.segment_list_widget.setStyleSheet(
            "QListWidget { border: none; background-color: transparent; }"
            "QListWidget::item:hover { background-color: #dddddd; }"
            "QListWidget::item:selected { background-color: transparent; }"
            "QListWidget::item:selected:hover { background-color: #dddddd; }"
        )
        self.segment_list_widget.model().rowsMoved.connect(self._on_segments_reordered)
        self.form_main_layout.addWidget(self.segment_list_widget)

        # 区間追加ボタン
        self.add_segment_button = QPushButton("路線の区間を追加")
        self.add_segment_button.clicked.connect(self._on_add_segment)
        self.form_main_layout.addWidget(self.add_segment_button)

        edit_form_layout.addWidget(self.form_main_area, stretch=1)

        # 駅順序プレビュー領域 (右側 220px)
        self.station_preview_area = QScrollArea()
        self.station_preview_area.setFixedWidth(220)
        self.station_preview_area.setWidgetResizable(True)
        self.station_preview_area.setStyleSheet("QScrollArea { border: none; border-left: 1px solid #dddddd; }")
        
        self.station_preview_content = QWidget()
        self.station_preview_layout = QVBoxLayout(self.station_preview_content)
        self.station_preview_layout.setContentsMargins(10, 10, 10, 10)
        self.station_preview_layout.setSpacing(0)

        # 駅順序プレビューの見出し
        lbl_preview = QLabel("駅順序プレビュー")
        lbl_preview.setStyleSheet("font-size: 14px; border: none;")
        self.station_preview_layout.addWidget(lbl_preview)
        
        self.direction_label = QLabel("下り列車の通過順で表示中")
        self.direction_label.setStyleSheet("font-size: 12px; color: #888888; padding-top: 10px; padding-bottom: 20px;")
        self.station_preview_layout.addWidget(self.direction_label)

        self.station_preview_layout.addStretch() # 内容を上部に寄せる

        self.station_preview_area.setWidget(self.station_preview_content)
        edit_form_layout.addWidget(self.station_preview_area)

        self.right_stack.addWidget(self.edit_form_page)

        # 初期リスト表示と表示切り替え
        self._populate_route_list()

    def _populate_route_list(self):
        self.route_list_widget.clear()
        initial_row = 0
        for i, rid in enumerate(self.project.routes_order):
            route = self.project.routes[rid]
            item = QListWidgetItem(route.get("route_name", rid))
            item.setData(Qt.UserRole, rid)
            self.route_list_widget.addItem(item)
            if rid == self.initial_route_id:
                initial_row = i
        
        if self.route_list_widget.count() > 0:
            self.right_stack.setCurrentWidget(self.edit_form_page)
            self.route_list_widget.setCurrentRow(initial_row)
        else:
            self.right_stack.setCurrentWidget(self.placeholder_page)

    def _on_routes_reordered(self, parent, start, end, destination, row):
        """運行系統の並び替えをプロジェクトデータに反映する"""
        new_order = []
        for i in range(self.route_list_widget.count()):
            item = self.route_list_widget.item(i)
            new_order.append(item.data(Qt.UserRole))
        
        self.project.routes_order = new_order
        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)

    def _on_route_selected(self):
        """運行系統の選択が変更されたときの処理"""
        selected = self.route_list_widget.selectedItems()
        if not selected:
            self.route_id_edit.clear()
            self.route_name_edit.clear()
            self.segment_list_widget.clear()
            return

        route_id = selected[0].data(Qt.UserRole)
        route_data = self.project.routes.get(route_id)
        if not route_data:
            return

        # シグナルをブロックして更新
        self.route_name_edit.blockSignals(True)
        self.route_id_edit.setText(route_id)
        self.route_name_edit.setText(route_data.get("route_name", ""))
        self.route_name_edit.blockSignals(False)

        self._populate_segment_list(route_data)
        self._populate_station_preview(route_data)

    def _on_route_name_changed(self, text: str):
        """名称が変更されたときにプロジェクトデータとサイドバーを更新する"""
        route_id = self.route_id_edit.text()
        if not route_id or route_id not in self.project.routes:
            return
        
        self.project.routes[route_id]["route_name"] = text
        
        # サイドバーのテキストを更新
        selected = self.route_list_widget.selectedItems()
        if selected and selected[0].data(Qt.UserRole) == route_id:
            selected[0].setText(text)

        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)

    def _get_stations_in_segment(self, line_id, start_station_id, end_station_id):
        """指定された路線の区間に含まれる駅のIDリストを順序通りに返す"""
        line_data = self.project.lines.get(line_id)
        if not line_data:
            return []

        line_station_ids = [s["station_id"] for s in line_data.get("station_list", [])]

        try:
            idx_start = line_station_ids.index(start_station_id)
            idx_end = line_station_ids.index(end_station_id)
        except ValueError:
            return [] # 路線で駅が見つからない場合

        stations_in_segment = []
        if idx_start <= idx_end:
            # 順向き
            for i in range(idx_start, idx_end + 1):
                stations_in_segment.append(line_station_ids[i])
        else:
            # 逆向き
            for i in range(idx_start, idx_end - 1, -1): # range(start, stop, step) -> stop is exclusive
                stations_in_segment.append(line_station_ids[i])
        
        return stations_in_segment

    def _populate_station_preview(self, route_data: dict):
        """駅順序プレビューエリアに駅のリストを表示する"""
        # 既存の動的に追加された駅アイテムとストレッチアイテムを削除
        # 見出しとdirection_labelは残すため、インデックス2から逆順に削除
        for i in reversed(range(2, self.station_preview_layout.count())):
            item = self.station_preview_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()
            self.station_preview_layout.removeItem(item)

        segments = route_data.get("line_segments", [])
        
        for seg in segments:
            line_id = seg.get("line_id")
            # line_colorが取得できない場合はデフォルト色を設定
            line_color = self.project.lines.get(line_id, {}).get("line_color", "#333333")
            start_sid = seg.get("start_station")
            end_sid = seg.get("end_station")

            stations_in_this_segment = self._get_stations_in_segment(line_id, start_sid, end_sid)
            
            line_color = self.project.lines.get(line_id, {}).get("line_color", "#333333")
            # 駅番号取得用のリストを取得
            line_station_list = self.project.lines.get(line_id, {}).get("station_list", [])

            for i, sid in enumerate(stations_in_this_segment):
                station_name = self.project.stations.get(sid, {}).get("station_name", sid)

                # 駅番号を取得して駅名の前に付加
                ls_item = next((s for s in line_station_list if s.get("station_id") == sid), None)
                s_num = ls_item.get("station_number") if ls_item else None
                display_name = f"[{s_num}] {station_name}" if s_num else station_name

                if sid == start_sid and i == 0:
                    display_name += " <span style='font-size: 12px; color: gray; font-weight: normal;'>(発)</span>"
                elif sid == end_sid and i == len(stations_in_this_segment) - 1:
                    display_name += " <span style='font-size: 12px; color: gray; font-weight: normal;'>(着)</span>"
                
                station_line_widget = QWidget()
                station_line_widget.setFixedHeight(40) # 行の高さを40pxに設定
                station_line_widget.setProperty("is_preview_station_item", True) # 削除対象を識別
                station_line_layout = QHBoxLayout(station_line_widget) # 5pxのスペースを設ける
                station_line_layout.setContentsMargins(0, 0, 0, 0)
                station_line_layout.setSpacing(5)

                color_bar = QLabel()
                color_bar.setFixedWidth(5)
                color_bar.setStyleSheet(f"background-color: {line_color};")
                station_line_layout.addWidget(color_bar)

                station_label = QLabel(display_name)
                
                # 駅の表示スタイルを設定
                station_data = self.project.stations.get(sid, {})
                if station_data.get("is_signal_station", False):
                    # 信号場は灰色
                    station_label.setStyleSheet("color: gray;")
                elif station_data.get("is_major_station", False):
                    # 主要駅は太字
                    font = station_label.font()
                    font.setBold(True)
                    station_label.setFont(font)
                else:
                    # デフォルトのスタイルに戻す
                    station_label.setStyleSheet("")
                    station_label.setFont(QFont()) # 太字を解除
                
                station_line_layout.addWidget(station_label)
                station_line_layout.addStretch()

                self.station_preview_layout.addWidget(station_line_widget)
        self.station_preview_layout.addStretch() # 最後にストレッチを追加

        if not segments:
            self.direction_label.setText("表示する駅がありません\n路線の区間を追加してください")
        else:
            self.direction_label.setText("下り列車の通過順で表示中")
    def _populate_segment_list(self, route_data: dict):
        """選択された系統に含まれる路線の部分区間リストを表示する"""
        self.segment_list_widget.clear()
        segments = route_data.get("line_segments") or []
        
        for i, seg in enumerate(segments):
            item_widget = QWidget()
            item_layout = QHBoxLayout(item_widget) # 上下に10pxの余白を設ける
            item_layout.setContentsMargins(0, 10, 0, 10)
            
            # 路線名
            line_id = seg.get("line_id")
            line_color = self.project.lines.get(line_id, {}).get("line_color", "#333333")
            line_name = self.project.lines.get(line_id, {}).get("line_name", line_id)

            # 色バー
            color_bar = QLabel()
            color_bar.setFixedWidth(10)
            color_bar.setStyleSheet(f"background-color: {line_color};")
            item_layout.addWidget(color_bar)

            line_label = QLabel(line_name)
            line_label.setFixedWidth(140)
            line_label.setAlignment(Qt.AlignCenter)
            item_layout.addWidget(line_label)
            
            # 区間 (始点駅-終点駅)
            start_sid = seg.get("start_station")
            end_sid = seg.get("end_station")
            start_name = self.project.stations.get(start_sid, {}).get("station_name", start_sid)
            end_name = self.project.stations.get(end_sid, {}).get("station_name", end_sid)
            segment_label = QLabel(f"{start_name} - {end_name}")
            segment_label.setAlignment(Qt.AlignCenter)
            item_layout.addWidget(segment_label, stretch=1)
            
            # 操作ボタン
            btn_layout = QHBoxLayout()
            btn_layout.setContentsMargins(0, 0, 0, 0)
            btn_layout.setSpacing(2)
            btn_edit = QPushButton("編集")
            btn_edit.setFixedSize(50, 30)
            btn_edit.clicked.connect(lambda _, s=seg, idx=i: self._on_edit_segment(s, idx))
            btn_split = QPushButton("分割")
            btn_split.setFixedSize(50, 30)
            btn_split.clicked.connect(lambda _, s=seg, idx=i: self._on_split_segment(s, idx))
            btn_delete = QPushButton("削除")
            btn_delete.setFixedSize(50, 30)
            btn_delete.clicked.connect(lambda _, idx=i: self._on_delete_segment(idx))
            btn_layout.addWidget(btn_edit)
            btn_layout.addWidget(btn_split)
            btn_layout.addWidget(btn_delete)
            item_layout.addLayout(btn_layout, stretch=0)
            
            list_item = QListWidgetItem()
            # ドラッグ＆ドロップ後にデータを復元するため、セグメントの辞書データを保持
            list_item.setData(Qt.UserRole, seg)
            list_item.setSizeHint(item_widget.sizeHint())
            self.segment_list_widget.addItem(list_item)
            self.segment_list_widget.setItemWidget(list_item, item_widget)
        self.segment_list_widget.update()

    def _on_segments_reordered(self, parent, start, end, destination, row):
        """路線の区間の並び替えをプロジェクトデータに反映する"""
        selected = self.route_list_widget.selectedItems()
        if not selected:
            return
        route_id = selected[0].data(Qt.UserRole)
        route_data = self.project.routes.get(route_id)
        if not route_data:
            return

        new_segments = []
        for i in range(self.segment_list_widget.count()):
            item = self.segment_list_widget.item(i)
            new_segments.append(item.data(Qt.UserRole))
        
        route_data["line_segments"] = new_segments
        
        # 操作ボタンのクロージャが参照するインデックスを正しく更新するためにリストを再描画
        self._populate_segment_list(route_data)
        self._populate_station_preview(route_data) # プレビューの更新

        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)

    def _on_add_route(self):
        """運行系統の追加ダイアログを表示し、データを追加する"""
        dialog = AddRouteDialog(self, self.project)
        if dialog.exec() == QDialog.Accepted:
            route_id = dialog.id_edit.text().strip()
            route_name = dialog.name_edit.text().strip()

            # プロジェクトデータに新規運行系統を追加
            self.project.routes[route_id] = {
                "route_id": route_id,
                "route_name": route_name,
                "line_segments" : [],
                "trains_by_diagram": {}
            }
            self.project.routes_order.append(route_id)

            # リスト表示を更新
            self._populate_route_list()

            # 新しく追加された項目を選択状態にする
            for i in range(self.route_list_widget.count()):
                if self.route_list_widget.item(i).text() == route_name:
                    self.route_list_widget.setCurrentRow(i)
                    break

            # 変更フラグを立てる (MainWindow)
            if hasattr(self.parent(), "set_modified"):
                self.parent().set_modified(True)

    def _on_add_segment(self):
        """路線の区間追加ダイアログを表示し、データを追加する"""
        valid_line_ids = [lid for lid in self.project.lines_order if len(self.project.lines[lid].get("station_list", [])) >= 2]
        if not valid_line_ids:
            QMessageBox.warning(self, "情報", "追加可能な路線がありません")
            return

        dialog = SelectSegmentDialog(self, self.project, is_add=True)
        if dialog.exec() == QDialog.Accepted:
            selected = self.route_list_widget.selectedItems()
            if not selected: return
            route_id = selected[0].data(Qt.UserRole)
            route_data = self.project.routes.get(route_id)
            
            route_data["line_segments"].append(dialog.get_data())
            self._populate_segment_list(route_data)
            self._populate_station_preview(route_data) # プレビューの更新
            if hasattr(self.parent(), "set_modified"):
                self.parent().set_modified(True)

    def _on_edit_segment(self, segment_data, index):
        """路線の区間編集ダイアログを表示し、データを更新する"""
        dialog = SelectSegmentDialog(self, self.project, is_add=False, 
                                     initial_line=segment_data.get("line_id"),
                                     initial_start=segment_data.get("start_station"),
                                     initial_end=segment_data.get("end_station"))
        if dialog.exec() == QDialog.Accepted:
            selected = self.route_list_widget.selectedItems()
            if not selected: return
            route_id = selected[0].data(Qt.UserRole)
            route_data = self.project.routes.get(route_id)
            
            route_data["line_segments"][index] = dialog.get_data()
            self._populate_segment_list(route_data)
            self._populate_station_preview(route_data) # プレビューの更新
            if hasattr(self.parent(), "set_modified"):
                self.parent().set_modified(True)

    def _on_split_segment(self, segment_data, index):
        """路線の区間を分割するダイアログを表示し、データを更新する"""
        line_id = segment_data.get("line_id")
        start_sid = segment_data.get("start_station")
        end_sid = segment_data.get("end_station")
        
        line_data = self.project.lines.get(line_id, {})
        station_ids = [s["station_id"] for s in line_data.get("station_list", [])]
        
        try:
            idx_start = station_ids.index(start_sid)
            idx_end = station_ids.index(end_sid)
        except ValueError:
            return

        # 駅数が3駅未満（隣接駅など）の場合は分割不可
        if abs(idx_start - idx_end) < 2:
            QMessageBox.information(self, "情報", "この区間はこれ以上分割できません")
            return
            
        dialog = SplitSegmentDialog(self, self.project, line_id, start_sid, end_sid)
        if dialog.exec() == QDialog.Accepted:
            split_sid = dialog.get_selected_station_id()
            
            selected = self.route_list_widget.selectedItems()
            if not selected: return
            route_id = selected[0].data(Qt.UserRole)
            route_data = self.project.routes.get(route_id)
            
            # 分割処理：元の要素を削除し、新しい2つの区間を挿入
            route_data["line_segments"].pop(index)
            route_data["line_segments"].insert(index, {"line_id": line_id, "start_station": start_sid, "end_station": split_sid})
            route_data["line_segments"].insert(index + 1, {"line_id": line_id, "start_station": split_sid, "end_station": end_sid})
            
            self._populate_segment_list(route_data)
            self._populate_station_preview(route_data) # プレビューの更新
            if hasattr(self.parent(), "set_modified"):
                self.parent().set_modified(True)

    def _on_delete_segment(self, index):
        """選択された区間を削除する"""
        selected = self.route_list_widget.selectedItems()
        if not selected: return
        route_id = selected[0].data(Qt.UserRole)
        route_data = self.project.routes.get(route_id)
        if route_data and 0 <= index < len(route_data["line_segments"]):
            route_data["line_segments"].pop(index)
            self._populate_segment_list(route_data)
            self._populate_station_preview(route_data) # プレビューの更新
            if hasattr(self.parent(), "set_modified"):
                self.parent().set_modified(True)


# 運転ダイヤ情報編集ダイアログ
class DiagramEditorDialog(QDialog):
    def __init__(self, parent, project: OptDiaProject, initial_diagram_id=None):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("運転ダイヤ情報")
        self.setFixedSize(640, 480)
        self.initial_diagram_id = initial_diagram_id

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 左側のサイドバー (幅220px固定)
        sidebar = QWidget()
        sidebar.setObjectName("diagram_editor_sidebar")
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet("#diagram_editor_sidebar { background-color: #f7f7f7; border-right: 1px solid #dddddd; }")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        sidebar_layout.setSpacing(5)

        sidebar_layout.addWidget(QLabel("<b>ダイヤの一覧</b>"))

        # ダイヤリスト
        self.diagram_list_widget = QListWidget()
        self.diagram_list_widget.setDragDropMode(QListWidget.InternalMove)
        self.diagram_list_widget.model().rowsMoved.connect(self._on_diagrams_reordered)
        sidebar_layout.addWidget(self.diagram_list_widget)

        # ダイヤ追加ボタン
        self.add_diagram_button = QPushButton("ダイヤの追加")
        # 動作はまだ設定しない
        sidebar_layout.addWidget(self.add_diagram_button)

        main_layout.addWidget(sidebar)

        # 右側のスペース (まだ実装しない)
        self.right_area = QWidget()
        main_layout.addWidget(self.right_area, stretch=1)

        self._populate_diagram_list()

    def _populate_diagram_list(self):
        """プロジェクトに登録されている運転ダイヤをリストに表示する"""
        self.diagram_list_widget.clear()
        initial_row = 0
        for i, did in enumerate(self.project.diagrams_order):
            diag = self.project.diagrams[did]
            item = QListWidgetItem(diag.get("diagram_name", did))
            item.setData(Qt.UserRole, did)
            bg_color = diag.get("background_color", "#ffffff")
            item.setBackground(QColor(bg_color))
            self.diagram_list_widget.addItem(item)
            if did == self.initial_diagram_id:
                initial_row = i
        
        if self.diagram_list_widget.count() > 0:
            self.diagram_list_widget.setCurrentRow(initial_row)


    def _on_diagrams_reordered(self, parent, start, end, destination, row):
        """並び替えられたダイヤリストの状態をプロジェクトデータに反映する"""
        new_order = []
        for i in range(self.diagram_list_widget.count()):
            item = self.diagram_list_widget.item(i)
            new_order.append(item.data(Qt.UserRole))
        
        self.project.diagrams_order = new_order
        # 親ウィンドウのmodifiedフラグを立てる
        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)


# アプリケーション情報ダイアログ
class AboutDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} について")
        self.setFixedSize(480, 320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 20)

        # アイコン
        icon_label = QLabel()
        icon_label.setPixmap(QIcon(":/assets/app_icon.ico").pixmap(128, 128))
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

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
        self.diagram_list_widget.setStyleSheet("font-size: 14px;")
        diagram_layout.addWidget(self.diagram_list_widget)

        # サイドバーの残りスペースを2等分するため、stretch=1 を指定
        sidebar_layout.addWidget(diagram_section, 1)

        # レイアウトにサイドバーを追加
        main_layout.addWidget(sidebar)
        
        # 右側のコンテンツ表示エリア (将来の拡張用)
        self.content_container = QWidget()
        main_layout.addWidget(self.content_container, stretch=1)

        # 初期リストの構築
        self._populate_route_list()
        self._populate_diagram_list()

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
            try:
                self.project = load_project(filepath)
                self.filepath = filepath
                self.set_modified(False)
                self._update_window_title()
                self._populate_route_list()
                self._populate_diagram_list()
            except Exception:
                QMessageBox.critical(self, "エラー", "このファイルは破損しています")
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
            self._update_window_title()

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

    def _on_edit_diagrams(self):
        """運転ダイヤ情報編集ウィンドウを表示する"""
        selected_items = self.diagram_list_widget.selectedItems()
        initial_diagram_id = selected_items[0].data(Qt.UserRole) if selected_items else None

        dialog = DiagramEditorDialog(self, self.project, initial_diagram_id)
        dialog.exec()
        self._populate_diagram_list()

    def _on_diagrams_reordered(self, parent, start, end, destination, row):
        """サイドバーでの運転ダイヤの並び替えをプロジェクトデータに反映する"""
        new_order = []
        for i in range(self.diagram_list_widget.count()):
            item = self.diagram_list_widget.item(i)
            new_order.append(item.data(Qt.UserRole))
        
        self.project.diagrams_order = new_order
        self.set_modified(True)


    def _on_routes_reordered(self, parent, start, end, destination, row):
        """サイドバーでの運行系統の並び替えをプロジェクトデータに反映する"""
        new_order = []
        for i in range(self.route_list_widget.count()):
            item = self.route_list_widget.item(i)
            new_order.append(item.data(Qt.UserRole))
        
        self.project.routes_order = new_order
        self.set_modified(True)


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
