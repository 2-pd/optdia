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

        # 運行系統 (routes: optdia_route[])
        self.routes, self.routes_order = self._split_collection(entities.get("routes", []), "route_id")
        for route in self.routes.values():
            # 定義に基づき、運行系統が直接保持する列車辞書(optdia_train_dict)を確保
            route.setdefault("inbound_trains", {})
            route.setdefault("outbound_trains", {})

            tbd = route.get("trains_by_diagram", {})
            for diagram_trains in tbd.values():
                # 各ダイヤ内の列車(optdia_diagram_train[])を辞書分割し、保存対象フラグを付与
                for key in ["inbound_trains", "outbound_trains"]:
                    if key in diagram_trains:
                        diagram_trains[key], diagram_trains[f"{key}_order"] = self._split_collection(
                            diagram_trains[key], "train_id"
                        )
                        for d_train in diagram_trains[key].values():
                            d_train["to_be_saved"] = True

        # 列車種別 (train_types: optdia_train_type[])
        self.train_types, self.train_types_order = self._split_collection(entities.get("train_types", []), "train_type_id")

        # 運転ダイヤ (diagrams: optdia_diagram[])
        self.diagrams, self.diagrams_order = self._split_collection(entities.get("diagrams", []), "diagram_id")

        # 車両運用グループ (operation_groups: optdia_operation_group[])
        self.operation_groups, self.operation_groups_order = self._split_collection(entities.get("operation_groups", []), "operation_group_id")

        # 運用 (operations) は TS 上で既に連想配列として定義されているためそのまま保持
        self.operations = entities.get("operations", {})

        # 各マスタ列車 (optdia_train) に、その列車が運転されるダイヤのIDを配列として保持する一時キーを追加
        # このキーは保存時には除去される
        for route_id in self.routes_order:
            route = self.routes[route_id]
            for train_key in ["inbound_trains", "outbound_trains"]:
                for train_id, m_train in route.get(train_key, {}).items():
                    m_train["_diagram_ids"] = [] # 一時キーを初期化

            # 各ダイヤを走査し、マスタ列車にダイヤIDを紐付ける
            for diagram_id in self.diagrams_order:
                tbd_for_diagram = route.get("trains_by_diagram", {}).get(diagram_id, {})
                for train_key in ["inbound_trains", "outbound_trains"]:
                    d_trains_for_diagram = tbd_for_diagram.get(train_key, {})
                    for d_train_id in d_trains_for_diagram:
                        m_train = route.get(train_key, {}).get(d_train_id)
                        if m_train is not None and diagram_id not in m_train["_diagram_ids"]:
                            m_train["_diagram_ids"].append(diagram_id)

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

            for key in ["inbound_trains", "outbound_trains"]:
                for train in route.get(key, {}).values():
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
        clean_train = {k: v for k, v in train_data.items() if k not in ["to_be_saved", "_diagram_ids", "_stop_map"]}
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

            # 1. いずれかのダイヤで使用されている(保存対象の)列車IDを収集
            active_tids = set()
            if "trains_by_diagram" in r:
                for dt in r["trains_by_diagram"].values():
                    for key in ["inbound_trains", "outbound_trains"]:
                        if key in dt:
                            for tid, d_train in dt[key].items():
                                if d_train.get("to_be_saved"):
                                    active_tids.add(tid)

            # 2. 運行系統直下の列車辞書の復元（使用されている列車のみを抽出し、停車駅を正規化）
            for key in ["inbound_trains", "outbound_trains"]:
                if key in r:
                    r_copy[key] = {
                        tid: self._clean_train_for_export(t)
                        for tid, t in r[key].items()
                        if tid in active_tids
                    }

            # 3. ダイヤ別の列車情報の復元 (optdia_diagram_train を配列に戻す)
            if "trains_by_diagram" in r:
                new_tbd = {}
                for did, dt in r["trains_by_diagram"].items():
                    dt_copy = dt.copy()
                    for key in ["inbound_trains", "outbound_trains"]:
                        order_key = f"{key}_order"
                        if key in dt and order_key in dt:
                            dt_copy[key] = [
                                {k: v for k, v in dt[key][tid].items() if k != "to_be_saved"}
                                for tid in dt[order_key]
                                if dt[key][tid].get("to_be_saved") is True
                        ]
                        del dt_copy[order_key]
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
            if is_compressed:
                # 圧縮保存 (.optd) の場合は、ファイルサイズを最小化するためインデントと余分な空白を削除
                json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
            else:
                # 非圧縮保存 (.optdia) の場合は、テキストエディタ等での可読性を考慮してインデント付きで保存
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