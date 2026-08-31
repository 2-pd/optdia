from abc import ABC, abstractmethod
import copy
from typing import Any, List, Dict, Optional


class BaseEvent(ABC):
    """すべての履歴イベントの基底クラス"""
    def __init__(self, route_id: str, direction: str, train_id: str):
        self.route_id = route_id
        self.direction = direction  # "inbound" or "outbound"
        self.train_id = train_id

    @property
    def train_key(self) -> str:
        return "inbound_trains" if self.direction == "inbound" else "outbound_trains"

    @property
    def order_key(self) -> str:
        return f"{self.train_key}_order"

    @abstractmethod
    def undo(self, project) -> None:
        pass

    @abstractmethod
    def redo(self, project) -> None:
        pass


# 列車の追加
class AddTrainEvent(BaseEvent):
    """
    列車の追加イベント
    - index: 追加された位置（order内のインデックス）
    - diagram_id: 運転ダイヤID
    - d_train: ダイヤ別列車情報
    - m_train: 列車マスタ情報
    """
    def __init__(self, route_id: str, direction: str, train_id: str, diagram_id: str, index: int, d_train: dict, m_train: dict):
        super().__init__(route_id, direction, train_id)
        self.diagram_id = diagram_id
        self.index = index
        self.d_train = copy.deepcopy(d_train)
        self.m_train = copy.deepcopy(m_train)

    def undo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        tbd = route.get("trains_by_diagram", {}).get(self.diagram_id, {})
        d_trains = tbd.get(self.train_key, {})
        order = tbd.get(self.order_key, [])
        m_trains = route.get(self.train_key, {})

        if self.train_id in order:
            order.remove(self.train_id)
        if self.train_id in d_trains:
            del d_trains[self.train_id]
        if self.train_id in m_trains:
            del m_trains[self.train_id]

    def redo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        tbd = route.get("trains_by_diagram", {}).get(self.diagram_id, {})
        d_trains = tbd.setdefault(self.train_key, {})
        order = tbd.setdefault(self.order_key, [])
        m_trains = route.setdefault(self.train_key, {})

        d_trains[self.train_id] = copy.deepcopy(self.d_train)
        m_trains[self.train_id] = copy.deepcopy(self.m_train)
        if self.index >= len(order):
            order.append(self.train_id)
        else:
            order.insert(self.index, self.train_id)


# 列車の並び替え
class ReorderTrainsEvent(BaseEvent):
    """
    列車の並び替えイベント
    - diagram_id: 運転ダイヤID
    - old_index: 移動前の位置
    - new_index: 移動後の位置
    - train_id: 移動対象の列車ID
    - converted_train_ids: 移動に伴い to_be_saved が True に変換された列車IDリスト（もしあれば）
    """
    def __init__(self, route_id: str, direction: str, train_id: str, diagram_id: str, old_index: int, new_index: int, converted_train_ids: Optional[List[str]] = None):
        super().__init__(route_id, direction, train_id)
        self.diagram_id = diagram_id
        self.old_index = old_index
        self.new_index = new_index
        self.converted_train_ids = converted_train_ids or []

    def undo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        tbd = route.get("trains_by_diagram", {}).get(self.diagram_id, {})
        order = tbd.get(self.order_key, [])
        d_trains = tbd.get(self.train_key, {})

        if self.new_index < len(order) and order[self.new_index] == self.train_id:
            item = order.pop(self.new_index)
            order.insert(self.old_index, item)

        for tid in self.converted_train_ids:
            if tid in d_trains:
                d_trains[tid]["to_be_saved"] = False

    def redo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        tbd = route.get("trains_by_diagram", {}).get(self.diagram_id, {})
        order = tbd.get(self.order_key, [])
        d_trains = tbd.get(self.train_key, {})

        if self.old_index < len(order) and order[self.old_index] == self.train_id:
            item = order.pop(self.old_index)
            order.insert(self.new_index, item)

        for tid in self.converted_train_ids:
            if tid in d_trains:
                d_trains[tid]["to_be_saved"] = True


# 列車の列車番号変更
class ChangeTrainNumberEvent(BaseEvent):
    def __init__(self, route_id: str, direction: str, train_id: str, old_value: str, new_value: str):
        super().__init__(route_id, direction, train_id)
        self.old_value = old_value
        self.new_value = new_value

    def undo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        m_train = route.get(self.train_key, {}).get(self.train_id)
        if m_train:
            m_train["train_number"] = self.old_value

    def redo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        m_train = route.get(self.train_key, {}).get(self.train_id)
        if m_train:
            m_train["train_number"] = self.new_value


