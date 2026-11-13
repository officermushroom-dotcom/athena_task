"""検証期間で持続予測を評価する。"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def main():
    config = json.loads((ROOT / "configs/baseline.json").read_text(encoding="utf-8"))
    date = config["timestamp_column"]
    target = config["target_column"]
    steps = config["forecast_horizon_steps"]
    split = config["split"]

    data = pd.read_csv(ROOT / config["data_path"], parse_dates=[date])
    data = data.sort_values(date).set_index(date)
    if not data.index.to_series().diff().iloc[1:].eq(pd.Timedelta(hours=1)).all():
        raise ValueError("観測日時が1時間間隔で並んでいません。")

    # 正解の時刻の行に、1時間前の油温を予測値として並べる。
    pairs = pd.DataFrame({"actual": data[target], "prediction": data[target].shift(steps)})

    # 正解の時刻で期間を選ぶ。7月1日0時の予測には6月30日23時の値を使える。
    validation = pairs.loc[
        (pairs.index >= pd.Timestamp(split["train_end"]))
        & (pairs.index < pd.Timestamp(split["validation_end"]))
    ]
    if validation.empty or validation.isna().any().any():
        raise ValueError("検証期間の実測値または予測に必要な油温が不足しています。")

    errors = validation["actual"] - validation["prediction"]
    metrics = {
        "n": len(validation),
        "mae": float(errors.abs().mean()),
        "rmse": float((errors.pow(2).mean()) ** 0.5),
    }
    result = json.dumps(metrics, indent=2)
    output = ROOT / config["output_dir"] / "metrics" / "persistence_validation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(result + "\n", encoding="utf-8")
    print(result)


if __name__ == "__main__":
    main()
