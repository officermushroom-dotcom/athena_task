"""ETTh1の初期EDA。実行: python -m athena_task.eda（pip install -e .後）。"""

from pathlib import Path
import json

import matplotlib
# ウィンドウを開かず、グラフを画像として保存する。
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# このファイルの場所からプロジェクト直下を取得する。
ROOT = Path(__file__).resolve().parents[2]
# 電力負荷を表す6列。
LOADS = ["HUFL", "HULL", "MUFL", "MULL", "LUFL", "LULL"]


def main():
    # 図表・集計結果の保存先を準備する（既存でもエラーにしない）。
    figures = ROOT / "outputs/figures"
    metrics = ROOT / "outputs/metrics"
    figures.mkdir(parents=True, exist_ok=True)
    metrics.mkdir(parents=True, exist_ok=True)
    # date列を日時として読み込む。
    df = pd.read_csv(ROOT / "assignment-main/data/ETTh1.csv", parse_dates=["date"])
    # 初年度のみで探索し、後続期間をモデル選択前の詳細分析から保留する。
    # 日時をインデックスにする。trainは現時点では探索用データを指す。
    train = df.set_index("date").loc[lambda x: x.index < "2017-07-01"]
    # 全期間の欠損・日時重複・時間間隔を確認する（補正や削除はしない）。
    quality = {
        "dataset": "ETTh1", "total_rows": len(df),
        "start": str(df.date.min()), "end": str(df.date.max()),
        "missing_per_column": df.isna().sum().to_dict(),
        "duplicate_timestamps": int(df.date.duplicated().sum()),
        # 隣接行の時刻差が1時間でない件数を数える。
        "non_hourly_steps": int(df.date.diff().dropna().ne(pd.Timedelta(hours=1)).sum()),
        "exploration_start": str(train.index.min()),
        "exploration_end": str(train.index.max()), "exploration_rows": len(train),
        "held_out_rows": len(df) - len(train),
    }
    (metrics / "eda_quality.json").write_text(json.dumps(quality, indent=2), encoding="utf-8")
    # 基本統計量を変数ごとの行にして保存する（Tは行・列の入れ替え）。
    train.describe().T.to_csv(metrics / "eda_summary.csv")
    # 同時刻の変数同士のPearson相関。相関は因果関係を意味しない。
    train.corr().to_csv(metrics / "eda_correlations.csv")
    # h行前の値と現在のOTとの相関。1時間間隔なのでh行前＝h時間前。
    # shiftで生じる欠損は、相関計算時にペア単位で除外される。
    lags = pd.DataFrame({c: [train[c].shift(h).corr(train.OT) for h in range(49)]
                         for c in LOADS + ["OT"]}, index=range(49))
    lags.index.name = "past_lag_hours"
    lags.to_csv(metrics / "eda_lag_correlations.csv")
    # 将来予測のベースライン候補を探索期間内だけで比較する。
    baseline = []
    for h in [1, 6, 24, 168]:
        # 「h時間前と同じ温度」と予測した場合の誤差。先頭h行は除外する。
        err = (train.OT - train.OT.shift(h)).dropna()
        # MAEは絶対誤差の平均、RMSEは二乗誤差の平均の平方根。
        baseline.append({"lag_hours": h, "n": len(err), "mae": err.abs().mean(),
                         "rmse": np.sqrt((err ** 2).mean())})
    pd.DataFrame(baseline).to_csv(metrics / "eda_persistence.csv", index=False)
    # 日付をまたいで0〜23時ごとの平均を集計する。
    train.groupby(train.index.hour).mean().to_csv(metrics / "eda_hourly_profile.csv")
    # 図の解像度と枠線の見た目を設定する。
    plt.rcParams.update({"figure.dpi": 140, "axes.spines.top": False,
                         "axes.spines.right": False})

    def save(name):
        # 余白を整えて保存し、図を閉じてメモリを解放する。
        plt.tight_layout()
        plt.savefig(figures / name)
        plt.close()

    # 図1：初年度全体の変化。日平均で長期的な傾向を見やすくする。
    fig, axes = plt.subplots(2, 1, figsize=(11, 6))
    train.OT.plot(ax=axes[0], lw=.5, alpha=.55, label="Hourly")
    # resample("D")は日時を日単位にまとめる処理。
    train.OT.resample("D").mean().plot(ax=axes[0], lw=1.5, label="Daily mean")
    axes[0].set(title="Oil temperature: exploration period", ylabel="OT (recorded value)")
    axes[0].legend()
    train[LOADS].resample("D").mean().plot(ax=axes[1], lw=.8)
    axes[1].set(title="Daily mean load measurements", ylabel="Load (units unspecified)")
    save("eda_overview.png")

    # 図2：最初の7日間を拡大し、短期的な変化を見る。
    fig, axes = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
    week = train.loc["2016-07-01":"2016-07-07"]
    week.OT.plot(ax=axes[0], color="tab:red")
    axes[0].set(title="First seven days (fixed window)", ylabel="OT")
    week[LOADS].plot(ax=axes[1], lw=.9)
    axes[1].set_ylabel("Load")
    save("eda_week.png")

    # 図3：相関行列を色と数値で表示する（-1〜1）。
    fig, ax = plt.subplots(figsize=(7, 6))
    corr = train.corr()
    im = ax.imshow(corr, vmin=-1, vmax=1, cmap="RdBu_r")
    ax.set_xticks(range(7), corr.columns, rotation=45)
    ax.set_yticks(range(7), corr.index)
    for i in range(7):
        for j in range(7):
            ax.text(j, i, f"{corr.iloc[i,j]:.2f}", ha="center", va="center", fontsize=9)
    fig.colorbar(im, ax=ax, label="Pearson correlation")
    ax.set_title("Contemporaneous correlations (not causation)")
    save("eda_correlations.png")

    # 図4：過去の負荷との相関と、OT自身の過去値との相関を表示する。
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    lags[LOADS].plot(ax=axes[0])
    axes[0].set(title="Past load vs current OT", xlabel="Past lag (hours)", ylabel="Pearson correlation")
    # 自己相関：現在のOTとh時間前のOTの関係を、最大1週間まで調べる。
    axes[1].plot(range(169), [train.OT.autocorr(h) for h in range(169)])
    axes[1].set(title="OT autocorrelation", xlabel="Lag (hours)", ylabel="Pearson correlation")
    save("eda_lags.png")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    # 図5：温度の分布と1時間ごとの変化量の分布。binsは棒の区間数。
    train.OT.hist(bins=50, ax=axes[0], color="tab:blue")
    axes[0].set(title="OT distribution", xlabel="OT", ylabel="Count")
    # diffは現在値−前の行の値を計算する。
    train.OT.diff().hist(bins=80, ax=axes[1], color="tab:orange")
    axes[1].set(title="Hourly OT changes", xlabel="OT(t) - OT(t-1)", ylabel="Count")
    save("eda_distribution.png")
    # 主な結果を端末にも表示する。探索期間の結果であり、最終テスト性能ではない。
    print(json.dumps(quality, indent=2))
    print("\nSummary\n", train.describe().T.round(3).to_string())
    print("\nCorrelation with OT\n", train.corr().OT.round(3).to_string())
    print("\nPersistence candidates (exploration only)\n", pd.DataFrame(baseline).to_string(index=False))
    # 変化の絶対値が大きい上位5件を表示する。異常と判定する処理ではない。
    print("\nLargest hourly changes\n", train.OT.diff().abs().nlargest(5).to_string())


# 直接実行したときだけ分析を開始する（import時には実行しない）。
if __name__ == "__main__":
    main()
