import json
import os
import gzip

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
                    for train in diagram_trains["inbound_trains"].values():
                        train["to_be_saved"] = True
                # 下り列車 (outbound_trains: optdia_train[])
                if "outbound_trains" in diagram_trains:
                    diagram_trains["outbound_trains"], diagram_trains["outbound_trains_order"] = self._split_collection(
                        diagram_trains["outbound_trains"], "train_id"
                    )
                    for train in diagram_trains["outbound_trains"].values():
                        train["to_be_saved"] = True

        # 列車種別 (train_types: optdia_train_type[])
        self.train_types, self.train_types_order = self._split_collection(entities.get("train_types", []), "train_type_id")

        # 運転ダイヤ (diagrams: optdia_diagram[])
        self.diagrams, self.diagrams_order = self._split_collection(entities.get("diagrams", []), "diagram_id")

        # 車両運用グループ (operation_groups: optdia_operation_group[])
        self.operation_groups, self.operation_groups_order = self._split_collection(entities.get("operation_groups", []), "operation_group_id")

        # 運用 (operations) は TS 上で既に連想配列として定義されているためそのまま保持
        self.operations = entities.get("operations", {})

        # 読込時に部分区間境界での分割処理を行い、発着時刻データが2つの部分区間に跨っている可能性を排除する
        self._split_all_boundary_stops()

    def _split_all_boundary_stops(self):
        """全路線の全列車に対し、部分区間境界駅での発着時刻分割を行う"""
        for route in self.routes.values():
            # 部分区間境界駅（路線の接続点）を特定
            segments = route.get("line_segments", [])
            boundary_stations = set()
            for i in range(len(segments) - 1):
                if segments[i]["end_station"] == segments[i+1]["start_station"]:
                    boundary_stations.add(segments[i]["end_station"])

            tbd_dict = route.get("trains_by_diagram", {})
            for tbd in tbd_dict.values():
                for key in ["inbound_trains", "outbound_trains"]:
                    for train in tbd.get(key, {}).values():
                        new_stops = []
                        for s in train.get("stops", []):
                            # 境界駅でかつ着発両方の時刻がある場合、分割する
                            if (s.get("station_id") in boundary_stations and 
                                s.get("arrival_time") and s.get("departure_time")):
                                
                                # 着時刻のみのデータ
                                s_arr = s.copy()
                                s_arr["departure_time"] = None
                                new_stops.append(s_arr)
                                
                                # 発時刻のみのデータ
                                s_dep = s.copy()
                                s_dep["arrival_time"] = None
                                new_stops.append(s_dep)
                            else:
                                new_stops.append(s)
                        train["stops"] = new_stops

    def _normalize_train_stops_for_save(self, stops):
        """保存用に、不要なデータの削除と、同一駅・路線の連続するデータの統合を行う"""
        if not stops:
            return []
        
        # 着時刻と発時刻が共に None のデータを削除
        stops = [
            s for s in stops
            if not (s.get("arrival_time") is None and s.get("departure_time") is None)
        ]

        merged_stops = []
        i = 0
        while i < len(stops):
            s1 = stops[i]
            # 最後の要素でなく、かつ「s1が着のみ」「s2が発のみ」かつ「同一駅・路線・方向」なら統合
            if i + 1 < len(stops):
                s2 = stops[i+1]
                if (s1["station_id"] == s2["station_id"] and 
                    s1["line_id"] == s2["line_id"] and 
                    s1["direction"] == s2["direction"] and
                    s1.get("arrival_time") and not s1.get("departure_time") and
                    not s2.get("arrival_time") and s2.get("departure_time")):
                    
                    combined = s1.copy()
                    combined["departure_time"] = s2["departure_time"]
                    merged_stops.append(combined)
                    i += 2
                    continue
            
            merged_stops.append(s1)
            i += 1
        return merged_stops

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

    def _clean_train_for_export(self, train_data: dict):
        """保存用に列車データから一時的な管理用フラグやインデックスを削除する"""
        clean_train = {k: v for k, v in train_data.items() if k != "to_be_saved"}
        if "stops" in clean_train:
            # 保存直前に、不要なデータの削除と、同一駅・路線の連続するデータの統合を行う
            stops = self._normalize_train_stops_for_save(clean_train["stops"])
            clean_train["stops"] = [
                {sk: sv for sk, sv in stop.items() if sk != "stop_idx"}
                for stop in stops
            ]
        return clean_train

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
                        dt_copy["inbound_trains"] = [
                            self._clean_train_for_export(dt["inbound_trains"][tid])
                            for tid in dt["inbound_trains_order"]
                            if dt["inbound_trains"][tid].get("to_be_saved") is True
                        ]
                        del dt_copy["inbound_trains_order"]
                    if "outbound_trains" in dt and "outbound_trains_order" in dt:
                        dt_copy["outbound_trains"] = [
                            self._clean_train_for_export(dt["outbound_trains"][tid])
                            for tid in dt["outbound_trains_order"]
                            if dt["outbound_trains"][tid].get("to_be_saved") is True
                        ]
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
        拡張子が .optd の場合は gzip 圧縮を行います。
        """
        data = self.to_dict()
        is_compressed = filepath.lower().endswith(".optd")
        open_func = gzip.open if is_compressed else open

        with open_func(filepath, "wt", encoding="utf-8") as f:
            # 日本語がエスケープされないよう ensure_ascii=False を指定し、インデント付きで保存します
            json.dump(data, f, ensure_ascii=False, indent=4)


def load_project(filepath: str) -> OptDiaProject:
    """
    指定されたパスから JSON ファイルを読み込み、OptDiaProject インスタンスを生成します。
    拡張子が .optd の場合は gzip 展開を行います。
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Project file not found: {filepath}")

    is_compressed = filepath.lower().endswith(".optd")
    open_func = gzip.open if is_compressed else open

    with open_func(filepath, "rt", encoding="utf-8") as f:
        data = json.load(f)
    
    return OptDiaProject(data)


def save_project(project: OptDiaProject, filepath: str):
    """
    OptDiaProject インスタンスを JSON ファイルとして保存します。
    """
    project.save_project(filepath)