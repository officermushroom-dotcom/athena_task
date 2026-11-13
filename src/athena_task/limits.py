"""報告スライドの「限界」のうち、手元のデータで確かめられるものを検証する。

最終構成（直近7日分＝672点の油温を使うRidge、1時間先、最初の12か月で学習）を使い、
次の5点を調べる。結果は outputs/metrics/37_limits_checks.json に保存する。

1. 系列1（ETTm1）に同じ構成を当てると、持続予測との差は出るか
2. 月ごとの誤差：夏（2017年7〜8月、検証期間）でも改善は続くか
3. 通知性能：通知の基準を検証期間で決め、最終テスト期間で検知・誤報を数える
4. 予測区間：検証期間の誤差の分位点で幅を作り、最終テスト期間で実測が収まる割合
5. 正則化の強さ（alpha）を変えても検証MAEは安定しているか
6. 高温時：学習期間の油温の90パーセンタイル以上で、過小予測は大きくないか

実行: python -m athena_task.limits
"""

import json

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

from athena_task.persistence import ROOT

HORIZON = 4          # 15分間隔で1時間先
HISTORY = 672        # 7日分
TRAIN_END = pd.Timestamp("2017-07-01")
VALID_END = pd.Timestamp("2018-01-01")


def build(dataset):
    data = pd.read_csv(ROOT / f"assignment-main/data/{dataset}.csv", parse_dates=["date"])
    oil = data.set_index("date").sort_index()["OT"]
    lags = pd.DataFrame({f"lag_{k}": oil.shift(HORIZON + k) for k in range(HISTORY)},
                        dtype="float32")
    table = lags.assign(actual=oil, now=oil.shift(HORIZON)).dropna()
    return table, list(lags.columns), oil


def split(table):
    train = table.loc[table.index < TRAIN_END]
    valid = table.loc[(table.index >= TRAIN_END) & (table.index < VALID_END)]
    test = table.loc[table.index >= VALID_END]
    return train, valid, test


def mae(a, b):
    return float(np.mean(np.abs(np.asarray(a) - np.asarray(b))))


def under(pred, actual):
    return float(np.mean(np.clip(np.asarray(actual) - np.asarray(pred), 0, None)))


def alert_stats(rise_actual, rise_pred, threshold, days):
    alarm = rise_pred >= threshold
    hits = int((rise_actual & alarm).sum())
    misses = int((rise_actual & ~alarm).sum())
    false_alarms = int((~rise_actual & alarm).sum())
    return {
        "alert_threshold": float(threshold),
        "hits": hits, "misses": misses, "false_alarms": false_alarms,
        "recall": hits / max(hits + misses, 1),
        "precision": hits / (hits + false_alarms) if hits + false_alarms else None,
        "false_alarms_per_day": false_alarms / days,
    }


def runs(mask):
    """連続してTrueになる区間を (開始, 終了) の組で返す。"""
    m = np.concatenate([[False], mask, [False]]).astype(int)
    d = np.diff(m)
    return list(zip(np.where(d == 1)[0], np.where(d == -1)[0]))


def event_stats(rise_actual, rise_pred, threshold, days):
    """15分ごとの行ではなく、連続した急上昇・通知を1件の出来事として数える。"""
    alarm = rise_pred >= threshold
    rise_events = runs(rise_actual)
    alarm_events = runs(alarm)
    detected = sum(alarm[s:e].any() for s, e in rise_events)
    false_events = sum(not rise_actual[s:e].any() for s, e in alarm_events)
    return {
        "rise_events": len(rise_events), "detected_events": int(detected),
        "event_recall": detected / max(len(rise_events), 1),
        "alarm_events": len(alarm_events), "false_alarm_events": int(false_events),
        "event_precision": (len(alarm_events) - false_events) / len(alarm_events) if alarm_events else None,
        "false_alarm_events_per_day": false_events / days,
    }


