"""PoC報告スライド用の図を作る。

既存の評価結果（outputs/metrics）を読み、ETTm2の最終テストだけは予測値を描くため再計算する。
再計算したMAEが 36_ettm2_sixty_minute_final_test.json と一致するかも確認する。
限界の検証結果（37_limits_checks.json）は先に python -m athena_task.limits で作る。

図はスライド上の表示サイズ（1インチ=100px）で作り、2倍の解像度で保存する。
文字は本文が約20px（スライドで約15pt）になるようにしている。

実行: python -m athena_task.report_figures
"""

import json

import matplotlib
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.patches import Patch
from sklearn.linear_model import Ridge

from athena_task.persistence import ROOT

matplotlib.rcParams["font.family"] = ["Meiryo", "Yu Gothic", "MS Gothic", "sans-serif"]
matplotlib.rcParams["axes.unicode_minus"] = False
matplotlib.rcParams["font.size"] = 14

INK = "#14232a"
INK_2 = "#4d5f66"
GRID = "#e1e6e8"
BASE = "#a3a9ab"   # 持続予測（比較の基準）は無彩色
RIDGE = "#2a78d6"  # メインカラー：Ridge
ACCENT = "#eb6834"  # アクセント：急上昇

METRICS = ROOT / "outputs/metrics"
FIGURES = ROOT / "outputs/figures"


def load(name):
    return json.loads((METRICS / f"{name}.json").read_text(encoding="utf-8"))


