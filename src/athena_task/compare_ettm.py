"""ETTm1とETTm2の学習期間を比較する。"""

import json

import pandas as pd
from matplotlib.figure import Figure

from athena_task.persistence import ROOT


def main():
    config = json.loads((ROOT / "configs/baseline.json").read_text(encoding="utf-8"))
    cutoff = pd.Timestamp(config["split"]["train_end"])
    output = ROOT / config["output_dir"]
    fig = Figure(figsize=(10, 7), layout="constrained")
    week, daily, acf = fig.subplots(3, 1)
    summary = {}
    for name in ("ETTm1", "ETTm2"):
        path = (ROOT / config["data_path"]).with_name(f"{name}.csv")
        data = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
        oil = data.loc[data.index < cutoff, "OT"]
        change = oil.diff().dropna()
        centered = oil - oil.groupby(oil.index.normalize()).transform("mean")
        slots = oil.index.hour + oil.index.minute / 60
        profile = centered.groupby(slots).mean()
        hours = range(193)
        correlations = [change.autocorr(lag) for lag in hours]
        summary[name] = {
            "n": len(oil),
            "change_mae": float(change.abs().mean()),
            "change_acf_15min": correlations[1],
            "change_acf_30min": correlations[2],
            "change_acf_24h": correlations[96],
            "oil_acf_24h": oil.autocorr(96),
            "daily_profile_range": float(profile.max() - profile.min()),
        }
        first_week = oil.iloc[:672]
        week.plot(first_week.index, first_week, label=name)
        daily.plot(profile.index, profile, label=name)
        acf.plot([lag / 4 for lag in hours], correlations, label=name)
    week.set(title="First seven days of training", ylabel="Oil temperature (OT)")
    daily.set(title="Average daily profile after subtracting each day's mean",
              xlabel="Hour of day", ylabel="OT minus daily mean")
    acf.set(title="Autocorrelation of 15-minute oil temperature changes",
            xlabel="Lag (hours)", ylabel="Correlation")
    acf.axhline(0, color="gray", linewidth=0.8)
    acf.set_ylim(-0.25, 1.05)
    for ax in (week, daily, acf):
        ax.legend()
    (output / "figures").mkdir(parents=True, exist_ok=True)
    (output / "metrics").mkdir(parents=True, exist_ok=True)
    fig.savefig(output / "figures/ettm_comparison.png", dpi=150)
    result = json.dumps(summary, indent=2)
    (output / "metrics/ettm_eda_comparison.json").write_text(result + "\n", encoding="utf-8")
    print(result)


if __name__ == "__main__":
    main()
