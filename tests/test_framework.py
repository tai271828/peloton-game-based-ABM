"""Fast end-to-end tests for the v0.4 framework contract.

Run:  python -m pytest tests/ -q     (from the project root)

Previous versions shipped with no automated tests; for a framework that
invites third-party strategy plugins, the contract (registry, determinism,
physics invariants, metric schema) needs to be executable.
"""

import math

import pytest

from peloton import RaceModel, StadiumTrack
from peloton.actions import Action
from peloton.analysis.calibrate import objective
from peloton.analysis.compare import compare, summarize
from peloton.analysis.metrics import race_metrics
from peloton.strategies import STRATEGIES, available, make_strategy
from peloton.strategies.base import BaseStrategy, register_strategy

#: small, fast race used by most tests (~60 steps).
FAST = dict(straight_m=150.0, bend_radius_m=40.0, n_laps=1)


def fast_model(**kw):
    kw.setdefault("n_riders", 12)
    kw.setdefault("n_teams", 3)
    kw.setdefault("params", FAST)
    kw.setdefault("collect", False)
    return RaceModel(**kw)


# -- track geometry ---------------------------------------------------------
def test_track_length_and_wrap():
    t = StadiumTrack(400.0, 80.0)
    assert math.isclose(t.length, 2 * 400 + 2 * math.pi * 80)
    x0, y0 = t.xy(0.0)
    x1, y1 = t.xy(t.length)            # full lap wraps to the start
    assert math.isclose(x0, x1, abs_tol=1e-9)
    assert math.isclose(y0, y1, abs_tol=1e-9)


def test_track_continuity():
    t = StadiumTrack(400.0, 80.0)
    prev = t.xy(0.0)
    for i in range(1, 400):
        cur = t.xy(t.length * i / 400)
        step = math.dist(prev, cur)
        assert step < t.length / 400 * 1.5   # no jumps at segment joins
        prev = cur


def test_track_straights_vs_bends():
    t = StadiumTrack(400.0, 80.0)
    assert t.on_straight(200.0)            # mid bottom straight
    assert not t.on_straight(400.0 + 10.0)  # in the right bend


# -- registry / plugin contract --------------------------------------------
def test_builtin_strategies_discovered():
    assert {"public_goods", "hawk_dove", "lead_out",
            "discrete_choice", "random"} <= set(available())


def test_plugin_registration_is_one_decorator():
    @register_strategy("test_only_keep")
    class KeepStrategy(BaseStrategy):
        def decide(self, view, perc):
            return Action.KEEP

    try:
        assert "test_only_keep" in available()
        m = fast_model(strategy="test_only_keep", seed=1)
        m.run()
        assert m.n_finished == 12
    finally:
        del STRATEGIES["test_only_keep"]   # keep the registry clean


def test_duplicate_name_rejected():
    with pytest.raises(ValueError):
        @register_strategy("public_goods")
        class Impostor(BaseStrategy):
            pass


def test_unknown_strategy_message():
    with pytest.raises(KeyError):
        make_strategy("no_such_game")


# -- model invariants --------------------------------------------------------
@pytest.mark.parametrize("name", sorted(
    {"public_goods", "hawk_dove", "lead_out", "discrete_choice", "random"}))
def test_every_game_finishes_with_unique_ranks(name):
    m = fast_model(strategy=name, seed=4)
    m.run()
    ranks = sorted(a.finish_rank for a in m.agents)
    assert ranks == list(range(len(m.agents)))


def test_same_seed_same_result():
    r = []
    for _ in range(2):
        m = fast_model(strategy="hawk_dove", seed=11)
        m.run()
        r.append([a.finish_rank for a in
                  sorted(m.agents, key=lambda a: a.unique_id)])
    assert r[0] == r[1]


def test_battery_drain_rewards_drafting_and_stamina():
    """v0.6 stamina: drafting drains less than pulling, and higher stamina
    drains slower (the cooperation tension + the trait that ranks riders)."""
    m = fast_model(strategy="random", seed=1)
    rider = next(iter(m.agents))
    rider.stamina = 1.0

    def drain(sheltered, stamina):
        rider.stamina = stamina
        rider.energy = 1.0
        m._update_energy(rider, v=14.0, sheltered=sheltered)
        return 1.0 - rider.energy

    # drafting (sheltered) costs strictly less than pulling (full wind).
    assert 0 < drain(True, 1.0) < drain(False, 1.0)
    # higher stamina drains less for the same effort.
    assert drain(False, 1.4) < drain(False, 0.8)
    # battery never leaves [0, 1].
    rider.energy = 0.0
    m._update_energy(rider, v=20.0, sheltered=False)
    assert rider.energy == 0.0


