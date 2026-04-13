# PiLot OS 仕様書 v1.0

Tesla車両管理に特化したRaspberry Pi向けアプライアンスOS

---

## 0. ドキュメント情報

| 項目 | 内容 |
|------|------|
| プロジェクト名 | PiLot |
| バージョン | v1.0（初版） |
| 作成日 | 2026-04-13 |
| 著作権 | RTCK |
| 対象車両 | Tesla全車種（Model Y RWD LFPを主要テスト対象） |
| ライセンス | 未定（OSS or 商用、後日決定） |

---

## 1. プロダクト概要

### 1.1 PiLotとは

PiLotは、microSDカードを焼いてRaspberry Piに差し込み、電源を入れるだけでTesla車両のデータロガー兼ダッシュボードとして動作するアプライアンスOSである。Docker、PostgreSQL、Grafanaといった技術スタックの知識を一切要求せず、ブラウザベースの初期設定ウィザードのみで運用を開始できる。

### 1.2 解決する課題

既存のTesla車両データ管理ツールには以下の課題がある。

TeslaMateはDocker Compose＋PostgreSQL＋Grafanaの知識が必須であり、技術者以外のテスラオーナーにとって導入障壁が極めて高い。TeslaFi・Tessie等の商用SaaSは月額課金に加え、走行データ・位置情報を第三者サーバーに預ける必要がある。Tesla公式アプリは走行履歴・電費分析が極めて簡素で、過去データの参照もほぼ不可能である。

PiLotはこれらの課題を「microSD焼くだけ」のワンアクションで解決する。

### 1.3 ターゲットユーザー

主要ターゲットはDockerやLinuxに馴染みのないテスラオーナーである。電費や充電コストに関心があり、データを自分の手元で管理したいが、サーバー構築の知識はない層を想定する。副次的ターゲットとして、TeslaMateのセットアップに挫折した技術者層、プライバシーを重視しクラウドSaaSを避けたい層も含む。

### 1.4 コアバリュー

| 価値 | 実現方法 |
|------|---------|
| ゼロコンフィグ | microSD焼き→電源ON→ブラウザで初期設定、以上 |
| データ主権 | 全データがローカルSDまたはユーザー指定のストレージに保存 |
| 電費特化 | 日本市場向けkm/kWh表示、ガソリン換算、季節・速度相関を標準搭載 |
| 自然言語アクセス | Claude Code連携により「先月の電費平均は？」で回答が返る |
| 拡張性 | GitHub CLI連携によるOS自体のカスタマイズ・コントリビューション |

---

## 2. システムアーキテクチャ

### 2.1 ベースOS

Raspberry Pi OS Lite（64-bit、Debian Bookworm ベース）をベースイメージとする。デスクトップ環境は搭載しない。PiLot固有のサービス群・設定・初期セットアップウィザードをプリインストールした状態でイメージを配布する。

ベースOSの選定理由は以下の通り。Raspberry Pi公式の最も安定したディストリビューションであること、apt パッケージエコシステムへのフルアクセス、Pi 3B〜Pi 5まで単一イメージで対応可能な公式サポート、OTA更新の基盤として実績があること。

### 2.2 全体構成図

```
┌─────────────────────────────────────────────────────┐
│  PiLot OS (Raspberry Pi OS Lite 64-bit)             │
│                                                     │
│  ┌───────────────┐  ┌────────────────────────────┐  │
│  │ tesla-poller   │  │ pilot-dashboard            │  │
│  │ (systemd)     │  │ (systemd)                  │  │
│  │               │  │                            │  │
│  │ Python 3.11+  │  │ FastAPI + uvicorn          │  │
│  │ Tesla Fleet   │  │ Jinja2 + Chart.js          │  │
│  │ API Client    │  │ WebSocket (live updates)   │  │
│  │  │            │  │                   │        │  │
│  │  ▼            │  │                   ▼        │  │
│  │ SQLite ◄──────┼──┼── Read ───────────┘        │  │
│  │ (WAL mode)    │  │                            │  │
│  └───────────────┘  └────────────────────────────┘  │
│                                                     │
│  ┌───────────────┐  ┌────────────────────────────┐  │
│  │ pilot-setup    │  │ pilot-sync                 │  │
│  │ (systemd)     │  │ (systemd timer)            │  │
│  │               │  │                            │  │
│  │ 初期設定       │  │ Google Drive同期           │  │
│  │ ウィザード     │  │ 外部ストレージ管理         │  │
│  │ (ポート 8080) │  │ バックアップ               │  │
│  └───────────────┘  └────────────────────────────┘  │
│                                                     │
│  ┌───────────────┐  ┌────────────────────────────┐  │
│  │ Claude Code    │  │ GitHub CLI                 │  │
│  │ (on-demand)   │  │ (pre-installed)            │  │
│  │               │  │                            │  │
│  │ 自然言語で     │  │ OS自体の更新              │  │
│  │ データクエリ   │  │ カスタマイズ               │  │
│  └───────────────┘  └────────────────────────────┘  │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │ pilot-kiosk (systemd, HDMI検出時のみ)        │    │
│  │ cage + Chromium → http://localhost            │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │ Tailscale (optional)                         │    │
│  │ リモートアクセスVPN                          │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

### 2.3 サービス一覧

| サービス名 | 種別 | ポート | 説明 |
|-----------|------|-------|------|
| tesla-poller | systemd service | — | Tesla Owner's APIポーリング、データ記録 |
| pilot-dashboard | systemd service | 80 (HTTP) | Webダッシュボード配信 |
| pilot-setup | systemd service | 8080 | 初期設定ウィザード（設定完了後に無効化） |
| pilot-kiosk | systemd service | — | HDMI接続時のキオスクブラウザ（cage + Chromium） |
| pilot-sync | systemd timer | — | 外部ストレージ・Google Drive同期 |
| pilot-watchdog | systemd service | — | サービス死活監視、自動復旧 |
| tailscaled | systemd service | — | リモートアクセスVPN（オプション） |

### 2.4 Dockerレス設計の理由

PiLotはDockerを一切使用しない。理由は以下の通り。

Pi 3B（1GB RAM）ではDockerデーモン自体が50-100MBのメモリを消費し、残りリソースでアプリケーションを動かす余裕がない。4コンテナ構成（TeslaMate相当）ではメモリ不足で実用に耐えない報告が複数ある。

PiLotのワークロードは単純である。数秒〜数十秒に1回のHTTPリクエスト、SQLiteへの1行INSERT、静的アセット＋JSONの配信。これにコンテナオーケストレーションは不要であり、systemdの`Restart=always`で十分な可用性を確保できる。

ターゲットユーザーにとって「Dockerとは何か」を説明すること自体が導入障壁となる。OSレベルでサービスが統合されていることで、ユーザーはその存在を意識する必要がない。

---

## 3. ハードウェア要件

### 3.1 サポートティア

| ティア | 対象ハードウェア | RAM | ストレージ | 状態 |
|--------|----------------|-----|----------|------|
| 推奨 | Raspberry Pi 5 | 4GB+ | NVMe SSD（HAT経由） | フル機能、最高性能 |
| 推奨 | Raspberry Pi 4 Model B | 2GB+ | USB 3.0 SSD | フル機能 |
| 最低要件 | Raspberry Pi 3 Model B / B+ | 1GB | microSD（高耐久） | フル機能、パフォーマンス注意 |
| 非対応 | Pi Zero / Zero 2 W / Pi 2以下 | — | — | メモリ・NIC不足 |

### 3.2 ストレージ要件

最低容量は16GB。推奨容量は32GB以上。テスラの走行データは走行中5秒間隔・駐車中60秒間隔のロギングで年間約4-18GBを消費する。3年運用を想定すると64GB以上が望ましい。

Pi 3Bの場合はmicroSDカードが唯一のストレージオプションとなる。Samsung PRO EnduranceまたはKingston High Endurance等の高耐久カードを推奨する。PiLotの書き込み頻度（数MB/日）であれば高耐久SDで3-5年の運用が見込める。

Pi 4以降ではUSB 3.0接続のSSD、Pi 5ではNVMe SSDを推奨する。

### 3.3 ネットワーク要件

有線Ethernet接続を推奨する。WiFiは初期設定およびEthernet非対応環境でのフォールバックとして対応する。Tesla Fleet APIへの常時インターネット接続が必須である。

### 3.4 電源

5V/3A以上のUSB電源を推奨する。UPS HAT（PiSugar 3等）はオプションだが、突然の電源断によるSDカード破損防止のために推奨する。

---

## 4. 初期セットアップフロー

### 4.1 イメージ書き込み

ユーザーはPiLot公式サイトからイメージファイル（.img.xz）をダウンロードし、Raspberry Pi ImagerまたはbalenaEtcher等でmicroSDカードに書き込む。Raspberry Pi Imagerの場合、カスタム設定画面でWiFi SSID・パスワード、ホスト名の事前設定が可能である。

### 4.2 初回起動

電源投入後、以下の処理が自動実行される。

1. ファイルシステムの拡張（SD全容量を使用）
2. パーティション構成の最適化（tmpfs設定、swap無効化）
3. pilot-setupサービスの起動（ポート8080）
4. mDNSによるホスト名ブロードキャスト（`pilot.local:8080`）

### 4.3 セットアップウィザード（ブラウザ）

同一ネットワーク上のデバイスから`http://pilot.local:8080`にアクセスすると、以下のステップを案内するウィザードが表示される。