# 列車の運転日追加(運転ダイヤ別の列車情報の生成)
class AddTrainDiagramEvent(BaseEvent):
    def __init__(self, route_id: str, direction: str, train_id: str, diagram_id: str, index: int, d_train: dict):
        super().__init__(route_id, direction, train_id)
        self.diagram_id = diagram_id
        self.index = index
        self.d_train = copy.deepcopy(d_train)

    def undo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        tbd = route.get("trains_by_diagram", {}).get(self.diagram_id, {})
        d_trains = tbd.get(self.train_key, {})
        order = tbd.get(self.order_key, [])
        m_train = route.get(self.train_key, {}).get(self.train_id)

        if self.train_id in order:
            order.remove(self.train_id)
        if self.train_id in d_trains:
            del d_trains[self.train_id]
        if m_train and "_diagram_ids" in m_train and self.diagram_id in m_train["_diagram_ids"]:
            m_train["_diagram_ids"].remove(self.diagram_id)

    def redo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        tbd = route.get("trains_by_diagram", {}).get(self.diagram_id, {})
        d_trains = tbd.setdefault(self.train_key, {})
        order = tbd.setdefault(self.order_key, [])
        m_train = route.get(self.train_key, {}).get(self.train_id)

        d_trains[self.train_id] = copy.deepcopy(self.d_train)
        if self.index >= len(order):
            order.append(self.train_id)
        else:
            order.insert(self.index, self.train_id)
        if m_train and "_diagram_ids" in m_train and self.diagram_id not in m_train["_diagram_ids"]:
            m_train["_diagram_ids"].append(self.diagram_id)
            m_train["_diagram_ids"].sort(key=lambda x: project.diagrams_order.index(x) if x in project.diagrams_order else 999)


# 列車の運転日削除(運転ダイヤ別の列車情報の削除)
class RemoveTrainDiagramEvent(BaseEvent):
    def __init__(self, route_id: str, direction: str, train_id: str, diagram_id: str, index: int, d_train: dict):
        super().__init__(route_id, direction, train_id)
        self.diagram_id = diagram_id
        self.index = index
        self.d_train = copy.deepcopy(d_train)

    def undo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        tbd = route.get("trains_by_diagram", {}).get(self.diagram_id, {})
        d_trains = tbd.setdefault(self.train_key, {})
        order = tbd.setdefault(self.order_key, [])
        m_train = route.get(self.train_key, {}).get(self.train_id)

        d_trains[self.train_id] = copy.deepcopy(self.d_train)
        if self.index >= len(order):
            order.append(self.train_id)
        else:
            order.insert(self.index, self.train_id)
        if m_train and "_diagram_ids" in m_train and self.diagram_id not in m_train["_diagram_ids"]:
            m_train["_diagram_ids"].append(self.diagram_id)
            m_train["_diagram_ids"].sort(key=lambda x: project.diagrams_order.index(x) if x in project.diagrams_order else 999)

    def redo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        tbd = route.get("trains_by_diagram", {}).get(self.diagram_id, {})
        d_trains = tbd.get(self.train_key, {})
        order = tbd.get(self.order_key, [])
        m_train = route.get(self.train_key, {}).get(self.train_id)

        if self.train_id in order:
            order.remove(self.train_id)
        if self.train_id in d_trains:
            del d_trains[self.train_id]
        if m_train and "_diagram_ids" in m_train and self.diagram_id in m_train["_diagram_ids"]:
            m_train["_diagram_ids"].remove(self.diagram_id)


# 列車への担当運用の登録
class AddTrainOperationEvent(BaseEvent):
    def __init__(self, route_id: str, direction: str, train_id: str, diagram_id: str, index: int, operation: dict):
        super().__init__(route_id, direction, train_id)
        self.diagram_id = diagram_id
        self.index = index
        self.operation = copy.deepcopy(operation)

    def undo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        d_train = route.get("trains_by_diagram", {}).get(self.diagram_id, {}).get(self.train_key, {}).get(self.train_id)
        if d_train and "operations" in d_train:
            if 0 <= self.index < len(d_train["operations"]):
                d_train["operations"].pop(self.index)

    def redo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        d_train = route.get("trains_by_diagram", {}).get(self.diagram_id, {}).get(self.train_key, {}).get(self.train_id)
        if d_train:
            ops = d_train.setdefault("operations", [])
            if self.index >= len(ops):
                ops.append(copy.deepcopy(self.operation))
            else:
                ops.insert(self.index, copy.deepcopy(self.operation))


