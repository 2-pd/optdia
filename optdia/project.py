import json
import os

# プロジェクトファイルの仕様バージョン (optdia_project.ts の定義に準拠)
PROJECT_SCHEMA_VERSION = "2026.06.001"

class OptDiaProject:
    """
    optdia_project.ts の定義に基づくプロジェクトデータ管理クラス。
    ID を持つオブジェクトの配列を、高速検索用の辞書と順序保持用のリストに分割して保持します。
    """

    def __init__(self, data: dict = None):
        if data is None:
            data = {}

        # メタデータの読み込みと最小限の初期値設定
        self.metadata = data.get("metadata", {})
        # 指定されたキーが存在しない場合にデフォルト値をセット
        self.metadata.setdefault("railroad_name", "")
        self.metadata.setdefault("description", "")
        self.metadata.setdefault("license_text", "")
        self.metadata.setdefault("project_schema_version", PROJECT_SCHEMA_VERSION)

        entities = data.get("entities", {})

        # TS定義で配列かつ内部に個別のIDを持つものを、高速検索用の辞書と順序リストに分割
        # 各エンティティごとに定義された ID キーを指定

        # 路線 (lines: optdia_line[])
        self.lines, self.lines_order = self._split_collection(entities.get("lines", []), "line_id")

        # 駅 (stations): 連想配列だが、内部の tracks (optdia_station_track[]) を分割
        self.stations = entities.get("stations", {})
        for station in self.stations.values():
            if "tracks" in station:
                station["tracks"], station["tracks_order"] = self._split_collection(station["tracks"], "track_id")

        # 運行系統 (routes: optdia_route[]): 内部に列車情報 (optdia_train[]) を含む
        self.routes, self.routes_order = self._split_collection(entities.get("routes", []), "route_id")
        for route in self.routes.values():
            tbd = route.get("trains_by_diagram", {})
            for diagram_trains in tbd.values():
                # 上り列車 (inbound_trains: optdia_train[])
                if "inbound_trains" in diagram_trains:
                    diagram_trains["inbound_trains"], diagram_trains["inbound_trains_order"] = self._split_collection(
                        diagram_trains["inbound_trains"], "train_id"
                    )
                # 下り列車 (outbound_trains: optdia_train[])
                if "outbound_trains" in diagram_trains:
                    diagram_trains["outbound_trains"], diagram_trains["outbound_trains_order"] = self._split_collection(
                        diagram_trains["outbound_trains"], "train_id"
                    )

        # 列車種別 (train_types: optdia_train_type[])
        self.train_types, self.train_types_order = self._split_collection(entities.get("train_types", []), "train_type_id")

        # 運転ダイヤ (diagrams: optdia_diagram[])
        self.diagrams, self.diagrams_order = self._split_collection(entities.get("diagrams", []), "diagram_id")

        # 車両運用グループ (operation_groups: optdia_operation_group[])
        self.operation_groups, self.operation_groups_order = self._split_collection(entities.get("operation_groups", []), "operation_group_id")

        # 運用 (operations) は TS 上で既に連想配列として定義されているためそのまま保持
        self.operations = entities.get("operations", {})

    def _split_collection(self, items: list, id_key: str):
        """
        指定された ID キーを含むオブジェクトの配列を、ID をキーとした辞書と、ID の順序リストに分割する。
        """
        item_dict = {}
        item_order = []
        
        for item in items:
            # 引数で指定された id_key を使用して ID を取得
            item_id = item.get(id_key)
            if item_id:
                item_dict[item_id] = item
                item_order.append(item_id)
        
        return item_dict, item_order

    def to_dict(self):
        """
        保存時などに元の配列形式に戻すための変換メソッド (オプション)
        """
        # 駅データの復元 (tracks を配列に戻す)
        stations_export = {}
        for sid, s in self.stations.items():
            s_copy = s.copy()
            if "tracks" in s and "tracks_order" in s:
                s_copy["tracks"] = [s["tracks"][tid] for tid in s["tracks_order"]]
                del s_copy["tracks_order"]
            stations_export[sid] = s_copy

        # 運行系統データの復元 (inbound/outbound_trains を配列に戻す)
        routes_export = []
        for rid in self.routes_order:
            r = self.routes[rid]
            r_copy = r.copy()
            if "trains_by_diagram" in r:
                new_tbd = {}
                for did, dt in r["trains_by_diagram"].items():
                    dt_copy = dt.copy()
                    if "inbound_trains" in dt and "inbound_trains_order" in dt:
                        dt_copy["inbound_trains"] = [dt["inbound_trains"][tid] for tid in dt["inbound_trains_order"]]
                        del dt_copy["inbound_trains_order"]
                    if "outbound_trains" in dt and "outbound_trains_order" in dt:
                        dt_copy["outbound_trains"] = [dt["outbound_trains"][tid] for tid in dt["outbound_trains_order"]]
                        del dt_copy["outbound_trains_order"]
                    new_tbd[did] = dt_copy
                r_copy["trains_by_diagram"] = new_tbd
            routes_export.append(r_copy)

        return {
            "metadata": self.metadata,
            "entities": {
                "lines": [self.lines[lid] for lid in self.lines_order],
                "stations": stations_export,
                "routes": routes_export,
                "train_types": [self.train_types[ttid] for ttid in self.train_types_order],
                "diagrams": [self.diagrams[did] for did in self.diagrams_order],
                "operations": self.operations,
                "operation_groups": [self.operation_groups[ogid] for ogid in self.operation_groups_order]
            }
        }

    def save_project(self, filepath: str):
        """
        プロジェクトデータを指定されたパスに JSON 形式で保存します。
        """
        data = self.to_dict()
        with open(filepath, "w", encoding="utf-8") as f:
            # 日本語がエスケープされないよう ensure_ascii=False を指定し、インデント付きで保存します
            json.dump(data, f, ensure_ascii=False, indent=4)


def load_project(filepath: str) -> OptDiaProject:
    """
    指定されたパスから JSON ファイルを読み込み、OptDiaProject インスタンスを生成します。
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Project file not found: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    return OptDiaProject(data)


def save_project(project: OptDiaProject, filepath: str):
    """
    OptDiaProject インスタンスを JSON ファイルとして保存します。
    """
    project.save_project(filepath)