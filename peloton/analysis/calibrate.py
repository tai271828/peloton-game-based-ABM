"""Fit the discrete-choice game theory to observed competition data.

This is the v0.4 "interpret real-world data" pipeline:

    data/stylized_facts.csv  --->  grid search + local refinement  --->
    fitted (w_cost, w_shelter, w_position, λ)  --->  English interpretation

The objective is weighted relative squared error between simulated and target
observables, averaged over seeds::

    L(θ) = Σ_k  weight_k · ((sim_k(θ) − target_k) / target_k)²

Because the parameters are *behavioural weights* in an interpretable utility
(see ``strategies/discrete_choice.py``), the fitted vector is not just a
curve-fit — it reads as a statement about how riders trade energy against
position against shelter, and how close to best-response (λ) they play.

CLI::

    python -m peloton.analysis.calibrate \
        --data data/stylized_facts.csv --out figures/calibration --seeds 3
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json

from peloton.model import RaceModel
from peloton.analysis.metrics import race_metrics

#: coarse first-pass grid over the behavioural weights.
DEFAULT_GRID = {
    "w_cost": [0.5, 1.0, 2.0],
    "w_shelter": [0.4, 0.8, 1.6],
    "w_position": [0.5, 1.0, 2.0],
    "lam": [2.0, 4.0, 8.0],
}
#: multiplicative neighbourhood for the local refinement pass.
REFINE_FACTORS = [0.7, 1.0, 1.4]


def load_targets(path: str) -> list[dict]:
    with open(path) as fh:
        rows = list(csv.DictReader(fh))
    return [{"observable": r["observable"], "target": float(r["target"]),
             "weight": float(r["weight"]), "source": r.get("source", "")}
            for r in rows]


def simulate_observables(strategy_params: dict, seeds, n_riders=48,
                         n_teams=8) -> dict:
    """Mean metric set for the discrete_choice game under given weights."""
    acc: dict[str, float] = {}
    n = 0
    for seed in seeds:
        m = RaceModel(n_riders=n_riders, n_teams=n_teams,
                      strategy="discrete_choice",
                      strategy_params=strategy_params,
                      seed=seed, collect=False)
        m.run()
        for k, v in race_metrics(m).items():
            acc[k] = acc.get(k, 0.0) + v
        n += 1
    return {k: v / n for k, v in acc.items()}


def objective(sim: dict, targets: list[dict]) -> float:
    loss = 0.0
    for t in targets:
        s = sim.get(t["observable"], float("nan"))
        loss += t["weight"] * ((s - t["target"]) / t["target"]) ** 2
    return loss


def _evaluate_many(combos, targets, seeds, log_every=None, tag=""):
    best, best_loss, best_sim, history = None, float("inf"), None, []
    for i, combo in enumerate(combos):
        sim = simulate_observables(combo, seeds)
        loss = objective(sim, targets)
        history.append({**combo, "loss": loss})
        if loss < best_loss:
            best, best_loss, best_sim = combo, loss, sim
        if log_every and (i + 1) % log_every == 0:
            print(f"[calibrate]{tag} {i + 1}/{len(combos)} "
                  f"best loss so far {best_loss:.4f}")
    return best, best_loss, best_sim, history


def fit(targets, seeds=range(3), grid=None) -> dict:
    """Coarse grid search, then one multiplicative refinement pass."""
    grid = grid or DEFAULT_GRID
    keys = list(grid)
    combos = [dict(zip(keys, vals))
              for vals in itertools.product(*(grid[k] for k in keys))]
    print(f"[calibrate] coarse grid: {len(combos)} candidates "
          f"x {len(list(seeds))} seeds")
    best, loss, sim, hist1 = _evaluate_many(combos, targets, seeds,
                                            log_every=20, tag=" coarse")

    refine = [dict(zip(keys, vals)) for vals in itertools.product(
        *([best[k] * f for f in REFINE_FACTORS] for k in keys))]
    refine = [c for c in refine if c != best]
    print(f"[calibrate] refining around {best}")
    best2, loss2, sim2, hist2 = _evaluate_many(refine, targets, seeds,
                                               log_every=30, tag=" refine")
    if loss2 < loss:
        best, loss, sim = best2, loss2, sim2

    return {"params": best, "loss": loss, "sim": sim,
            "history": hist1 + hist2}


def interpret(params: dict) -> list[str]:
    """Read the fitted weights back as statements about rider behaviour."""
    w_c, w_s, w_p, lam = (params["w_cost"], params["w_shelter"],
                          params["w_position"], params["lam"])
    lines = [
        f"energy vs position: riders weight energy expenditure "
        f"{w_c / w_p:.2f}x as heavily as positional gain "
        f"({'conservation-dominated' if w_c > w_p else 'position-dominated'} racing),",
        f"shelter: drafting carries {w_s:.2f} utility units — "
        f"{'a strong' if w_s >= w_p else 'a secondary'} motive next to "
        f"positioning ({w_p:.2f}),",
        f"rationality: lambda = {lam:.1f} — "
        + ("close to uniform random play."
           if lam < 1 else
           "noisy but clearly directed choices (quantal response), well short "
           "of strict best response." if lam < 10 else
           "near best-response play."),
    ]
    return lines


def figure(result: dict, targets: list[dict], default_sim: dict, path: str):
    """Bars: simulated-vs-target per observable, before vs after fitting."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    obs = [t["observable"] for t in targets]
    tgt = np.array([t["target"] for t in targets])
    pre = np.array([default_sim.get(o, np.nan) for o in obs])
    post = np.array([result["sim"].get(o, np.nan) for o in obs])

    fig, axes = plt.subplots(1, len(obs), figsize=(3.1 * len(obs), 4.2))
    for ax, o, t, b, a in zip(axes, obs, tgt, pre, post):
        ax.bar([0, 1, 2], [t, b, a],
               color=["0.35", "#9ecae1", "#d62728"], width=0.65)
        for x, v in enumerate([t, b, a]):
            ax.text(x, v, f"{v:.2f}", ha="center", va="bottom", fontsize=8)
        ax.set_xticks([0, 1, 2])
        ax.set_xticklabels(["target\n(data)", "default\nweights",
                            "fitted\nweights"], fontsize=8)
        ax.set_title(o.replace("_", "\n"), fontsize=9)
    p = result["params"]
    holdout = result.get("loss_holdout")
    fig.suptitle(
        "Calibrating the discrete-choice game to race data — "
        f"fitted: w_cost={p['w_cost']:.2f}, w_shelter={p['w_shelter']:.2f}, "
        f"w_position={p['w_position']:.2f}, λ={p['lam']:.1f} "
        f"(fit loss {result['loss']:.3f}"
        + (f", holdout loss {holdout:.3f})" if holdout is not None else ")"),
        fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    fig.savefig(path, dpi=110)
    plt.close(fig)


#: offset separating fitting seeds from holdout seeds.
HOLDOUT_OFFSET = 1000


def holdout_eval(params: dict, targets, n_seeds: int) -> tuple[float, dict]:
    """Re-evaluate fitted params on fresh seeds (winner's-curse control).

    Selecting parameters on the same stochastic draws used to score them
    biases the reported loss downward. The number to quote is this one.
    """
    seeds = range(HOLDOUT_OFFSET, HOLDOUT_OFFSET + n_seeds)
    sim = simulate_observables(params, seeds)
    return objective(sim, targets), sim


def main():
    ap = argparse.ArgumentParser(
        description="Fit discrete_choice weights to observed race data.")
    ap.add_argument("--data", default="data/stylized_facts.csv")
    ap.add_argument("--out", default="figures/calibration",
                    help="basename for .png figure and .json fit result")
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--reeval", metavar="FIT_JSON", default=None,
                    help="skip fitting; holdout-evaluate an existing fit")
    args = ap.parse_args()

    targets = load_targets(args.data)
    seeds = range(args.seeds)

    if args.reeval:
        with open(args.reeval) as fh:
            stored = json.load(fh)
        loss_h, sim_h = holdout_eval(stored["params"], targets, args.seeds)
        print(f"[calibrate] {args.reeval}: fit loss {stored['loss']:.4f}  "
              f"holdout loss {loss_h:.4f}")
        stored["loss_holdout"] = loss_h
        stored["sim_holdout"] = sim_h
        with open(args.reeval, "w") as fh:
            json.dump(stored, fh, indent=2)
        return

    default_sim = simulate_observables({}, seeds)
    print(f"[calibrate] default-weight loss: "
          f"{objective(default_sim, targets):.4f}")

    result = fit(targets, seeds=seeds)
    print(f"[calibrate] fitted {result['params']}  "
          f"fit loss {result['loss']:.4f}")
    loss_h, sim_h = holdout_eval(result["params"], targets, args.seeds)
    result["loss_holdout"], result["sim_holdout"] = loss_h, sim_h
    print(f"[calibrate] holdout loss {loss_h:.4f}  <- quote this one")
    for line in interpret(result["params"]):
        print("  ->", line)

    with open(args.out + ".json", "w") as fh:
        json.dump({k: result[k] for k in
                   ("params", "loss", "loss_holdout", "sim", "sim_holdout")},
                  fh, indent=2)
    figure(result, targets, default_sim, args.out + ".png")
    print(f"[calibrate] wrote {args.out}.png and {args.out}.json")


if __name__ == "__main__":
    main()