# 列車からの担当運用の除外
class RemoveTrainOperationEvent(BaseEvent):
    def __init__(self, route_id: str, direction: str, train_id: str, diagram_id: str, index: int, operation: dict):
        super().__init__(route_id, direction, train_id)
        self.diagram_id = diagram_id
        self.index = index
        self.operation = copy.deepcopy(operation)

    def undo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        d_train = route.get("trains_by_diagram", {}).get(self.diagram_id, {}).get(self.train_key, {}).get(self.train_id)
        if d_train:
            ops = d_train.setdefault("operations", [])
            if self.index >= len(ops):
                ops.append(copy.deepcopy(self.operation))
            else:
                ops.insert(self.index, copy.deepcopy(self.operation))

    def redo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        d_train = route.get("trains_by_diagram", {}).get(self.diagram_id, {}).get(self.train_key, {}).get(self.train_id)
        if d_train and "operations" in d_train:
            if 0 <= self.index < len(d_train["operations"]):
                d_train["operations"].pop(self.index)


# 列車の担当運用の変更
class ChangeTrainOperationEvent(BaseEvent):
    def __init__(self, route_id: str, direction: str, train_id: str, diagram_id: str, old_operations: list, new_operations: list):
        super().__init__(route_id, direction, train_id)
        self.diagram_id = diagram_id
        self.old_operations = copy.deepcopy(old_operations)
        self.new_operations = copy.deepcopy(new_operations)

    def undo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        d_train = route.get("trains_by_diagram", {}).get(self.diagram_id, {}).get(self.train_key, {}).get(self.train_id)
        if d_train:
            d_train["operations"] = copy.deepcopy(self.old_operations)

    def redo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        d_train = route.get("trains_by_diagram", {}).get(self.diagram_id, {}).get(self.train_key, {}).get(self.train_id)
        if d_train:
            d_train["operations"] = copy.deepcopy(self.new_operations)


# 列車の両数の変更
class ChangeTrainCarCountEvent(BaseEvent):
    def __init__(self, route_id: str, direction: str, train_id: str, diagram_id: str, old_value: Optional[int], new_value: Optional[int]):
        super().__init__(route_id, direction, train_id)
        self.diagram_id = diagram_id
        self.old_value = old_value
        self.new_value = new_value

    def undo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        d_train = route.get("trains_by_diagram", {}).get(self.diagram_id, {}).get(self.train_key, {}).get(self.train_id)
        if d_train:
            d_train["car_count"] = self.old_value

    def redo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        d_train = route.get("trains_by_diagram", {}).get(self.diagram_id, {}).get(self.train_key, {}).get(self.train_id)
        if d_train:
            d_train["car_count"] = self.new_value


# 列車の種別の変更
class ChangeTrainTypeEvent(BaseEvent):
    def __init__(self, route_id: str, direction: str, train_id: str, old_value: Optional[str], new_value: Optional[str]):
        super().__init__(route_id, direction, train_id)
        self.old_value = old_value
        self.new_value = new_value

    def undo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        m_train = route.get(self.train_key, {}).get(self.train_id)
        if m_train:
            m_train["train_type_id"] = self.old_value

    def redo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        m_train = route.get(self.train_key, {}).get(self.train_id)
        if m_train:
            m_train["train_type_id"] = self.new_value


# 列車の号数の変更
class ChangeTrainNamedNumberEvent(BaseEvent):
    def __init__(self, route_id: str, direction: str, train_id: str, old_value: Optional[int], new_value: Optional[int]):
        super().__init__(route_id, direction, train_id)
        self.old_value = old_value
        self.new_value = new_value

    def undo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        m_train = route.get(self.train_key, {}).get(self.train_id)
        if m_train:
            m_train["named_train_number"] = self.old_value

    def redo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        m_train = route.get(self.train_key, {}).get(self.train_id)
        if m_train:
            m_train["named_train_number"] = self.new_value


