"""v0.4 experiment figures.

    01_compare_all.png       side-by-side dashboard, all registered games
                             (also produced by: python -m peloton.analysis.compare)
    02_choice_explainer.png  how the discrete-choice utility turns state into
                             action probabilities (the educational picture)
    03_calibration.png       fit to data (produced by: python -m peloton.analysis.calibrate)
    04_rationality_sweep.png lambda from random play to best response — the
                             quantal-response bridge, in emergent observables

Run everything:  python experiments.py
"""

from __future__ import annotations

import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from peloton import RaceModel
from peloton.agent import Neighbor, Perception, SelfView
from peloton.analysis.compare import compare, dashboard, to_markdown
from peloton.analysis.metrics import race_metrics
from peloton.strategies import available, make_strategy

FIG = "figures"
FITTED_JSON = os.path.join(FIG, "03_calibration.json")


def fitted_params() -> dict:
    """Fitted discrete-choice weights if calibration has run, else defaults."""
    if os.path.exists(FITTED_JSON):
        with open(FITTED_JSON) as fh:
            return json.load(fh)["params"]
    return {}


# --------------------------------------------------------------------------
# 01 — the comparison dashboard (the goal-1 deliverable)
# --------------------------------------------------------------------------
def fig_compare(seeds=range(20)):
    df = compare(available(), seeds=seeds)
    dashboard(df, os.path.join(FIG, "01_compare_all.png"))
    to_markdown(df, os.path.join(FIG, "01_compare_all.md"))
    from peloton.analysis.stats import paired_markdown
    from peloton.analysis.metrics import DASHBOARD_METRICS
    paired_markdown(df, [k for k, _ in DASHBOARD_METRICS],
                    os.path.join(FIG, "01_compare_all_paired.md"))
    print("[experiments] wrote 01_compare_all.png/.md + paired contrasts")


# --------------------------------------------------------------------------
# 02 — what the discrete-choice black box actually computes
# --------------------------------------------------------------------------
def _fake_state(energy_frac, progress, wheel=True, drafting=False):
    view = SelfView(skill=1.0, energy=2200 * energy_frac, energy_max=2200,
                    speed=13.0, team=0, is_drafting=drafting,
                    progress=progress, is_captain=False)
    nb = (Neighbor(gap=4.0, lane=0.0, speed=13.0, team=1, is_captain=False),)
    perc = Perception(ahead=nb if wheel else (), behind=(),
                      pack_speed=13.0, dist_to_finish=(1 - progress) * 3900,
                      in_sprint_zone=(1 - progress) * 3900 <= 250)
    return view, perc


