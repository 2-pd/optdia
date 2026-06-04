#!/usr/bin/env python3
# coding: utf-8

import sys
import os
import re
import subprocess
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QColor, QPainter, QPixmap, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QMessageBox, QDialog, QLabel,
    QLineEdit, QTextEdit, QDialogButtonBox, QListWidget, QTabWidget,
    QListWidgetItem, QCheckBox, QColorDialog, QStackedWidget,
    QRadioButton, QComboBox, QGroupBox, QFormLayout, QSpinBox
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

        # 左側の垂直レイアウト (幅160px固定)
        left_panel = QWidget()
        left_panel.setFixedWidth(160)
        left_panel.setStyleSheet("background-color: #f7f7f7; border-right: 1px solid #dddddd;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(5)

        left_layout.addWidget(QLabel("<b>路線の一覧</b>"))
        
        # 路線リスト
        self.line_list_widget = QListWidget()
        self.line_list_widget.setDragDropMode(QListWidget.InternalMove)
        self.line_list_widget.itemSelectionChanged.connect(self._on_line_selected)
        self.line_list_widget.model().rowsMoved.connect(self._on_lines_reordered)
        left_layout.addWidget(self.line_list_widget)
        
        # 路線追加ボタン
        self.add_line_button = QPushButton("路線の追加")
        self.add_line_button.clicked.connect(self._on_add_line)
        left_layout.addWidget(self.add_line_button)

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
        station_left_panel.setFixedWidth(180)
        station_left_panel.setStyleSheet("background-color: #f7f7f7; border-right: 1px solid #dddddd;")
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

        # 各種チェックボックス
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
        bottom_base_info_layout.addLayout(left_vertical_layout)

        # 2つ目の垂直配置レイアウト
        right_vertical_layout = QVBoxLayout()
        right_vertical_layout.addWidget(QLabel("乗り場:"))
        self.track_list_widget = QListWidget()
        right_vertical_layout.addWidget(self.track_list_widget)
        self.add_track_button = QPushButton("乗り場の追加")
        self.add_track_button.clicked.connect(self._on_add_track) # 仮の接続
        right_vertical_layout.addWidget(self.add_track_button)
        bottom_base_info_layout.addLayout(right_vertical_layout)

        base_info_layout.addRow(bottom_base_info_layout)
        station_form_layout.addWidget(self.base_info_group)

        # 2つ目のQGroupBox: <路線名>に関連する駅情報
        self.line_station_group = QGroupBox("路線に関連する駅情報")
        line_station_layout = QFormLayout(self.line_station_group)
        self.station_number_edit = QLineEdit()
        self.station_number_edit.setFixedWidth(80)
        self.station_number_edit.textChanged.connect(self._on_line_station_info_changed)
        line_station_layout.addRow("駅番号:", self.station_number_edit)
        self.running_time_spin = QSpinBox()
        self.running_time_spin.setRange(0, 86400)
        self.running_time_spin.setSuffix(" 秒")
        self.running_time_spin.valueChanged.connect(self._on_line_station_info_changed)
        line_station_layout.addRow("起点駅からの基準運転時分:", self.running_time_spin)
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
            self.running_time_spin.setValue(0)

        self.station_name_edit.blockSignals(False)
        self.station_kana_edit.blockSignals(False)
        self.station_number_edit.blockSignals(False)
        self.running_time_spin.blockSignals(False)
        self.station_initial_edit.blockSignals(False)
        self.is_major_station_checkbox.blockSignals(False)
        self.is_signal_station_checkbox.blockSignals(False)
        self.show_arrival_time_checkbox.blockSignals(False)
        self.show_track_number_checkbox.blockSignals(False)

    def _populate_line_list(self):
        """プロジェクトに登録されている路線をリストに表示する"""
        self.line_list_widget.clear()
        for line_id in self.project.lines_order:
            line = self.project.lines[line_id]
            symbol = line.get("line_symbol") or ""
            name = line.get("line_name", "")
            display_text = f"[{symbol}] {name}" if symbol else name
            
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
        self.line_station_group.setTitle(f"{line_name}における駅情報")
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
            self.line_station_group.setTitle(f"{text}における駅情報")
            self._update_station_list_label(text)
            if hasattr(self.parent(), "set_modified"):
                self.parent().set_modified(True)
            # リストウィジェットの表示も更新
            selected_items = self.line_list_widget.selectedItems()
            if selected_items and selected_items[0].data(Qt.UserRole) == line_id:
                symbol = line_data.get("line_symbol") or ""
                name = line_data.get("line_name", "")
                display_text = f"[{symbol}] {name}" if symbol else name
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
                display_text = f"[{symbol}] {name}" if symbol else name
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
            self.project.lines[line_id] = self.project.lines[line_id] # Ensure it's added to the dict

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
        self.running_time_spin.setValue(rt if rt is not None else 0)

        self.station_initial_edit.setText(station_data.get("station_initial", "") or "")
        self.is_major_station_checkbox.setChecked(station_data.get("is_major_station", False))
        self.is_signal_station_checkbox.setChecked(station_data.get("is_signal_station", False))
        self.show_arrival_time_checkbox.setChecked(station_data.get("show_arrival_time", False))
        self.show_track_number_checkbox.setChecked(station_data.get("show_track_number", False))

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
        """特定の路線における駅情報が変更されたとき、プロジェクトデータを更新する"""
        station_id = self.station_id_edit.text()
        if not station_id or not self.current_selected_line_data: return

        line_station_item = next((s for s in self.current_selected_line_data.get("station_list", []) 
                                  if s.get("station_id") == station_id), None)
        if not line_station_item: return
        
        num = self.station_number_edit.text().strip()
        line_station_item["station_number"] = num if num else None
        
        val = self.running_time_spin.value()
        line_station_item["absolute_standard_running_time"] = val if val > 0 else None
        
        selected_items = self.station_list_widget.selectedItems()
        if selected_items and selected_items[0].data(Qt.UserRole) == station_id:
            self._update_station_list_item_display(selected_items[0], station_id)

        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)

    def _on_add_track(self):
        """乗り場の追加ボタンが押されたときの処理 (仮)"""
        QMessageBox.information(self, "情報", "乗り場の追加機能はまだ実装されていません。")

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
        self.btn_lines.clicked.connect(self._on_edit_lines_stations)
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

    def _on_edit_lines_stations(self):
        """路線・駅情報編集ダイアログを表示する"""
        dialog = LineStationEditorDialog(self, self.project)
        dialog.exec()


# アプリ起動処理
def main():
    app = QApplication(sys.argv)

    # アプリケーションアイコンの設定
    app.setWindowIcon(QIcon(":/assets/app_icon.ico"))

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