**Step 1: 言語・地域設定**
言語（日本語/English）、タイムゾーン、電費表示単位（km/kWh, Wh/km, kWh/100km）、通貨を選択。

**Step 2: Tesla アカウント連携**
Tesla Owner's APIのOAuth 2.0フローを実行する。ユーザーはTeslaアカウントのメールアドレスとパスワード（＋MFA）でログインし、PiLotにデータアクセスを許可する。取得したリフレッシュトークンはローカルに暗号化保存される。複数車両がアカウントに紐づく場合は対象車両を選択する。開発者登録やドメイン設定は一切不要である。

**Step 3: 車両情報確認**
APIから取得した車両情報（モデル、VIN、バッテリータイプ、ソフトウェアバージョン）を表示し、正しいことを確認。rated効率定数のデフォルト値を車種から自動設定する。

**Step 4: 電気料金設定**
自宅充電の電気料金プランを設定する。固定単価（¥/kWh）または時間帯別単価（深夜・昼間・ピーク）に対応する。スーパーチャージャー料金はTeslaのデフォルト値をプリセット。

**Step 5: ストレージ設定**
デフォルトのローカルSDストレージに加え、外部USB SSD（検出された場合に表示）およびGoogle Drive同期のオプションを設定する。

**Step 6: オプション機能**
Tailscale（リモートアクセス）、Claude Code連携、GitHub CLI連携の有効化を選択する。

**Step 7: 完了**
設定サマリーを表示し、確定後にtesla-pollerおよびpilot-dashboardサービスを起動する。pilot-setupサービスは無効化し、以降はダッシュボードのポート80に自動リダイレクトする。

### 4.4 セットアップウィザードの再実行

ダッシュボードの設定画面から、またはSSHで`sudo pilot-reconfigure`コマンドを実行することで、セットアップウィザードを再度起動できる。

---

## 5. データ収集エンジン（tesla-poller）

### 5.1 アーキテクチャ

Python 3.11+で実装する。asyncioベースの非同期設計とし、以下のコンポーネントで構成する。

**StateManager**: 車両の状態（online/asleep/driving/charging/idle）を管理するステートマシン。状態に応じてポーリング間隔と取得エンドポイントを動的に切り替える。

**TeslaAPIClient**: Tesla Fleet APIとの通信を担当。OAuth 2.0トークンの自動リフレッシュ、レートリミット管理、エラーハンドリングを内包する。

**DataRecorder**: APIレスポンスをパースし、SQLiteに書き込む。走行・充電セッションの開始/終了を自動検出し、集約レコードを生成する。

**SleepGuard**: 車両のスリープを妨害しないよう、アイドル状態を検知して軽量APIに切り替える。バンパイアドレインの最小化が目的。

### 5.2 ポーリング戦略

| 車両状態 | ポーリング対象 | 間隔 | 理由 |
|---------|--------------|------|------|
| driving | vehicle_data | 5秒 | 高精度の走行ログ取得 |
| charging | vehicle_data | 60秒 | 充電カーブの記録に十分 |
| idle（〜15分） | vehicle_data | 30秒 | ユーザーが乗車しようとしている可能性 |
| idle（15分〜） | vehicles（状態のみ） | 90秒 | スリープ試行を妨害しない |
| asleep | vehicles（状態のみ） | 120秒 | 起床検知のみ |
| offline | vehicles（状態のみ） | 300秒 | 圏外・地下駐車場等 |

**重要**: `GET /api/1/vehicles/{vin}`（車両リスト）は車両を起こさない。`vehicle_data`は車両のスリープタイマーをリセットする。この区別がバンパイアドレイン防止の鍵となる。

### 5.3 スリープガードのロジック

```
アイドル検出
  → 15分経過: vehicle_dataポーリング停止
  → vehicles（状態確認のみ）に切り替え
  → 車両がasleepを報告: ポーリング間隔を120秒に拡大
  → 車両がonlineに復帰: vehicle_dataポーリング再開
  → 走行（shift_state != null）検出: driving状態へ遷移
  → 充電（charging_state == "Charging"）検出: charging状態へ遷移
```

### 5.4 API戦略: Owner's API優先、Fleet APIはオプション

PiLot v1.0では**Tesla Owner's API（非公式）**をデフォルトのデータソースとして使用する。

**Owner's APIを選択する理由**:

Owner's APIはTesla公式モバイルアプリが使用しているものと同一のAPIであり、認証はTeslaアカウントのメールアドレスとパスワード（＋MFA）のみで完結する。開発者登録、アプリ審査、ドメインへの公開鍵ホスティングといったFleet API固有の手順が一切不要であり、PiLotの「microSD焼いてウィザードで設定するだけ」というコンセプトと完全に整合する。

APIコストはゼロである。Fleet APIが従量課金制（2025年1月〜）であるのに対し、Owner's APIには課金の仕組み自体が存在しない。

**Owner's APIのリスク**:

Owner's APIは非公式であり、Teslaがいつでも廃止・変更する可能性がある。ただしTesla公式アプリ自体が同じAPIを使用しているため、突然の廃止は考えにくい。TeslaMateを含む主要なOSSプロジェクトが長年このAPIをベースに動作し続けている実績もある。

**方針**: Owner's APIが塞がれた場合はFleet APIへの移行を検討するか、サービス終了とする。

#### Owner's API認証

| 項目 | 値 |
|------|---|
| Authorization URL | `https://auth.tesla.com/oauth2/v3/authorize` |
| Token URL | `https://auth.tesla.com/oauth2/v3/token` |
| API Base URL | `https://owner-api.teslamotors.com/api/1` |
| 認証方式 | OAuth 2.0（Teslaアカウント認証） |
| リフレッシュトークン有効期限 | 約45日（使用で延長） |

セットアップウィザードでTeslaアカウントにログインするだけでトークンを取得する。リフレッシュトークンはローカルに暗号化保存し、自動リフレッシュで維持する。

#### Fleet API対応（オプション）

上級者向けオプションとして、ユーザーが自身のFleet APIアプリケーション登録（Client ID / Client Secret）を持っている場合に、Fleet APIへの切り替えを設定画面から行えるようにする。Fleet APIを使用する場合、以下のメリットがある。

- 公式サポートされたAPIであり長期的な安定性が高い
- Fleet Telemetry（プッシュ型データ配信）が利用可能
- 車両コマンド（充電開始/停止、エアコン制御等）が利用可能

ただしFleet APIの利用には開発者登録・審査・ドメイン設定が必要であり、月$10のクレジットを超える使用量には従量課金が発生する。PiLotのセットアップウィザードではこれらの手順を案内するが、Owner's APIと比較してセットアップ難易度は大幅に上がる。

### 5.5 レートリミットとスリープ保護

Owner's APIにはTesla公式のレートリミット仕様は公開されていないが、コミュニティの知見として以下が知られている。

- 過剰なリクエスト（数秒間隔の連続ポーリング等）でHTTP 429が返る場合がある
- 車両のスリープを妨げる過度なポーリングは待機電力（バンパイアドレイン）の原因となる

PiLotでは5.2節のポーリング戦略に従い、車両状態に応じた適切な間隔でリクエストを行う。特にアイドル→スリープ遷移期間中はvehicle_dataを叩かず、状態確認のみの軽量リクエストに切り替えることでバンパイアドレインを最小化する。

### 5.6 Fleet Telemetry対応（将来・Fleet API有効時のみ）

Fleet TelemetryはFleet APIの機能であり、サーバーサイドプッシュ型のデータ配信でポーリングより高精度かつ低コストなデータ取得が可能である。ただし公開ドメインへのmTLS WebSocket待ち受けが必要であり、Pi 3B＋家庭ネットワーク環境での運用ハードルが高い。

Fleet API有効ユーザー向けのオプション機能として、v2.0以降でTailscale Funnel経由のFleet Telemetry受信を追加する計画とする。データベーススキーマは、Telemetry固有フィールド（EnergyRemaining, PackVoltage, PackCurrent等）の格納に対応できるよう拡張可能な設計とする。

---

## 6. データベース設計

### 6.1 エンジン選定

SQLite 3（WALモード）を使用する。

選定理由は以下の通り。Pi 3B（1GB RAM）での動作に最適であること（使用メモリ5-20MB）。サーバープロセス不要で運用管理コストがゼロであること。単一ファイルのためバックアップ・移行が`cp`で完結すること。PiLotの「単一ライター＋中程度リード」パターンにWALモードが完全に適合すること。

PRAGMA設定は以下の通り。

```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = -8000;      -- 8MB（Pi 3Bでは-4000に縮小）
PRAGMA busy_timeout = 5000;
PRAGMA foreign_keys = ON;
PRAGMA auto_vacuum = INCREMENTAL;
```