def test_counters_track_steps():
    m = fast_model(strategy="public_goods", seed=2)
    m.run()
    for a in m.agents:
        assert a.n_steps > 0
        assert sum(a.action_counts.values()) == a.n_steps
        assert 0 <= a.n_sheltered <= a.n_steps


# -- analysis ---------------------------------------------------------------
def test_metrics_schema_and_shares():
    m = fast_model(strategy="discrete_choice", seed=3)
    m.run()
    mt = race_metrics(m)
    assert mt["finish_rate"] == 1.0
    shares = sum(v for k, v in mt.items() if k.startswith("share_"))
    assert math.isclose(shares, 1.0, abs_tol=1e-9)
    assert mt["winner_time_s"] > 0


def test_compare_runs_per_seed_and_strategy():
    df = compare(["random", "public_goods"], n_riders=12, n_teams=3,
                 seeds=range(2), params=FAST)
    assert len(df) == 4
    assert set(summarize(df).index) == {"random", "public_goods"}


def test_calibration_objective_orders_fits():
    targets = [{"observable": "x", "target": 10.0, "weight": 1.0}]
    assert objective({"x": 10.0}, targets) == 0.0
    assert objective({"x": 12.0}, targets) < objective({"x": 15.0}, targets)


# -- v0.5 additions -----------------------------------------------------------
def test_per_rider_strategy_params():
    sp = [{"p_coop": 1.0 if i == 0 else 0.0} for i in range(12)]
    m = fast_model(strategy="public_goods", strategy_params=sp, seed=3)
    riders = sorted(m.agents, key=lambda a: a.unique_id)
    assert riders[0].strategy.p_coop == 1.0
    assert all(r.strategy.p_coop == 0.0 for r in riders[1:])
    with pytest.raises(ValueError):
        fast_model(strategy="public_goods", strategy_params=[{}], seed=3)


def test_batch_runner_orders_and_matches_serial():
    from peloton.analysis.batch import run_many
    cfgs = [dict(n_riders=12, n_teams=3, params=FAST,
                 strategy="public_goods", seed=s) for s in (0, 1)]
    serial = run_many(cfgs, workers=1)
    parallel = run_many(cfgs * 2, workers=2)
    assert parallel[0] == serial[0] and parallel[1] == serial[1]
    assert parallel[2] == serial[0]      # order preserved


def test_deviation_focal_isolation():
    from peloton.analysis.deviation import _focal_rank, _skills
    job = dict(strategy="public_goods", param="p_coop", field_value=0.5,
               dev_value=0.0, seed=2, n_riders=12, n_teams=3)
    r1, r2 = _focal_rank(job), _focal_rank(job)
    assert r1 == r2                       # deterministic
    assert 0.0 <= r1 <= 1.0
    assert _skills(12, 2)[6] == 1.0       # focal rider pinned to skill 1.0


def test_evolution_step_clips_and_tracks():
    from peloton.analysis.evolution import evolve
    r = evolve(generations=3, n_riders=12, n_teams=3, seed=1)
    assert len(r["mean"]) == 3
    assert all(0.0 <= p <= 1.0 for p in r["final_pop"])


def test_paired_table_pairs_on_seed():
    import pandas as pd
    from peloton.analysis.stats import paired_table
    df = pd.DataFrame([
        {"strategy": "a", "seed": 0, "m": 1.0},
        {"strategy": "a", "seed": 1, "m": 2.0},
        {"strategy": "b", "seed": 0, "m": 0.5},
        {"strategy": "b", "seed": 1, "m": 1.5},
    ])
    t = paired_table(df, ["m"])
    assert len(t) == 1
    assert t.iloc[0]["n"] == 2
    assert abs(t.iloc[0]["mean_diff(A-B)"] - 0.5) < 1e-12


def test_sensitivity_factor_ranges_cover_defaults():
    from peloton.analysis.sensitivity import FACTORS
    from peloton.params import DEFAULT_PARAMS
    for name, lo, hi in FACTORS:
        assert lo < DEFAULT_PARAMS[name] < hi, name


def test_mesa_space_holds_track_positions():
    import math
    m = fast_model(strategy="public_goods", seed=5)
    assert all(a.pos is not None for a in m.agents)
    for _ in range(20):
        m.step()
    for a in m.agents:
        if not a.finished:
            assert math.dist(a.pos, m.track.xy(a.s, a.lane)) < 1e-9
    # space bounds contain every rider
    for a in m.agents:
        assert m.space.x_min <= a.pos[0] <= m.space.x_max
        assert m.space.y_min <= a.pos[1] <= m.space.y_max
