# ATHENA インターン選考課題

ETTデータセットを使って変圧器の油温（OT）を予測し、故障を防ぐための判断に役立つかを調べる課題。
このように、実際に使えそうかを試す検証をPoCと呼ぶ。

## 最初に読むファイル

- `docs/assumptions.md`：今回、どのような条件で予測するか。
- `docs/modeling_plan.md`：データの分け方、誤差の測り方、比較する予測方法。それぞれを選んだ理由。
- `src/athena_task/eda.py`：データを読み、集計とグラフ作成を行うコード。短いコメント付き。

- [実験記録](docs/experiment_log.md)：各比較の条件と結果。

## フォルダ構成

```text
athena_task/
├── assignment-main/       # 受領資料・元データ（変更しない）
│   ├── README.pdf
│   └── data/              # ETTh1, ETTh2, ETTm1, ETTm2
├── configs/               # 実験設定
├── notebooks/             # EDA・結果の探索
├── src/athena_task/        # データ処理・特徴量・学習・評価
├── outputs/
│   ├── figures/           # 図表
│   └── metrics/           # 評価結果
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

## 最終テスト

ETTm2の1時間先予測では、2018年1月以降の16,976件で、7日分の油温を使うRidgeのMAEが持続予測の0.9108から0.4608に下がった。1日分でも0.4675だった。結果はETTm2の油温予測に関するもので、実機での警報性能は別途検証が必要。

元データを `assignment-main/data/` に配置し、以下を実行する。

```powershell
python -m athena_task.ridge --dataset ETTm2 --sixty-minutes --week-recent --final-test
```

## 提出物

- 再現可能な実装プログラム
- クライアント向けPoC報告スライド（PDF、メッセージ＆ボディ構成）

公開前に、受領PDF・データの公開可否とライセンスを確認する。受領資料は初期設定でGit管理から除外する。
