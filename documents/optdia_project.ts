/* --------------------------------------------------------------------------------
 *
 *   鉄道ダイヤグラム編集ソフト OptDia  プロジェクトファイル(.optdia)内部構造
 *
 * --------------------------------------------------------------------------------
 */


// 仕様バージョン 2026.06.001

// OptDiaでは、鉄道ダイヤグラムデータを以下のオブジェクト「optdia_project」に適合するJSON文字列として、拡張子「.optdia」のファイルに保存する。
// 「optdia_project」オブジェクトに適合するJSON文字列をgzip圧縮して保存したファイルも利用可能であり、その場合の拡張子は「.optd」となる。


// optdiaファイルの基底となるオブジェクト
export interface optdia_project {
    metadata: optdia_project_metadata; // プロジェクトファイルのメタデータ(下記)
    entities: optdia_project_entities; // プロジェクトのコンテンツ本体(下記)
}


// プロジェクトファイルのメタデータを格納するオブジェクト
interface optdia_project_metadata {
    railroad_name: string; // 路線系統名
    description: string; // 路線系統についての説明文
    license_text: string; // プロジェクトファイルのライセンス文
    project_schema_version: string; // プロジェクトファイルの仕様バージョン
}


// プロジェクトのコンテンツ本体を格納するオブジェクト
interface optdia_project_entities {
    lines: optdia_line[]; // 各路線の情報(下記)を表示順に配列で
    stations: optdia_station_dict; // 各駅の情報(下記)を連想配列で
    routes: optdia_route[]; // 運行系統の情報(下記)を表示順に配列で
    train_types: optdia_train_type[]; // 各列車種別の情報(下記)を表示順に配列で
    diagrams: optdia_diagram[]; // 運転ダイヤの情報(下記)を表示順に配列で
    operations: optdia_operation_dict; // 各車両運用の情報(下記)を連想配列で
    operation_groups: optdia_operation_group[]; // 各車両運用グループの情報(下記)を表示順に配列で
}


// 路線情報を格納するオブジェクト
interface optdia_line {
    line_id: string; // 路線ID
    line_name: string; // 路線名
    line_color: string; // 路線の色(デフォルト値は #333333)
    line_symbol: string | null; // 路線記号等(1〜2文字の英数字または1文字のマルチバイト文字)
    inbound_direction_is_forward_direction: boolean; // 編成の前位向きと列車の上り向きが一致するか否か
    station_list: optdia_line_station[]; // 路線に駅を紐付ける情報(下記)を起点側の駅のものから順に配列で
}


// 駅IDと駅情報のペアを格納するオブジェクト
interface optdia_station_dict {
    [station_id: string]: optdia_station; // 各駅の情報(下記)
}


// 駅情報を格納するオブジェクト
interface optdia_station {
    station_name: string; // 駅名
    station_name_kana: string; // 駅名のひらがな表記
    station_initial: string | null; // 駅名の1文字表記(使用しない場合はnull)
    is_major_station: boolean; // 主要駅か否か
    is_signal_station: boolean; // 信号場か否か
    show_arrival_time: boolean; // 時刻表で着時刻を表示するか否か
    show_track_number: boolean; // 時刻表で乗り場を表示するか否か
    tracks: optdia_station_track[]; // 乗り場情報(下記)を表示順に配列で
}


// 乗り場情報を格納するオブジェクト
interface optdia_station_track {
    track_id: string; // 乗り場ID(異なる駅との重複は制限されない)
    track_number: string; // 乗り場番号(アルファベット等も使用可能)
}


// 路線に駅情報を紐付けるためのオブジェクト
interface optdia_line_station {
    station_id: string; // 駅ID
    station_number: string | null; // 駅番号
    inbound_main_track: string | null; // 上り本線の乗り場ID
    outbound_main_track: string | null; // 下り本線の乗り場ID
    absolute_standard_running_time: number | null; // 起点駅からの基準運転時分(秒単位、未入力の場合はnull)
}


// 運行系統情報を格納するオブジェクト
interface optdia_route {
    route_id: string; // 運行系統ID
    route_name: string; // 運行系統名
    line_segments: optdia_line_segment[]; // 路線の部分区間(下記)を下り列車の通過順に配列で
    trains_by_diagram: optdia_route_diagram_dict; // ダイヤ別の上下列車情報(下記)
}


// 路線の部分区間情報を格納するオブジェクト
interface optdia_line_segment {
    line_id: string; // 路線ID
    start_station: string; // 区間の始点となる駅のID
    end_station: string; // 区間の終点となる駅のID(始点と終点の位置関係が路線情報での駅の順序と逆の場合は、路線が逆向きで経路に配置されていることを意味する)
}


// 運転ダイヤIDとそのダイヤで運転される列車の情報のペアを格納するオブジェクト
interface optdia_route_diagram_dict {
    [diagram_id: string]: optdia_route_diagram_trains; // 各ダイヤの上下列車情報(下記)
}