データベースファイルの配置はデフォルトで`/var/lib/pilot/pilot.db`とする。

### 6.2 テーブル定義

#### cars（車両マスタ）

```sql
CREATE TABLE cars (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    vin           TEXT NOT NULL UNIQUE,
    model         TEXT,                    -- 'Model Y', 'Model 3' 等
    trim          TEXT,                    -- 'RWD', 'Long Range', 'Performance'
    battery_type  TEXT,                    -- 'LFP', 'NMC', '4680'
    exterior_color TEXT,
    car_version   TEXT,                    -- ソフトウェアバージョン
    efficiency    REAL DEFAULT 0.149,      -- rated kWh/km（Model Y RWD LFP default）
    usable_battery_capacity_kwh REAL DEFAULT 57.0,
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now'))
);
```

#### positions（走行中のデータポイント、最大テーブル）

```sql
CREATE TABLE positions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    car_id          INTEGER NOT NULL REFERENCES cars(id),
    drive_id        INTEGER REFERENCES drives(id),
    timestamp       TEXT NOT NULL,          -- ISO 8601
    latitude        REAL,
    longitude       REAL,
    speed           INTEGER,                -- km/h
    power           REAL,                   -- kW（正=消費、負=回生）
    odometer        REAL,                   -- km
    battery_level   INTEGER,                -- SOC %
    usable_battery_level INTEGER,
    rated_range_km  REAL,                   -- 定格レンジ km
    est_range_km    REAL,                   -- 推定レンジ km
    elevation       INTEGER,                -- 標高 m（SRTM/API由来）
    heading         INTEGER,                -- 方位 0-359
    inside_temp     REAL,                   -- °C
    outside_temp    REAL,                   -- °C
    is_climate_on   INTEGER DEFAULT 0,      -- boolean
    battery_heater  INTEGER DEFAULT 0,      -- boolean
    tpms_fl         REAL,                   -- タイヤ空気圧 bar
    tpms_fr         REAL,
    tpms_rl         REAL,
    tpms_rr         REAL,
    fan_status      INTEGER
);

CREATE INDEX idx_positions_drive ON positions(drive_id);
CREATE INDEX idx_positions_timestamp ON positions(car_id, timestamp);
```

#### drives（走行セッション集約）

```sql
CREATE TABLE drives (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    car_id                INTEGER NOT NULL REFERENCES cars(id),
    start_time            TEXT NOT NULL,
    end_time              TEXT,
    start_lat             REAL,
    start_lng             REAL,
    end_lat               REAL,
    end_lng               REAL,
    start_address         TEXT,
    end_address           TEXT,
    distance_km           REAL,             -- 走行距離
    duration_min          REAL,
    start_odometer        REAL,
    end_odometer          REAL,
    start_battery_level   INTEGER,
    end_battery_level     INTEGER,
    start_rated_range_km  REAL,
    end_rated_range_km    REAL,
    outside_temp_avg      REAL,
    speed_max             INTEGER,
    speed_avg             REAL,
    power_max             REAL,             -- 最大消費 kW
    power_min             REAL,             -- 最大回生 kW（負値）
    total_ascent_m        INTEGER,          -- 累積上昇 m
    total_descent_m       INTEGER,          -- 累積下降 m
    -- 電費（計算値）
    energy_consumed_kwh   REAL,             -- 消費電力量
    energy_regen_kwh      REAL,             -- 回生電力量
    efficiency_whkm       REAL,             -- Wh/km
    efficiency_kmkwh      REAL,             -- km/kWh
    road_type             TEXT,             -- 'highway', 'city', 'mixed'（速度分布から推定）
    is_complete           INTEGER DEFAULT 0
);

CREATE INDEX idx_drives_time ON drives(car_id, start_time);
```

#### charging_sessions（充電セッション集約）

```sql
CREATE TABLE charging_sessions (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    car_id                INTEGER NOT NULL REFERENCES cars(id),
    start_time            TEXT NOT NULL,
    end_time              TEXT,
    latitude              REAL,
    longitude             REAL,
    address               TEXT,
    charger_type          TEXT,             -- 'home_ac', 'supercharger', 'chademo', 'destination', 'other_dc'
    charger_brand         TEXT,
    start_battery_level   INTEGER,
    end_battery_level     INTEGER,
    charge_energy_added   REAL,             -- kWh（車載表示値）
    charge_energy_used    REAL,             -- kWh（グリッド由来推定値）
    max_charger_power     REAL,             -- kW
    duration_min          REAL,
    outside_temp_avg      REAL,
    cost_jpy              REAL,             -- コスト（円）
    cost_per_kwh          REAL,             -- 単価（¥/kWh）
    is_complete           INTEGER DEFAULT 0
);
```

#### charges（充電中のデータポイント）

```sql
CREATE TABLE charges (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    charging_session_id   INTEGER NOT NULL REFERENCES charging_sessions(id),
    timestamp             TEXT NOT NULL,
    battery_level         INTEGER,
    usable_battery_level  INTEGER,
    charge_energy_added   REAL,             -- kWh
    charger_power         REAL,             -- kW
    charger_voltage       INTEGER,
    charger_current       INTEGER,
    charger_phases        INTEGER,
    outside_temp          REAL,
    battery_heater        INTEGER DEFAULT 0,
    conn_charge_cable     TEXT,
    fast_charger_type     TEXT
);

CREATE INDEX idx_charges_session ON charges(charging_session_id);
```

#### states（車両状態遷移記録）

```sql
CREATE TABLE states (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    car_id     INTEGER NOT NULL REFERENCES cars(id),
    state      TEXT NOT NULL,               -- 'online', 'asleep', 'offline', 'driving', 'charging'
    start_time TEXT NOT NULL,
    end_time   TEXT
);
```

#### settings（ユーザー設定）

```sql
CREATE TABLE settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
-- 初期値例:
-- 'locale' -> 'ja'
-- 'timezone' -> 'Asia/Tokyo'
-- 'efficiency_unit' -> 'km_kwh'     -- 'km_kwh', 'wh_km', 'kwh_100km'
-- 'currency' -> 'JPY'
-- 'electricity_rate_home' -> '{"type":"tou","night":12.5,"day":28.0,"peak":38.0}'
-- 'sc_rate_per_kwh' -> '55'
-- 'gasoline_price_per_liter' -> '175'
-- 'gasoline_reference_kmpl' -> '15'
-- 'google_drive_enabled' -> 'false'
-- 'google_drive_folder_id' -> ''
-- 'external_storage_path' -> ''
-- 'tailscale_enabled' -> 'false'
-- 'claude_code_enabled' -> 'false'
```

#### software_updates（ソフトウェア更新履歴）

```sql
CREATE TABLE software_updates (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    car_id     INTEGER NOT NULL REFERENCES cars(id),
    version    TEXT NOT NULL,
    timestamp  TEXT NOT NULL
);
```

#### telemetry_extra（Fleet Telemetry専用フィールド、将来拡張）

```sql
CREATE TABLE telemetry_extra (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    car_id          INTEGER NOT NULL REFERENCES cars(id),
    timestamp       TEXT NOT NULL,
    field_name      TEXT NOT NULL,          -- 'EnergyRemaining', 'PackVoltage' 等
    field_value     REAL
);

CREATE INDEX idx_telemetry_ts ON telemetry_extra(car_id, timestamp, field_name);
```

### 6.3 電費計算ロジック

PiLotは定格レンジ変化法（TeslaMate方式）をベースとし、将来のFleet Telemetry対応時にEnergyRemaining差分法へ移行する設計とする。

**走行1回あたりの消費電力量（kWh）**:

```
energy_consumed_kwh = (start_rated_range_km - end_rated_range_km) × cars.efficiency
```

**電費（Wh/km）**:

```
efficiency_whkm = energy_consumed_kwh × 1000 / distance_km
```

**電費（km/kWh）**:

```
efficiency_kmkwh = distance_km / energy_consumed_kwh
```

**ガソリン換算（km/L相当）**:

```
gasoline_equivalent_kmpl = efficiency_kmkwh × gasoline_energy_density_kwh_per_liter
-- ガソリン1Lあたり約8.9kWhのエネルギー量
-- 例: 6.5 km/kWh × 8.9 = 57.9 km/L相当
```

**効率定数の自動校正**: 充電セッション（10分以上、SOC 95%未満）が2回以上蓄積された時点で、走行距離と充電量の関係から`cars.efficiency`を統計的に再計算し、デフォルト値を上書きする。

**道路種別の推定**: 走行中の速度分布から自動分類する。80km/h超の割合が60%以上であれば`highway`、30km/h以下が40%以上であれば`city`、それ以外は`mixed`とする。

---

## 7. ダッシュボード

### 7.1 技術スタック

