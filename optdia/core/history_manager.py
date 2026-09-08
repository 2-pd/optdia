from collections import deque
from typing import List, Union
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox, QApplication
from core.events import BaseEvent, BaseTemporaryStablingEvent, HistoryExecutionError


class HistoryManager(QObject):
    """
    OptDiaのUndo / Redo履歴を管理するクラス
    - ユーザーによる1回の操作ごとにBaseEventまたはBaseTemporaryStablingEventのリストとしてundo_stack/redo_stackに格納される
    - 最大100件の履歴を保持する
    """
    historyChanged = Signal()
    undone = Signal(list)  # list[BaseEvent | BaseTemporaryStablingEvent]
    redone = Signal(list)  # list[BaseEvent | BaseTemporaryStablingEvent]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.undo_stack: deque[List[Union[BaseEvent, BaseTemporaryStablingEvent]]] = deque(maxlen=100)
        self.redo_stack: deque[List[Union[BaseEvent, BaseTemporaryStablingEvent]]] = deque(maxlen=100)

    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self.redo_stack) > 0

    def push_events(self, events: List[Union[BaseEvent, BaseTemporaryStablingEvent]]) -> None:
        """1回の操作に対応するイベントのリストをスタックに追加する"""
        if not events:
            return
        self.undo_stack.append(events)
        self.redo_stack.clear()
        self.historyChanged.emit()

    def undo(self, project) -> bool:
        """直前のイベントリストを取り出し、逆順で元に戻す"""
        if not self.can_undo():
            return False
        events = self.undo_stack.pop()
        
        # 実行可否の検証
        try:
            for event in reversed(events):
                if hasattr(event, "validate_undo"):
                    event.validate_undo(project)
                event.undo(project)
        except HistoryExecutionError as e:
            self.clear()
            self._show_error_dialog(str(e))
            return False
        except Exception as e:
            self.clear()
            self._show_error_dialog("プロジェクトデータが変更されたためこれ以上操作を元に戻すことができません")
            return False

        self.redo_stack.append(events)
        self.undone.emit(events)
        self.historyChanged.emit()
        return True

    def redo(self, project) -> bool:
        """直前にUndoされたイベントリストを取り出し、順方向に再実行する"""
        if not self.can_redo():
            return False
        events = self.redo_stack.pop()

        # 実行可否の検証
        try:
            for event in events:
                if hasattr(event, "validate_redo"):
                    event.validate_redo(project)
                event.redo(project)
        except HistoryExecutionError as e:
            self.clear()
            self._show_error_dialog(str(e))
            return False
        except Exception as e:
            self.clear()
            self._show_error_dialog("プロジェクトデータが変更されたためこれ以上操作をやり直すことができません")
            return False

        self.undo_stack.append(events)
        self.redone.emit(events)
        self.historyChanged.emit()
        return True

    def _show_error_dialog(self, message: str) -> None:
        parent_widget = self.parent() if isinstance(self.parent(), QMessageBox) or hasattr(self.parent(), "window") else None
        if parent_widget and hasattr(parent_widget, "window"):
            parent_widget = parent_widget.window()
        active_window = parent_widget or QApplication.activeWindow()
        QMessageBox.warning(active_window, "エラー", message)

    def clear(self) -> None:
        """履歴をクリアする"""
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.historyChanged.emit()

