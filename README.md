# RoomEntryDetection

室内の USB カメラでドアを監視し、**外からドアが開いた**ときだけ音と [ntfy.sh](https://ntfy.sh) で通知するインターホン替わりアプリです。

- 録画なし（ソフト起動中のみカメラを使用）
- 室内から外出するとき（ドア付近に先に動きがある場合）は通知しない
- 人物検出（YOLO）ではなく、ドア ROI の SSIM + 動き検出で軽量動作

## 必要環境

- Windows（サーバー PC 想定）
- Python 3.10+
- USB カメラ

## セットアップ

```powershell
cd RoomEntryDetection
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy config.example.yaml config.yaml
```

`config.yaml` を編集:

- `notify.ntfy_topic` — ntfy.sh のトピック名（推測されにくい名前にする）
- 必要に応じて `camera.device_index` など

通知音（任意）: `assets/alert.wav` を置く。無い場合はシステムビープを鳴らします。

## ROI（監視領域）の設定

カメラ接続後、初回に ROI を設定します。

```powershell
python tools/setup_roi.py
```

1. ドア面板全体をドラッグで指定 → Enter
2. 室内側・ドア付近（外出時に人が映る床面）を指定 → Enter

### カメラ配置の目安

- ドア全体が画面に入る
- **presence ROI** は蝶番側・室内側に置く（廊下側は含めない）
- **door ROI** はドア面板全体

## 起動

```powershell
python -m src.main
```

デバッグ用プレビュー（ROI・SSIM・動き状態を表示）:

```yaml
# config.yaml
debug:
  show_preview: true
```

プレビュー中は `Q` または `Esc` で終了。

## 動作確認（カメラ接続後）

| 操作 | 期待結果 |
|------|----------|
| ドアを閉じたまま | SSIM 高、通知なし |
| 室内からドアへ歩いて開ける | presence に動き → **通知なし** |
| ドア付近に誰もいない状態で外から開ける | **音 + ntfy 通知** |

## 閾値調整

`config.yaml` の `detection` セクション:

| パラメータ | 説明 |
|------------|------|
| `door_ssim_threshold` | これ以下で「ドアが開いた」（低いほど鈍感） |
| `motion_pixel_ratio_threshold` | presence ROI の動き検出感度 |
| `motion_lookback_seconds` | 開く前この秒数動きがあれば外出とみなす |
| `alert_cooldown_seconds` | 連続通知の間隔 |

誤検知が多い場合: SSIM 閾値を下げる、presence ROI を狭める、動き閾値を上げる。

## 常時起動（Windows タスクスケジューラ）

1. **タスクスケジューラ** を開く
2. **基本タスクの作成**
3. トリガー: **ログオン時**（または **コンピューターの起動時**）
4. 操作: **プログラムの開始**
   - プログラム: `C:\Users\...\RoomEntryDetection\.venv\Scripts\python.exe`
   - 引数: `-m src.main`
   - 開始: `C:\Users\...\RoomEntryDetection`
5. 完了

ログ確認はコンソール出力をファイルにリダイレクトするか、タスクの履歴を参照してください。

## ntfy スマホ通知

1. [ntfy アプリ](https://ntfy.sh) をインストール
2. `config.yaml` と同じトピック名をサブスクライブ
3. 入室検知時にプッシュ通知が届く

## プロジェクト構成

```
RoomEntryDetection/
  config.example.yaml
  requirements.txt
  assets/alert.wav          # 任意
  src/
    main.py                 # メインループ
    camera.py
    door_detector.py
    presence_detector.py
    state_machine.py
    notifier.py
    config.py
  tools/
    setup_roi.py            # ROI 設定
```

## ライセンス

Private use.
