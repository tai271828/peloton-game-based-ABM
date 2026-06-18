"""The race model: a peloton on a stadium track, driven by plug-in strategies.

The per-step contract (``docs/specification.md`` §8) is:

    1. perceive   build SelfView + Perception for every active rider
    2. decide     action[i] = rider.strategy.decide(view, perc)   # the black box
    3. resolve    map actions -> target speed + wind exposure; resolve drafting
    4. dynamics   relax speed toward target; update energy; mark dropped
    5. move       advance s / lane; lap & finish bookkeeping; assign rank
    6. collect    snapshot for plots + animation

The model **never** branches on which strategy is in use — it only calls
``strategy.decide``. Adding a new game theory therefore requires no change here.
Physics (drafting, energy, sprint) is computed centrally so it is identical for
every game, which is exactly what makes the games comparable.
"""

from __future__ import annotations

from mesa import Model
from mesa.datacollection import DataCollector
from mesa.space import ContinuousSpace

from peloton.actions import Action
from peloton.agent import Cyclist, Neighbor, Perception, Role, SelfView
from peloton.params import DEFAULT_PARAMS, loop_length
from peloton.track import StadiumTrack
from peloton.strategies import make_strategy


class RaceModel(Model):
    """A single mass-start peloton race.

    Parameters
    ----------
    n_riders, n_teams : int
        Field size and number of teams.
    strategy : str
        Name of the game theory every rider uses (registry key). Switching this
        one string swaps the entire field's decision logic — nothing else.
    strategy_mix : dict[str, float] | None
        Optional ``{name: weight}`` to let several games share one race. Overrides
        ``strategy`` when given.
    strategy_params : dict | None
        Extra params forwarded to every strategy instance.
    params : dict | None
        Overrides for :data:`core.params.DEFAULT_PARAMS`.
    skills, strategy_names : sequence | None
        Optional explicit per-rider skill / strategy assignment (length n_riders).
    """

    def __init__(self, n_riders=60, n_teams=6, strategy="public_goods",
                 strategy_mix=None, strategy_params=None, params=None,
                 skills=None, strategy_names=None, seed=None, collect=True):
        super().__init__(rng=seed)
        self.params = {**DEFAULT_PARAMS, **(params or {})}
        p = self.params
        # strategy_params: one dict shared by all riders, OR (v0.5) a list of
        # n_riders dicts for per-rider parameters — needed for unilateral-
        # deviation (EGTA) experiments, evolutionary populations, and
        # heterogeneous (mixed-logit-style) fields.
        if isinstance(strategy_params, list):
            if len(strategy_params) != n_riders:
                raise ValueError(f"strategy_params list has "
                                 f"{len(strategy_params)} entries for "
                                 f"{n_riders} riders")
            self.strategy_params = strategy_params
        else:
            self.strategy_params = strategy_params or {}
        self.collect = collect       # False = skip per-step DataCollector snapshots
                                     # (fast mode for calibration sweeps; the cheap
                                     # per-agent counters below are always kept)

        self.track = StadiumTrack(p["straight_m"], p["bend_radius_m"])
        self.loop = loop_length(p)
        self.race_distance = p["n_laps"] * self.loop
        self.dt = p["dt"]
        self.clock = 0.0           # our race clock in seconds (Mesa owns self.time)
        self.n_finished = 0
        self._n_packs = 1
        self.lane_lo, self.lane_hi = self._lane_bounds()

        # Mesa space of record (v0.5 space refactor): rider positions live in
        # a ContinuousSpace holding the true (x, y) on the stadium track, so
        # Mesa tooling (SolaraViz space components, Euclidean queries) sees
        # them natively. The *physics* deliberately stays in arc-length
        # (s, lane): racing distance is along the track, and a Euclidean
        # neighbourhood would treat riders across the infield as "close".
        margin = 5.0
        L, R = p["straight_m"], p["bend_radius_m"]
        half_w = R + self.lane_hi + margin
        self.space = ContinuousSpace(
            x_min=-(R + self.lane_hi + margin),
            x_max=L + R + self.lane_hi + margin,
            y_min=-half_w, y_max=half_w, torus=False)

        rng = self.random
        names = self._resolve_strategy_names(
            n_riders, strategy, strategy_mix, strategy_names, rng)

        for i in range(n_riders):
            team = i % n_teams
            v_max_i, stamina_i = self._draw_traits(rng, team, n_teams)
            # `skills=` (used by EGTA/deviation to freeze & pin a focal rider)
            # now overrides the stamina trait, keeping that experiment valid.
            if skills is not None:
                stamina_i = skills[i]
            sp = (self.strategy_params[i]
                  if isinstance(self.strategy_params, list)
                  else self.strategy_params)
            strat = make_strategy(names[i], sp)
            strat.reset(rng)
            rider = Cyclist(self, v_max=v_max_i, stamina=stamina_i,
                            team=team, strategy=strat)
            rider.strategy_name = names[i]
            # grid start: a staggered block so packs/gaps exist immediately.
            rider.distance = (n_riders - 1 - i) * p["start_gap_m"]
            rider.s = rider.distance % self.loop
            rider.lane = self._grid_lane(i)
            self.space.place_agent(rider, self.track.xy(rider.s, rider.lane))

        self._assign_roles(n_teams)

        self.datacollector = DataCollector(
            model_reporters={
                "n_finished": lambda m: m.n_finished,
                "n_dropped": lambda m: int(sum(a.dropped for a in m.agents)),
                "n_packs": lambda m: m._n_packs,
                "lead_dist": lambda m: max(a.distance for a in m.agents),
                "spread_m": lambda m: (max(a.distance for a in m.agents)
                                       - min(a.distance for a in m.agents)),
                "mean_speed": lambda m: (sum(a.speed for a in m.agents)
                                         / len(m.agents)),
            },
            agent_reporters={
                "s": "s", "lane": "lane", "speed": "speed",
                "energy": "energy", "distance": "distance",
                "action": lambda a: a.action.value,
                "is_drafting": "is_drafting", "dropped": "dropped",
                "team": "team", "skill": "skill",
                "role": lambda a: a.role.value,
                "strategy": "strategy_name", "finish_rank": "finish_rank",
            },
        )
        if self.collect:
            self.datacollector.collect(self)

    # ------------------------------------------------------------------
    # setup helpers
    # ------------------------------------------------------------------
    def _draw_traits(self, rng, team: int, n_teams: int) -> tuple[float, float]:
        """Draw (v_max, stamina) for a rider on ``team``.

        Across teams the max-velocity *mean* is a high->low linear spread
        (team 0 strongest); within a team it is Normal(mu_t, v_max_sd).
        Stamina is an i.i.d. truncated-Normal endurance multiplier.
        """
        p = self.params
        if n_teams > 1:
            frac = team / (n_teams - 1)
        else:
            frac = 0.0
        mu_t = p["v_max_hi"] - (p["v_max_hi"] - p["v_max_lo"]) * frac
        v_max = max(p["v_max_floor"],
                    min(p["v_max_ceil"], rng.gauss(mu_t, p["v_max_sd"])))
        stamina = max(p["stamina_min"],
                      min(p["stamina_max"],
                          rng.gauss(p["stamina_mean"], p["stamina_sd"])))
        return v_max, stamina

    def _assign_roles(self, n_teams: int) -> None:
        """One captain per team — the rider best combining v_max and stamina.

        Captaincy goes to the highest within-team ``z(v_max) + z(stamina)``
        (standardised so the two traits, on different scales, weigh equally).
        """
        for t in range(n_teams):
            mates = [a for a in self.agents if a.team == t]
            if not mates:
                continue
            captain = max(mates, key=lambda a: self._captain_score(a, mates))
            captain.role = Role.CAPTAIN

    @staticmethod
    def _captain_score(rider, mates) -> float:
        def z(x, xs):
            m = sum(xs) / len(xs)
            sd = (sum((v - m) ** 2 for v in xs) / len(xs)) ** 0.5
            return (x - m) / sd if sd > 0 else 0.0
        vs = [a.v_max for a in mates]
        ss = [a.stamina for a in mates]
        return z(rider.v_max, vs) + z(rider.stamina, ss)

    def _lane_bounds(self) -> tuple[float, float]:
        p = self.params
        half = (p["n_lanes"] - 1) * p["lane_width_m"] / 2.0
        return -half, half

    def _grid_lane(self, i: int) -> float:
        p = self.params
        col = i % p["n_lanes"]
        return self.lane_lo + col * p["lane_width_m"]

    def _resolve_strategy_names(self, n, strategy, mix, explicit, rng):
        if explicit is not None:
            return list(explicit)
        if mix:
            names, weights = zip(*mix.items())
            total = sum(weights)
            cum, picks = [], []
            acc = 0.0
            for w in weights:
                acc += w / total
                cum.append(acc)
            for _ in range(n):
                r = rng.random()
                picks.append(names[next(k for k, c in enumerate(cum) if r <= c)])
            return picks
        return [strategy] * n

    # ------------------------------------------------------------------
    # perception
    # ------------------------------------------------------------------
    def _perceive_all(self, active) -> dict:
        """Build every rider's Perception in one sorted sweep.

        Riders are sorted by distance once and each rider scans outward only as
        far as ``sense_radius_m``, so the cost is O(n log n + n·k) per step
        instead of the O(n²) all-pairs loop used in v0.2/v0.3. Neighbour lists
        come out already ordered nearest-first in both directions.
        """
        p = self.params
        radius = p["sense_radius_m"]
        pack_gap = p["pack_gap_m"]
        arr = sorted(active, key=lambda a: a.distance)
        n = len(arr)
        percs = {}
        for i, rider in enumerate(arr):
            ahead, behind = [], []
            pack_speeds = [rider.speed]
            for j in range(i + 1, n):                  # outward, increasing gap
                o = arr[j]
                gap = o.distance - rider.distance
                if gap > radius:
                    break
                ahead.append(Neighbor(gap=gap, lane=o.lane, speed=o.speed,
                                      team=o.team,
                                      is_captain=(o.role is Role.CAPTAIN)))
                if gap <= pack_gap:
                    pack_speeds.append(o.speed)
            for j in range(i - 1, -1, -1):             # outward, increasing gap
                o = arr[j]
                gap = o.distance - rider.distance      # <= 0
                if -gap > radius:
                    break
                behind.append(Neighbor(gap=gap, lane=o.lane, speed=o.speed,
                                       team=o.team,
                                       is_captain=(o.role is Role.CAPTAIN)))
                if -gap <= pack_gap:
                    pack_speeds.append(o.speed)
            dist_to_finish = self.race_distance - rider.distance
            percs[rider] = Perception(
                ahead=tuple(ahead),
                behind=tuple(behind),
                pack_speed=sum(pack_speeds) / len(pack_speeds),
                dist_to_finish=dist_to_finish,
                in_sprint_zone=dist_to_finish <= p["sprint_m"],
            )
        return percs

    def _self_view(self, rider) -> SelfView:
        return SelfView(
            skill=rider.skill, energy=rider.energy, energy_max=rider.energy_max,
            speed=rider.speed, team=rider.team, is_drafting=rider.is_drafting,
            progress=min(1.0, rider.distance / self.race_distance),
            is_captain=(rider.role is Role.CAPTAIN),
            v_max=rider.v_max, stamina=rider.stamina,
        )

    # ------------------------------------------------------------------
    # action -> physics
    # ------------------------------------------------------------------
    def _has_wheel_ahead(self, perc: Perception) -> bool:
        p = self.params
        nb = perc.nearest_ahead
        return (nb is not None and 0 < nb.gap <= p["draft_gap_m"])

    def _sheltered(self, rider, perc: Perception) -> bool:
        """A close wheel directly ahead in a near lane gives shelter."""
        p = self.params
        for nb in perc.ahead:
            if nb.gap > p["draft_gap_m"]:
                break
            if abs(nb.lane - rider.lane) <= p["draft_lane_m"]:
                return True
        return False

    def _target_speed(self, rider, perc: Perception) -> tuple[float, float]:
        """Return (target_speed, target_lane) for this step's action.

        v0.6: a PULL's target speed is *emergent* — it scales with the rider's
        own ``v_max``, its remaining battery, and an urgency term that rises
        toward the finish. A fresh rider pulling in the finale therefore reaches
        ~``v_max`` (this replaces the dedicated sprint mode); a tired or early
        puller cruises. Drafting tucks in at the pack/wheel pace.
        """
        p = self.params
        a = rider.action
        v, lane = rider.speed, rider.lane
        nb = perc.nearest_ahead
        vcap = rider.v_max                               # per-rider ceiling

        if a is Action.PULL:
            progress = min(1.0, rider.distance / self.race_distance)
            urgency = 0.25 + 1.75 * progress ** 2
            v_floor = p["v_min"]
            target = v_floor + (vcap - v_floor) * rider.energy * (0.4 + 0.6 * urgency)
            target = min(vcap, target)
            lane = 0.0                                   # move to the front line
        elif a is Action.DRAFT:
            target = nb.speed if nb is not None else perc.pack_speed
            lane = nb.lane if nb is not None else lane   # tuck behind the wheel
        elif a is Action.SPEED_UP:
            target = min(vcap, v + p["dv"])
            lane = 0.0 if nb is None else self._overtake_lane(rider, nb)
        elif a is Action.SLOW_DOWN:
            target = max(p["v_min"], v - p["dv"])
        else:  # KEEP
            target = v
        return target, lane

    def _overtake_lane(self, rider, nb: Neighbor) -> float:
        """Pick a lane offset to the side of the wheel ahead to move up."""
        # step toward the nearer open edge relative to the blocker's lane.
        if nb.lane <= 0:
            return min(self.lane_hi, rider.lane + self.params["lane_width_m"])
        return max(self.lane_lo, rider.lane - self.params["lane_width_m"])

    def _update_energy(self, rider, v, sheltered):
        """v0.6 stamina: a velocity-driven, stamina-governed battery drain.

            dB = drain_c * v * exposure * dt / stamina

        Exposure is full (1.0) in the wind and ``draft_factor`` when sheltered,
        so pulling costs more than drafting (the cooperation tension). Higher
        ``stamina`` drains slower. Monotone decrease (no recovery in v1); a
        rider that empties the battery is dropped.
        """
        p = self.params
        exposure = p["draft_factor"] if sheltered else 1.0
        rider.energy -= p["drain_c"] * v * exposure * self.dt / rider.stamina
        rider.energy = max(0.0, min(1.0, rider.energy))

    # ------------------------------------------------------------------
    def step(self):
        p = self.params
        self.clock += self.dt
        active = [a for a in self.agents if not a.finished]
        if not active:
            return

        # 1. perceive + 2. decide.
        percs = self._perceive_all(active)
        for rider in active:
            rider.decide(self._self_view(rider), percs[rider])

        # 3-5. resolve -> dynamics -> move.
        for rider in active:
            perc = percs[rider]

            if rider.dropped:
                # lost contact: solo, slow, no shelter.
                target = p["v_solo"]
                rider.is_drafting = False
                rider.speed += (target - rider.speed) * (self.dt / p["accel_tau"])
                self._update_energy(rider, rider.speed, sheltered=False)
            else:
                target, target_lane = self._target_speed(rider, perc)
                rider.speed += (target - rider.speed) * (self.dt / p["accel_tau"])
                # clamp to this rider's own speed ceiling (v0.6: per-rider v_max).
                rider.speed = max(p["v_min"], min(rider.v_max, rider.speed))
                # PULL forces full wind; otherwise shelter depends on geometry.
                rider.is_drafting = (rider.action is not Action.PULL
                                     and self._sheltered(rider, perc))
                self._update_energy(rider, rider.speed, rider.is_drafting)
                if rider.energy <= 0.0:
                    rider.dropped = True
                self._nudge_lane(rider, target_lane)

            # cheap online counters (always on; analysis can avoid dataframes).
            rider.n_steps += 1
            rider.n_sheltered += rider.is_drafting
            rider.action_counts[rider.action] += 1
            if rider.speed > rider.peak_speed:
                rider.peak_speed = rider.speed

            # move.
            rider.distance += rider.speed * self.dt
            rider.s = rider.distance % self.loop
            rider.laps = int(rider.distance // self.loop)
            if rider.distance >= self.race_distance:
                rider.finished = True
                rider.finish_time = self.clock
                rider.finish_rank = self.n_finished
                self.n_finished += 1

        self._separate(active)
        # sync the mesa space: one move per rider per step, after lateral
        # separation so the space always holds the final (x, y) of the step.
        for rider in active:
            self.space.move_agent(rider, self.track.xy(rider.s, rider.lane))
        self._n_packs = self._count_packs(active)
        if self.collect:
            self.datacollector.collect(self)

    # ------------------------------------------------------------------
    # lateral dynamics (overtaking + keeping the animation legible)
    # ------------------------------------------------------------------
    def _nudge_lane(self, rider, target_lane):
        step = self.params["lane_step_m"]
        delta = max(-step, min(step, target_lane - rider.lane))
        rider.lane = max(self.lane_lo, min(self.lane_hi, rider.lane + delta))

    def _separate(self, active):
        """One gentle pass pushing apart riders that overlap in (s, lane)."""
        p = self.params
        riders = sorted(active, key=lambda a: a.distance)
        for i, a in enumerate(riders):
            for b in riders[i + 1:]:
                if b.distance - a.distance > p["sep_s_m"]:
                    break
                dl = a.lane - b.lane
                if abs(dl) < p["sep_lane_m"]:
                    push = (p["sep_lane_m"] - abs(dl)) / 2.0
                    sign = 1.0 if dl >= 0 else -1.0
                    a.lane = max(self.lane_lo, min(self.lane_hi, a.lane + sign * push))
                    b.lane = max(self.lane_lo, min(self.lane_hi, b.lane - sign * push))

    def _count_packs(self, active) -> int:
        gap = self.params["pack_gap_m"]
        ds = sorted(a.distance for a in active)
        if not ds:
            return 0
        packs = 1
        for prev, cur in zip(ds, ds[1:]):
            if cur - prev > gap:
                packs += 1
        return packs

    # ------------------------------------------------------------------
    def run(self, max_steps=4000):
        while self.n_finished < len(self.agents) and self.steps < max_steps:
            self.step()
        return self