| 層 | 技術 | 理由 |
|----|------|------|
| バックエンド | FastAPI（Python） | 軽量、async対応、型ヒント |
| テンプレート | Jinja2 | サーバーサイドレンダリングでPi負荷を軽減 |
| グラフ | Chart.js 4.x | クライアントサイドレンダリング、軽量 |
| 地図 | Leaflet.js + OpenStreetMap | ライセンスフリー |
| リアルタイム | WebSocket（FastAPI内蔵） | 充電中・走行中のライブ更新 |
| CSS | Tailwind CSS（CDN） | ビルド不要、レスポンシブ |

Pi 3Bでのメモリ使用目標はFastAPI＋uvicorn合計で80MB以下とする。

### 7.2 画面構成

#### ホーム

車両の現在状態をカード形式で表示する。SOC（大型ゲージ）、推定航続距離、現在地（地図サムネイル）、車両状態（走行中/充電中/スリープ中等）、直近の走行の電費サマリーを配置する。走行中・充電中はWebSocketでリアルタイム更新する。

#### 電費ダッシュボード（メイン画面）

電費分析に特化した画面。以下の要素で構成する。

**サマリーカード群**: 今日/今週/今月/通算の平均電費（km/kWhまたはWh/km）、走行距離、消費kWh、電気代（¥）。

**電費推移グラフ**: 日次/週次/月次の切り替え。折れ線グラフに外気温のオーバーレイ。

**速度帯別電費チャート**: 横軸=速度帯（10km/h刻み）、縦軸=平均Wh/km。空力抗力の指数的増加を可視化する。

**気温×電費散布図**: 横軸=外気温、縦軸=Wh/km。20°C付近がスイートスポットであることを視覚化する。

**道路種別比較**: 高速道路 vs 一般道 vs 混合の電費比較。棒グラフ。

**月間コスト**: 充電にかかった電気代の月間推移。ガソリン車での想定コストとの差額を併記。

#### 走行ログ

走行セッションの一覧をカード形式で表示する。各カードに日時、出発地→到着地、距離、電費、所要時間を表示する。カードをタップするとルート地図（Leaflet）＋標高プロファイル＋速度/電力/SOCの時系列グラフを展開する。

#### 充電ログ

充電セッションの一覧。場所、充電器種別、追加kWh、最大kW、所要時間、コスト（¥）を表示する。充電カーブ（SOC vs kW）のグラフ付き。自宅/SC/サードパーティのフィルタリング機能。

#### バッテリー健全性

SOC100%時の推定航続距離の推移グラフ（劣化トラッキング）。充電サイクル数（部分充電を累積）。LFP固有の注意事項（週1回100%充電推奨）をインフォカードで常時表示する。

#### 車両情報

ソフトウェアバージョン履歴、タイヤ空気圧の現在値と推移、走行距離（オドメーター）。

#### 設定

電気料金プラン、表示単位、ストレージ管理、Google Drive同期、Tailscale、Claude Code連携、GitHub CLI連携の設定画面。APIリクエスト数/コストのモニタリング。

### 7.3 日本市場向け表示ルール

電費の主表示は`km/kWh`とする（設定で変更可能）。全電費表示箇所にガソリン換算（km/L相当）を小テキストで併記するオプションを設ける。通貨は日本円（¥）をデフォルトとし、小数点以下は表示しない。日時は`YYYY/MM/DD HH:mm`形式。距離はkm、速度はkm/h、温度は°C、気圧はbar。

### 7.4 ローカルGUIモード（HDMI直結）

Raspberry PiにHDMIディスプレイ＋キーボード＋マウスを接続して、ダッシュボードを直接操作できるキオスクモードを提供する。PCやスマートフォンが手元にない状態でもPiLotの全機能にアクセス可能とし、ガレージや玄関への常設ディスプレイとしての利用も想定する。

#### 技術実装

PiLot OS Liteにはデスクトップ環境を搭載しないが、ローカルGUI用に最小限のディスプレイスタックをプリインストールする。

| コンポーネント | 役割 | メモリ使用目安 |
|-------------|------|-------------|
| cage | Wayland compositor（キオスク特化、軽量） | 5-10MB |
| Chromium | キオスクブラウザ（`--kiosk`モード） | 80-150MB |

`cage`は単一アプリケーションだけを全画面表示するWayland compositorで、GNOME/KDE等のデスクトップ環境と比較して極めて軽量である。Chromiumは`--kiosk --noerrdialogs --disable-translate --no-first-run`オプションでキオスクモード起動し、`http://localhost`（pilot-dashboard）を表示する。

```
# systemdサービス: pilot-kiosk.service
[Unit]
Description=PiLot Kiosk Display
After=pilot-dashboard.service
Wants=pilot-dashboard.service

[Service]
Type=simple
User=pilot
Environment=WLR_LIBINPUT_NO_DEVICES=1
ExecStart=/usr/bin/cage -- /usr/bin/chromium-browser \
    --kiosk \
    --noerrdialogs \
    --disable-translate \
    --no-first-run \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --disable-features=TranslateUI \
    --ozone-platform=wayland \
    http://localhost
Restart=always
RestartSec=5

[Install]
WantedBy=graphical.target
```

#### HDMIの自動検出と起動制御

pilot-kiosk.serviceは**HDMIケーブル接続時のみ自動起動**する。HDMI未接続（ヘッドレス運用）時はサービスを起動せず、cage/Chromiumのメモリ消費をゼロにする。

```bash
# /usr/lib/pilot/hdmi-detect.sh
# udevルールでHDMIホットプラグを検知し、kioskサービスを起動/停止
if tvservice -s | grep -q "HDMI"; then
    systemctl start pilot-kiosk.service
else
    systemctl stop pilot-kiosk.service
fi
```

Pi 3B（1GB RAM）ではChromiumのメモリ使用が支配的になるため、キオスクモード動作時のメモリバジェットは以下の通りとなる。

| コンポーネント | ヘッドレス時 | キオスク時 |
|-------------|-----------|----------|
| OS + systemd | 150MB | 150MB |
| tmpfs | 128MB | 128MB |
| tesla-poller | 40MB | 40MB |
| pilot-dashboard | 80MB | 80MB |
| cage + Chromium | 0MB | 90-150MB |
| SQLite キャッシュ | 32MB | 32MB |
| zram | 256MB | 256MB |
| **空き** | **314MB+** | **164-224MB** |

Pi 3Bでもキオスク動作は可能だが余裕は少なくなる。Pi 4（2GB+）以降では問題ない。ダッシュボードのデータ描画量が多い画面（長期間の電費推移グラフ等）ではPi 3Bでレンダリングがもたつく可能性があるが、データのページネーションとChart.jsのデータ間引き（decimation）で軽減する。

#### キオスクモードのUI調整

HDMI接続時は以下のUI最適化を自動適用する。

マウスカーソルの非表示（タッチ操作未検出時、30秒で自動非表示）。画面焼き付き防止のスクリーンセーバー（10分無操作で画面暗転、任意キー/マウスで復帰）。フルスクリーン表示に最適化されたレイアウト（ブラウザのアドレスバー・タブバーなし）。

#### リモートアクセスQRコード

キオスク画面のホーム画面右下に、ダッシュボードURLのQRコードを常時表示する。スマートフォンのカメラで読み取るだけで、URL手入力なしにダッシュボードへアクセスできる。

QRコードに埋め込むURLは以下の優先順位で決定する。

1. Tailscale有効時: `https://pilot.{tailnet}.ts.net`（外出先からもアクセス可能）
2. LAN内: `http://{実IP}` （mDNS非対応デバイスでも確実に接続）
3. フォールバック: `http://pilot.local`

QRコードはサーバーサイドでSVG生成（`qrcode`Pythonライブラリ）し、ダッシュボードのテンプレートに埋め込む。IPアドレスやTailscaleホスト名が変更された場合は自動で再生成する。

初期セットアップウィザード画面でも同様にQRコードを表示し、「スマートフォンで続きの設定を行う」フローにも対応する。Tesla OAuthのログイン画面はスマートフォンのブラウザのほうがパスワードマネージャーが使えて入力しやすいため、HDMI画面で開始→QR読み取り→スマホでTeslaログイン完了→Pi側に自動反映、というハンドオフフローも実装する。

#### 初期セットアップのローカル実行

初回起動時にHDMIが接続されている場合、セットアップウィザード（pilot-setup、ポート8080）もキオスクブラウザで直接表示する。これにより、別デバイスからのブラウザアクセスなしでPi単体でセットアップを完結できる。キーボードでWiFi設定やTeslaアカウントのログインを行う。

---

## 8. UI/UXデザインシステム

PiLotの全画面（ダッシュボード、セットアップウィザード、キオスク表示）に一貫して適用されるデザイン原則・コンポーネント・インタラクションパターンを定義する。

### 8.1 外部依存の排除方針

PiLotはインターネット接続が不安定な環境（ガレージ等）でも確実に動作する必要がある。CDNに依存するアセットは一切使用せず、全リソースをOS内にバンドルする。

