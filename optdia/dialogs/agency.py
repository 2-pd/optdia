import re
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QWidget, QListWidget, QListWidgetItem,
    QStackedWidget
)
from core.project import OptDiaProject


def validate_agency_url(url_str: str) -> tuple[bool, str]:
    """
    URL文字列のバリデーションを行う関数。
    空欄の場合は有効と判定する。
    正しくない場合は (False, 警告テキスト) を返す。
    """
    if not url_str:
        return True, ""

    if not (url_str.startswith("https://") or url_str.startswith("http://")):
        return False, "【注意】URLは https:// または http:// で始まる必要があります"

    # RFC 3986 に準拠する有効なURL文字の正規表現
    # 空ホスト名（https:// や http:// 単体）も除外
    pattern = r"^https?://[a-zA-Z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+$"
    if not re.match(pattern, url_str):
        return False, "【注意】URLに使用できない文字が含まれています"

    if url_str in ("https://", "http://"):
        return False, "【注意】URLのホスト名が指定されていません"

    return True, ""


class AgencyEditorDialog(QDialog):
    """
    鉄道事業者情報編集ダイアログ
    """
    def __init__(self, parent, project: OptDiaProject):
        super().__init__(parent)
        self.project = project
        self._current_agency_id: str | None = None

        self.setWindowTitle("鉄道事業者情報の編集")
        self.setFixedSize(640, 480)

        # メインレイアウト（左右2分割）
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- 左側の領域 (幅180px) ---
        left_panel = QWidget()
        left_panel.setFixedWidth(180)
        left_panel.setProperty("class", "dialog_sidebar")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(5)

        # 1. 「鉄道事業者」ラベル
        agency_label = QLabel("鉄道事業者")
        agency_label.setStyleSheet("font-weight: bold;")
        left_layout.addWidget(agency_label)

        # 2. 鉄道事業者名を一覧表示するためのリストウィジェット「鉄道事業者リスト」
        self.agency_list_widget = QListWidget()
        self.agency_list_widget.setDragDropMode(QListWidget.InternalMove)
        self.agency_list_widget.model().rowsMoved.connect(self._on_agencies_reordered)
        self.agency_list_widget.itemSelectionChanged.connect(self._on_agency_selected)
        left_layout.addWidget(self.agency_list_widget)

        # 3. 「鉄道事業者の追加」ボタン (クリック時の動作はまだ設定しない)
        self.add_agency_button = QPushButton("鉄道事業者の追加")
        left_layout.addWidget(self.add_agency_button)

        # 4. 「鉄道事業者はドラッグ操作で並び替え可能です」ラベル
        drag_info_label = QLabel("鉄道事業者はドラッグ操作で並び替え可能です")
        drag_info_label.setWordWrap(True)
        drag_info_label.setProperty("class", "informational_text")
        left_layout.addWidget(drag_info_label)

        main_layout.addWidget(left_panel)

        # --- 右側の領域 (スタックドウィジェット) ---
        self.right_stack = QStackedWidget()
        main_layout.addWidget(self.right_stack, stretch=1)

        # プレースホルダーページ (項目が存在しないとき)
        self.placeholder_page = QWidget()
        placeholder_layout = QVBoxLayout(self.placeholder_page)
        placeholder_label = QLabel("鉄道事業者を追加してください")
        placeholder_label.setAlignment(Qt.AlignCenter)
        placeholder_label.setProperty("class", "placeholder_label")
        placeholder_layout.addWidget(placeholder_label)
        self.right_stack.addWidget(self.placeholder_page)

        # 編集フォームページ (項目が存在するとき)
        self.edit_form_page = QWidget()
        edit_form_layout = QVBoxLayout(self.edit_form_page)
        edit_form_layout.setContentsMargins(20, 20, 20, 20)
        edit_form_layout.setSpacing(8)

        # 1. 「事業者ID:」というラベル
        edit_form_layout.addWidget(QLabel("事業者ID:"))
        # 事業者IDが表示される1行テキストボックス(常に無効状態)
        self.agency_id_edit = QLineEdit()
        self.agency_id_edit.setEnabled(False)
        edit_form_layout.addWidget(self.agency_id_edit)

        # 2. 「事業者名:」というラベル
        edit_form_layout.addWidget(QLabel("事業者名:"))
        # 事業者名を編集するための1行テキストボックス
        self.agency_name_edit = QLineEdit()
        self.agency_name_edit.textEdited.connect(self._on_agency_name_edited)
        edit_form_layout.addWidget(self.agency_name_edit)

        # 3. 「事業者名の省略表記:」というラベル
        edit_form_layout.addWidget(QLabel("事業者名の省略表記:"))
        # 事業者名の省略表記を編集するための1行テキストボックス
        self.agency_short_name_edit = QLineEdit()
        self.agency_short_name_edit.textEdited.connect(self._on_agency_short_name_edited)
        edit_form_layout.addWidget(self.agency_short_name_edit)

        # 4. 「事業者公式サイトのURL:」というラベル
        edit_form_layout.addWidget(QLabel("事業者公式サイトのURL:"))
        # 事業者公式サイトのURLを編集するための1行テキストボックス
        self.agency_url_edit = QLineEdit()
        self.agency_url_edit.textEdited.connect(self._on_agency_url_edited)
        edit_form_layout.addWidget(self.agency_url_edit)

        # URLとして正しくない文字列が入力されたときに警告を表示するためのラベル
        self.url_warning_label = QLabel("")
        self.url_warning_label.setStyleSheet("color: #cc6600; font-size: 12px;")
        self.url_warning_label.setWordWrap(True)
        edit_form_layout.addWidget(self.url_warning_label)

        edit_form_layout.addStretch()

        # 最下部右端の「この事業者を削除」ボタン
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        self.delete_agency_button = QPushButton("この事業者を削除")
        self.delete_agency_button.setProperty("class", "delete_button")
        bottom_layout.addWidget(self.delete_agency_button)
        edit_form_layout.addLayout(bottom_layout)

        self.right_stack.addWidget(self.edit_form_page)

        # リスト初期化
        self._populate_agency_list()
        if self.agency_list_widget.count() > 0:
            self.agency_list_widget.setCurrentRow(0)
        else:
            self._update_stack_view()

    def _update_stack_view(self):
        """鉄道事業者リストの項目有無に応じてスタックドウィジェットの表示を切り替える"""
        if self.agency_list_widget.count() == 0:
            self.right_stack.setCurrentWidget(self.placeholder_page)
            self._current_agency_id = None
        else:
            self.right_stack.setCurrentWidget(self.edit_form_page)

    def _populate_agency_list(self):
        """プロジェクトデータに基づいて鉄道事業者リストを構築する"""
        self.agency_list_widget.blockSignals(True)
        self.agency_list_widget.clear()

        for agency_id in self.project.agencies_order:
            agency = self.project.agencies.get(agency_id)
            if not agency:
                continue
            display_name = agency.get("agency_name", "")
            item = QListWidgetItem(display_name)
            item.setData(Qt.UserRole, agency_id)
            self.agency_list_widget.addItem(item)

        self.agency_list_widget.blockSignals(False)
        self._update_stack_view()

    def _on_agency_selected(self):
        """リストで選択中の鉄道事業者の情報をフォームに反映する"""
        selected_items = self.agency_list_widget.selectedItems()
        if not selected_items:
            self._update_stack_view()
            return

        agency_id = selected_items[0].data(Qt.UserRole)
        agency = self.project.agencies.get(agency_id)
        if not agency:
            self._update_stack_view()
            return

        self._current_agency_id = agency_id
        self._update_stack_view()

        # フォームの値を更新（シグナルをブロックして変更ハンドラが発火しないようにする）
        self.agency_id_edit.blockSignals(True)
        self.agency_name_edit.blockSignals(True)
        self.agency_short_name_edit.blockSignals(True)
        self.agency_url_edit.blockSignals(True)

        self.agency_id_edit.setText(agency.get("agency_id", ""))
        self.agency_name_edit.setText(agency.get("agency_name", ""))
        self.agency_short_name_edit.setText(agency.get("agency_short_name", ""))
        raw_url = agency.get("agency_url")
        self.agency_url_edit.setText(raw_url if raw_url is not None else "")

        self.agency_id_edit.blockSignals(False)
        self.agency_name_edit.blockSignals(False)
        self.agency_short_name_edit.blockSignals(False)
        self.agency_url_edit.blockSignals(False)

        # URLのバリデーション表示更新
        self._validate_and_display_url_warning(self.agency_url_edit.text().strip())

    def _on_agency_name_edited(self, text: str):
        """事業者名が編集された時の処理"""
        if not self._current_agency_id:
            return
        agency = self.project.agencies.get(self._current_agency_id)
        if agency is not None:
            agency["agency_name"] = text
            # リストアイテムの表示テキストも更新
            selected_items = self.agency_list_widget.selectedItems()
            if selected_items:
                selected_items[0].setText(text)
            self._set_modified()

    def _on_agency_short_name_edited(self, text: str):
        """事業者名の省略表記が編集された時の処理"""
        if not self._current_agency_id:
            return
        agency = self.project.agencies.get(self._current_agency_id)
        if agency is not None:
            agency["agency_short_name"] = text
            self._set_modified()

    def _on_agency_url_edited(self, text: str):
        """事業者公式サイトのURLが編集された時の処理"""
        if not self._current_agency_id:
            return
        agency = self.project.agencies.get(self._current_agency_id)
        if agency is not None:
            url_str = text.strip()
            # 空欄のときはプロジェクトデータのagency_urlにNoneがセットされる
            agency["agency_url"] = url_str if url_str else None
            self._validate_and_display_url_warning(url_str)
            self._set_modified()

    def _validate_and_display_url_warning(self, url_str: str):
        """URLのバリデーションを行い警告ラベルを更新する"""
        is_valid, warning_msg = validate_agency_url(url_str)
        if not is_valid:
            self.url_warning_label.setText(warning_msg)
        else:
            self.url_warning_label.setText("")

    def _on_agencies_reordered(self, parent, start, end, destination, row):
        """ドラッグアンドドロップで並び替えられた順序をプロジェクトデータに反映する"""
        new_order = []
        for i in range(self.agency_list_widget.count()):
            item = self.agency_list_widget.item(i)
            new_order.append(item.data(Qt.UserRole))

        self.project.agencies_order = new_order
        self._set_modified()

    def _set_modified(self):
        """親ウィンドウに変更状態を通知する"""
        if hasattr(self.parent(), "set_modified"):
            self.parent().set_modified(True)
