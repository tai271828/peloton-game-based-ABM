"""Side-by-side comparison of game theories — the framework's reason to exist.

Runs any set of registered strategies on **identical seeds** (same skill draws,
same start grid, same physics) and reports the standard metric set per
strategy, as a tidy DataFrame, a markdown table, and a dashboard figure with
mean ± sd bars plus the action-mix fingerprint.

Library use::

    from peloton.analysis import compare, summarize
    df = compare(["public_goods", "hawk_dove", "lead_out"], seeds=range(10))
    print(summarize(df).to_string())

CLI (any auto-discovered strategy name works)::

    python -m peloton.analysis.compare public_goods hawk_dove lead_out \
        --seeds 10 --out figures/compare
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from peloton.model import RaceModel
from peloton.actions import Action
from peloton.analysis.metrics import DASHBOARD_METRICS, race_metrics
from peloton.strategies import available


def _params_for(name: str, strategy_params) -> dict | None:
    """``strategy_params`` may be flat (applies to all) or ``{name: dict}``."""
    if not strategy_params:
        return None
    per = strategy_params.get(name)
    return per if isinstance(per, dict) else strategy_params


def compare(strategies, n_riders=48, n_teams=8, seeds=range(10),
            strategy_params=None, params=None) -> pd.DataFrame:
    """Run every (strategy, seed) race and return one metrics row per race."""
    rows = []
    for name in strategies:
        sp = _params_for(name, strategy_params)
        for seed in seeds:
            m = RaceModel(n_riders=n_riders, n_teams=n_teams, strategy=name,
                          strategy_params=sp, params=params,
                          seed=seed, collect=False)
            m.run()
            rows.append({"strategy": name, "seed": seed, **race_metrics(m)})
    return pd.DataFrame(rows)


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    """Mean over seeds, one row per strategy (numeric columns only)."""
    return (df.drop(columns="seed")
              .groupby("strategy")
              .mean(numeric_only=True)
              .round(3))


def to_markdown(df: pd.DataFrame, path: str) -> None:
    summ = summarize(df)
    cols = [k for k, _ in DASHBOARD_METRICS] + \
           [f"share_{a.value}" for a in Action]
    with open(path, "w") as fh:
        fh.write("# Strategy comparison (mean over seeds)\n\n")
        fh.write(summ[cols].to_markdown())
        fh.write("\n")


def dashboard(df: pd.DataFrame, path: str, title=None) -> None:
    """Mean ± sd bars for the standard metrics + an action-mix panel."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    strategies = list(dict.fromkeys(df["strategy"]))
    cmap = plt.get_cmap("tab10")
    colors = {s: cmap(i % 10) for i, s in enumerate(strategies)}

    n_panels = len(DASHBOARD_METRICS) + 1
    ncols = 4
    nrows = -(-n_panels // ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(3.2 * ncols, 3.4 * nrows))
    axes = axes.ravel()

    from peloton.analysis.stats import mean_ci
    for ax, (key, label) in zip(axes, DASHBOARD_METRICS):
        for i, s in enumerate(strategies):
            vals = df.loc[df["strategy"] == s, key].dropna()
            mean, half = mean_ci(vals)            # error bars are 95% CIs
            ax.bar(i, mean, yerr=half, capsize=3,
                   color=colors[s], width=0.65)
        ax.set_xticks(range(len(strategies)))
        ax.set_xticklabels([s.replace("_", "\n") for s in strategies],
                           fontsize=8)
        ax.set_title(label, fontsize=10)

    # action-mix fingerprint: stacked decision shares per strategy.
    ax = axes[len(DASHBOARD_METRICS)]
    bottoms = np.zeros(len(strategies))
    act_cmap = plt.get_cmap("viridis")
    for k, act in enumerate(Action):
        vals = [df.loc[df["strategy"] == s, f"share_{act.value}"].mean()
                for s in strategies]
        ax.bar(range(len(strategies)), vals, bottom=bottoms,
               color=act_cmap(k / (len(Action) - 1)), width=0.65,
               label=act.value)
        bottoms += np.array(vals)
    ax.set_xticks(range(len(strategies)))
    ax.set_xticklabels([s.replace("_", "\n") for s in strategies], fontsize=8)
    ax.set_title("action mix\n(decision shares)", fontsize=10)
    ax.legend(fontsize=6, loc="center left", bbox_to_anchor=(1.0, 0.5))

    for ax in axes[n_panels:]:
        ax.axis("off")

    fig.suptitle(title or
                 "Same physics, same seeds — swapped game theory: "
                 "emergent behaviour side by side", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(
        description="Compare registered game theories on identical seeds.")
    ap.add_argument("strategies", nargs="*", default=None,
                    help=f"strategy names (default: all = {available()})")
    ap.add_argument("--riders", type=int, default=48)
    ap.add_argument("--teams", type=int, default=8)
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--out", default="figures/compare",
                    help="output basename (.png + .md are appended)")
    args = ap.parse_args()

    names = args.strategies or available()
    unknown = [n for n in names if n not in available()]
    if unknown:
        ap.error(f"unknown strategies {unknown}; available: {available()}")

    df = compare(names, n_riders=args.riders, n_teams=args.teams,
                 seeds=range(args.seeds))
    print(summarize(df).to_string())
    dashboard(df, args.out + ".png")
    to_markdown(df, args.out + ".md")
    from peloton.analysis.stats import paired_markdown
    paired_markdown(df, [k for k, _ in DASHBOARD_METRICS],
                    args.out + "_paired.md")
    print(f"[compare] wrote {args.out}.png/.md and {args.out}_paired.md")


if __name__ == "__main__":
    main()