| 種別 | 採用 | 不採用（理由） |
|------|------|--------------|
| CSS | バニラCSS＋CSS Custom Properties | Tailwind CDN（外部依存）、Bootstrap（肥大） |
| フォント | システムフォントスタック | Google Fonts（外部依存）、Webフォント全般 |
| アイコン | インラインSVG（自作/MIT） | Font Awesome CDN、Material Icons CDN |
| グラフ | Chart.js 4.x（ローカルバンドル） | 外部CDN経由のChart.js |
| 地図 | Leaflet.js（ローカルバンドル）＋OSMタイルキャッシュ | Google Maps API（外部依存＋有料） |
| QRコード | Python `qrcode`ライブラリでSVG生成 | 外部QRコードAPI |
| JavaScript | バニラJS（ES2020+） | React、Vue等のフレームワーク |

OSMタイルは初回表示時にローカルキャッシュし、以降はオフラインでも表示可能とする。キャッシュ容量の上限は設定画面で指定可能（デフォルト256MB）。

### 8.2 デザイン原則

**1. データファースト**: 装飾を排し、数値とグラフを最前面に出す。電費のkm/kWh値は常に1秒以内に視認できるサイズで表示する。

**2. グランサビリティ（一瞥性）**: ガレージを通りかかったときにチラッと見るだけで車両の状態がわかる。キオスク画面のホームは3m離れた距離から主要情報が読み取れるフォントサイズを確保する。

**3. 低認知負荷**: 1画面に表示する情報カテゴリは最大4つ。それ以上はタブまたはスクロールで分離する。操作導線は最大3タップで任意の画面に到達できる設計とする。

**4. 一貫性**: 同じデータは常に同じ色・形式・位置で表示する。電費は常に緑系、充電は常に青系、警告は常にアンバー系。

**5. オフラインファースト**: インターネット接続が切れてもダッシュボードは正常表示される。API通信エラー時は最後に取得したデータを表示し、接続状態をインジケーターで示す。

### 8.3 カラーシステム

ダークモードをデフォルトとする。車内・ガレージでの視認性と目への負担を考慮した選択である。ライトモードは設定で切り替え可能。

CSS Custom Propertiesで全色を定義し、テーマ切り替えは`:root`の変数差し替えのみで実現する。

#### ダークテーマ（デフォルト）

```css
:root[data-theme="dark"] {
  /* ベース */
  --color-bg-primary:     #0f1117;   /* 最背面 */
  --color-bg-secondary:   #1a1d27;   /* カード背景 */
  --color-bg-tertiary:    #242834;   /* 入力欄、ホバー */
  --color-border:         #2e3344;   /* 境界線 */
  --color-border-subtle:  #232738;   /* 薄い境界線 */

  /* テキスト */
  --color-text-primary:   #e8eaed;   /* 本文 */
  --color-text-secondary: #9aa0b0;   /* 補足 */
  --color-text-tertiary:  #6b7280;   /* プレースホルダー */
  --color-text-inverse:   #0f1117;   /* 反転テキスト */

  /* セマンティック — 電費・エネルギー */
  --color-efficiency:     #34d399;   /* 電費良好 — 緑 */
  --color-efficiency-bg:  #34d39915; /* 電費背景 */
  --color-charging:       #60a5fa;   /* 充電中 — 青 */
  --color-charging-bg:    #60a5fa15; /* 充電背景 */
  --color-driving:        #a78bfa;   /* 走行中 — 紫 */
  --color-driving-bg:     #a78bfa15; /* 走行背景 */
  --color-regen:          #2dd4bf;   /* 回生 — ティール */
  --color-consumption:    #fb923c;   /* 高消費 — オレンジ */

  /* ステータス */
  --color-success:        #34d399;
  --color-warning:        #fbbf24;
  --color-error:          #f87171;
  --color-info:           #60a5fa;

  /* SOCゲージ グラデーション */
  --color-soc-critical:   #ef4444;   /* 0-10% */
  --color-soc-low:        #f97316;   /* 10-20% */
  --color-soc-medium:     #eab308;   /* 20-50% */
  --color-soc-good:       #22c55e;   /* 50-80% */
  --color-soc-full:       #34d399;   /* 80-100% */
}
```

#### ライトテーマ

```css
:root[data-theme="light"] {
  --color-bg-primary:     #f8f9fb;
  --color-bg-secondary:   #ffffff;
  --color-bg-tertiary:    #f1f3f7;
  --color-border:         #e2e5eb;
  --color-border-subtle:  #edf0f4;
  --color-text-primary:   #1a1d27;
  --color-text-secondary: #5f6577;
  --color-text-tertiary:  #9aa0b0;
  --color-text-inverse:   #ffffff;
  /* セマンティックカラーは明度を調整、色相は維持 */
  --color-efficiency:     #059669;
  --color-charging:       #2563eb;
  --color-driving:        #7c3aed;
  --color-regen:          #0d9488;
  --color-consumption:    #ea580c;
}
```

#### カラー運用ルール

電費に関する数値は常に`--color-efficiency`で表示する。良い電費ほど彩度が高くなるグラデーションは使用しない（色覚多様性への配慮）。代わりに上下矢印（↑改善/↓悪化）をテキストで併記する。

グラフの系列色は最大6色とし、以下の固定パレットを使用する。

```css
--chart-1: #60a5fa;  /* 青 */
--chart-2: #34d399;  /* 緑 */
--chart-3: #a78bfa;  /* 紫 */
--chart-4: #fbbf24;  /* 黄 */
--chart-5: #fb923c;  /* オレンジ */
--chart-6: #f87171;  /* 赤 */
```

### 8.4 タイポグラフィ

システムフォントスタックのみを使用する。Webフォントのダウンロードは一切発生しない。

```css
:root {
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans JP",
               "Hiragino Sans", "Hiragino Kaku Gothic ProN", Meiryo,
               sans-serif;
  --font-mono: "SF Mono", "Cascadia Code", "Fira Code", "Noto Sans Mono CJK JP",
               Consolas, monospace;
}
```

日本語環境ではNoto Sans JP → Hiragino Sans → Meiryoの順にフォールバックする。

#### タイプスケール

| 用途 | サイズ | ウェイト | 行間 | 変数名 |
|------|-------|---------|------|--------|
| ヒーロー数値（SOC、電費メイン） | 48px / 3rem | 700 | 1.1 | `--text-hero` |
| 大型数値（カードのメイン値） | 32px / 2rem | 600 | 1.2 | `--text-display` |
| 画面タイトル | 24px / 1.5rem | 600 | 1.3 | `--text-title` |
| セクション見出し | 18px / 1.125rem | 600 | 1.4 | `--text-heading` |
| 本文 | 15px / 0.9375rem | 400 | 1.6 | `--text-body` |
| 補足テキスト | 13px / 0.8125rem | 400 | 1.5 | `--text-caption` |
| ラベル・単位 | 11px / 0.6875rem | 500 | 1.4 | `--text-label` |

キオスクモード（3m視認）ではヒーロー数値を72px、大型数値を48pxに自動スケールアップする。メディアクエリではなく、キオスク専用CSSクラスで制御する。

### 8.5 レイアウトシステム

CSS Gridをベースとし、画面幅に応じたブレークポイントでカラム数を切り替える。

```css
:root {
  --spacing-xs:  4px;
  --spacing-sm:  8px;
  --spacing-md:  16px;
  --spacing-lg:  24px;
  --spacing-xl:  32px;
  --spacing-2xl: 48px;

  --radius-sm:   6px;
  --radius-md:   10px;
  --radius-lg:   16px;
  --radius-full: 9999px;

  --shadow-card: 0 1px 3px rgba(0, 0, 0, 0.3);
  --shadow-elevated: 0 4px 12px rgba(0, 0, 0, 0.4);
}
```

#### ブレークポイント

| 名称 | 幅 | カラム数 | 用途 |
|------|---|---------|------|
| mobile | 〜639px | 1 | スマートフォン縦 |
| tablet | 640-1023px | 2 | タブレット、スマホ横 |
| desktop | 1024-1439px | 3 | PC、キオスク（HD） |
| wide | 1440px〜 | 4 | 大型モニター、キオスク（FHD） |

ダッシュボードのカードグリッドは上記カラム数に応じて自動リフローする。カード幅は`minmax(280px, 1fr)`で最低幅を保証し、潰れることを防ぐ。

### 8.6 コンポーネント定義

全コンポーネントはバニラHTML＋CSS＋JSで実装する。Webコンポーネント（Custom Elements）は使用しない（Pi 3BのChromiumバージョン互換性を考慮）。

#### データカード

ダッシュボードの基本構成要素。

```
┌─────────────────────────┐
│  ラベル           単位   │  ← --text-label, --color-text-secondary
│                         │
│  主要数値               │  ← --text-display, --color-text-primary
│                         │
│  サブ情報  |  トレンド   │  ← --text-caption, トレンド矢印
└─────────────────────────┘
```

構造: `background: var(--color-bg-secondary)`, `border: 1px solid var(--color-border-subtle)`, `border-radius: var(--radius-md)`, `padding: var(--spacing-lg)`。ホバー時は`border-color: var(--color-border)`にトランジション（150ms ease）。タップ/クリックで詳細ビューを展開するカードは右上に`>`シェブロンアイコンを表示。

