# OptDia

**鉄道ダイヤグラム編集ソフトの新しい選択肢**  
  
OptDiaはクロスプラットフォームの鉄道時刻表・車両運用表編集アプリケーションです。  
時刻表は一般的な表計算ソフトに近い感覚で操作可能としており、車両運用表もグラフィカルな編集に対応しています。


## システム要件・インストール方法

OptDiaの動作には以下のシステム構成を推奨します。

- 各種GNU/Linuxディストリビューション(Fedoraにて動作確認済み)、またはWindows 11
- 最新安定版のPython 3
- PySide6(およびQt6)

上記の構成が適切にインストールされている環境であれば、OptDia本体(optdia.py)はファイルをダブルクリックするだけで起動します。


## アイコン・スタイルシート更新時の操作

assets.qrcに記載されているアイコンやスタイルシートなどのファイルを編集した場合や、assets.qrcのファイルを追加または削除した場合は、assets.qrcのあるフォルダで以下のコマンドを実行してassets_rc.pyを更新してください。  
※このコマンドを実行するには、事前に端末へpyside6-toolsパッケージをインストールしておく必要があります。

```
pyside6-rcc -compress-algo zlib assets.qrc -o assets_rc.py
```


## Windows用インストーラーのビルド

### インストーラーの作成に必要なアプリケーション
Windows用のインストーラーパッケージを作成するには、以下のアプリケーションを導入済みのWindows端末が必要となります。

- PyInstaller
- Inno Setup

### インストーラーの作成
インストーラーを作成するには、まず、optdia.pyのあるフォルダにて以下のコマンドを実行してください。

```
python -m PyInstaller --noconsole --onedir ./optdia.py --icon ./assets/app_icon.ico
```

次に、Inno Setupでoptdia.issを開き、以下の項目を設定してからコンパイルを実行すればインストーラーが生成されます。

- MyAppVersion ・・・ OptDia本体のバージョン番号を設定してください。
- WorkDir ・・・ optdia.issがあるフォルダの絶対パスを指定してください。


## ライセンス

OptDia本体とこのリポジトリに含まれる各種ファイルは無権利創作宣言( https://www.2pd.jp/license/ )に準拠して著作権放棄されています。


## このリポジトリについて

2pd.jpドメインのFossilリポジトリ( https://fossil.2pd.jp/optdia/ )以外は全てミラーです。リポジトリのクローンを行う場合はFossilリポジトリのご利用を推奨します。  
また、このソフトウェアについてのお問い合わせや不具合の報告はMidari Createへご連絡ください。