// 運行系統・運転ダイヤ別の上下列車情報を格納するオブジェクト
interface optdia_route_diagram_trains {
    inbound_trains: optdia_train[]; // 上り列車の情報(下記)を表示順に配列で
    outbound_trains: optdia_train[]; // 下り列車の情報(個々のオブジェクトの基本構造は上り列車と同じ)を表示順に配列で
}


// 列車種別情報を格納するオブジェクト
interface optdia_train_type {
    train_type_id: string; // 列車種別ID
    train_type_name: string; // 列車種別名
    train_type_short_name: string; // 列車種別の短縮名
    train_name: string | null;// 列車愛称
    is_in_service: boolean; // 営業列車の種別か否か
    main_color: string; // 列車種別の基本色(デフォルト値は #333333)
    background_color: string; // 時刻表での列車種別の背景色(デフォルト値は #ffffff)
    line_weight: "thin" | "normal" | "bold"; // ダイヤグラムでの線の太さ(細、標準、太)
    line_style: "solid" | "dashed" | "dotted"; // ダイヤグラムでの線スタイル(実線、破線、点線)
}


// 運転ダイヤ情報を格納するオブジェクト
interface optdia_diagram {
    diagram_id: string; // 運転ダイヤID
    diagram_name: string; // 運転ダイヤ名
    background_color: string; // 駅時刻表等での運転ダイヤの背景色(デフォルト値は #cccccc)
}


// 列車情報を格納するオブジェクト
interface optdia_train {
    train_id: string; // 列車ID
    train_number: string; // 列車番号(アルファベット等も使用可能)
    operations: optdia_train_operation[]; // 列車の担当運用情報(下記)を前位側(方反でない場合を基準とする)から順に配列で
    train_type_id: string | null; // 列車種別ID
    named_train_number: number | null; // 列車の号数
    car_count: null | number; // 両数(nullの場合は担当運用の所定両数の合計値が指定されたものとみなす)
    destination: null | string; // 行き先表示(nullの場合は終着駅の駅名が指定されたものとみなす)
    subsequent_trains: string[]; // 連続する列車のID(0〜2件)
    note: string; // 備考
    stops: optdia_train_stop[]; // 経由駅情報(下記)を経由順に配列で
}


// 列車の経由駅情報
interface optdia_train_stop {
    station_id: string; // 駅ID
    track_id: string | null; // 乗り場ID
    arrival_time: string; // 到着時刻(hh:mm:ss形式)
    departure_time: string; // 発車時刻(hh:mm:ss形式)
    stop_type: 1 | 0 | -1; // 客扱い情報(1:停車、0:通過、-1運転停車)
}


// 車両運用IDと車両運用情報のペアを格納するオブジェクト
interface optdia_operation_dict {
    [operation_id: string]: optdia_operation; // 各車両運用の情報(下記)
}


// 車両運用情報を格納するオブジェクト
interface optdia_operation {
    operation_number: string; // 運用番号(アルファベットや漢字等も使用可能)
    car_count: number; // 運用の所定両数
    min_car_count: number; // 運用に充当可能な最低の編成両数
    max_car_count: number; // 運用に充当可能な最大の編成両数
    main_color: string; // 運用の表示色(デフォルト値は #ffffff)
    start_location: string; // 運用の出庫場所名
    start_track: string | null; // 運用の出庫場所の乗り場等(乗り場等が規定されていない場合はnull)
    start_time: string | null; // 運用の出庫時間(hh:mm:ss形式、出庫しない場合はnull)
    end_location: string; // 運用の入庫場所名
    end_track: string | null; // 運用の入庫場所の乗り場等(乗り場等が規定されていない場合はnull)
    end_time: string; // 運用の入庫時間(hh:mm:ss形式、入庫しない場合はnull)
    note: string; // 備考
    temporary_stabling_events: optdia_temporary_stabling_event[]; // 一時入庫の情報(下記)を時系列順に配列で
}


// 一時入庫の情報
interface optdia_temporary_stabling_event {
    stabled_location: string; // 入庫場所名
    start_time: string; // 入庫時刻
    end_time: string; // 出庫時刻
    formations_can_changed: boolean; // 編成が変更される可能性があるか否か
    note: string; // 備考
}


// 列車の担当運用を格納するオブジェクト
interface optdia_train_operation {
    operation_id: string; // 車両運用ID
    formation_is_reversed: boolean; // 方反(編成の向きが逆転している状態)か否か
}


// 車両運用グループの情報を格納するオブジェクト
interface optdia_operation_group {
    operation_group_id: string; // 運用グループID
    operation_group_name: string; // 運用グループ名
    main_color: string; // 運用グループの表示色(デフォルト値は #ffffff)
    operations: string[]; // グループに属する車両運用のIDを表示順に配列で
}