#### SOCゲージ

車両のバッテリー残量を表す円弧型ゲージ。ホーム画面の最も目立つ位置に配置する。

SVGで描画する。円弧の`stroke-dasharray`をSOC%に連動させ、`stroke`色はSOC値に応じて`--color-soc-*`変数を段階的に適用する。中央にSOC数値（`--text-hero`サイズ）、ゲージ下部に残航続距離（km）を表示する。アニメーションはCSS transitionのみ（`stroke-dasharray 500ms ease-out`）で実現し、JavaScriptアニメーションライブラリは使用しない。

#### 電費インジケーター

現在の電費をリアルタイム表示する横長バー。

効率スケール（例: 3.0〜9.0 km/kWh）上に現在値のマーカーを表示する。スケールの背景はグラデーション（赤→黄→緑）とし、マーカー位置で現在の電費が直感的にわかる。走行中はWebSocket経由で1秒間隔更新。

#### 充電カーブチャート

Chart.jsの折れ線グラフ。横軸=SOC（%）、縦軸=充電速度（kW）。

```javascript
// Chart.jsグローバル設定（PiLot共通）
Chart.defaults.color = 'var(--color-text-secondary)';
Chart.defaults.borderColor = 'var(--color-border)';
Chart.defaults.font.family = 'var(--font-sans)';
Chart.defaults.animation.duration = 300;
Chart.defaults.plugins.legend.display = false; // 単系列時は非表示
Chart.defaults.elements.point.radius = 0;      // データポイントドット非表示
Chart.defaults.elements.line.borderWidth = 2;
Chart.defaults.elements.line.tension = 0.3;    // 軽い曲線
```

全チャートで`animation.duration`を300msに統一する。Pi 3Bでのレンダリング負荷を考慮し、アニメーション無効化オプションを設定に用意する。

#### ナビゲーション

画面左端に縦型サイドバーナビゲーションを配置する。モバイル幅ではボトムバーに切り替わる。

```
サイドバー（desktop/wide）     ボトムバー（mobile/tablet）
┌──────┐                      ┌────┬────┬────┬────┬────┐
│ 🏠  │ ホーム              │ 🏠 │ ⚡ │ 🔋 │ 🗺  │ ⚙  │
│ ⚡  │ 電費                └────┴────┴────┴────┴────┘
│ 🔋  │ 充電
│ 🗺  │ 走行
│ 🔧  │ 車両
│ ⚙  │ 設定
└──────┘
```

アイコンはインラインSVGで実装する。アクティブ状態は左ボーダー（サイドバー時）またはトップボーダー（ボトムバー時）＋アイコン色変更で示す。ナビゲーション項目は最大7個とし、サブ画面はメイン画面内のタブで管理する。

#### ステータスバー

画面上部に固定表示する細いバー。車両状態（走行中/充電中/スリープ中/オフライン）、最終データ取得時刻、API接続状態を常時表示する。

車両状態はドットインジケーター＋テキストで示す。走行中=紫パルス、充電中=青パルス、オンライン=緑点灯、スリープ=灰色点灯、オフライン=赤点灯。パルスアニメーションはCSS `@keyframes`で実装する。

#### ボタン

| 種別 | 用途 | スタイル |
|------|------|---------|
| プライマリ | 主要アクション（保存、開始） | 背景: `--color-charging`、テキスト: 白、角丸: `--radius-md` |
| セカンダリ | 副次アクション（キャンセル、戻る） | 背景: `--color-bg-tertiary`、テキスト: `--color-text-primary` |
| デストラクティブ | 破壊的操作（削除、リセット） | 背景: `--color-error`、テキスト: 白 |
| ゴースト | 補助操作（もっと見る、切替） | 背景: transparent、テキスト: `--color-charging` |

全ボタンの最小タッチターゲットは44×44px（WCAG 2.5.8準拠）。`:active`状態で`transform: scale(0.97)`を100msで適用する。

#### フォーム入力

セットアップウィザードで使用する入力要素。

```css
.input {
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  color: var(--color-text-primary);
  font-size: var(--text-body);
  transition: border-color 150ms ease;
}
.input:focus {
  border-color: var(--color-charging);
  outline: 2px solid var(--color-charging);
  outline-offset: -2px;
}
```

ラベルは入力欄の上に配置（フローティングラベル不使用。JSが不要で、アクセシビリティに優れる）。バリデーションエラーは入力欄下部にインラインで`--color-error`テキスト表示する。

### 8.7 インタラクションパターン

#### 画面遷移

ページ間遷移はフルリロードではなく、`fetch`によるHTMLフラグメント取得＋DOM差し替えで実現する（SPA的な挙動をフレームワークなしで実装）。メインコンテンツ領域のみを差し替え、サイドバーナビゲーション・ステータスバーは維持する。

遷移時はコンテンツ領域に`opacity 0→1`のフェードイン（150ms ease）を適用する。ページ内の詳細展開は`max-height`トランジション（200ms ease）で実現する。

#### リアルタイム更新（WebSocket）

走行中および充電中はWebSocket接続でデータをプッシュする。更新されたデータカードには微細なフラッシュ（`background-color`を一瞬`--color-bg-tertiary`にしてフェードバック、300ms）で変化を視覚フィードバックする。WebSocket切断時は自動再接続（1秒→2秒→4秒…の指数バックオフ、最大30秒）を行い、ステータスバーに接続状態を表示する。

#### ローディング

初回データ取得中はスケルトンスクリーン（`--color-bg-tertiary`のパルスアニメーション）を表示する。スピナーは使用しない。データが部分的に取得済みの場合は取得済み部分から順次表示（プログレッシブレンダリング）する。

#### エラー処理

| エラー種別 | 表示方法 | ユーザーアクション |
|----------|---------|----------------|
| API通信エラー | ステータスバーに赤インジケーター＋最終取得時刻表示 | 自動リトライ、手動リトライボタン |
| トークン期限切れ | フルスクリーンのモーダルで再認証を促す | Tesla再ログイン |
| DB読み取りエラー | エラーカード表示（赤枠、エラーメッセージ） | 設定画面へ誘導 |
| ストレージ残量不足 | ダッシュボード上部に警告バナー（アンバー） | ストレージ管理画面へのリンク |

エラーメッセージは技術用語を避け、対処方法を必ず併記する。例: 「Teslaサーバーに接続できません。インターネット接続を確認してください。（最終取得: 5分前）」

#### 空状態（Empty State）

データが存在しない画面（初回起動直後等）では、イラスト（インラインSVG）＋説明テキスト＋次のアクション提案を表示する。例: 走行ログ画面 →「まだ走行データがありません。車で出かけると自動で記録が始まります。」

### 8.8 チャート共通ルール

#### データ量の制御

Pi 3BのChromiumでのレンダリング負荷を考慮し、1チャートあたりのデータポイント上限を設ける。

| 表示期間 | 最大ポイント数 | 間引き方法 |
|---------|-------------|----------|
| 24時間 | 500 | 間引きなし |
| 1週間 | 500 | LTTB（Largest Triangle Three Buckets） |
| 1ヶ月 | 300 | LTTB |
| 1年 | 365 | 日次平均に集約 |
| 全期間 | 500 | 週次平均に集約 |

Chart.jsのdecimationプラグインでLTTBアルゴリズムを使用する。元データの形状を視覚的に保持しつつデータポイント数を削減する。

#### ツールチップ

チャート上のホバー/タップでツールチップを表示する。ツールチップには日時、数値（単位付き）、可能な場合は比較値（前日比等）を含む。背景は`--color-bg-secondary`、境界は`--color-border`、角丸は`--radius-sm`。

#### 軸ラベル

Y軸の単位は軸タイトルとして1回表示し、各目盛りには数値のみを表示する（「150 Wh/km」ではなく目盛りは「150」、軸タイトルが「Wh/km」）。X軸の日時フォーマットは表示期間に応じて自動切替する（24時間: HH:mm、1週間: M/D、1ヶ月: M/D、1年: YYYY/M）。

### 8.9 地図表示ルール

Leaflet.jsを使用する。タイルはOpenStreetMapを使用し、初回表示時にローカルにキャッシュする。

タイルキャッシュの実装はService Workerで行い、キャッシュストレージの上限は設定で指定（デフォルト256MB）。上限到達時はLRUで古いタイルを削除する。

走行ルートのオーバーレイは`polyline`で描画し、電費ヒートマップ表示（区間電費に応じて線色を緑→黄→赤にグラデーション）をオプションとする。

### 8.10 アクセシビリティ

WAI-ARIA属性を適切に付与する。`role`、`aria-label`、`aria-live`（リアルタイム更新領域）を使用し、スクリーンリーダーでの基本的なナビゲーションを可能にする。

色だけで情報を伝えない。グラフの系列は色に加えて線種（実線/破線/点線）を併用する。ステータスのドットインジケーターは色＋形状（丸/三角/四角）を組み合わせる。