# 列車の行き先の変更
class ChangeTrainDestinationEvent(BaseEvent):
    def __init__(self, route_id: str, direction: str, train_id: str, diagram_id: str, old_value: Optional[str], new_value: Optional[str]):
        super().__init__(route_id, direction, train_id)
        self.diagram_id = diagram_id
        self.old_value = old_value
        self.new_value = new_value

    def undo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        d_train = route.get("trains_by_diagram", {}).get(self.diagram_id, {}).get(self.train_key, {}).get(self.train_id)
        if d_train:
            d_train["destination"] = self.old_value

    def redo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        d_train = route.get("trains_by_diagram", {}).get(self.diagram_id, {}).get(self.train_key, {}).get(self.train_id)
        if d_train:
            d_train["destination"] = self.new_value


# 列車の経由駅情報の追加
class AddTrainStopEvent(BaseEvent):
    def __init__(self, route_id: str, direction: str, train_id: str, index: int, stop: dict):
        super().__init__(route_id, direction, train_id)
        self.index = index
        self.stop = copy.deepcopy(stop)

    def undo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        m_train = route.get(self.train_key, {}).get(self.train_id)
        if m_train and "stops" in m_train:
            stop_idx = self.stop.get("stop_idx")
            m_train["stops"] = [s for s in m_train["stops"] if s.get("stop_idx") != stop_idx]
            if "_stop_map" in m_train and stop_idx in m_train["_stop_map"]:
                del m_train["_stop_map"][stop_idx]

    def redo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        m_train = route.get(self.train_key, {}).get(self.train_id)
        if m_train:
            stops = m_train.setdefault("stops", [])
            stop_idx = self.stop.get("stop_idx")
            stops = [s for s in stops if s.get("stop_idx") != stop_idx]
            stops.append(copy.deepcopy(self.stop))
            stops.sort(key=lambda x: x.get("stop_idx", 0))
            m_train["stops"] = stops
            if "_stop_map" in m_train:
                matching = next((s for s in stops if s.get("stop_idx") == stop_idx), None)
                if matching:
                    m_train["_stop_map"][stop_idx] = matching


# 列車の経由駅情報の削除
class RemoveTrainStopEvent(BaseEvent):
    def __init__(self, route_id: str, direction: str, train_id: str, index: int, stop: dict):
        super().__init__(route_id, direction, train_id)
        self.index = index
        self.stop = copy.deepcopy(stop)

    def undo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        m_train = route.get(self.train_key, {}).get(self.train_id)
        if m_train:
            stops = m_train.setdefault("stops", [])
            stop_idx = self.stop.get("stop_idx")
            stops = [s for s in stops if s.get("stop_idx") != stop_idx]
            stops.append(copy.deepcopy(self.stop))
            stops.sort(key=lambda x: x.get("stop_idx", 0))
            m_train["stops"] = stops
            if "_stop_map" in m_train:
                matching = next((s for s in stops if s.get("stop_idx") == stop_idx), None)
                if matching:
                    m_train["_stop_map"][stop_idx] = matching

    def redo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        m_train = route.get(self.train_key, {}).get(self.train_id)
        if m_train and "stops" in m_train:
            stop_idx = self.stop.get("stop_idx")
            m_train["stops"] = [s for s in m_train["stops"] if s.get("stop_idx") != stop_idx]
            if "_stop_map" in m_train and stop_idx in m_train["_stop_map"]:
                del m_train["_stop_map"][stop_idx]


# 列車の経由駅情報の変更
class ChangeTrainStopEvent(BaseEvent):
    def __init__(self, route_id: str, direction: str, train_id: str, stop_idx: int, old_stop: dict, new_stop: dict):
        super().__init__(route_id, direction, train_id)
        self.stop_idx = stop_idx
        self.old_stop = copy.deepcopy(old_stop)
        self.new_stop = copy.deepcopy(new_stop)

    def undo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        m_train = route.get(self.train_key, {}).get(self.train_id)
        if m_train:
            for i, s in enumerate(m_train.get("stops", [])):
                if s.get("stop_idx") == self.stop_idx:
                    m_train["stops"][i] = copy.deepcopy(self.old_stop)
                    if "_stop_map" in m_train:
                        m_train["_stop_map"][self.stop_idx] = m_train["stops"][i]
                    break

    def redo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        m_train = route.get(self.train_key, {}).get(self.train_id)
        if m_train:
            for i, s in enumerate(m_train.get("stops", [])):
                if s.get("stop_idx") == self.stop_idx:
                    m_train["stops"][i] = copy.deepcopy(self.new_stop)
                    if "_stop_map" in m_train:
                        m_train["_stop_map"][self.stop_idx] = m_train["stops"][i]
                    break


