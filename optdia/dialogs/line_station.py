import re
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QColorDialog, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QCheckBox, QStackedWidget,
    QRadioButton, QComboBox, QGroupBox, QFormLayout, QSpinBox, QWidget, QTabWidget
)
from core.project import OptDiaProject
from common.gui_utils import HtmlDelegate, create_color_square_pixmap
from common.widgets import ColorPickerWidget

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

        layout.addSpacing(10)

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

        new_layout.addSpacing(20)

        # 発着番線の自動設定
        self.auto_track_checkbox = QCheckBox("発着番線の自動設定")
        self.auto_track_checkbox.setChecked(True)
        new_layout.addWidget(self.auto_track_checkbox)

        new_layout.addSpacing(10)

        self.track_range_widget = QWidget()
        self.track_range_layout = QHBoxLayout(self.track_range_widget)
        self.track_range_layout.setContentsMargins(0, 0, 0, 0)
        self.track_range_layout.setSpacing(5)

        self.track_start_spin = QSpinBox()
        self.track_start_spin.setRange(0, 99)
        self.track_start_spin.setValue(1)
        self.track_end_spin = QSpinBox()
        self.track_end_spin.setRange(0, 99)
        self.track_end_spin.setValue(2)
        self.track_suffix_edit = QLineEdit("番")
        self.track_suffix_edit.setFixedWidth(60)

        self.track_range_layout.addWidget(self.track_start_spin)
        self.track_range_layout.addWidget(QLabel("〜"))
        self.track_range_layout.addWidget(self.track_end_spin)
        self.track_range_layout.addWidget(self.track_suffix_edit)
        self.track_range_layout.addWidget(QLabel("線"))
        self.track_range_layout.addStretch()
        new_layout.addWidget(self.track_range_widget)

        self.track_range_widget.setEnabled(True)
        self.auto_track_checkbox.toggled.connect(self.track_range_widget.setEnabled)

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


# 発着番線の追加ダイアログ
class AddTrackDialog(QDialog):
    def __init__(self, parent, station_data: dict):
        super().__init__(parent)
        self.station_data = station_data
        self.setWindowTitle("発着番線の追加")
        self.setFixedSize(400, 300)
        self._is_track_name_manually_edited = False
        self._is_track_short_name_manually_edited = False

        layout = QVBoxLayout(self)

        # 発着番線ID
        layout.addWidget(QLabel("発着番線ID:"))
        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("例) 1")
        self.id_edit.textChanged.connect(self._on_id_changed)
        layout.addWidget(self.id_edit)

        # 警告表示
        self.warning_label = QLabel("")
        self.warning_label.setStyleSheet("color: red; padding-left: 5px;")
        layout.addWidget(self.warning_label)

        # 発着番線名
        layout.addWidget(QLabel("発着番線名:"))
        self.number_edit = QLineEdit()
        self.number_edit.setPlaceholderText("例) 1番")
        self.number_edit.textEdited.connect(self._on_number_edited)
        layout.addWidget(self.number_edit)

        # 発着番線名の省略表記
        layout.addWidget(QLabel("発着番線名の省略表記(2文字以内):"))
        self.short_number_edit = QLineEdit()
        self.short_number_edit.setPlaceholderText("例) 1")
        self.short_number_edit.textEdited.connect(self._on_short_number_edited)
        self.short_number_edit.editingFinished.connect(self._on_short_number_editing_finished)
        layout.addWidget(self.short_number_edit)

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
        if not self._is_track_name_manually_edited:
            self.number_edit.setText(text)
        if not self._is_track_short_name_manually_edited:
            truncated_text = text[:2] if len(text) > 2 else text
            self.short_number_edit.setText(truncated_text)

    def _on_number_edited(self):
        """ユーザーが手動で番号を編集したことを記録する"""
        self._is_track_name_manually_edited = True

    def _on_short_number_edited(self):
        """ユーザーが手動で省略表記を編集したことを記録する"""
        self._is_track_short_name_manually_edited = True

    def _on_short_number_editing_finished(self):
        """省略表記の入力欄のフォーカスが外れたときに、3文字目以降を削除する"""
        text = self.short_number_edit.text()
        if len(text) > 2:
            self.short_number_edit.setText(text[:2])

    def _on_add_clicked(self):
        """入力内容の検証"""
        # 念のための切り詰め処理
        if len(self.short_number_edit.text()) > 2:
            self.short_number_edit.setText(self.short_number_edit.text()[:2])

        track_id = self.id_edit.text().strip()
        track_name = self.number_edit.text().strip()
        track_short_name = self.short_number_edit.text().strip()

        if not track_id:
            self.warning_label.setText("発着番線IDを入力してください")
            self.id_edit.setStyleSheet("background-color: #ffeeee;")
            return

        if not re.match(r"^[a-zA-Z0-9_]+$", track_id):
            self.warning_label.setText("IDには半角英数字とアンダーバーのみが使用可能です")
            self.id_edit.setStyleSheet("background-color: #ffeeee;")
            return

        # 重複チェック (stations[station_id]["tracks"] 内でチェック)
        existing_tracks = self.station_data.get("tracks", {})
        if track_id in existing_tracks:
            self.warning_label.setText("発着番線IDが既に現在の駅で使用されています")
            self.id_edit.setStyleSheet("background-color: #ffeeee;")
            return
        
        if not track_name:
            self.warning_label.setText("発着番線名を入力してください")
            self.number_edit.setStyleSheet("background-color: #ffeeee;")
            return

        if not track_short_name:
            self.warning_label.setText("発着番線名の省略表記を入力してください")
            self.short_number_edit.setStyleSheet("background-color: #ffeeee;")
            return

        self.accept()