キーボードナビゲーションに対応する。Tab/Shift+Tabでフォーカス移動、Enterで選択/展開、Escで閉じる。フォーカスリングは`outline: 2px solid var(--color-charging)`で視認性を確保する。

### 8.11 パフォーマンス目標

| 指標 | 目標値 | 測定条件 |
|------|-------|---------|
| 初回描画（FCP） | 1.5秒以内 | Pi 3B、ローカル接続 |
| 操作可能（TTI） | 2.5秒以内 | Pi 3B、ローカル接続 |
| ページ遷移 | 300ms以内 | Pi 3B、キャッシュ済み |
| チャート描画 | 500ms以内 | Pi 3B、500データポイント |
| WebSocket更新反映 | 100ms以内 | Pi 4以降 |

HTMLはサーバーサイドレンダリング（Jinja2）で生成し、クライアントサイドJSは「チャート描画」「WebSocket接続」「画面遷移のfetch」「フォームバリデーション」の4つの役割に限定する。JSバンドルの総サイズ上限は200KB（gzip前）とする。Chart.js（約60KB gzip）が最大の依存であり、それ以外のJSは自作コードのみで構成する。

CSSの総サイズ上限は30KB（gzip前）とする。

---

## 9. アクセスモード

PiLotは以下の4つのアクセスモードを提供する。用途に応じて併用可能である。

### 8.1 ローカルGUI（HDMI＋キーボード＋マウス）

7.4節の通り、Raspberry PiにHDMIディスプレイを直結してダッシュボードを操作する。初期セットアップもこのモードで完結可能。常設ディスプレイとしての運用に適する。画面右下のQRコードをスマートフォンで読み取ることで、モード8.2への即座のハンドオフが可能。

### 8.2 LAN内ブラウザアクセス

同一ネットワーク上のPC・スマートフォン・タブレットから`http://pilot.local`にアクセスする。mDNS（Avahi）によるホスト名解決で、IPアドレスの手動入力は不要。最も一般的な日常利用モード。

### 8.3 SSH

`ssh pilot@pilot.local`でコマンドライン接続する。Claude Codeの利用、ログ確認、設定ファイルの直接編集、`pilot-update`によるOS更新等に使用する。技術者向け。

### 8.4 Tailscaleリモートアクセス（オプション）

Tailscale VPNを有効化すると、外出先からダッシュボードおよびSSHにアクセス可能になる。ルーターのポート開放やDDNS設定は不要で、`https://pilot.tailnet-name.ts.net`でセキュアに接続できる。MagicDNSによるホスト名解決、WireGuard暗号化、Tailscale ACLによるアクセス制御を提供する。100デバイスまで無料。

---

## 10. ストレージ管理

### 8.1 ローカルSD（デフォルト）

データベースファイル（`/var/lib/pilot/pilot.db`）はデフォルトでmicroSDカードに保存する。SDカード磨耗対策として以下を自動設定する。

```
# fstab設定
tmpfs /tmp         tmpfs defaults,noatime,nosuid,size=64M  0 0
tmpfs /var/log     tmpfs defaults,noatime,nosuid,size=32M  0 0
tmpfs /var/tmp     tmpfs defaults,noatime,nosuid,size=32M  0 0

# マウントオプション
/dev/mmcblk0p2 / ext4 defaults,noatime,commit=600 0 1
```

swapは無効化する。Log2Ramをプリインストールし、ログは1時間ごとにSDへフラッシュする。

### 8.2 外部USBストレージ（オプション）

Pi 4/5でUSB SSDが接続された場合、セットアップウィザードまたは設定画面から外部ストレージへのデータベース移行を選択できる。`/var/lib/pilot/`のシンボリックリンク先を切り替え、既存データを自動コピーする。ext4フォーマットを推奨し、NTFSやexFATはリードオンリーマウントによるフォールバック対応とする。

### 8.3 Google Drive同期（オプション）

Google Drive APIを使用し、SQLiteデータベースのバックアップを定期的にアップロードする。

| 項目 | 仕様 |
|------|------|
| 認証 | OAuth 2.0（セットアップウィザードで設定） |
| 同期対象 | pilot.dbのスナップショット（.bak） |
| 同期間隔 | 1日1回（デフォルト、設定変更可能） |
| 保持世代 | 直近7世代（古いバックアップは自動削除） |
| 帯域制限 | アップロード速度を1Mbpsに制限（オプション） |
| 暗号化 | AES-256で暗号化してからアップロード（パスフレーズはローカル保持） |

Google Drive同期はpilot-sync systemd timerで実行する。rcloneをバックエンドとして使用し、Google Drive以外のクラウドストレージ（Dropbox、OneDrive等）への将来拡張も容易にする。

### 8.4 データ保持ポリシー

positionsテーブル（最大のテーブル）について、デフォルトでは無期限保持する。ストレージ逼迫時は設定画面から古いpositionsデータの間引き（5秒→30秒間隔に集約）またはアーカイブ（gzip圧縮でエクスポート後に削除）を実行できる。drives, charging_sessions等の集約テーブルは常に保持する。

---

## 11. Claude Code連携

### 9.1 概要

Claude Codeをインストールし、PiLot上のSQLiteデータベースに対して自然言語でクエリ・分析を実行可能にする。ユーザーはSSHまたは将来的にはダッシュボードのチャットUIから「先月の電費平均は？」「高速と下道で電費どのくらい違う？」「伊賀SCまでの充電計画を立てて」と入力すると、Claude Codeがデータベースを参照して回答する。

### 9.2 セットアップ

Claude Codeのインストールはセットアップウィザードのオプション画面で有効化を選択した場合に自動実行する。ユーザーのAnthropicAPIキーをローカルに暗号化保存する。

```bash
# インストール（セットアップ時に自動実行）
npm install -g @anthropic-ai/claude-code
```

### 9.3 PiLot専用CLAUDE.md

Claude Codeがリポジトリコンテキストとして参照する`CLAUDE.md`をPiLot OSに同梱する。以下の情報を含む。

```markdown
# PiLot - Tesla Vehicle Management OS

## データベース
- SQLite: /var/lib/pilot/pilot.db
- スキーマ: 本ドキュメントの「データベース設計」セクションを参照
- 電費の主要テーブル: drives（集約）, positions（生データ）
- 充電の主要テーブル: charging_sessions（集約）, charges（生データ）

## 電費計算
- km/kWh = distance_km / energy_consumed_kwh
- Wh/km = energy_consumed_kwh * 1000 / distance_km
- ガソリン換算 km/L = km/kWh × 8.9

## よくあるクエリパターン
- 月別電費: SELECT strftime('%Y-%m', start_time) as month, AVG(efficiency_kmkwh) ...
- 速度帯別: JOIN positions ON drive_id ...
- 充電コスト: SELECT SUM(cost_jpy) FROM charging_sessions WHERE ...

## 設定参照
- settings テーブルにユーザー設定が格納
- efficiency_unit: 'km_kwh' | 'wh_km' | 'kwh_100km'

## 注意事項
- データベースへの書き込みは行わない（読み取りのみ）
- 日本語で回答する
```

### 9.4 ダッシュボードからのチャットUI（将来）

v1.0ではSSH経由でのClaude Code使用を基本とする。v2.0以降でダッシュボードにチャットウィジェットを埋め込み、ブラウザから自然言語クエリを投げられるUIを追加する計画とする。バックエンドでClaude Code CLIをsubprocessとして呼び出し、結果をWebSocket経由でフロントエンドに返す設計を想定する。

---

## 12. GitHub CLI連携

### 10.1 目的

PiLot OSのソースコード自体をGitHubリポジトリで管理し、以下を可能にする。

ユーザーがOSの更新を`gh`コマンドで取得できること。カスタムダッシュボードや機能追加のプルリクエストを直接PiLotから提出できること。Issueの作成・バグレポートをPiLotから直接行えること。コミュニティ貢献の敷居を最小化すること。

### 10.2 プリインストール構成

```bash
# GitHub CLI（gh）をプリインストール
# 初回使用時に `gh auth login` で認証
gh version  # 動作確認
```

### 10.3 PiLot OS更新フロー

```bash
# OS更新（ユーザーが実行）
pilot-update

# 内部実装:
# 1. gh release list --repo pilot-os/pilot-os --limit 5
# 2. 最新リリースのchangelogを表示
# 3. ユーザー確認後、gh release download でアセット取得
# 4. systemdサービス停止 → ファイル差し替え → マイグレーション → サービス再開
```

ダッシュボードの設定画面からも更新確認・適用が可能。更新前にSQLiteデータベースの自動バックアップを実行する。

### 10.4 カスタマイズワークフロー

技術者ユーザーはPiLot OSの設定やダッシュボードテンプレートをforkし、自分の環境で直接編集・プッシュできる。

```bash
# リポジトリをクローン
gh repo clone pilot-os/pilot-os ~/pilot-src

# ダッシュボードテンプレートを編集
nano ~/pilot-src/dashboard/templates/efficiency.html

# 変更をテスト
sudo systemctl restart pilot-dashboard

# 満足したらプッシュ / PR作成
cd ~/pilot-src
git add -A && git commit -m "Add custom efficiency chart"
gh pr create --title "Custom efficiency chart" --body "..."
```

