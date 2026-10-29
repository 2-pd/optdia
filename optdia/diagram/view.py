import copy
from PySide6.QtWidgets import QGraphicsView, QMenu, QMessageBox, QGraphicsPathItem
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QWheelEvent
from .scene import DiagramScene, DiagramHeaderScene, DiagramStationScene
from .dialogs import AddTrainDialog, delete_train
from previews.train_detail import TrainDetailPreviewDialog

# 運行ダイヤグラムの上部ビュー（時刻ヘッダー）
class DiagramHeaderView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = DiagramHeaderScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setFixedHeight(20)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def update_header(self):
        self.scene.update_header()


# 運行ダイヤグラムの左側ビュー（駅名）
class DiagramStationView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = DiagramStationScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setFixedWidth(120)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def update_stations(self, project, stations_data):
        self.scene.update_stations(project, stations_data)


# 運行ダイヤグラムのメインビュー
class DiagramView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = DiagramScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    def update_diagram(self, project, selected_target: str, route_id: str, diagram_id: str,
            filter_train_type_id: str = None,
            filter_train_type_ids: set = None,
            filter_operation_ids: set = None):
        return self.scene.update_diagram(project, selected_target, route_id, diagram_id,
                filter_train_type_id=filter_train_type_id,
                filter_train_type_ids=filter_train_type_ids,
                filter_operation_ids=filter_operation_ids)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        main_win = self.window()
        if hasattr(main_win, "diagram_height_combo"):
            if main_win.diagram_height_combo.currentData() == "auto":
                if hasattr(main_win, "_update_diagram_view"):
                    main_win._update_diagram_view()

    def wheelEvent(self, event: QWheelEvent):
        # Shiftキーが押されているときは横スクロール
        if event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
            # ホイールの回転量を取得
            angle_delta = event.angleDelta().y()
            # 水平スクロールバーを取得
            hbar = self.horizontalScrollBar()
            if hbar:
                # 現在の値から、回転量に応じて値を増減させる
                hbar.setValue(hbar.value() - angle_delta)
            # イベントを処理したことをシステムに伝える
            event.accept()
        else:
            # Shiftが押されていないときは通常の上下スクロール
            super().wheelEvent(event)

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        scene_pos = self.mapToScene(event.pos())
        rect = QRectF(scene_pos.x() - 4.0, scene_pos.y() - 4.0, 8.0, 8.0)
        items = [i for i in self.scene.items(rect) if isinstance(i, QGraphicsPathItem)]
        if items:
            train_data = self._find_train_by_path_items(items)
            if train_data:
                self._handle_train_detail_action(train_data)

    def contextMenuEvent(self, event):
        scene_pos = self.mapToScene(event.pos())

        # クリック位置の周辺に列車のパスが存在するか判定
        # 半径4pxの矩形領域内にあるQGraphicsPathItemを探索
        rect = QRectF(scene_pos.x() - 4.0, scene_pos.y() - 4.0, 8.0, 8.0)
        items = [i for i in self.scene.items(rect) if isinstance(i, QGraphicsPathItem)]

        if items:
            # 列車のパスが存在する場合はパス上専用のコンテキストメニューを表示
            # クリック位置に最も近い列車を特定する
            train_data = self._find_train_by_path_items(items)
            menu = QMenu(self)
            train_detail_action = menu.addAction("列車の詳細")
            edit_train_action = menu.addAction("この列車を時刻表で編集")
            add_train_action = menu.addAction("ここに列車を追加")
            delete_train_action = menu.addAction("この列車を削除")
            selected_action = menu.exec(event.globalPos())
            if selected_action == train_detail_action and train_data is not None:
                self._handle_train_detail_action(train_data)
            elif selected_action == edit_train_action and train_data is not None:
                self._handle_edit_train_action(train_data)
            elif selected_action == add_train_action:
                self._handle_add_train_action(scene_pos)
            elif selected_action == delete_train_action and train_data is not None:
                self._handle_delete_train_action(train_data)
            return

        menu = QMenu(self)
        add_train_action = menu.addAction("ここに列車を追加")
        selected_action = menu.exec(event.globalPos())

        if selected_action == add_train_action:
            self._handle_add_train_action(scene_pos)

    def _find_train_by_path_items(self, path_items):
        """
        path_itemsのリストから、rendered_trainsリスト内で対応する列車データを返す。
        対応する列車が見つからない場合はNoneを返す。
        """
        path_item_set = set(id(item) for item in path_items)
        for train_data in self.scene.rendered_trains:
            for p_item in train_data.get("path_items", []):
                if id(p_item) in path_item_set:
                    return train_data
        return None

    def _handle_train_detail_action(self, train_data):
        parent_widget = self.window()
        project = getattr(self.scene, "project", None)
        if parent_widget and hasattr(parent_widget, "project"):
            project = parent_widget.project
        route_id = train_data.get("route_id")
        direction = train_data.get("direction")
        train_id = train_data.get("train_id")
        if project and route_id and direction and train_id:
            dialog = TrainDetailPreviewDialog(parent_widget, project, route_id, direction, train_id)
            dialog.exec()

    def _handle_edit_train_action(self, train_data):
        main_win = self.window()
        if main_win and hasattr(main_win, "edit_train_in_timetable"):
            route_id = train_data.get("route_id")
            direction = train_data.get("direction")
            train_id = train_data.get("train_id")
            main_win.edit_train_in_timetable(route_id, direction, train_id)

    def _handle_add_train_action(self, scene_pos):
        # メインウィンドウを探索
        main_win = self.window()

        # diagram_line_comboで「選択中の運行系統」以外が選択されているかを判定
        is_route_selected = True
        if hasattr(main_win, "diagram_line_combo"):
            combo_text = main_win.diagram_line_combo.currentText()
            combo_data = main_win.diagram_line_combo.currentData()
            if combo_text != "選択中の運行系統" and combo_data != "route":
                is_route_selected = False

        if not is_route_selected:
            QMessageBox.critical(
                self,
                "エラー",
                "路線単位でダイヤグラムを表示している状態では列車を追加できません。\n"
                "列車を追加するには運行系統別のダイヤグラム表示に切り替えてください。"
            )
            return

        # 運行系統および運転ダイヤIDの取得
        project = getattr(main_win, "project", self.scene.project)
        route_id = getattr(self.scene, "route_id", None)
        diagram_id = getattr(self.scene, "diagram_id", None)
        history_manager = getattr(main_win, "history_manager", None)

        if not project or not route_id or not diagram_id:
            return

        # 最も近い駅と時刻の計算
        stations_data = getattr(self.scene, "stations_data", []) or []
        default_station_id = None
        if stations_data:
            closest_st = min(stations_data, key=lambda st: abs(st["y"] - scene_pos.y()))
            default_station_id = closest_st.get("station_id")

        scale_x = getattr(self.scene, "scale_x", 6.0)
        total_minutes = max(0, scene_pos.x() / scale_x)
        default_hour = int(total_minutes // 60)
        default_minute = int(round(total_minutes % 60))
        if default_minute == 60:
            default_minute = 0
            default_hour += 1

        dlg = AddTrainDialog(
            self,
            project=project,
            route_id=route_id,
            diagram_id=diagram_id,
            history_manager=history_manager,
            default_station_id=default_station_id,
            default_hour=default_hour,
            default_minute=default_minute
        )

        if dlg.exec():
            # プロジェクトの変更フラグを設定し、ビューを再描画
            if hasattr(main_win, "set_modified"):
                main_win.set_modified(True)
            if hasattr(main_win, "_update_diagram_view"):
                main_win._update_diagram_view()
            if hasattr(main_win, "timetable_model"):
                main_win.timetable_model.update_data(
                    main_win.timetable_model.route_id,
                    main_win.timetable_model.diagram_id,
                    main_win.timetable_model.direction
                )

    def _handle_delete_train_action(self, train_data):
        """
        ダイヤグラム上の列車パスを右クリックして「この列車を削除」を選択したときの処理。
        """
        if delete_train(self, train_data):
            # ビューの更新
            main_win = self.window()

            if hasattr(main_win, "set_modified"):
                main_win.set_modified(True)
            if hasattr(main_win, "_update_diagram_view"):
                main_win._update_diagram_view()
            if hasattr(main_win, "timetable_model"):
                main_win.timetable_model.update_data(
                    main_win.timetable_model.route_id,
                    main_win.timetable_model.diagram_id,
                    main_win.timetable_model.direction
                )