def fig_choice_explainer():
    strat = make_strategy("discrete_choice", fitted_params())
    strat.reset(None)              # probabilities only; no sampling rng needed
    from peloton.strategies.discrete_choice import _ACTIONS

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    cmap = plt.get_cmap("viridis")

    # (a) probabilities vs race progress, healthy battery, wheel available.
    xs = np.linspace(0, 1, 200)
    probs = np.array([strat.probabilities(*_fake_state(0.8, x)) for x in xs])
    axes[0].stackplot(xs, probs.T, labels=[a.value for a in _ACTIONS],
                      colors=[cmap(i / 4) for i in range(5)], alpha=0.9)
    axes[0].set_xlabel("race progress (energy 80%)")
    axes[0].set_title("(a) early race: sit in — finale: positional fight\n"
                      "no sprint rule is hard-coded; it falls out of the utility")

    # (b) probabilities vs remaining energy, early in the race (progress 0.15).
    # Early is where the energy/position trade-off is alive; by mid-race the
    # fitted positional urgency dominates the choice regardless of battery.
    es = np.linspace(0, 1, 200)
    probs = np.array([strat.probabilities(*_fake_state(e, 0.15)) for e in es])
    axes[1].stackplot(es, probs.T, labels=[a.value for a in _ACTIONS],
                      colors=[cmap(i / 4) for i in range(5)], alpha=0.9)
    axes[1].set_xlabel("energy fraction remaining (early race, progress 0.15)")
    axes[1].set_title("(b) early on, the emptier the battery,\n"
                      "the stronger the pull of the draft")

    for ax in axes:
        ax.set_ylabel("choice probability")
        ax.set_ylim(0, 1)
        ax.set_xlim(0, 1)
    axes[1].legend(loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=8)
    p = {**{"w_cost": 1.0, "w_shelter": 0.8, "w_position": 1.0, "lam": 4.0},
         **fitted_params()}
    fig.suptitle("Inside the discrete-choice black box: P(action) = softmax(λ·u) — "
                 f"w_cost={p['w_cost']:.2f}, w_shelter={p['w_shelter']:.2f}, "
                 f"w_position={p['w_position']:.2f}, λ={p['lam']:.1f}",
                 fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(os.path.join(FIG, "02_choice_explainer.png"), dpi=110)
    plt.close(fig)
    print("[experiments] wrote 02_choice_explainer.png")


# --------------------------------------------------------------------------
# 04 — rationality sweep: random play -> best response
# --------------------------------------------------------------------------
def fig_rationality_sweep(lams=(0.0, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0),
                          seeds=range(6)):
    base = fitted_params()
    series = {"mean_speed_kmh": [], "drafted_share": [], "share_speed_up": []}
    spread = {k: [] for k in series}
    for lam in lams:
        vals = {k: [] for k in series}
        for s in seeds:
            m = RaceModel(n_riders=48, n_teams=8, strategy="discrete_choice",
                          strategy_params={**base, "lam": lam},
                          seed=s, collect=False)
            m.run()
            mt = race_metrics(m)
            for k in series:
                vals[k].append(mt[k])
        for k in series:
            series[k].append(np.mean(vals[k]))
            spread[k].append(np.std(vals[k]))

    labels = {"mean_speed_kmh": "mean field speed (km/h)",
              "drafted_share": "time sheltered (share)",
              "share_speed_up": "SPEED_UP share of decisions"}
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.2))
    x = np.array(lams)
    for ax, k in zip(axes, series):
        ax.errorbar(x, series[k], yerr=spread[k], marker="o", capsize=3,
                    color="#d62728")
        ax.set_xscale("symlog", linthresh=0.5)
        ax.set_xlabel("rationality λ  (0 = random play)")
        ax.set_title(labels[k], fontsize=10)
        ax.axvline(0, color="0.8", lw=1, ls="--")
    fig.suptitle("Quantal response bridges the null model and best response: "
                 "emergent behaviour vs rationality λ", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(os.path.join(FIG, "04_rationality_sweep.png"), dpi=110)
    plt.close(fig)
    print("[experiments] wrote 04_rationality_sweep.png")


# --------------------------------------------------------------------------
# 05 — empirical equilibrium via unilateral deviation (v0.5)
# --------------------------------------------------------------------------
DEV_CACHE = os.path.join(FIG, "05_deviation_cache.json")


def compute_deviation(seeds=range(30), workers=None):
    """Run the (long) deviation grids once and cache the raw payoffs."""
    from peloton.analysis.deviation import deviation_payoffs
    fields = [round(0.1 * k, 1) for k in range(1, 10)]
    pg = deviation_payoffs("public_goods", "p_coop", fields,
                           [round(0.1 * k, 1) for k in range(11)],
                           seeds, workers=workers)
    hd = deviation_payoffs("hawk_dove", "base_hawk", fields,
                           fields, seeds, workers=workers)
    with open(DEV_CACHE, "w") as fh:
        json.dump({"public_goods": {str(f): {str(d): v for d, v in by.items()}
                                    for f, by in pg.items()},
                   "hawk_dove": {str(f): {str(d): v for d, v in by.items()}
                                 for f, by in hd.items()}}, fh)
    print("[experiments] deviation grids cached")


def _load_dev():
    with open(DEV_CACHE) as fh:
        raw = json.load(fh)
    return {g: {float(f): {float(d): v for d, v in by.items()}
                for f, by in grid.items()} for g, grid in raw.items()}


def fig_deviation_equilibrium():
    from peloton.analysis.stats import mean_ci
    if not os.path.exists(DEV_CACHE):
        compute_deviation()
    data = _load_dev()

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.4))
    cmap = plt.get_cmap("plasma")

    # (a) public-goods deviation payoff curves for a few field values.
    pg = data["public_goods"]
    show = [0.1, 0.3, 0.5, 0.8]
    for fv in show:
        devs = sorted(pg[fv])
        m, h = zip(*(mean_ci(pg[fv][d]) for d in devs))
        axes[0].errorbar(devs, m, yerr=h, marker="o", ms=3, capsize=2,
                         color=cmap(fv), label=f"field q={fv}")
    axes[0].set_xlabel("focal rider's $p_{coop}$ (deviation)")
    axes[0].set_ylabel("focal finish (0=win, lower=better)")
    axes[0].legend(fontsize=8)
    axes[0].set_title("(a) public goods: deviation payoffs are U-shaped\n"
                      "a little pulling beats pure free-riding (position!)")

    # (b)/(c): best response vs the diagonal -> empirical equilibrium.
    for ax, game, param in ((axes[1], "public_goods", "p_coop"),
                            (axes[2], "hawk_dove", "base_hawk")):
        grid = data[game]
        fields = sorted(grid)
        brs = [min(grid[f], key=lambda d: sum(grid[f][d]) / len(grid[f][d]))
               for f in fields]
        ax.plot(fields, brs, "o-", color="#d62728", label="best response")
        ax.plot([0, 1], [0, 1], "--", color="0.6", label="diagonal (BR = field)")
        eq = min(zip(fields, brs), key=lambda t: abs(t[1] - t[0]))
        ax.axvline(eq[0], color="0.4", lw=1, ls=":")
        ax.annotate(f"empirical eq \u2248 {eq[0]:.1f}", (eq[0], eq[1]),
                    xytext=(eq[0] + 0.05, max(0.05, eq[1] - 0.18)),
                    fontsize=9, arrowprops=dict(arrowstyle="->"))
        ax.set_xlabel(f"field {param}")
        ax.set_ylabel(f"best-response {param}")
        ax.set_xlim(0, 1); ax.set_ylim(0, 1)
        ax.legend(fontsize=8)
        ax.set_title(f"({'b' if game == 'public_goods' else 'c'}) {game}: "
                     "best response vs diagonal")

    fig.suptitle("Measured, not asserted: unilateral-deviation payoffs locate "
                 "the equilibria (48 riders, 30 paired seeds)", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(os.path.join(FIG, "05_deviation_equilibrium.png"), dpi=110)
    plt.close(fig)
    print("[experiments] wrote 05_deviation_equilibrium.png")


# --------------------------------------------------------------------------
# 06 — evolutionary dynamics + stability cross-check (v0.5)
# --------------------------------------------------------------------------
EVO_CACHE = os.path.join(FIG, "06_evolution_cache.json")


def compute_evolution(n_runs=5, generations=60, workers=None):
    from peloton.analysis.evolution import evolve_many
    runs = evolve_many(n_runs=n_runs, generations=generations,
                       workers=workers)
    with open(EVO_CACHE, "w") as fh:
        json.dump(runs, fh)
    print("[experiments] evolution runs cached")


def fig_evolution():
    from peloton.analysis.stats import mean_ci
    if not os.path.exists(EVO_CACHE):
        compute_evolution()
    with open(EVO_CACHE) as fh:
        runs = json.load(fh)

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4))

    # (a) trajectories of the population-mean p_coop.
    last_means = []
    for r in runs:
        axes[0].plot(r["mean"], alpha=0.7, lw=1.4)
        last_means.append(np.mean(r["mean"][-10:]))
    p_hat = float(np.mean(last_means))
    axes[0].axhline(p_hat, color="0.3", ls="--", lw=1,
                    label=f"evolved mean $\\hat{{p}}$ = {p_hat:.2f}")
    axes[0].set_xlabel("generation (1 race each, top half reproduces)")
    axes[0].set_ylabel("population mean $p_{coop}$")
    axes[0].set_ylim(0, 1)
    axes[0].legend(fontsize=9)
    axes[0].set_title(f"(a) {len(runs)} independent evolutionary runs\n"
                      "cooperation settles at an interior level")

    # (b) stability cross-check against the deviation harness: the evolved
    # mean should sit where unilateral deviations stop paying.
    if os.path.exists(DEV_CACHE):
        pg = _load_dev()["public_goods"]
        fields = sorted(pg)
        nearest = min(fields, key=lambda f: abs(f - p_hat))
        devs = sorted(pg[nearest])
        m, h = zip(*(mean_ci(pg[nearest][d]) for d in devs))
        axes[1].errorbar(devs, m, yerr=h, marker="o", ms=3, capsize=2,
                         color="#d62728")
        axes[1].axvline(p_hat, color="0.3", ls="--", lw=1,
                        label=f"evolved $\\hat{{p}}$ = {p_hat:.2f}")
        best = devs[int(np.argmin(m))]
        axes[1].axvline(best, color="#1f77b4", ls=":", lw=1.4,
                        label=f"best deviation = {best:.1f}")
        axes[1].set_xlabel(f"focal rider $p_{{coop}}$ (field at q={nearest})")
        axes[1].set_ylabel("focal finish (0=win, lower=better)")
        axes[1].legend(fontsize=9)
        axes[1].set_title("(b) stability check: deviation payoffs\n"
                          "around the evolved level")
    fig.suptitle("Evolutionary dynamics rediscover the interior equilibrium "
                 "(selection on finish rank, mutation sd 0.05)", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    fig.savefig(os.path.join(FIG, "06_evolution.png"), dpi=110)
    plt.close(fig)
    print("[experiments] wrote 06_evolution.png")


# --------------------------------------------------------------------------
# validation battery — pattern-oriented checks, all on v0.5 physics
# --------------------------------------------------------------------------
def compute_battery(out=os.path.join(FIG, "validation_battery.json")):
    """Re-run every qualitative pattern claim on the current model."""
    import scipy.stats as sps
    from peloton import Role
    res = {}

    # P1 free-riding pays: corr(p_coop, normalised rank) > 0.
    pc, rk = [], []
    for s in range(12):
        m = RaceModel(n_riders=50, strategy="public_goods", seed=s,
                      collect=False); m.run()
        n = len(m.agents)
        for a in m.agents:
            pc.append(a.strategy.p_coop); rk.append(a.finish_rank / (n - 1))
    r, p = sps.pearsonr(pc, rk)
    res["P1_freeriding_pays"] = {"corr": r, "p": p, "passes": bool(r > 0 and p < 0.01)}

    # P2 tragedy: all-defect field slower than q=0.3 field.
    def wt(q, seeds=range(8)):
        ts = []
        for s in seeds:
            m = RaceModel(n_riders=40, n_teams=4, strategy="public_goods",
                          strategy_params={"p_coop": q}, seed=s,
                          collect=False); m.run()
            ts.append(min(a.finish_time for a in m.agents))
        return ts
    t0, t3 = wt(0.0), wt(0.3)
    w = sps.wilcoxon([a - b for a, b in zip(t0, t3)])
    res["P2_tragedy"] = {"t_q0": float(np.mean(t0)), "t_q03": float(np.mean(t3)),
                         "wilcoxon_p": float(w.pvalue),
                         "passes": bool(np.mean(t0) > np.mean(t3) and w.pvalue < 0.05)}

    # P3+P4 calibrated discrete_choice: winner more sheltered than field; pull share low.
    df = compare(["discrete_choice"], seeds=range(20),
                 strategy_params=fitted_params())
    res["P3_winner_sheltered"] = {
        "winner_drafted": float(df["winner_drafted_share"].mean()),
        "field_drafted": float(df["drafted_share"].mean()),
        "passes": bool(df["winner_drafted_share"].mean()
                       > df["drafted_share"].mean())}
    res["P4_low_pull_share"] = {"share_pull": float(df["share_pull"].mean()),
                                "passes": bool(df["share_pull"].mean() < 0.10)}

    # P5 organised teams beat disorganised (mixed field captains).
    lo, sf = [], []
    for s in range(24):
        names = ["lead_out" if (i % 8) % 2 == 0 else "public_goods"
                 for i in range(48)]
        m = RaceModel(n_riders=48, n_teams=8, strategy_names=names, seed=s,
                      collect=False); m.run()
        n = len(m.agents)
        for a in m.agents:
            if a.role is Role.CAPTAIN:
                (lo if a.strategy_name == "lead_out" else sf).append(
                    a.finish_rank / (n - 1))
    res["P5_organised_wins"] = {"leadout_captain": float(np.mean(lo)),
                                "selfish_captain": float(np.mean(sf)),
                                "passes": bool(np.mean(lo) < np.mean(sf))}

    # P6 pace spikes in the finale (full collection, calibrated game).
    m = RaceModel(n_riders=48, n_teams=8, strategy="discrete_choice",
                  strategy_params=fitted_params(), seed=7, collect=True)
    m.run()
    mdf = m.datacollector.get_model_vars_dataframe()
    spd = mdf["mean_speed"]
    res["P6_finale_spike"] = {
        "last10pct_kmh": float(spd.iloc[-max(1, len(spd) // 10):].mean() * 3.6),
        "overall_kmh": float(spd.mean() * 3.6),
        "passes": bool(spd.iloc[-max(1, len(spd) // 10):].mean() > spd.mean())}

    # P7 docking vs Hoenigman 2011: cooperating costs weak riders more.
    rows = []
    for s in range(20):
        m = RaceModel(n_riders=50, strategy="public_goods", seed=100 + s,
                      collect=False); m.run()
        n = len(m.agents)
        for a in m.agents:
            rows.append((a.skill, a.strategy.p_coop, a.finish_rank / (n - 1)))
    import pandas as pd
    d = pd.DataFrame(rows, columns=["skill", "pc", "rank"])
    lo_t, hi_t = d["skill"].quantile([1 / 3, 2 / 3])
    slope = {}
    for name, sub in (("weak", d[d.skill <= lo_t]), ("strong", d[d.skill >= hi_t])):
        slope[name] = float(np.polyfit(sub["pc"], sub["rank"], 1)[0])
    res["P7_skill_strategy_docking"] = {**slope,
                                        "passes": bool(slope["weak"] > slope["strong"])}

    with open(out, "w") as fh:
        json.dump(res, fh, indent=2)
    n_pass = sum(v["passes"] for v in res.values())
    print(f"[experiments] validation battery: {n_pass}/{len(res)} patterns pass "
          f"-> {out}")
    return res


def main():
    os.makedirs(FIG, exist_ok=True)
    fig_compare()
    fig_choice_explainer()
    fig_rationality_sweep()
    fig_deviation_equilibrium()
    fig_evolution()
    print("[experiments] done (03_calibration.* comes from "
          "`python -m peloton.analysis.calibrate`)")


if __name__ == "__main__":
    main()