---

## 13. OS レベルの設計

### 11.1 パーティション構成

| パーティション | マウントポイント | ファイルシステム | サイズ | 用途 |
|-------------|---------------|---------------|------|------|
| boot | /boot/firmware | FAT32 | 512MB | カーネル、DTB、config.txt |
| rootfs | / | ext4 | 残り全部 | OS＋データ |

rootfsはnoatime, commit=600でマウントする。初回起動時にパーティションをSD全容量に自動拡張する。

### 11.2 メモリ最適化（Pi 3B対応）

| 対策 | 効果 |
|------|------|
| GPU メモリを16MBに制限（gpu_mem=16） | 約48MB節約 |
| swap無効化 | SD書き込み削減 |
| /tmp, /var/log, /var/tmp を tmpfs化 | SD書き込み削減 |
| zram有効化（256MB、lz4圧縮） | 実効メモリ約1.3倍 |
| 不要サービス無効化（bluetooth, avahi-daemon等） | 50MB以上節約 |

目標メモリバジェット（Pi 3B、1GB）:

| コンポーネント | 使用量目安 |
|-------------|----------|
| OS + systemd | 150MB |
| tmpfs（/tmp, /var/log, /var/tmp） | 128MB |
| zram | 256MB（圧縮済み） |
| tesla-poller（Python） | 40MB |
| pilot-dashboard（FastAPI + uvicorn） | 80MB |
| SQLite ページキャッシュ | 32MB |
| 空き（余裕） | 314MB+ |

### 11.3 セキュリティ

デフォルトユーザーは`pilot`（パスワード: 初期設定ウィザードで設定必須）。SSHはデフォルトで有効（パスワード認証、鍵認証推奨の案内表示）。Tesla Fleet APIトークンは`/var/lib/pilot/secrets/`にファイルパーミッション600で保存し、pilot-pollerサービスアカウントのみが読み取り可能とする。ダッシュボードへの認証はv1.0ではLAN内アクセスを前提に無認証とし、Tailscale有効時はTailscaleの認証に委譲する。v2.0以降でBasic認証またはセッション認証をオプション追加する。

ファイアウォール（nftables）はデフォルトでポート22（SSH）、80（ダッシュボード）、8080（セットアップ時のみ）を開放し、他は全拒否する。

### 11.4 ログ管理

journaldをログバックエンドとし、`Storage=volatile`（RAMのみ）に設定する。ログの永続化が必要な場合はLog2Ram経由でSDに非同期書き込み。ログローテーションは`SystemMaxUse=32M`で制限する。

### 11.5 自動更新とヘルスチェック

pilot-watchdogサービスが以下を監視する。

- tesla-poller: 5分以上レスポンスなしで自動再起動
- pilot-dashboard: HTTP 200チェック（30秒間隔）
- SQLite: 整合性チェック（1日1回、`PRAGMA integrity_check`）
- ストレージ空き容量: 10%以下で警告、5%以下で古いpositionsの間引きを提案
- API使用量: 月間クレジット残量の監視

NTP同期（systemd-timesyncd）はデフォルト有効とする。タイムゾーンは初期設定で選択したものを使用する。

---

## 14. ビルド・配布

### 12.1 イメージビルドパイプライン

pi-genをベースにカスタムステージを追加してPiLot OSイメージを生成する。GitHub Actionsで自動ビルドし、Releaseページで配布する。

```
pi-gen stage0-3（Raspberry Pi OS Lite ベース）
  └─ stage-pilot（PiLotカスタムステージ）
      ├─ cage（Waylandキオスクcompositor）+ Chromium（キオスクブラウザ）
      ├─ Python 3.11+ venv + 依存パッケージ（httpx, uvicorn, jinja2, qrcode等）
      ├─ FastAPI + uvicorn + Chart.js + Leaflet.js
      ├─ SQLite3
      ├─ GitHub CLI (gh)
      ├─ Node.js + Claude Code（オプション有効時にインストール）
      ├─ Tailscale（オプション有効時にインストール）
      ├─ rclone（Google Drive同期用）
      ├─ pilot-setup / tesla-poller / pilot-dashboard / pilot-sync / pilot-watchdog
      ├─ systemdユニットファイル群
      ├─ CLAUDE.md
      ├─ /var/lib/pilot/ ディレクトリ構造
      └─ OS最適化設定（tmpfs, noatime, gpu_mem, zram等）
```

### 12.2 配布形式

| ファイル | 内容 | 対象 |
|--------|------|------|
| pilot-os-vX.X.X.img.xz | フルイメージ（圧縮済み） | 新規インストール |
| pilot-update-vX.X.X.tar.gz | 差分更新パッケージ | 既存環境の更新 |
| SHA256SUMS | チェックサム | 整合性検証 |

### 12.3 対応アーキテクチャ

arm64（aarch64）の単一イメージでPi 3B（64-bit対応）〜Pi 5まで対応する。Pi 3Bは公式に64-bit OSをサポートしているため、armhf（32-bit）イメージは提供しない。

---

## 15. 将来ロードマップ

### v1.1

- 複数車両対応（ダッシュボードで切り替え）
- 充電スケジュール最適化（深夜帯に自動調整）
- OTA更新のダッシュボードUI統合

### v2.0

- Fleet Telemetry対応（Tailscale Funnel経由）
- ダッシュボード内Claude Codeチャットウィジェット
- Basic認証 / セッション認証
- iOSコンパニオンアプリ（ビューアー）
- ScanMyTesla連携（OBD-IIドングル経由のBMSデータ）

### v3.0

- セントリーモード動画のローカル自動整理・ハイライト抽出
- マルチユーザー（家族内での走行データ個別管理）
- Home Assistant連携
- Grafanaオプション統合（上級者向け）

---

## 16. 技術的制約と既知のリスク

### Tesla API依存

PiLot v1.0はTesla Owner's API（非公式）に依存している。TeslaがOwner's APIを廃止または仕様変更した場合、PiLotのデータ収集機能が停止する。現時点ではTesla公式モバイルアプリが同一APIを使用しており、TeslaMateを含む大規模OSSコミュニティが長年このAPIで運用を続けているため、突然の廃止リスクは低いと判断する。

万が一Owner's APIが塞がれた場合の対応方針は「Fleet APIへの移行を検討するか、サービス終了」とする。Fleet APIへの移行にはユーザー側の開発者登録が必要となるため、PiLotのゼロコンフィグというコアバリューとの両立が課題となる。

軽減策として、APIクライアントを抽象レイヤーで分離し、Owner's APIとFleet APIの切り替えが最小限のコード修正で対応できる設計とする。

### SDカード信頼性（Pi 3B）

Pi 3BではmicroSDカードが唯一のストレージであり、書き込み磨耗によるデータ損失リスクがある。軽減策としてWALモード、noatime、tmpfs、Log2Ramを適用するが、高耐久カードの使用をユーザーに強く推奨する。Google Drive同期を有効化することで、カード故障時のデータ復旧を可能にする。

### メモリ制約（Pi 3B）

1GB RAMでの運用は可能だが余裕は少ない。Chart.jsの大量データポイント描画やブラウザの同時接続数増加でOOMリスクがある。ダッシュボードのデータ取得はページネーション必須とし、1リクエストあたりの最大データポイント数を制限する。

### OAuth 2.0トークンの45日期限

Owner's APIのリフレッシュトークンは約45日で失効する（定期的な使用で延長される）。PiLotが正常に稼働している限り自動リフレッシュで維持されるが、45日以上電源オフの場合は再認証が必要となる。ダッシュボードにトークン有効期限の表示と、期限切れ前の通知機能を搭載する。

---

## 付録A: Model Y RWD（LFP）効率定数リファレンス

| パラメータ | 値 | 出典 |
|----------|------|------|
| Rated効率定数 | 149 Wh/km | Tesla EPA / TeslaMate |
| 使用可能バッテリー容量 | 57 kWh | 実測値 |
| 公称バッテリー容量 | 60 kWh | CATL LFP60 |
| セル構成 | 108s1p | — |
| 公称セル電圧 | 3.2V | LFP化学特性 |
| Cd値（Juniper） | 0.23 | Tesla公式 |
| 最大DC充電速度 | 170 kW | スペック |
| 車両重量 | 約1,900 kg | — |

## 付録B: 電費ベンチマーク（実測参考値）

| 条件 | Wh/km | km/kWh | ガソリン換算 km/L |
|------|-------|--------|-----------------|
| 市街地 夏季 | 113-130 | 7.7-8.8 | 69-78 |
| 混合 通年 | 155-175 | 5.7-6.5 | 51-58 |
| 高速 90km/h | 142 | 7.0 | 62 |
| 高速 120km/h | 195 | 5.1 | 45 |
| 市街地 冬季 | 170 | 5.9 | 53 |
| 高速 冬季 | 228 | 4.4 | 39 |
