"""直近3点の油温を使うRidge回帰を検証する。"""

import argparse
import json

import pandas as pd
from sklearn.linear_model import Ridge

from athena_task.persistence import ROOT


def alert_counts(actual_crossing, alarm):
    hits = int((actual_crossing & alarm).sum())
    misses = int((actual_crossing & ~alarm).sum())
    false_alarms = int((~actual_crossing & alarm).sum())
    return {"hits": hits, "misses": misses, "false_alarms": false_alarms}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    load_options = parser.add_mutually_exclusive_group()
    load_options.add_argument("--with-load", action="store_true", help="予測時点の負荷6項目を追加する")
    load_options.add_argument("--with-load-history", action="store_true", help="予測時点と1・2時間前の負荷を追加する")
    load_options.add_argument("--with-lag10-load", action="store_true", help="予測対象の10時間前のHULLとMULLを追加する")
    load_options.add_argument("--with-lag10-and-15-load", action="store_true", help="10時間前のHULL・MULLと15時間前のHUFL・MUFLを追加する")
    load_options.add_argument("--with-daily-oil", action="store_true", help="予測対象の24時間前の油温を追加する")
    load_options.add_argument("--with-two-days-oil", action="store_true", help="予測対象の24・48時間前の油温を追加する")
    load_options.add_argument("--with-seven-days-oil", action="store_true", help="過去7日分の同時刻の油温を追加する")
    parser.add_argument("--alerts", action="store_true", help="1時間先のしきい値到達を評価する")
    parser.add_argument("--lightgbm", action="store_true", help="油温の入力をそろえてLightGBMを評価する")
    parser.add_argument("--three-hours", action="store_true", help="3時間先の油温を持続予測と比較する")
    parser.add_argument("--one-hour-metrics", action="store_true", help="1時間先の誤差と急上昇の検知をまとめて評価する")
    parser.add_argument("--compare-training-length", action="store_true", help="12か月と15か月の学習期間を比較する")
    parser.add_argument("--three-hour-load", action="store_true", help="3時間先の比較に予測時点の負荷を追加する")
    parser.add_argument("--dataset", choices=["ETTh1", "ETTh2", "ETTm1", "ETTm2"], default="ETTh1")
    parser.add_argument("--fifteen-minutes", action="store_true", help="ETTm?15?????????")
    parser.add_argument("--thirty-minutes", action="store_true", help="ETTmの30分先を直近3点で予測する")
    parser.add_argument("--sixty-minutes", action="store_true", help="ETTm?60?????3??????")
    parser.add_argument("--five-recent", action="store_true", help="1時間先の比較に直近5点のRidgeを追加する")
    parser.add_argument("--week-recent", action="store_true", help="1時間先の比較に直近1週間の油温を追加する")
    parser.add_argument("--compare-history-lengths", action="store_true", help="直近1日・7日・14日の油温を比較する")
    parser.add_argument("--final-test", action="store_true", help="ETTm2の確定モデルを2018年以降で評価する")
    args = parser.parse_args()
    if args.final_test and (
        args.dataset != "ETTm2" or not (args.sixty_minutes and args.week_recent)
        or args.compare_training_length or args.compare_history_lengths
    ):
        parser.error("--final-test は --dataset ETTm2 --sixty-minutes --week-recent と指定してください。")
    if args.compare_history_lengths and not (args.sixty_minutes and args.week_recent):
        parser.error("--compare-history-lengths は --sixty-minutes --week-recent と一緒に指定してください。")
    if args.week_recent and not args.sixty_minutes:
        parser.error("--week-recent は --sixty-minutes と一緒に指定してください。")
    if args.five_recent and not args.sixty_minutes:
        parser.error("--five-recent は --sixty-minutes と一緒に指定してください。")
    short_horizon = args.thirty_minutes or args.sixty_minutes
    if args.thirty_minutes and args.sixty_minutes:
        parser.error("Choose one forecast horizon.")
    if short_horizon and (
        not args.dataset.startswith("ETTm") or args.fifteen_minutes or args.one_hour_metrics
        or args.three_hours or args.alerts or args.lightgbm
        or any((args.with_load, args.with_load_history, args.with_lag10_load,
                args.with_lag10_and_15_load, args.with_daily_oil, args.with_two_days_oil,
                args.with_seven_days_oil))
    ):
        parser.error("--thirty-minutes / --sixty-minutes はETTmを指定し、他の実験オプションを外してください。")
    if args.fifteen_minutes and (not args.dataset.startswith("ETTm") or not args.one_hour_metrics):
        parser.error("--fifteen-minutes ?ETTm? --one-hour-metrics ??????????")
    if args.three_hour_load and not args.three_hours:
        parser.error("--three-hour-load は --three-hours と一緒に指定してください。")
    if args.compare_training_length and (
        not (args.with_seven_days_oil or (args.sixty_minutes and args.week_recent))
        or args.three_hours or args.alerts or args.lightgbm or args.one_hour_metrics
        or args.compare_history_lengths
    ):
        parser.error("--compare-training-length は --with-seven-days-oil と一緒に指定してください。")
    if args.one_hour_metrics and (
        not args.with_seven_days_oil or args.three_hours or args.alerts or args.lightgbm
    ):
        parser.error("--one-hour-metrics は --with-seven-days-oil と一緒に指定してください。")
    if args.three_hours and (not args.with_seven_days_oil or args.alerts or args.lightgbm):
        parser.error("--three-hours は --with-seven-days-oil と一緒に指定してください。")
    if args.lightgbm and (not args.with_seven_days_oil or args.alerts):
        parser.error("--lightgbm は --with-seven-days-oil と一緒に指定してください。")

    config = json.loads((ROOT / "configs/baseline.json").read_text(encoding="utf-8"))
    date = config["timestamp_column"]
    target = config["target_column"]
    steps = 3 if args.three_hours else config["forecast_horizon_steps"]
    if args.one_hour_metrics and steps != 1:
        parser.error("--one-hour-metrics は1時間先予測専用です。")
    if args.alerts and (not args.with_seven_days_oil or steps != 1):
        parser.error("--alerts は1時間先予測の --with-seven-days-oil と一緒に指定してください。")
    split = config["split"]
    train_end = pd.Timestamp(split["train_end"])
    validation_end = pd.Timestamp(split["validation_end"])

    data_path = ROOT / config["data_path"]
    if args.dataset != "ETTh1":
        data_path = data_path.with_name(f"{args.dataset}.csv")
    rows_per_hour = 4 if args.dataset.startswith("ETTm") else 1
    data = pd.read_csv(data_path, parse_dates=[date])
    data = data.sort_values(date).set_index(date)
    if not args.final_test:
        data = data.loc[data.index < validation_end]
    if not data.index.to_series().diff().iloc[1:].eq(pd.Timedelta(minutes=60 // rows_per_hour)).all():
        raise ValueError("観測日時が1時間間隔で並んでいません。")

    # 11時が正解なら、10時・9時・8時の油温を同じ行に並べる。
    oil = data[target]
    horizon_rows = steps * rows_per_hour
    if args.fifteen_minutes or short_horizon:
        horizon_rows = 1 if args.fifteen_minutes else (4 if args.sixty_minutes else 2)
    recent_stride = 1 if args.fifteen_minutes or short_horizon else rows_per_hour
    inputs = pd.DataFrame({
        "ot_now": oil.shift(horizon_rows),
        "ot_previous": oil.shift(horizon_rows + recent_stride),
        "ot_two_back": oil.shift(horizon_rows + 2 * recent_stride),
    })
    recent_columns = inputs.columns
    if args.five_recent or args.week_recent:
        for lag in (3, 4):
            inputs[f"ot_{lag}_back"] = oil.shift(horizon_rows + lag)
    five_columns = inputs.columns
    if args.week_recent:
        week_points = 168 * rows_per_hour
        history_points = week_points * (2 if args.compare_history_lengths else 1)
        # 予測時点を含む履歴をまとめて作る。
        older = {f"ot_{lag}_back": oil.shift(horizon_rows + lag)
                 for lag in range(5, history_points)}
        inputs = pd.concat([inputs, pd.DataFrame(older)], axis=1)
        del older
    filename = "ridge_validation.json"
    history_rows = steps + 2
    if args.with_daily_oil or args.with_two_days_oil or args.with_seven_days_oil:
        if steps > 24:
            raise ValueError("24時間前の油温が予測時点でまだ観測されていません。")
        # 今日11時の油温を予測するなら、昨日11時の油温を足す。
        inputs["ot_lag24"] = oil.shift((24) * rows_per_hour)
        history_rows = max(history_rows, 24)
        filename = "ridge_with_daily_oil_validation.json"
    if args.with_two_days_oil or args.with_seven_days_oil:
        inputs["ot_lag48"] = oil.shift((48) * rows_per_hour)
        history_rows = max(history_rows, 48)
        filename = "ridge_with_two_days_oil_validation.json"
    if args.with_seven_days_oil:
        # 昨日・一昨日に加えて、3〜7日前の同じ時刻の油温を使う。
        extra_columns = []
        for days_ago in range(3, 8):
            hours_ago = 24 * days_ago
            column = f"ot_lag{hours_ago}"
            inputs[column] = oil.shift((hours_ago) * rows_per_hour)
            extra_columns.append(column)
        history_rows = max(history_rows, 168)
        filename = "ridge_with_seven_days_oil_validation.json"
    if args.with_lag10_load or args.with_lag10_and_15_load:
        if steps > 10:
            raise ValueError("10時間前の負荷が予測時点でまだ観測されていません。")
        # 正解が11時なら、EDAで相関が強かった10時間前（1時）の負荷を使う。
        inputs[["HULL_lag10", "MULL_lag10"]] = data[["HULL", "MULL"]].shift((10) * rows_per_hour)
        history_rows = max(history_rows, 10)
        filename = "ridge_with_lag10_load_validation.json"
    if args.with_lag10_and_15_load:
        # 正解が11時なら、15時間前は前日の20時。
        inputs[["HUFL_lag15", "MUFL_lag15"]] = data[["HUFL", "MUFL"]].shift((15) * rows_per_hour)
        history_rows = max(history_rows, 15)
        filename = "ridge_with_lag10_and_15_load_validation.json"
    load_columns = ["HUFL", "HULL", "MUFL", "MULL", "LUFL", "LULL"]
    if args.three_hour_load:
        # 13時を予測する場合は、10時に観測済みの負荷を使う。
        inputs[load_columns] = data[load_columns].shift((steps) * rows_per_hour)
    if args.with_load or args.with_load_history:
        inputs[load_columns] = data[load_columns].shift((steps) * rows_per_hour)
        filename = "ridge_with_load_validation.json"
        if args.with_load_history:
            # 11時の予測に使う10時の負荷に、9時・8時の負荷を加える。
            for hours_ago in (1, 2):
                columns = [f"{name}_{hours_ago}h_ago" for name in load_columns]
                inputs[columns] = data[load_columns].shift((steps + hours_ago) * rows_per_hour)
            filename = "ridge_with_load_history_validation.json"
    # 履歴が足りない先頭行を除き、正解の時刻で学習と検証を分ける。
    # 15分先の比較と同じ学習対象を使うため、最初の7日分を外す。
    first_row = 168 * rows_per_hour if short_horizon else history_rows * rows_per_hour
    if args.week_recent:
        first_row = horizon_rows + history_points - 1
    pairs = inputs.assign(actual=oil).iloc[first_row:]
    train = pairs.loc[pairs.index < train_end]
    evaluation_start = validation_end if args.final_test else train_end
    validation = pairs.loc[pairs.index >= evaluation_start]
    if train.empty or validation.empty or pairs.isna().any().any():
        raise ValueError("学習・検証に必要な観測値が不足しています。")

    # 最初の比較では、重みを抑える強さを1に固定する。
    def summarize_underprediction(errors):
        return {
            name: {
                "n": int(mask.sum()),
                "mean_underprediction": float(errors[mask].clip(lower=0).mean()) if mask.any() else None,
                "mean_overprediction": float((-errors[mask]).clip(lower=0).mean()) if mask.any() else None,
                "mean_prediction_minus_actual": float(-errors[mask].mean()) if mask.any() else None,
            }
            for name, mask in three_hour_groups.items()
        }

    if args.three_hours or args.final_test:
        high_threshold = float(oil.loc[oil.index < train_end].quantile(0.9))
        rise_threshold = float(oil.diff(steps * rows_per_hour).loc[oil.index < train_end].quantile(0.9))
        three_hour_groups = {
            "high_temperature": validation["actual"] >= high_threshold,
            "rapid_rise": validation["actual"] - validation["ot_now"] >= rise_threshold,
            "other_hours": validation["actual"] - validation["ot_now"] < rise_threshold,
        }

    def summarize_three_hour_alerts(predictions):
        predicted_rise = predictions - validation["ot_now"]
        counts = alert_counts(three_hour_groups["rapid_rise"], predicted_rise >= rise_threshold)
        events = counts["hits"] + counts["misses"]
        alerts = counts["hits"] + counts["false_alarms"]
        return {
            **counts,
            "recall": counts["hits"] / events if events else None,
            "precision": counts["hits"] / alerts if alerts else None,
        }

    def evaluate(columns, *, check_alerts=False, model=None, match_overprediction=None):
        if model is None:
            model = Ridge(alpha=1.0)
        model.fit(train[columns], train["actual"])
        predictions = model.predict(validation[columns])
        errors = validation["actual"] - predictions
        if match_overprediction is not None:
            from scipy.optimize import brentq

            # 検証データ上で過大予測量をそろえ、負荷の効果を調べる。
            other_errors = errors[three_hour_groups["other_hours"]]

            def gap(offset):
                return float((offset - other_errors).clip(lower=0).mean()) - match_overprediction

            offset = brentq(gap, float(other_errors.min()),
                            float(other_errors.max()) + match_overprediction)
            errors = errors - offset
            predictions = predictions + offset
        result = {
            "n": len(validation),
            "mae": float(errors.abs().mean()),
            "rmse": float((errors.pow(2).mean()) ** 0.5),
        }
        if args.three_hours or short_horizon:
            # 実測を下回った幅を平均する。実測以上の予測は0とする。
            result["mean_underprediction"] = float(errors.clip(lower=0).mean())
        if args.three_hours:
            result["underprediction_by_group"] = summarize_underprediction(errors)
            result["rapid_rise_alerts"] = summarize_three_hour_alerts(predictions)
        if args.final_test:
            result["rapid_rise"] = summarize_underprediction(errors)["rapid_rise"]
        if isinstance(model, Ridge):
            result["alpha"] = model.alpha
        if match_overprediction is not None:
            result["offset"] = offset
        if check_alerts:
            # しきい値は学習期間の全観測から決め、検証期間では固定する。
            threshold = float(oil.loc[oil.index < train_end].quantile(0.9))
            current = validation["ot_now"]
            # 現在がしきい値未満の時点だけ、次の1時間での到達を判定する。
            eligible = current < threshold
            crossing = eligible & (validation["actual"] >= threshold)
            result["alerts"] = {
                "threshold": threshold,
                "eligible_n": int(eligible.sum()),
                "actual_crossings": int(crossing.sum()),
                "persistence": alert_counts(crossing, eligible & (current >= threshold)),
                "ridge": alert_counts(crossing, eligible & (predictions >= threshold)),
            }
        return result

    if args.final_test:
        errors = validation["actual"] - validation["ot_now"]
        metrics = {
            "horizon_minutes": 60,
            "train_n": len(train),
            "test_n": len(validation),
            "test_start": str(validation.index.min()),
            "test_end": str(validation.index.max()),
            "rapid_rise_threshold": rise_threshold,
            "persistence": {
                "mae": float(errors.abs().mean()),
                "rmse": float((errors.pow(2).mean()) ** 0.5),
                "mean_underprediction": float(errors.clip(lower=0).mean()),
                "rapid_rise": summarize_underprediction(errors)["rapid_rise"],
            },
            "ridge_day": evaluate(inputs.columns[:24 * rows_per_hour]),
            "ridge_week": evaluate(inputs.columns),
        }
        filename = "sixty_minute_final_test.json"
    elif short_horizon and not args.compare_training_length:
        persistence_errors = validation["actual"] - validation["ot_now"]
        ridge_metrics = evaluate(recent_columns)
        metrics = {
            "horizon_minutes": 60 if args.sixty_minutes else 30,
            "train_n": len(train),
            "n": len(validation),
            "persistence": {
                "mae": float(persistence_errors.abs().mean()),
                "rmse": float((persistence_errors.pow(2).mean()) ** 0.5),
                "mean_underprediction": float(persistence_errors.clip(lower=0).mean()),
            },
            "ridge": ridge_metrics,
        }
        interval = "sixty" if args.sixty_minutes else "thirty"
        filename = f"{interval}_minute_metrics_validation.json"
        if args.five_recent or args.week_recent:
            metrics["ridge_five_recent"] = evaluate(five_columns)
            filename = "sixty_minute_recent_history_comparison.json"
        if args.week_recent:
            metrics["ridge_week_recent"] = evaluate(inputs.columns[:week_points])
            filename = "sixty_minute_week_history_comparison.json"
        if args.compare_history_lengths:
            metrics["ridge_day_recent"] = evaluate(inputs.columns[:24 * rows_per_hour])
            metrics["ridge_two_weeks_recent"] = evaluate(inputs.columns)
            filename = "sixty_minute_history_lengths_comparison.json"
    elif args.compare_training_length:
        if steps != 1:
            parser.error("--compare-training-length は1時間先予測専用です。")
        # 正解の日時で区切り、10月以降の同じ行で全手法を評価する。
        extended_end = train_end + pd.DateOffset(months=3)
        extended_train = pairs.loc[pairs.index < extended_end]
        common_validation = pairs.loc[pairs.index >= extended_end]
        if common_validation.empty or len(extended_train) == len(train):
            raise ValueError("比較に必要な追加学習期間または共通検証期間がありません。")

        def summarize_errors(prediction):
            errors = common_validation["actual"] - prediction
            return {
                "mae": float(errors.abs().mean()),
                "rmse": float(errors.pow(2).mean() ** 0.5),
                "mean_underprediction": float(errors.clip(lower=0).mean()),
            }

        metrics = {
            "horizon_hours": steps,
            "validation_start": str(extended_end),
            "validation_end_exclusive": str(validation_end),
            "n": len(common_validation),
            "persistence": summarize_errors(common_validation["ot_now"]),
        }
        for label, training in (("ridge_12_months", train), ("ridge_15_months", extended_train)):
            model = Ridge(alpha=1.0)
            model.fit(training[inputs.columns], training["actual"])
            prediction = model.predict(common_validation[inputs.columns])
            metrics[label] = {"train_n": len(training), **summarize_errors(prediction)}
        filename = "training_length_validation.json"
    elif args.one_hour_metrics:
        # 学習期間の全観測で上昇幅の境目を求め、検証では固定する。
        threshold = float(oil.diff(horizon_rows).loc[oil.index < train_end].quantile(0.9))
        current = validation["ot_now"]
        actual = validation["actual"]
        actual_rise = (actual - current) >= threshold

        def summarize(prediction):
            errors = actual - prediction
            counts = alert_counts(actual_rise, (prediction - current) >= threshold)
            event_count = counts["hits"] + counts["misses"]
            return {
                "mae": float(errors.abs().mean()),
                "rmse": float(errors.pow(2).mean() ** 0.5),
                "mean_underprediction": float(errors.clip(lower=0).mean()),
                **counts,
                "recall": counts["hits"] / event_count if event_count else None,
            }

        model = Ridge(alpha=1.0).fit(train[inputs.columns], train["actual"])
        prediction = model.predict(validation[inputs.columns])
        from matplotlib.figure import Figure

        observed_change = actual - current
        predicted_change = prediction - current
        # 急上昇の定義は固定し、通知を出す基準だけを変える。
        alert_tradeoff = []
        event_count = int(actual_rise.sum())
        for alert_threshold in (threshold, 0.5, 0.3, 0.2, 0.1, 0.05):
            counts = alert_counts(actual_rise, predicted_change >= alert_threshold)
            alerts = counts["hits"] + counts["false_alarms"]
            alert_tradeoff.append({
                "alert_threshold": alert_threshold,
                **counts,
                "recall": counts["hits"] / event_count if event_count else None,
                "precision": counts["hits"] / alerts if alerts else None,
            })
        fig = Figure(figsize=(8, 5), layout="constrained")
        ax = fig.subplots()
        ax.scatter(observed_change[~actual_rise], predicted_change[~actual_rise],
                   s=9, alpha=0.22, label="Other hours")
        ax.scatter(observed_change[actual_rise], predicted_change[actual_rise],
                   s=16, alpha=0.65, color="tab:orange", label="Actual rapid rises")
        ax.axvline(threshold, color="tab:red", linestyle="--", label=f"Threshold: +{threshold:.3f}")
        ax.axhline(threshold, color="tab:red", linestyle="--")
        ax.axhline(0, color="gray", linewidth=0.8)
        interval = "15-minute" if args.fifteen_minutes else "1-hour"
        ax.set(xlabel=f"Actual {interval} oil temperature change",
               ylabel=f"Predicted {interval} oil temperature change",
               title="Ridge: actual vs. predicted change (validation)")
        ax.legend()
        figure_path = ROOT / config["output_dir"] / "figures" / ("one_hour_rise_scatter.png" if args.dataset == "ETTh1" else f"{args.dataset.lower()}_{interval}_rise_scatter.png")
        figure_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(figure_path, dpi=150)
        metrics = {
            "horizon_hours": steps,
            "train_n": len(train),
            "n": len(validation),
            "rise_threshold": threshold,
            "actual_rapid_rises": int(actual_rise.sum()),
            "persistence": summarize(current),
            "ridge": summarize(prediction),
            "ridge_alert_tradeoff": alert_tradeoff,
            "ridge_rapid_rise_diagnostics": {
                "positive_predictions": int((predicted_change[actual_rise] > 0).sum()),
                "median_predicted_change": float(predicted_change[actual_rise].median()) if actual_rise.any() else None,
                "max_predicted_change": float(predicted_change[actual_rise].max()) if actual_rise.any() else None,
            },
        }
        filename = "one_hour_metrics_validation.json"
        if args.fifteen_minutes:
            recent_columns = ["ot_now", "ot_previous", "ot_two_back"]
            recent_model = Ridge(alpha=1.0).fit(train[recent_columns], train["actual"])
            metrics["matched_recent_only"] = summarize(recent_model.predict(validation[recent_columns]))
            metrics.pop("horizon_hours")
            metrics["horizon_minutes"] = 15
            filename = "fifteen_minute_metrics_validation.json"
    else:
        metrics = evaluate(inputs.columns, check_alerts=args.alerts)
    if args.lightgbm:
        from lightgbm import LGBMRegressor

        # 初回は浅めの木を100本使い、検証結果を見ながら設定は変えない。
        settings = dict(n_estimators=100, learning_rate=0.1, num_leaves=15,
                        objective="regression_l1", random_state=config["random_seed"],
                        n_jobs=2, verbosity=-1)
        metrics = {
            "lightgbm": evaluate(inputs.columns, model=LGBMRegressor(**settings)),
            "matched_ridge": metrics,
            "settings": settings,
            "train_n": len(train),
        }
        filename = "lightgbm_validation.json"
    if args.alerts:
        filename = "ridge_alerts_validation.json"
    if args.with_seven_days_oil and not (
        args.lightgbm or args.one_hour_metrics or args.compare_training_length or args.three_hours
    ):
        metrics["matched_two_days_oil"] = evaluate(inputs.columns.drop(extra_columns))
        metrics["train_n"] = len(train)
    if args.with_two_days_oil:
        metrics["matched_daily_oil"] = evaluate(inputs.columns.drop("ot_lag48"))
        metrics["train_n"] = len(train)
    if args.with_lag10_and_15_load:
        metrics["matched_lag10_only"] = evaluate(inputs.columns.drop(["HUFL_lag15", "MUFL_lag15"]))
        metrics["train_n"] = len(train)
    if args.with_daily_oil:
        # 昨日の油温を外したモデルも、同じ学習行と検証行で評価する。
        metrics["matched_oil_only"] = evaluate(inputs.columns.drop("ot_lag24"))
        metrics["train_n"] = len(train)
    if args.three_hours:
        # 持続予測は、予測を出す時刻の油温をそのまま使う。
        errors = validation["actual"] - validation["ot_now"]
        metrics = {
            "horizon_hours": steps,
            "train_n": len(train),
            "high_temperature_threshold": high_threshold,
            "rapid_rise_threshold": rise_threshold,
            "ridge": metrics,
            "persistence": {
                "n": len(validation),
                "mae": float(errors.abs().mean()),
                "rmse": float((errors.pow(2).mean()) ** 0.5),
                "mean_underprediction": float(errors.clip(lower=0).mean()),
                "underprediction_by_group": summarize_underprediction(errors),
                "rapid_rise_alerts": summarize_three_hour_alerts(validation["ot_now"]),
            },
        }
        filename = "three_hours_validation.json"
        if args.three_hour_load:
            metrics["ridge_with_load"] = metrics["ridge"]
            metrics["ridge"] = evaluate(inputs.columns.drop(load_columns))
            target_overprediction = metrics["ridge_with_load"]["underprediction_by_group"]["other_hours"]["mean_overprediction"]
            metrics["ridge_with_offset"] = evaluate(
                inputs.columns.drop(load_columns), match_overprediction=target_overprediction
            )
            filename = "three_hours_with_load_validation.json"
    result = json.dumps(metrics, indent=2)
    if args.dataset != "ETTh1":
        filename = f"{args.dataset.lower()}_{filename}"
    output = ROOT / config["output_dir"] / "metrics" / filename
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(result + "\n", encoding="utf-8")
    print(result)


if __name__ == "__main__":
    main()