def main():
    results = {"description": "最終構成（Ridge・直近672点・1時間先）で、報告スライドの限界を検証した結果。"}

    # 1. 系列1に同じ構成を当てる
    table, cols, _ = build("ETTm1")
    train, valid, test = split(table)
    model = Ridge(alpha=1.0).fit(train[cols], train["actual"])
    results["ettm1_same_config"] = {
        part: {
            "n": len(frame),
            "persistence_mae": mae(frame["now"], frame["actual"]),
            "ridge_mae": mae(model.predict(frame[cols]), frame["actual"]),
        }
        for part, frame in (("validation", valid), ("test", test))
    }
    del table, train, valid, test

    # 以降はETTm2
    table, cols, oil = build("ETTm2")
    train, valid, test = split(table)
    model = Ridge(alpha=1.0).fit(train[cols], train["actual"])
    pred = {"validation": model.predict(valid[cols]), "test": model.predict(test[cols])}
    frames = {"validation": valid, "test": test}

    # 2. 月ごとの誤差
    monthly = []
    for part in ("validation", "test"):
        frame = frames[part].assign(ridge=pred[part])
        for month, g in frame.groupby(frame.index.to_period("M")):
            monthly.append({
                "month": str(month), "n": len(g),
                "mean_oil": float(g["actual"].mean()),
                "persistence_mae": mae(g["now"], g["actual"]),
                "ridge_mae": mae(g["ridge"], g["actual"]),
            })
    results["ettm2_monthly"] = monthly

    # 3. 通知性能：急上昇の基準は学習期間、通知の基準は検証期間で決めて、テストに当てる
    # 最終テスト（No.36）と同じ急上昇の基準を使う
    rise_threshold = json.loads((ROOT / "outputs/metrics/36_ettm2_sixty_minute_final_test.json")
                                .read_text(encoding="utf-8"))["rapid_rise_threshold"]
    rises = {p: (frames[p]["actual"] - frames[p]["now"]).to_numpy() >= rise_threshold for p in frames}
    pred_rise = {p: pred[p] - frames[p]["now"].to_numpy() for p in frames}
    days = {p: len(frames[p]) / 96 for p in frames}
    candidates = np.round(np.arange(0.2, 3.51, 0.05), 2)
    # 基準の選定と評価は、どちらも15分ごとの判定で数える。
    # 連続した通知を1回とまとめる数え方は、基準を下げて通知を出しっぱなしにすると
    # 見かけの誤報が減ってしまうため使わない（参考値としてのみ保存する）。
    sweep = [alert_stats(rises["validation"], pred_rise["validation"], t, days["validation"])
             for t in candidates]
    # 方針A：検証で的中率50%以上を保つ中で検知率が最大の基準
    eligible = [s for s in sweep if s["precision"] is not None and s["precision"] >= 0.5]
    policy_a = max(eligible, key=lambda s: s["recall"])
    # 方針B：検証で誤報が1日あたり1件以下に収まる中で検知率が最大の基準
    eligible_b = [s for s in sweep if s["false_alarms_per_day"] <= 1.0]
    policy_b = max(eligible_b, key=lambda s: s["recall"])
    results["ettm2_alerts"] = {
        "counting": "15分ごとの判定で数える。急上昇＝その時刻までの1時間の実測上昇幅が基準以上、通知＝1時間前に出した予測上昇幅が通知基準以上",
        "rapid_rise_threshold": rise_threshold,
        "rapid_rise_rows": {p: int(rises[p].sum()) for p in frames},
        "validation_sweep": sweep,
        "policies": {
            name: {
                "rule": rule,
                "validation": chosen,
                "test": alert_stats(rises["test"], pred_rise["test"],
                                    chosen["alert_threshold"], days["test"]),
                "test_events_reference": event_stats(rises["test"], pred_rise["test"],
                                                     chosen["alert_threshold"], days["test"]),
            }
            for name, rule, chosen in (
                ("precision_50", "検証で的中率50%以上の中で検知率最大", policy_a),
                ("one_false_alarm_per_day", "検証で誤報1日1件以下の中で検知率最大", policy_b),
            )
        },
        "persistence_note": "持続予測は予測上昇幅が常に0のため通知できない",
    }

    # 4. 予測区間：検証の誤差（実測−予測）の5%・95%分位点
    resid = valid["actual"].to_numpy() - pred["validation"]
    low, high = np.quantile(resid, [0.05, 0.95])
    test_resid = test["actual"].to_numpy() - pred["test"]
    inside = (test_resid >= low) & (test_resid <= high)
    rise_mask = rises["test"]
    results["ettm2_interval_90"] = {
        "lower_offset": float(low), "upper_offset": float(high),
        "width": float(high - low),
        "test_coverage": float(inside.mean()),
        "test_coverage_rapid_rise": float(inside[rise_mask].mean()),
        "test_actual_above_upper_rapid_rise": float((test_resid[rise_mask] > high).mean()),
    }

    # 5. alpha の感度（検証期間）
    results["ettm2_alpha_validation_mae"] = {
        str(a): mae(Ridge(alpha=a).fit(train[cols], train["actual"]).predict(valid[cols]),
                    valid["actual"])
        for a in (0.01, 0.1, 1.0, 10.0, 100.0, 1000.0)
    }

    # 6. 高温時：学習期間の油温の90パーセンタイル以上
    high_temp = float(np.quantile(oil.loc[oil.index < TRAIN_END], 0.9))
    hot = {}
    for part in frames:
        mask = frames[part]["actual"].to_numpy() >= high_temp
        hot[part] = {
            "n": int(mask.sum()),
            "persistence_mae": mae(frames[part]["now"].to_numpy()[mask], frames[part]["actual"].to_numpy()[mask]) if mask.any() else None,
            "ridge_mae": mae(pred[part][mask], frames[part]["actual"].to_numpy()[mask]) if mask.any() else None,
            "persistence_under": under(frames[part]["now"].to_numpy()[mask], frames[part]["actual"].to_numpy()[mask]) if mask.any() else None,
            "ridge_under": under(pred[part][mask], frames[part]["actual"].to_numpy()[mask]) if mask.any() else None,
        }
    results["ettm2_high_temperature"] = {"threshold": high_temp, **hot}

    out = ROOT / "outputs/metrics/37_limits_checks.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in results.items() if k != "ettm2_alerts"}, ensure_ascii=False, indent=1))
    print(json.dumps(results["ettm2_alerts"]["policies"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
