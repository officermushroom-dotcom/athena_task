# ATHENA インターン選考課題

ETTデータセットを使って変圧器の油温（OT）を予測し、故障を防ぐための判断に役立つかを調べる課題。
このように、実際に使えそうかを試す検証をPoCと呼ぶ。

## 最初に読むファイル

- `docs/assumptions.md`：今回、どのような条件で予測するか。
- `docs/modeling_plan.md`：データの分け方、誤差の測り方、比較する予測方法。それぞれを選んだ理由。
- `src/athena_task/eda.py`：データを読み、集計とグラフ作成を行うコード。短いコメント付き。

未決定の設定は、検証方針を整理したうえで追加する。

## フォルダ構成

```text
athena_task/
├── assignment-main/       # 受領資料・元データ（変更しない）
│   ├── README.pdf
│   └── data/              # ETTh1, ETTh2, ETTm1, ETTm2
├── configs/               # 実験設定
├── notebooks/             # EDA・結果の探索
├── src/athena_task/        # データ処理・特徴量・学習・評価
├── data/processed/        # 加工データ（Git管理対象外）
├── outputs/
│   ├── figures/           # 図表
│   ├── metrics/           # 評価結果
│   ├── models/            # 学習済みモデル（Git管理対象外）
│   └── predictions/       # 予測結果（Git管理対象外）
├── reports/               # PoC報告・スライド構成
└── docs/                  # 前提・実験記録
```

## 環境構築（PowerShell）

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

分析用の追加パッケージ：`python -m pip install -e ".[analysis]"`

## 進め方

1. 予測する時間と、使える情報を決める。
2. グラフや集計で、データの傾向を調べる（EDA）。ここまでは実施済み。
3. データの分け方と、予測の良し悪しを測る方法を決める。ここまで方針を整理済み。
4. 持続予測（現在と同じ油温と予測）とRidge回帰を比較する。今は入力の詳細を決める前の段階。
5. 結果を確認してから、次の改善を一つずつ考える。



## 提出物

- 再現可能な実装プログラム
- クライアント向けPoC報告スライド（PDF、メッセージ＆ボディ構成）

公開前に、受領PDF・データの公開可否とライセンスを確認する。受領資料は初期設定でGit管理から除外する。
