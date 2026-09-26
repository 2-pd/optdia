import html
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame
)
from PySide6.QtCore import Qt
from core.project import OptDiaProject
from dialogs.operation import VehicleOperationEditorDialog
from previews.train_detail import TrainDetailPreviewDialog


def _format_time_hhmm(time_str: str) -> str:
    """時刻文字列 (hh:mm:ss または hh:mm) から秒の部分を除去して hh:mm 形式とする"""
    if not time_str:
        return "--:--"
    parts = time_str.split(":")
    if len(parts) >= 2:
        try:
            return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
        except ValueError:
            return "--:--"
    return time_str


def _time_to_seconds(text: str):
    """時刻文字列を秒単位の数値に変換する"""
    if not text:
        return None
    try:
        parts = text.split(':')
        if len(parts) == 3:
            h, m, s = map(int, parts)
            return h * 3600 + m * 60 + s
        elif len(parts) == 2:
            h, m = map(int, parts)
            return h * 3600 + m * 60
    except (ValueError, AttributeError):
        pass
    return None


class OperationDetailPreviewDialog(QDialog):
    """運用詳細ダイアログ"""
    def __init__(self, parent, project: OptDiaProject, diagram_id: str, operation: dict, operation_id: str = None, group_id: str = None):
        super().__init__(parent)
        self.project = project
        self.diagram_id = diagram_id
        self.operation = operation
        self.operation_id = operation_id
        self.group_id = group_id

        # 運用番号の取得
        op_num = self.operation.get("operation_number", "")
        self.setWindowTitle(f"{op_num} 運用の詳細情報")
        self.setFixedSize(480, 640)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # スクロールエリアの設定
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        main_layout.addWidget(self.scroll_area)

        self._build_content()

    def _build_content(self):
        """ダイアログの内容を構築・再描画する"""
        # 最新の運用情報を取得
        if self.operation_id:
            diag_ops = self.project.diagrams.get(self.diagram_id, {}).get("operations", {})
            if self.operation_id in diag_ops:
                self.operation = diag_ops[self.operation_id]

        op_num = self.operation.get("operation_number", "")
        self.setWindowTitle(f"{op_num} 運用の詳細情報")

        container_widget = QWidget()
        container_widget.setProperty("class", "scroll_content")
        container_widget.setStyleSheet("""
            QLabel { font-size: 16px; }
            .down_arrow { color: #cccccc; font-size: 12px; }
        """)
        container_layout = QVBoxLayout(container_widget)
        container_layout.setContentsMargins(10, 10, 10, 30)
        container_layout.setSpacing(6)

        # 運用番号ラベル
        main_color = self.operation.get("main_color", "#ffffff")
        op_title_label = QLabel(f"{html.escape(str(op_num))} 運用")
        op_title_label.setAlignment(Qt.AlignCenter)
        op_title_label.setFixedHeight(40)
        op_title_label.setStyleSheet(
            f"background-color: {main_color}; font-size: 20px; font-weight: bold;"
        )
        container_layout.addWidget(op_title_label)

        # 所定両数ラベル
        car_count = self.operation.get("car_count", 0)
        min_car_count = self.operation.get("min_car_count", 0)
        max_car_count = self.operation.get("max_car_count", 0)
        car_label_text = f'{car_count}両 <span style="font-size: 12px;">(最小{min_car_count} 〜 最大{max_car_count}両)</span>'
        car_label = QLabel(car_label_text)
        car_label.setAlignment(Qt.AlignCenter)
        car_label.setTextFormat(Qt.RichText)
        car_label.setStyleSheet("color: #666666; font-size: 14px;")
        container_layout.addWidget(car_label)

        # 運用編集ボタン
        edit_button = QPushButton("この運用を編集")
        edit_button.setFixedHeight(30)
        edit_button.setCursor(Qt.PointingHandCursor)
        edit_button.clicked.connect(self._open_editor)
        container_layout.addWidget(edit_button)

        # 出庫場所ラベル
        start_loc = self.operation.get("start_location", "") or ""
        start_track = self.operation.get("start_track")
        start_track_str = f"({start_track})" if start_track else ""
        start_time_str = _format_time_hhmm(self.operation.get("start_time"))
        start_label_text = f"○ <b>{start_loc}{start_track_str}出庫</b> {start_time_str}"
        start_label = QLabel(start_label_text)
        start_label.setFixedHeight(24)
        start_label.setAlignment(Qt.AlignCenter)
        start_label.setTextFormat(Qt.RichText)
        container_layout.addWidget(start_label)

        down_arrow_label = QLabel("▼")
        down_arrow_label.setAlignment(Qt.AlignCenter)
        down_arrow_label.setFixedHeight(12)
        down_arrow_label.setProperty("class", "down_arrow")
        container_layout.addWidget(down_arrow_label)

        assigned_trains = self._collect_assigned_trains()
        for train_data in assigned_trains:
            row_label = QLabel(train_data["html_text"])
            row_label.setAlignment(Qt.AlignCenter)
            row_label.setTextFormat(Qt.RichText)
            row_label.setFixedHeight(24)

            if not train_data.get("is_stabling"):
                row_label.setCursor(Qt.PointingHandCursor)

                def make_train_click_handler(r_id, d_dir, t_id):
                    def mouse_press(event):
                        if event.button() == Qt.LeftButton:
                            dialog = TrainDetailPreviewDialog(self, self.project, r_id, d_dir, t_id)
                            dialog.exec()
                    return mouse_press

                row_label.mousePressEvent = make_train_click_handler(
                    train_data["route_id"], train_data["direction"], train_data["train_id"]
                )
            container_layout.addWidget(row_label)

            train_down_arrow_label = QLabel("▼")
            train_down_arrow_label.setAlignment(Qt.AlignCenter)
            train_down_arrow_label.setFixedHeight(12)
            train_down_arrow_label.setProperty("class", "down_arrow")
            container_layout.addWidget(train_down_arrow_label)

        # 入庫場所ラベル
        end_loc = self.operation.get("end_location", "") or ""
        end_track = self.operation.get("end_track")
        end_track_str = f"({end_track})" if end_track else ""
        end_time_str = _format_time_hhmm(self.operation.get("end_time"))
        end_label_text = f"△ <b>{end_loc}{end_track_str}入庫</b> {end_time_str}"
        end_label = QLabel(end_label_text)
        end_label.setFixedHeight(24)
        end_label.setAlignment(Qt.AlignCenter)
        end_label.setTextFormat(Qt.RichText)
        container_layout.addWidget(end_label)

        container_layout.addStretch()

        self.scroll_area.setWidget(container_widget)

    def _open_editor(self):
        """車両運用情報編集ダイアログを開く"""
        dialog = VehicleOperationEditorDialog(
            self.parent(),
            self.project,
            self.diagram_id,
            self.group_id,
            self.operation_id
        )
        dialog.exec()
        if hasattr(self.parent(), "_update_op_group_combo"):
            self.parent()._update_op_group_combo()
        self._build_content()

    def _get_station_initial_or_first_char(self, station_entry_id: str, fallback_station_id: str = None) -> str:
        """始発駅・終着駅の駅名の1文字表記(Noneの場合は駅名の1文字目で代用)を取得する"""
        station_id = getattr(self.project, "station_entry_to_station_id", {}).get(station_entry_id) or fallback_station_id
        if not station_id:
            return "？"
        station = self.project.stations.get(station_id, {})
        initial = station.get("station_initial")
        if initial:
            return str(initial)[0]
        station_name = station.get("station_name", "")
        if station_name:
            return station_name[0]
        return "？"

    def _collect_assigned_trains(self) -> list:
        """
        表示対象の車両運用に属する列車を operation_train_lookup を使用して読み込み、
        始発駅発車時刻の早い順にソートする。
        ソート後の並び順で連続している列車が、種別IDと列車番号が同一で、
        かつ、連続する列車(subsequent_trains)として紐づけられている場合、それらの列車を統合して1行に表示する。
        一時入庫(temporary_stabling_events)も列車と区別なく1つのリストにまとめて返す。
        """
        train_entries = []

        # operation_id の取得
        op_id = self.operation_id
        if not op_id:
            # 渡された辞書から operation_id を逆引き
            diag_ops = self.project.diagrams.get(self.diagram_id, {}).get("operations", {})
            for k, v in diag_ops.items():
                if v is self.operation:
                    op_id = k
                    break

        if not op_id:
            return train_entries

        # operation_train_lookup から該当する列車リストを取得
        lookup_dict = getattr(self.project, "operation_train_lookup", {})
        diag_lookup = lookup_dict.get(self.diagram_id, {})
        assigned_list = diag_lookup.get(op_id, [])

        for item in assigned_list:
            route_id = item.get("route_id")
            direction = item.get("direction")
            train_id = item.get("train_id")

            route = self.project.routes.get(route_id, {})
            train_key = "inbound_trains" if direction == "inbound" else "outbound_trains"
            m_train = route.get(train_key, {}).get(train_id, {})
            if not m_train:
                continue

            stops = m_train.get("stops", [])
            if not stops:
                continue

            first_stop = stops[0]
            last_stop = stops[-1]

            first_dep_str = first_stop.get("departure_time") or first_stop.get("arrival_time") or ""
            last_arr_str = last_stop.get("arrival_time") or last_stop.get("departure_time") or ""

            first_dep_sec = _time_to_seconds(first_dep_str)
            sort_key_time = first_dep_sec if first_dep_sec is not None else 24 * 3600 + 1

            # 運転ダイヤ別列車情報 (subsequent_trains 取得用)
            tbd = route.get("trains_by_diagram", {}).get(self.diagram_id, {})
            d_train = tbd.get(train_key, {}).get(train_id, {})
            subsequent_trains = d_train.get("subsequent_trains", []) if d_train else []

            # 列車種別情報
            train_type_id = m_train.get("train_type_id")
            train_type = self.project.train_types.get(train_type_id, {}) if train_type_id else {}
            train_type_short_name = train_type.get("train_type_short_name", "")
            train_type_color = train_type.get("main_color", "#333333")

            # 列車番号
            train_number = m_train.get("train_number", "")

            # 始発駅・終着駅の1文字表記
            first_st_initial = self._get_station_initial_or_first_char(
                first_stop.get("station_entry_id"), first_stop.get("station_id")
            )
            last_st_initial = self._get_station_initial_or_first_char(
                last_stop.get("station_entry_id"), last_stop.get("station_id")
            )

            # 時刻 (hh:mm形式)
            dep_hhmm = _format_time_hhmm(first_dep_str)
            arr_hhmm = _format_time_hhmm(last_arr_str)

            train_entries.append({
                "sort_key_time": sort_key_time,
                "train_number": train_number,
                "train_type_id": train_type_id,
                "train_type_short_name": train_type_short_name,
                "train_type_color": train_type_color,
                "route_id": route_id,
                "direction": direction,
                "train_id": train_id,
                "subsequent_trains": subsequent_trains,
                "first_st_initial": first_st_initial,
                "last_st_initial": last_st_initial,
                "dep_hhmm": dep_hhmm,
                "arr_hhmm": arr_hhmm,
                "is_stabling": False,
            })

        # 一時入庫イベントを追加
        temporary_stabling_events = self.operation.get("temporary_stabling_events", []) or []
        for event in temporary_stabling_events:
            stabled_location = event.get("stabled_location", "")
            start_time_str = event.get("start_time", "")
            end_time_str = event.get("end_time", "")
            start_sec = _time_to_seconds(start_time_str)
            sort_key_time = start_sec if start_sec is not None else 24 * 3600 + 1
            start_hhmm = _format_time_hhmm(start_time_str)
            end_hhmm = _format_time_hhmm(end_time_str)
            location_color = "#cc3333" if event.get("formations_can_changed") else "#666666"
            escaped_location = html.escape(str(stabled_location))
            train_html = f'<b>{escaped_location}</b><span style="color: {location_color};">待機</span>&nbsp;&nbsp;{start_hhmm} 〜 {end_hhmm}'
            train_entries.append({
                "sort_key_time": sort_key_time,
                "train_number": "",
                "train_type_id": None,
                "is_stabling": True,
                "html_text": train_html,
                "route_id": None,
                "direction": None,
                "train_id": None,
            })

        # 始発駅発車時刻の早い順にソート
        train_entries.sort(key=lambda x: (x["sort_key_time"], x["train_number"]))

        # 連続している列車の統合処理（is_stabling=Trueのものは統合対象外とする）
        merged_groups = []
        for train in train_entries:
            if train.get("is_stabling"):
                merged_groups.append([train])
                continue
            if not merged_groups or merged_groups[-1][0].get("is_stabling"):
                merged_groups.append([train])
            else:
                current_group = merged_groups[-1]
                prev_train = current_group[-1]

                if prev_train["train_type_id"] == train["train_type_id"] and prev_train["train_number"] == train["train_number"]:
                    current_group.append(train)
                else:
                    merged_groups.append([train])

        # 表示用HTMLおよびアイテム情報の構築
        result_trains = []
        for group in merged_groups:
            first_train = group[0]

            if first_train.get("is_stabling"):
                # 一時入庫はhtml_textがすでに設定されている
                result_trains.append({
                    "route_id": None,
                    "direction": None,
                    "train_id": None,
                    "html_text": first_train["html_text"],
                    "is_stabling": True,
                })
                continue

            last_train = group[-1]

            train_type_color = first_train["train_type_color"]
            escaped_type_short_name = html.escape(str(first_train["train_type_short_name"]))
            escaped_train_number = html.escape(str(first_train["train_number"]))

            first_initial = html.escape(str(first_train["first_st_initial"]))
            last_initial = html.escape(str(last_train["last_st_initial"]))
            dep_time = first_train["dep_hhmm"]
            arr_time = last_train["arr_hhmm"]

            colored_part = f'<b style="color: {train_type_color};">{escaped_type_short_name} {escaped_train_number}</b>'
            train_html = f'{colored_part}&nbsp;&nbsp;{first_initial} {dep_time} → {arr_time} {last_initial}'

            result_trains.append({
                "route_id": first_train["route_id"],
                "direction": first_train["direction"],
                "train_id": first_train["train_id"],
                "html_text": train_html,
                "is_stabling": False,
            })

        return result_trains
