"""Statistics helpers — paired comparisons and confidence intervals.

The comparison harness runs every strategy on **identical seeds** (common
random numbers). That is a paired design: for a fair strategy-vs-strategy
claim, analyse per-seed *differences*, not two independent samples. Earlier
versions plotted ±1 sd and eyeballed; v0.5 reports n, 95 % CIs, and a
Wilcoxon signed-rank p-value alongside the paired-t interval (ranks and
winner-derived metrics are not reliably normal).
"""

from __future__ import annotations

import itertools
import math

import pandas as pd
from scipy import stats as sps


def mean_ci(values, level: float = 0.95) -> tuple[float, float]:
    """Mean and half-width of the t confidence interval."""
    v = pd.Series(values).dropna()
    n = len(v)
    if n < 2:
        return (float(v.mean()) if n else float("nan")), float("nan")
    half = sps.t.ppf(0.5 + level / 2, n - 1) * v.std(ddof=1) / math.sqrt(n)
    return float(v.mean()), float(half)


def paired_table(df: pd.DataFrame, metrics: list[str],
                 level: float = 0.95) -> pd.DataFrame:
    """Pairwise strategy contrasts on common seeds.

    For every strategy pair and metric: n common seeds, mean paired
    difference (A − B), its t CI half-width, and the Wilcoxon signed-rank p.
    """
    rows = []
    strategies = list(dict.fromkeys(df["strategy"]))
    by = {s: df[df["strategy"] == s].set_index("seed") for s in strategies}
    for a, b in itertools.combinations(strategies, 2):
        seeds = by[a].index.intersection(by[b].index)
        for metric in metrics:
            d = (by[a].loc[seeds, metric] - by[b].loc[seeds, metric]).dropna()
            mean, half = mean_ci(d, level)
            if len(d) >= 2 and (d != 0).any():
                p = float(sps.wilcoxon(d).pvalue)
            else:
                p = float("nan")
            rows.append({
                "metric": metric, "A": a, "B": b, "n": len(d),
                "mean_diff(A-B)": mean, f"ci{int(level * 100)}_half": half,
                "wilcoxon_p": p,
                "significant": bool(abs(mean) > half) if half == half else False,
            })
    return pd.DataFrame(rows)


def paired_markdown(df: pd.DataFrame, metrics: list[str], path: str) -> None:
    table = paired_table(df, metrics)
    with open(path, "w") as fh:
        fh.write("# Paired strategy contrasts (common random numbers)\n\n")
        fh.write(f"n = common seeds per pair; CI = 95% t interval on the "
                 f"per-seed difference; Wilcoxon = signed-rank test.\n\n")
        fh.write(table.round(4).to_markdown(index=False))
        fh.write("\n")
