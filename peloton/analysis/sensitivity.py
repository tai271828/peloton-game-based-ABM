"""Local and global sensitivity analysis (Morris screening + Sobol indices).

The reference configuration is the calibrated ``discrete_choice`` game (the
canonical model of the report). Three QoIs summarise the emergent behaviour:
``mean_speed_kmh``, ``finish_spread_s``, ``drafted_share``.

Two deliberately separate questions:

* **Behavioural/physical factors** (drafting strength, W′ knee, sprint
  length, ...): which ones *drive* the emergent behaviour? → Morris
  screening (cheap, ranks factors by μ*), then Sobol S1/ST on the top set
  (variance decomposition, interaction detection).
* **Numerical parameters** (``dt``): the model must be *insensitive* —
  a robustness check, not a science question — handled by ``dt_sweep``.

Stochasticity: each sample point is averaged over ``reps`` seed-replicates;
SALib then sees the replicate mean (standard practice for noisy simulators).

CLI::

    python -m peloton.analysis.sensitivity morris --workers 7
    python -m peloton.analysis.sensitivity sobol  --workers 7
    python -m peloton.analysis.sensitivity dt
"""

from __future__ import annotations

import argparse
import json
import os

import numpy as np

from peloton.analysis.batch import run_many

QOIS = ["mean_speed_kmh", "finish_spread_s", "drafted_share"]

#: behavioural/physical factors and their ranges (v0.6 model). The W'/sprint
#: knobs of v0.5 are gone; the live physics is now the trait spread (v_max
#: mean/spread, stamina), the exponential drain constant, drafting geometry,
#: and the aerobic engine. Each default sits strictly inside its range.
FACTORS: list[tuple[str, float, float]] = [
    ("draft_factor", 0.45, 0.80),     # slipstream strength (exposure when sheltered)
    ("v_max_hi", 17.0, 21.0),         # fastest team's mean max velocity
    ("v_max_lo", 14.0, 18.0),         # slowest team's mean max velocity
    ("v_max_sd", 0.2, 1.0),           # within-team max-velocity spread
    ("stamina_mean", 0.8, 1.2),       # field endurance level
    ("drain_c", 0.0002, 0.0005),      # battery drain per (m/s * s) at full wind
    ("aero_coeff", 16.0, 28.0),       # aero power scale (cost of speed)
    ("aer_power", 11.9, 22.1),        # sustainable aerobic power at stamina=1
    ("draft_gap_m", 5.6, 10.4),       # longitudinal drafting reach
    ("sense_radius_m", 14.0, 26.0),   # perception radius
]

FITTED_JSON = os.path.join("figures", "03_calibration.json")


def _problem(factors=None) -> dict:
    factors = factors or FACTORS
    return {"num_vars": len(factors),
            "names": [f[0] for f in factors],
            "bounds": [[f[1], f[2]] for f in factors]}


def _strategy_params() -> dict:
    if os.path.exists(FITTED_JSON):
        with open(FITTED_JSON) as fh:
            return json.load(fh)["params"]
    return {}


def evaluate(X: np.ndarray, names: list[str], reps: int = 3,
             workers: int | None = None) -> dict[str, np.ndarray]:
    """Run the model at each sample row; return replicate-mean QoI arrays."""
    sp = _strategy_params()
    configs = []
    for row in X:
        overrides = dict(zip(names, (float(v) for v in row)))
        for rep in range(reps):
            configs.append(dict(n_riders=48, n_teams=8,
                                strategy="discrete_choice",
                                strategy_params=sp, params=overrides,
                                seed=rep))
    results = run_many(configs, workers=workers)
    out = {}
    for q in QOIS:
        vals = np.array([r[q] for r in results]).reshape(len(X), reps)
        out[q] = vals.mean(axis=1)
    return out


# -- Morris screening --------------------------------------------------------
def run_morris(r: int = 20, reps: int = 3, workers=None, out="figures"):
    from SALib.analyze import morris as morris_a
    from SALib.sample import morris as morris_s

    problem = _problem()
    X = morris_s.sample(problem, N=r, seed=1)
    print(f"[sensitivity] Morris: {len(X)} points x {reps} reps "
          f"= {len(X) * reps} races")
    Y = evaluate(X, problem["names"], reps=reps, workers=workers)

    results = {}
    for q in QOIS:
        si = morris_a.analyze(problem, X, Y[q], seed=1)
        results[q] = {"mu_star": list(map(float, si["mu_star"])),
                      "sigma": list(map(float, si["sigma"])),
                      "names": list(si["names"])}
    with open(os.path.join(out, "07_sensitivity_morris.json"), "w") as fh:
        json.dump(results, fh, indent=2)
    _plot_morris(results, os.path.join(out, "07_sensitivity_morris.png"))
    return results