# 発着番線の編集ダイアログ
class EditTrackDialog(QDialog):
    def __init__(self, parent, track_id: str, track_name: str, track_short_name: str):
        super().__init__(parent)
        self.setWindowTitle("発着番線の編集")
        self.setFixedSize(400, 280)

        layout = QVBoxLayout(self)

        # 発着番線ID (編集不可)
        layout.addWidget(QLabel("発着番線ID(変更不可):"))
        self.id_edit = QLineEdit(track_id)
        self.id_edit.setReadOnly(True)
        self.id_edit.setStyleSheet("background-color: #eeeeee; color: #888888;")
        layout.addWidget(self.id_edit)

        # 発着番線名
        layout.addWidget(QLabel("発着番線名:"))
        self.number_edit = QLineEdit(track_name)
        layout.addWidget(self.number_edit)

        # 発着番線名の省略表記
        layout.addWidget(QLabel("発着番線名の省略表記(2文字以内):"))
        self.short_number_edit = QLineEdit(track_short_name)
        self.short_number_edit.editingFinished.connect(self._on_short_number_editing_finished)
        layout.addWidget(self.short_number_edit)

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

    def _on_short_number_editing_finished(self):
        """省略表記の入力欄のフォーカスが外れたときに、3文字目以降を削除する"""
        text = self.short_number_edit.text()
        if len(text) > 2:
            self.short_number_edit.setText(text[:2])

    def accept(self):
        """入力内容の検証と受け入れ"""
        # 念のための切り詰め処理
        if len(self.short_number_edit.text()) > 2:
            self.short_number_edit.setText(self.short_number_edit.text()[:2])

        track_name = self.number_edit.text().strip()
        track_short_name = self.short_number_edit.text().strip()

        if not track_name:
            QMessageBox.warning(self, "エラー", "発着番線名を入力してください。")
            return
        if not track_short_name:
            QMessageBox.warning(self, "エラー", "発着番線名の省略表記を入力してください。")
            return
        
        super().accept()


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
        self.show_track_name_checkbox = QCheckBox("発着番線を表示")
        self.show_track_name_checkbox.stateChanged.connect(self._on_station_base_info_changed)
        left_vertical_layout.addWidget(self.show_track_name_checkbox)
        left_vertical_layout.addStretch()
        bottom_base_info_layout.addLayout(left_vertical_layout)

        # 2つ目の垂直配置レイアウト
        right_vertical_layout = QVBoxLayout()
        right_vertical_layout.addWidget(QLabel("発着番線:"))
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
        self.delete_track_button = QPushButton("削除")
        self.delete_track_button.clicked.connect(self._on_delete_track)
        track_btn_layout.addWidget(self.delete_track_button)
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

        # 駅削除ボタン
        self.delete_station_button = QPushButton("この駅を削除")
        self.delete_station_button.setFixedSize(120, 30)
        self.delete_station_button.clicked.connect(self._on_delete_station)
        self.delete_station_button.setStyleSheet("QPushButton { color: #cc3333; border: none; text-decoration: underline; background-color: transparent; }")
        station_form_layout.addWidget(self.delete_station_button, alignment=Qt.AlignRight)

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
        self.color_picker = ColorPickerWidget("#333333")
        self.color_picker.colorChanged.connect(self._on_line_color_changed)
        self.line_info_layout.addWidget(self.color_picker)

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

        # 路線削除ボタン
        self.delete_line_button = QPushButton("この路線を削除")
        self.delete_line_button.setFixedSize(120, 30)
        self.delete_line_button.clicked.connect(self._on_delete_line)
        self.delete_line_button.setStyleSheet("QPushButton { color: #cc3333; border: none; text-decoration: underline; background-color: transparent; }")
        self.line_info_layout.addWidget(self.delete_line_button, alignment=Qt.AlignRight)

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
        self.color_picker.setEnabled(enabled)
        self.line_symbol_edit.setEnabled(enabled)
        self.inbound_direction_checkbox.setEnabled(enabled)
        self.station_list_widget.setEnabled(enabled)
        self.add_station_button.setEnabled(enabled)
        self.delete_line_button.setEnabled(enabled)
        
        if not enabled:
            self.line_name_edit.blockSignals(True)
            self.line_symbol_edit.blockSignals(True)
            self.inbound_direction_checkbox.blockSignals(True)
            self.line_id_display.clear()
            self.line_name_edit.clear()
            self.color_picker.set_color("#000000")
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
            self.show_track_name_checkbox.setChecked(False)
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
        self.show_track_name_checkbox.blockSignals(False)
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
        self.color_picker.set_color(current_color)

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

    def _on_line_color_changed(self, new_color_hex: str):
        """色が変更されたときにプロジェクトデータとリスト表示を更新する"""
        if self.current_selected_line_data:
            self.current_selected_line_data["line_color"] = new_color_hex
            
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
        self.show_track_name_checkbox.blockSignals(True)

        self.station_name_edit.setText(station_data.get("station_name", ""))
        self.station_kana_edit.setText(station_data.get("station_name_kana", ""))
        self.station_number_edit.setText(line_station_item.get("station_number") or "")
        rt = line_station_item.get("absolute_standard_running_time")
        self.running_time_spin.setValue(rt if rt is not None else -1)

        # 発着番線コンボボックスの更新
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
                t_name = t_data.get("track_name") or tid
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
        self.show_track_name_checkbox.setChecked(station_data.get("show_track_name", False))

        self._populate_track_list(station_data)

        self.station_name_edit.blockSignals(False)
        self.station_kana_edit.blockSignals(False)
        self.station_number_edit.blockSignals(False)
        self.running_time_spin.blockSignals(False)
        self.station_initial_edit.blockSignals(False)
        self.is_major_station_checkbox.blockSignals(False)
        self.is_signal_station_checkbox.blockSignals(False)
        self.show_arrival_time_checkbox.blockSignals(False)
        self.show_track_name_checkbox.blockSignals(False)

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
        station_data["show_track_name"] = self.show_track_name_checkbox.isChecked()
        
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
        """駅の発着番線リストを表示する"""
        self.track_list_widget.clear()
        tracks = station_data.get("tracks", {})
        tracks_order = station_data.get("tracks_order", [])
        for tid in tracks_order:
            track = tracks.get(tid)
            if track:
                display_name = track.get("track_name") or tid
                item = QListWidgetItem(display_name)
                item.setData(Qt.UserRole, tid)
                self.track_list_widget.addItem(item)

    def _on_add_track(self):
        """発着番線の追加ダイアログを表示し、プロジェクトデータに反映する"""
        station_id = self.station_id_edit.text()
        if not station_id:
            return
        station_data = self.project.stations.get(station_id)
        if not station_data:
            return

        dialog = AddTrackDialog(self, station_data)
        if dialog.exec() == QDialog.Accepted:
            track_id = dialog.id_edit.text().strip()
            track_name = dialog.number_edit.text().strip()
            track_short_name = dialog.short_number_edit.text().strip()

            if "tracks" not in station_data: station_data["tracks"] = {}
            if "tracks_order" not in station_data: station_data["tracks_order"] = []

            station_data["tracks"][track_id] = {
                "track_id": track_id,
                "track_name": track_name,
                "track_short_name": track_short_name
            }
            station_data["tracks_order"].append(track_id)

            self._populate_track_list(station_data)
            self._on_station_selected()
            if hasattr(self.parent(), "set_modified"):
                self.parent().set_modified(True)

    def _on_edit_track(self):
        """選択中の発着番線の情報を編集するダイアログを表示する"""
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

        dialog = EditTrackDialog(self, track_id, 
                                 track_data.get("track_name", ""), 
                                 track_data.get("track_short_name", ""))
        if dialog.exec() == QDialog.Accepted:
            track_data["track_name"] = dialog.number_edit.text().strip()
            track_data["track_short_name"] = dialog.short_number_edit.text().strip()
            
            self._populate_track_list(station_data)
            self._on_station_selected()
            
            # 編集していた項目を再選択する
            for i in range(self.track_list_widget.count()):
                if self.track_list_widget.item(i).data(Qt.UserRole) == track_id:
                    self.track_list_widget.setCurrentRow(i)
                    break

            if hasattr(self.parent(), "set_modified"):
                self.parent().set_modified(True)

    def _on_delete_line(self):
        """現在選択中の路線を削除し、関連する運行系統や列車データ、孤立駅をクリーンアップする"""
        line_id = self.current_selected_line_id
        if not line_id or line_id not in self.project.lines:
            return

        reply = QMessageBox.question(
            self,
            "路線の削除",
            "この路線を削除しますか？\n"
            "この路線を削除すると、時刻表からはこの路線内の発着時刻が全て削除され、"
            "この路線のみに登録されている駅の情報も失われます。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # 1. 削除対象の路線に含まれていた駅を特定（後で孤立駅チェックに使用）
        line_data = self.project.lines[line_id]
        stations_in_line = [s["station_id"] for s in line_data.get("station_list", [])]

        # 2. 全ての運行系統の区間設定（line_segments）から削除対象路線を削除
        for route in self.project.routes.values():
            if "line_segments" in route:
                route["line_segments"] = [seg for seg in route["line_segments"] if seg.get("line_id") != line_id]

        # 3. 全ての列車の経由駅情報（stops）から削除対象路線のデータを削除
        for route in self.project.routes.values():
            # 運行系統から削除された線区の segment_id 一覧を事前に取得
            valid_segment_ids = {seg["segment_id"] for seg in route.get("line_segments", []) if "segment_id" in seg}
            for train_key in ["inbound_trains", "outbound_trains"]:
                trains_dict = route.get(train_key, {})
                for train in trains_dict.values():
                    if "stops" in train:
                        train["stops"] = [stop for stop in train["stops"] if stop.get("segment_id") in valid_segment_ids]

        # 4. プロジェクトの路線データ本体から削除
        del self.project.lines[line_id]
        if line_id in self.project.lines_order:
            self.project.lines_order.remove(line_id)

        # 5. 他の路線で使用されていない駅をプロジェクトの駅情報から削除
        for sid in stations_in_line:
            is_used_elsewhere = False
            for other_line in self.project.lines.values():
                if any(s.get("station_id") == sid for s in other_line.get("station_list", [])):
                    is_used_elsewhere = True
                    break
            
            if not is_used_elsewhere and sid in self.project.stations:
                del self.project.stations[sid]

        # 6. UIの更新
        self.current_selected_line_id = None
        self.current_selected_line_data = None
        self._populate_line_list()
        
        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)

    def _on_delete_station(self):
        """現在編集中の駅を現在の路線から削除し、必要に応じてプロジェクト全体から削除する"""
        if not self.current_selected_line_id or not self.current_selected_line_data:
            return

        selected_items = self.station_list_widget.selectedItems()
        if not selected_items:
            return

        station_id = selected_items[0].data(Qt.UserRole)
        station_data = self.project.stations.get(station_id)
        if not station_data:
            return

        line_name = self.current_selected_line_data.get("line_name", self.current_selected_line_id)

        # 1. 運行系統の制約チェック
        # 全ての運行系統を走査し、編集中の路線の部分区間の始点・終点になっていないか確認
        for route in self.project.routes.values():
            for seg in route.get("line_segments", []):
                if seg.get("line_id") == self.current_selected_line_id:
                    if seg.get("start_station") == station_id or seg.get("end_station") == station_id:
                        QMessageBox.warning(
                            self,
                            "エラー",
                            "この駅は運行系統で部分区間の始点または終点として設定されているため削除できません"
                        )
                        return

        # 2. 路線からの削除確認
        reply = QMessageBox.question(
            self,
            "駅の削除",
            f"「{line_name}」からこの駅を削除しますか？\n"
            "駅を削除すると、時刻表の列車に設定されているこの駅の発着時刻も削除されます。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # 3. 孤立駅（他路線での利用有無）のチェック
        other_lines_using = False
        for lid, line in self.project.lines.items():
            if lid == self.current_selected_line_id:
                continue
            if any(s.get("station_id") == station_id for s in line.get("station_list", [])):
                other_lines_using = True
                break

        if not other_lines_using:
            reply = QMessageBox.question(
                self,
                "確認",
                f"この駅は「{line_name}」以外の路線には登録されていません。このまま削除を実行すると駅情報は全て失われます。\n"
                "よろしいですか？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # 4. 実際の削除処理
        # A. 路線情報の駅リストから削除
        self.current_selected_line_data["station_list"] = [
            s for s in self.current_selected_line_data.get("station_list", [])
            if s.get("station_id") != station_id
        ]

        # B. 全ての列車の発着情報を検査し、削除対象の駅・路線ペアの経由駅データを削除
        for route in self.project.routes.values():
            seg_map = {seg["segment_id"]: seg for seg in route.get("line_segments", []) if "segment_id" in seg}
            for train_key in ["inbound_trains", "outbound_trains"]:
                trains_dict = route.get(train_key, {})
                for train in trains_dict.values():
                    if "stops" in train:
                        train["stops"] = [
                            stop for stop in train["stops"]
                            if not (stop.get("station_id") == station_id and seg_map.get(stop.get("segment_id"), {}).get("line_id") == self.current_selected_line_id)
                        ]

        # C. 他の路線で使用されていない場合は、プロジェクト全体の駅情報からも削除
        if not other_lines_using:
            if station_id in self.project.stations:
                del self.project.stations[station_id]

        # 5. UIの更新
        self._populate_station_list(self.current_selected_line_data)
        
        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)

    def _on_delete_track(self):
        """選択中の発着番線を削除する"""
        selected_items = self.track_list_widget.selectedItems()
        if not selected_items:
            return

        track_id = selected_items[0].data(Qt.UserRole)
        station_id = self.station_id_edit.text()
        station_data = self.project.stations.get(station_id)
        if not station_data:
            return

        reply = QMessageBox.question(
            self,
            "発着番線の削除",
            "この駅から選択中の発着番線を削除しますか？\n"
            "発着番線を削除すると、時刻表の列車に設定されているこの発着番線の情報も失われます。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # 1. プロジェクトデータ（駅情報）から削除
            if "tracks" in station_data and track_id in station_data["tracks"]:
                del station_data["tracks"][track_id]
            if "tracks_order" in station_data and track_id in station_data["tracks_order"]:
                station_data["tracks_order"].remove(track_id)

            # 2. 全ての列車の発着情報を検査し、削除した番線設定を解除
            for route in self.project.routes.values():
                for train_key in ["inbound_trains", "outbound_trains"]:
                    trains_dict = route.get(train_key, {})
                    for train in trains_dict.values():
                        for stop in train.get("stops", []):
                            if stop.get("station_id") == station_id and stop.get("track_id") == track_id:
                                stop["track_id"] = None

            # UIの更新
            self._populate_track_list(station_data)
            self._on_station_selected()
            
            if hasattr(self.parent(), "set_modified"):
                self.parent().set_modified(True)

    def _on_tracks_reordered(self, parent, start, end, destination, row):
        """並び替えられた発着番線リストの状態をプロジェクトデータに反映する"""
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
                    "show_track_name": False,
                    "tracks": {},
                    "tracks_order": []
                }

                # 発着番線の自動追加
                if dialog.auto_track_checkbox.isChecked():
                    start = dialog.track_start_spin.value()
                    end = dialog.track_end_spin.value()
                    suffix = dialog.track_suffix_edit.text()
                    if start <= end:
                        for i in range(start, end + 1):
                            tid = str(i)
                            self.project.stations[station_id]["tracks"][tid] = {
                                "track_id": tid,
                                "track_name": f"{i}{suffix}",
                                "track_short_name": str(i)
                            }
                            self.project.stations[station_id]["tracks_order"].append(tid)

                new_station_id = station_id
            else:
                # 既存駅の参照
                new_station_id = dialog.station_combo.currentData()

            # 発着番線情報の自動設定（プロジェクトデータ上での並び順に従い、最初を下り、最後を上り本線とする）
            inbound_main = None
            outbound_main = None
            st_data = self.project.stations.get(new_station_id)
            if st_data and "tracks_order" in st_data and st_data["tracks_order"]:
                tids = st_data["tracks_order"]
                if tids:
                    outbound_main = tids[0]
                    inbound_main = tids[-1]

            # 選択中の路線の駅リストに追加
            station_list = self.current_selected_line_data.get("station_list", [])
            # 重複チェック
            if any(s.get("station_id") == new_station_id for s in station_list):
                QMessageBox.warning(self, "エラー", "選択された駅は編集中の路線に登録済みです。")
                return
            
            station_list.append({
                "station_id": new_station_id,
                "station_number": None,
                "inbound_main_track": inbound_main,
                "outbound_main_track": outbound_main,
                "absolute_standard_running_time": None
            })
            self.current_selected_line_data["station_list"] = station_list
            
            # UI更新
            self._populate_station_list(self.current_selected_line_data)

            # 新しく追加された駅を選択状態にする
            for i in range(self.station_list_widget.count()):
                if self.station_list_widget.item(i).data(Qt.UserRole) == new_station_id:
                    self.station_list_widget.setCurrentRow(i)
                    break

            if hasattr(self.parent(), "set_modified"):
                self.parent().set_modified(True)