# 列車への連続する列車の追加
class AddSubsequentTrainEvent(BaseEvent):
    def __init__(self, route_id: str, direction: str, train_id: str, diagram_id: str, index: int, subsequent_train: dict):
        super().__init__(route_id, direction, train_id)
        self.diagram_id = diagram_id
        self.index = index
        self.subsequent_train = copy.deepcopy(subsequent_train)

    def undo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        d_train = route.get("trains_by_diagram", {}).get(self.diagram_id, {}).get(self.train_key, {}).get(self.train_id)
        if d_train and "subsequent_trains" in d_train:
            if 0 <= self.index < len(d_train["subsequent_trains"]):
                d_train["subsequent_trains"].pop(self.index)

    def redo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        d_train = route.get("trains_by_diagram", {}).get(self.diagram_id, {}).get(self.train_key, {}).get(self.train_id)
        if d_train:
            subs = d_train.setdefault("subsequent_trains", [])
            if self.index >= len(subs):
                subs.append(copy.deepcopy(self.subsequent_train))
            else:
                subs.insert(self.index, copy.deepcopy(self.subsequent_train))


# 列車からの連続する列車の削除
class RemoveSubsequentTrainEvent(BaseEvent):
    def __init__(self, route_id: str, direction: str, train_id: str, diagram_id: str, index: int, subsequent_train: dict):
        super().__init__(route_id, direction, train_id)
        self.diagram_id = diagram_id
        self.index = index
        self.subsequent_train = copy.deepcopy(subsequent_train)

    def undo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        d_train = route.get("trains_by_diagram", {}).get(self.diagram_id, {}).get(self.train_key, {}).get(self.train_id)
        if d_train:
            subs = d_train.setdefault("subsequent_trains", [])
            if self.index >= len(subs):
                subs.append(copy.deepcopy(self.subsequent_train))
            else:
                subs.insert(self.index, copy.deepcopy(self.subsequent_train))

    def redo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        d_train = route.get("trains_by_diagram", {}).get(self.diagram_id, {}).get(self.train_key, {}).get(self.train_id)
        if d_train and "subsequent_trains" in d_train:
            if 0 <= self.index < len(d_train["subsequent_trains"]):
                d_train["subsequent_trains"].pop(self.index)


# 列車の連続する列車の変更
class ChangeSubsequentTrainEvent(BaseEvent):
    def __init__(self, route_id: str, direction: str, train_id: str, diagram_id: str, old_subsequent_trains: list, new_subsequent_trains: list):
        super().__init__(route_id, direction, train_id)
        self.diagram_id = diagram_id
        self.old_subsequent_trains = copy.deepcopy(old_subsequent_trains)
        self.new_subsequent_trains = copy.deepcopy(new_subsequent_trains)

    def undo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        d_train = route.get("trains_by_diagram", {}).get(self.diagram_id, {}).get(self.train_key, {}).get(self.train_id)
        if d_train:
            d_train["subsequent_trains"] = copy.deepcopy(self.old_subsequent_trains)

    def redo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        d_train = route.get("trains_by_diagram", {}).get(self.diagram_id, {}).get(self.train_key, {}).get(self.train_id)
        if d_train:
            d_train["subsequent_trains"] = copy.deepcopy(self.new_subsequent_trains)


# 列車の備考の変更
class ChangeTrainNoteEvent(BaseEvent):
    def __init__(self, route_id: str, direction: str, train_id: str, old_value: str, new_value: str):
        super().__init__(route_id, direction, train_id)
        self.old_value = old_value
        self.new_value = new_value

    def undo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        m_train = route.get(self.train_key, {}).get(self.train_id)
        if m_train:
            m_train["note"] = self.old_value

    def redo(self, project) -> None:
        route = project.routes.get(self.route_id, {})
        m_train = route.get(self.train_key, {}).get(self.train_id)
        if m_train:
            m_train["note"] = self.new_value