def style(ax, grid="y"):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(GRID)
    ax.tick_params(colors=INK_2, labelsize=13)
    if grid:
        ax.grid(axis=grid, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def new_figure(width, height):
    return Figure(figsize=(width, height), layout="constrained", facecolor="white")


def save(fig, name):
    fig.savefig(FIGURES / name, dpi=200)


def eda_signal():
    """左：油温との相関（1時間前の油温 vs 負荷6項目）。右：ETTm1/ETTm2の日内パターン。"""
    lags = pd.read_csv(METRICS / "02_eda_lag_correlations.csv", index_col=0)
    names = ["1時間前のOT", "HULL", "MULL", "LUFL", "LULL", "HUFL", "MUFL"]
    values = [lags.loc[1, "OT"]] + [lags.loc[0, c] for c in names[1:]]

    fig = new_figure(11.5, 3.9)
    left, right = fig.subplots(1, 2, width_ratios=[1, 1.2])
    colors = [RIDGE] + [BASE] * 6
    left.barh(names[::-1], values[::-1], color=colors[::-1], height=0.62)
    for y, v in enumerate(values[::-1]):
        left.text(v + 0.02, y, f"{v:.2f}", va="center", fontsize=13, color=INK)
    left.set_xlim(0, 1.15)
    left.set_title("ETTh1：油温OTとの相関", fontsize=15, color=INK, loc="left")
    style(left, grid="x")

    cutoff = pd.Timestamp("2017-07-01")
    for name, color in (("ETTm1", BASE), ("ETTm2", RIDGE)):
        data = pd.read_csv(ROOT / f"assignment-main/data/{name}.csv", parse_dates=["date"])
        oil = data.set_index("date").sort_index().loc[lambda d: d.index < cutoff, "OT"]
        centered = oil - oil.groupby(oil.index.normalize()).transform("mean")
        profile = centered.groupby(oil.index.hour + oil.index.minute / 60).mean()
        right.plot(profile.index, profile, color=color, linewidth=2.6)
        right.annotate(f"{name}　幅 {profile.max() - profile.min():.1f}",
                       (profile.idxmax(), profile.max()), xytext=(12, 2),
                       textcoords="offset points", color=INK, fontsize=13)
    right.axhline(0, color=INK_2, linewidth=0.8)
    right.set_xticks(range(0, 25, 6), [f"{h}時" for h in range(0, 25, 6)])
    right.set_xlim(0, 24)
    right.set_ylabel("日平均からの差", color=INK_2)
    right.set_title("日内パターン：学習期間の時刻別平均", fontsize=15, color=INK, loc="left")
    style(right)
    save(fig, "report_eda_signal.png")


def series_gap():
    """4系列の3時間先・検証MAE：持続予測とRidge（油温のみ）。"""
    rows = {"ETTh1": load("15-16-21_three_hours_validation")}
    for name in ("ETTm1", "ETTh2", "ETTm2"):
        rows[name] = load(f"26_{name.lower()}_three_hours_with_load_validation")
    order = ["ETTh1", "ETTm1", "ETTh2", "ETTm2"]

    fig = new_figure(11.5, 3.6)
    ax = fig.subplots()
    width = 0.36
    for i, name in enumerate(order):
        p, r = rows[name]["persistence"]["mae"], rows[name]["ridge"]["mae"]
        ax.bar(i - width / 2 - 0.01, p, width, color=BASE)
        ax.bar(i + width / 2 + 0.01, r, width, color=RIDGE)
        ax.text(i - width / 2, p + 0.05, f"{p:.2f}", ha="center", fontsize=13, color=INK_2)
        ax.text(i + width / 2, r + 0.05, f"{r:.2f}", ha="center", fontsize=13, color=INK)
        ax.text(i, max(p, r) + 0.38, f"−{(1 - r / p) * 100:.0f}%", ha="center",
                fontsize=18, fontweight="bold", color=INK)
    ax.set_xticks(range(4), ["系列1・1時間間隔\nETTh1", "系列1・15分間隔\nETTm1",
                             "系列2・1時間間隔\nETTh2", "系列2・15分間隔\nETTm2"], color=INK)
    ax.set_ylim(0, 3.2)
    ax.set_ylabel("3時間先の検証MAE", color=INK_2)
    ax.axvline(1.5, color=GRID, linewidth=1.2)
    ax.legend(handles=[Patch(color=BASE, label="持続予測"), Patch(color=RIDGE, label="Ridge")],
              frameon=False, loc="upper left", fontsize=13)
    style(ax)
    save(fig, "report_series_gap.png")


def final_test_predictions():
    """ETTm2・1時間先の最終テストを再計算し、予測値を返す。"""
    data = pd.read_csv(ROOT / "assignment-main/data/ETTm2.csv", parse_dates=["date"])
    oil = data.set_index("date").sort_index()["OT"]
    horizon = 4  # 15分間隔で1時間先
    inputs = pd.DataFrame({f"lag_{k}": oil.shift(horizon + k) for k in range(672)})
    table = inputs.assign(actual=oil, now=oil.shift(horizon)).dropna()
    train = table.loc[table.index < pd.Timestamp("2017-07-01")]
    test = table.loc[table.index >= pd.Timestamp("2018-01-01")]
    model = Ridge(alpha=1.0).fit(train[inputs.columns], train["actual"])
    result = pd.DataFrame({
        "actual": test["actual"],
        "persistence": test["now"],
        "ridge": model.predict(test[inputs.columns]),
    })
    expected = load("36_ettm2_sixty_minute_final_test")
    mae = (result["ridge"] - result["actual"]).abs().mean()
    if len(train) != expected["train_n"] or abs(mae - expected["ridge_week"]["mae"]) > 1e-6:
        raise ValueError(f"最終テストの再計算が一致しません: n={len(train)}, MAE={mae}")
    return result, expected["rapid_rise_threshold"]


def final_example(result, threshold):
    """最終テスト期間で急上昇が多い2日間の予測と実測。"""
    rises = (result["actual"] - result["persistence"]) >= threshold
    daily = rises.groupby(result.index.normalize()).sum()
    start = daily.rolling(2).sum().idxmax() - pd.Timedelta(days=1)
    window = result.loc[start:start + pd.Timedelta(hours=47, minutes=45)]

    fig = new_figure(11.5, 3.6)
    ax = fig.subplots()
    ax.plot(window.index, window["actual"], color=INK, linewidth=2.6, label="実測")
    ax.plot(window.index, window["persistence"], color=BASE, linewidth=2.2,
            linestyle=(0, (4, 2)), label="持続予測")
    ax.plot(window.index, window["ridge"], color=RIDGE, linewidth=2.2, label="Ridge・7日分")
    rise_points = window.loc[rises.loc[window.index]]
    ax.scatter(rise_points.index, rise_points["actual"], s=46, color=ACCENT,
               edgecolor="white", linewidth=1.5, zorder=5, label="実測の急上昇")
    ax.legend(frameon=False, loc="upper left", fontsize=13)
    ax.set_ylabel("油温の記録値", color=INK_2)
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%m/%d %H時"))
    ax.set_xlim(window.index[0], window.index[-1])
    style(ax)
    save(fig, "report_final_example.png")
    return str(start.date())


def monthly():
    """ETTm2・1時間先：月ごとのMAE（検証期間と最終テスト期間）。"""
    rows = load("37_limits_checks")["ettm2_monthly"]
    fig = new_figure(7.0, 4.0)
    ax = fig.subplots()
    x = np.arange(len(rows))
    width = 0.38
    ax.bar(x - width / 2 - 0.01, [r["persistence_mae"] for r in rows], width, color=BASE)
    ax.bar(x + width / 2 + 0.01, [r["ridge_mae"] for r in rows], width, color=RIDGE)
    ax.set_xticks(x, [f"{int(r['month'][5:])}月" for r in rows], fontsize=12)
    ax.axvline(5.5, color=INK_2, linewidth=1, linestyle=(0, (3, 3)))
    ax.text(2.5, 1.5, "検証 2017年", ha="center", fontsize=13, color=INK_2)
    ax.text(8.5, 1.5, "最終テスト 2018年", ha="center", fontsize=13, color=INK_2)
    ax.set_ylim(0, 1.62)
    ax.set_yticks([0, 0.4, 0.8, 1.2])
    ax.set_ylabel("1時間先のMAE", color=INK_2)
    ax.legend(handles=[Patch(color=BASE, label="持続予測"), Patch(color=RIDGE, label="Ridge・7日分")],
              frameon=False, loc="upper left", fontsize=12, ncols=2, bbox_to_anchor=(0, 0.92))
    style(ax)
    save(fig, "report_monthly.png")


def alert_sweep():
    """ETTm2・1時間先（検証期間）：通知基準ごとの検知率と的中率。"""
    alerts = load("37_limits_checks")["ettm2_alerts"]
    sweep = [s for s in alerts["validation_sweep"] if s["precision"] is not None]
    t = [s["alert_threshold"] for s in sweep]
    fig = new_figure(6.4, 4.0)
    ax = fig.subplots()
    ax.plot(t, [s["recall"] * 100 for s in sweep], color=RIDGE, linewidth=2.6)
    ax.plot(t, [s["precision"] * 100 for s in sweep], color=INK, linewidth=2.6,
            linestyle=(0, (5, 2)))
    ax.text(t[-1] + 0.05, sweep[-1]["recall"] * 100, "検知率", va="center", fontsize=13, color=INK)
    ax.text(t[-1] + 0.05, sweep[-1]["precision"] * 100, "的中率", va="center", fontsize=13, color=INK)
    for key, label in (("precision_50", "A"), ("one_false_alarm_per_day", "B")):
        th = alerts["policies"][key]["validation"]["alert_threshold"]
        ax.axvline(th, color=ACCENT, linewidth=1.6)
        ax.text(th + 0.05, 108, f"基準{label}：+{th:.2f}", ha="left", va="top",
                fontsize=13, color=INK)
    ax.set_xlabel("通知する予測上昇幅：1時間あたり", color=INK_2)
    ax.set_ylabel("%", color=INK_2)
    ax.set_ylim(0, 112)
    ax.set_xlim(t[0], t[-1] + 0.6)
    style(ax)
    save(fig, "report_alert_sweep.png")


def main():
    FIGURES.mkdir(parents=True, exist_ok=True)
    eda_signal()
    series_gap()
    result, threshold = final_test_predictions()
    start = final_example(result, threshold)
    monthly()
    alert_sweep()
    print(f"図を {FIGURES} に保存しました（最終テストの例: {start} から2日間）。")


if __name__ == "__main__":
    main()
