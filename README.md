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
cd room-entry-detection
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy config.example.yaml config.yaml
```

`config.yaml` を編集:

- `notify.ntfy_topic` — ntfy.sh のトピック名（推測されにくい名前にする）
- `notify.entry_message` — ntfy 通知本文の1行目（デフォルトは「ドアが開きました（外からの入室）」）
- 必要に応じて `camera.device_index` など

通知音（任意）: `assets/alert.wav` を置く。無い場合はシステムビープを鳴らします。

## カメラ配置の目安

- ドア全体が画面に入る
- 照明がドア ROI 内で大きく変わりすぎない（直射日光の移動などは SSIM 誤検知の原因になりやすい）
- **door ROI** はドア面板全体
- **presence ROI** の範囲がある（ドアの下や横）

## ROI（監視領域）の設定

カメラを**本番と同じ位置・向き・解像度**に固定してから設定してください。向きを変えると `config.yaml` の ROI を取り直す必要があります。

### 設定手順（`setup_roi.py`）

```powershell
python tools/setup_roi.py
```

| 操作 | 説明 |
|------|------|
| ドラッグ | マウスで矩形を描く |
| Enter | 現在の矩形を確定して次へ |
| R | いまのステップの矩形をやり直し |
| Q / Esc | 保存せず終了 |

1. **door ROI** — ドアの面板全体をドラッグ → Enter
2. **presence ROI** — 室内側の床・通路をドラッグ → Enter

確定すると `config.yaml` の `roi.door` / `roi.presence` に `[x, y, width, height]`（左上座標 + 幅・高さ、ピクセル）で保存されます。

手動編集も可能ですが、プレビュー（`debug.show_preview: true`）で枠が意図どおりか必ず確認してください。
### presence ROI の置き方（詳細）

presence ROI は、**ドアが閉じているあいだ**に「室内からドアへ向かう人の動き」を見る領域です。開き始めた瞬間に直前の動きがあったかを記録し、あれば外出（通知しない）、なければ外からの入室候補（通知する）と判定します。

#### 含める範囲

- **室内側**の床〜腰の高さ（外出するとき、開ける数秒前に足や下半身が入る通路）
- 室内からドアへ一直線で歩いてくるルート

#### 含めない・避ける範囲

- **door ROI と重ねない**（ドア面板・隙間の開閉は door 側の SSIM だけが見る。重なると開閉の見た目変化が「動き」と混ざり、外出判定が不安定になる）
- **廊下側**（ドアの外。閉扉中に廊下の人影や光が入ると誤って「直前に動きあり」になり、本当の外からの入室を見逃す）
- ドアの隙間からだけ見える廊下の床
- カーテン・植物など、常に揺れるもの（MOG2 が常時「動き」と判定しやすい）

#### 設定後の確認

`debug.show_preview: true` で起動し、オレンジ枠（presence）と緑/赤枠（door）を確認します。

| 確認項目 | 期待 |
|----------|------|
| 枠の重なり | door（緑/赤）と presence（オレンジ）が重なっていない |
| 閉扉・静止 | `recent_motion` / オレンジ表示が落ち着いている |
| 室内から歩いて開ける | 開く前に `recent_motion` になり、**通知なし** |
| 外から開ける | 開く直前まで `clear` のまま、**通知あり** |

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

## `detection` 閾値（`config.yaml`）

`camera.fps` と組み合わせて効きます（例: fps 10 なら `door_open_min_frames: 5` は約 0.5 秒）。

### ドアの開閉（`door_detector.py`）

| パラメータ | 意味 | 上げると | 下げると |
|------------|------|----------|----------|
| `door_ssim_threshold` | door ROI の現在画像と「閉じた基準」の SSIM が**この値未満**なら「開いている候補」（0〜1） | 開閉とみなしにくい（鈍感）。照明のゆらぎに強い | 開閉とみなしやすい（敏感）。誤って「開いた」になりやすい |
| `door_open_min_frames` | 開/閉の候補が**連続何フレーム**続いたら確定するか | 反応が遅いがチラつきに強い | 反応は速いが一瞬の誤検知で状態が切り替わりやすい |
| `door_closed_stable_seconds` | 閉じたまま安定しているとき、**基準画像を更新する間隔**（秒）。照明の緩やかな変化への追従用 | 基準が固定されやすい（長期で見た目が変わると SSIM がずれうる） | 環境変化に追従しやすい（基準が頻繁に変わり判定が不安定になりうる） |

プレビューの `door SSIM=...` を参考に、**閉扉で閾値付近以上、開扉で明らかに下がる**ように合わせます。デフォルトは `0.82` です。

### 室内側の動き（`presence_detector.py`）

ドアが**開いている間は動きを数えません**。閉じている間だけ presence ROI で MOG2 の前景割合を計算します。

| パラメータ | 意味 | 上げると | 下げると |
|------------|------|----------|----------|
| `motion_pixel_ratio_threshold` | presence ROI 内で「動き」とみなす画素割合の下限（例: `0.02` = 2%） | 感度低下。小さな動きは無視 → 外出を見逃しやすい | 感度上昇。影・ノイズでも動きになり → 外出時の通知抑制されやすい |
| `motion_lookback_seconds` | この秒数以内に一度でも動きがあれば `has_recent_motion`（開き始めた瞬間に記録） | 「さっき動いた」を長く覚える → 外出抑制は強いが、遅れて扉だけ開くと誤抑制しうる | 直前の動きだけ見る → 歩いてから少し待って開けると誤通知しうる |

### 通知の抑制（`state_machine.py`）

| パラメータ | 意味 |
|------------|------|
| `alert_cooldown_seconds` | 一度入室通知したあと、同じ通知を何秒抑えるか（連続アラート防止）。検知ロジック自体は止めない |

### 調整の目安

| 症状 | 試すこと |
|------|----------|
| 閉めたまま・微振動で「開いた」 | `door_ssim_threshold` を**下げる**、`door_open_min_frames` を**増やす** |
| 本当に開けても検知しない | `door_ssim_threshold` を**上げる**（上げすぎ注意）、door ROI の見え方・照明を見直す |
| 室内から開けるのに通知する | presence ROI を広げる／廊下側を除く、door と**重ねない**、`motion_pixel_ratio_threshold` を**下げる**、`motion_lookback_seconds` を**長くする** |
| 外から開けたのに通知しない | presence が広すぎ／廊下の動きを拾っていないか確認、`motion_pixel_ratio_threshold` を**上げる** |
| 連続で何度も鳴る | `alert_cooldown_seconds` を**長くする** |

`config.example.yaml` にデフォルト値の例があります。

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