def _plot_morris(results: dict, path: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, len(QOIS), figsize=(4.6 * len(QOIS), 4.6))
    for ax, q in zip(axes, QOIS):
        res = results[q]
        order = np.argsort(res["mu_star"])[::-1]
        names = [res["names"][i] for i in order]
        mu = [res["mu_star"][i] for i in order]
        sg = [res["sigma"][i] for i in order]
        y = np.arange(len(names))[::-1]
        ax.barh(y, mu, color="#1f77b4", label="μ* (influence)")
        ax.barh(y, sg, height=0.35, color="#d62728", alpha=0.8,
                label="σ (interaction/nonlin.)")
        ax.set_yticks(y)
        ax.set_yticklabels(names, fontsize=8)
        ax.set_title(q, fontsize=10)
    axes[0].legend(fontsize=8)
    fig.suptitle("Morris screening — which physics drives the emergent "
                 "behaviour (v0.6 binary discrete_choice)", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(path, dpi=110)
    plt.close(fig)
    print(f"[sensitivity] wrote {path}")


def top_factors(morris_results: dict, k: int = 6) -> list[str]:
    """Factors ranked by max μ* across QoIs (normalised per QoI)."""
    score: dict[str, float] = {}
    for q in QOIS:
        res = morris_results[q]
        mx = max(res["mu_star"]) or 1.0
        for name, mu in zip(res["names"], res["mu_star"]):
            score[name] = max(score.get(name, 0.0), mu / mx)
    return sorted(score, key=score.get, reverse=True)[:k]


# -- Sobol indices ------------------------------------------------------------
def _matrix_to_nested(m: np.ndarray) -> list[list[float | None]]:
    """JSON-safe nested list; SALib leaves NaN off the S2 upper triangle."""
    return [[None if not np.isfinite(v) else float(v) for v in row]
            for row in np.asarray(m)]


def run_sobol(n: int = 128, reps: int = 3, workers=None, out="figures",
              factors: list[str] | None = None,
              second_order: bool = True):
    """Sobol variance decomposition: first order (S1), second order (S2),
    and total order (ST).

    ``S1`` is the variance share each factor explains on its own; ``ST``
    additionally folds in every interaction the factor takes part in, so the
    ``ST − S1`` gap is its total interaction load. ``S2[i, j]`` isolates the
    *pairwise* interaction between factors i and j — i.e. which specific pairs
    create the ST−S1 gap. Computing S2 needs the larger Saltelli design
    (``N·(2D+2)`` rows instead of ``N·(D+2)``); pass ``second_order=False``
    to fall back to the cheaper S1/ST-only run.
    """
    from SALib.analyze import sobol as sobol_a
    from SALib.sample import sobol as sobol_s

    if factors is None:
        with open(os.path.join(out, "07_sensitivity_morris.json")) as fh:
            factors = top_factors(json.load(fh))
    sel = [f for f in FACTORS if f[0] in factors]
    problem = _problem(sel)
    X = sobol_s.sample(problem, n, calc_second_order=second_order, seed=1)
    print(f"[sensitivity] Sobol on {problem['names']}: {len(X)} points "
          f"x {reps} reps = {len(X) * reps} races "
          f"(second_order={second_order})")
    Y = evaluate(X, problem["names"], reps=reps, workers=workers)

    results = {}
    for q in QOIS:
        si = sobol_a.analyze(problem, Y[q], calc_second_order=second_order,
                             seed=1)
        results[q] = {"S1": list(map(float, si["S1"])),
                      "ST": list(map(float, si["ST"])),
                      "S1_conf": list(map(float, si["S1_conf"])),
                      "ST_conf": list(map(float, si["ST_conf"])),
                      "names": problem["names"]}
        if second_order:
            results[q]["S2"] = _matrix_to_nested(si["S2"])
            results[q]["S2_conf"] = _matrix_to_nested(si["S2_conf"])
    with open(os.path.join(out, "08_sensitivity_sobol.json"), "w") as fh:
        json.dump(results, fh, indent=2)
    _plot_sobol(results, os.path.join(out, "08_sensitivity_sobol.png"))
    if second_order:
        _plot_sobol_s2(results,
                       os.path.join(out, "08b_sensitivity_sobol_s2.png"))
    return results


def _plot_sobol(results: dict, path: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, len(QOIS), figsize=(4.6 * len(QOIS), 4.4))
    for ax, q in zip(axes, QOIS):
        res = results[q]
        x = np.arange(len(res["names"]))
        ax.bar(x - 0.2, res["S1"], width=0.4, yerr=res["S1_conf"],
               capsize=2, color="#1f77b4", label="S1 (first order)")
        ax.bar(x + 0.2, res["ST"], width=0.4, yerr=res["ST_conf"],
               capsize=2, color="#d62728", label="ST (total)")
        ax.set_xticks(x)
        ax.set_xticklabels(res["names"], rotation=45, ha="right", fontsize=8)
        ax.set_title(q, fontsize=10)
        ax.axhline(0, color="0.6", lw=0.8)
    axes[0].legend(fontsize=8)
    fig.suptitle("Sobol variance decomposition (top Morris factors; "
                 "ST−S1 gap = interactions)", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(path, dpi=110)
    plt.close(fig)
    print(f"[sensitivity] wrote {path}")


def _plot_sobol_s2(results: dict, path: str):
    """Second-order indices as a symmetric pairwise-interaction heatmap."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, len(QOIS), figsize=(4.9 * len(QOIS), 4.6))
    # shared symmetric colour scale across QoIs for comparability
    vmax = 0.0
    for q in QOIS:
        for row in results[q]["S2"]:
            for v in row:
                if v is not None:
                    vmax = max(vmax, abs(v))
    vmax = vmax or 1.0

    last_im = None
    for ax, q in zip(axes, QOIS):
        res = results[q]
        names = res["names"]
        d = len(names)
        # symmetrise the upper-triangular S2 (None -> NaN, diagonal blank)
        m = np.full((d, d), np.nan)
        for i in range(d):
            for j in range(d):
                v = res["S2"][i][j]
                if v is not None:
                    m[i, j] = v
                    m[j, i] = v
        last_im = ax.imshow(m, cmap="coolwarm", vmin=-vmax, vmax=vmax)
        ax.set_xticks(range(d))
        ax.set_yticks(range(d))
        ax.set_xticklabels(names, rotation=45, ha="right", fontsize=7)
        ax.set_yticklabels(names, fontsize=7)
        ax.set_title(q, fontsize=10)
        for i in range(d):
            for j in range(d):
                if np.isfinite(m[i, j]):
                    ax.text(j, i, f"{m[i, j]:.2f}", ha="center",
                            va="center", fontsize=6, color="0.1")
    fig.colorbar(last_im, ax=axes, fraction=0.025, pad=0.02,
                 label="S2 (pairwise interaction)")
    fig.suptitle("Sobol second-order indices — which factor *pairs* "
                 "interact (v0.6 binary discrete_choice)", fontsize=12)
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    print(f"[sensitivity] wrote {path}")


# -- numerical robustness: timestep ------------------------------------------
def dt_sweep(dts=(0.25, 0.5, 1.0, 2.0), seeds=range(10), workers=None,
             out="figures"):
    from peloton.analysis.stats import mean_ci
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sp = _strategy_params()
    configs = [dict(n_riders=48, n_teams=8, strategy="discrete_choice",
                    strategy_params=sp, params={"dt": float(dt)},
                    seed=int(s))
               for dt in dts for s in seeds]
    results = run_many(configs, workers=workers)
    n_seeds = len(list(seeds))

    fig, axes = plt.subplots(1, len(QOIS), figsize=(4.4 * len(QOIS), 4))
    for ax, q in zip(axes, QOIS):
        means, halves = [], []
        for i, dt in enumerate(dts):
            vals = [results[i * n_seeds + j][q] for j in range(n_seeds)]
            m, h = mean_ci(vals)
            means.append(m); halves.append(h)
        ax.errorbar(dts, means, yerr=halves, marker="o", capsize=3,
                    color="#2ca02c")
        ax.axvline(1.0, ls="--", color="0.6", lw=1)
        ax.set_xscale("log")
        ax.set_xlabel("dt (s)   [default 1.0]")
        ax.set_title(q, fontsize=10)
    fig.suptitle("Numerical robustness: QoIs vs integration timestep "
                 "(claim: insensitive near the default)", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    path = os.path.join(out, "09_dt_robustness.png")
    fig.savefig(path, dpi=110)
    plt.close(fig)
    print(f"[sensitivity] wrote {path}")


def main():
    ap = argparse.ArgumentParser(description="Sensitivity analyses.")
    ap.add_argument("which", choices=["morris", "sobol", "dt", "all"])
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--morris-r", type=int, default=20)
    ap.add_argument("--sobol-n", type=int, default=128)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--no-second-order", action="store_true",
                    help="skip Sobol S2 (cheaper N·(D+2) design)")
    args = ap.parse_args()
    if args.which in ("morris", "all"):
        run_morris(r=args.morris_r, reps=args.reps, workers=args.workers)
    if args.which in ("sobol", "all"):
        run_sobol(n=args.sobol_n, reps=args.reps, workers=args.workers,
                  second_order=not args.no_second_order)
    if args.which in ("dt", "all"):
        dt_sweep(workers=args.workers)


if __name__ == "__main__":
    main()
