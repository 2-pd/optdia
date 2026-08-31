from collections import deque
from typing import List
from PySide6.QtCore import QObject, Signal
from core.events import BaseEvent


class HistoryManager(QObject):
    """
    OptDiaのUndo / Redo履歴を管理するクラス
    - ユーザーによる1回の操作ごとにBaseEventのリストとしてundo_stack/redo_stackに格納される
    - 最大100件の履歴を保持する
    """
    historyChanged = Signal()
    undone = Signal(list)  # list[BaseEvent]
    redone = Signal(list)  # list[BaseEvent]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.undo_stack: deque[List[BaseEvent]] = deque(maxlen=100)
        self.redo_stack: deque[List[BaseEvent]] = deque(maxlen=100)

    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self.redo_stack) > 0

    def push_events(self, events: List[BaseEvent]) -> None:
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
        for event in reversed(events):
            event.undo(project)
        self.redo_stack.append(events)
        self.undone.emit(events)
        self.historyChanged.emit()
        return True

    def redo(self, project) -> bool:
        """直前にUndoされたイベントリストを取り出し、順方向に再実行する"""
        if not self.can_redo():
            return False
        events = self.redo_stack.pop()
        for event in events:
            event.redo(project)
        self.undo_stack.append(events)
        self.redone.emit(events)
        self.historyChanged.emit()
        return True

    def clear(self) -> None:
        """履歴をクリアする"""
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.historyChanged.emit()
