"""Default simulation parameters (SI units: metres, seconds, m/s).

A single flat dict, mirroring the v0.1 prototype's pattern, so experiments can
override any value with ``RaceModel(params={...})``. Speeds are stored in m/s;
convert to km/h only for display (``* 3.6``).
"""

from __future__ import annotations

import math

# Reference: 50 km/h ≈ 13.9 m/s, 60 km/h ≈ 16.7 m/s, 33 km/h ≈ 9.2 m/s.

DEFAULT_PARAMS: dict = dict(
    # --- track geometry (stadium / discorectangle) -------------------
    straight_m=400.0,        # length of each straight (m)
    bend_radius_m=80.0,      # radius of each semicircular bend (m)
    n_laps=3,                # laps to race
    n_lanes=6,               # lateral lines available (for drafting / overtakes)
    lane_width_m=1.0,        # spacing between lanes (m), for geometry + animation

    # --- time --------------------------------------------------------
    dt=1.0,                  # seconds per step

    # --- speeds (m/s) ------------------------------------------------
    v_min=9.0,               # floor speed (soft-pedalling pack, ~32 km/h)
    v_cruise=12.0,           # initial / neutral speed (~43 km/h)
    v_max=18.0,              # hard ceiling on sustained speed (~65 km/h)
    v_solo=8.0,              # speed a dropped rider decays toward (~29 km/h)
    dv=0.6,                  # speed delta per SPEED_UP / SLOW_DOWN step
    dv_pull=0.4,             # extra pace a PULL adds on top of pack speed
    accel_tau=2.0,           # steps to relax speed toward its target (inertia)

    # --- perception / packs ------------------------------------------
    sense_radius_m=20.0,     # how far ahead/behind a rider perceives others
    pack_gap_m=12.0,         # arc-gap above which a pack is considered to split

    # --- drafting ----------------------------------------------------
    draft_gap_m=8.0,         # max gap-ahead (m) at which you catch a wheel
    draft_lane_m=1.5,        # max lateral offset (m) to be "behind" a wheel
    draft_factor=0.62,       # fraction of aero power a sheltered rider pays

    # --- lateral (lane) dynamics, for overtakes + animation ----------
    lane_step_m=0.5,         # max lateral move per step toward intent
    sep_s_m=3.0,             # riders closer than this in arc-length ...
    sep_lane_m=0.9,          # ... and this laterally get nudged apart
    start_gap_m=2.5,         # arc-length spacing of the grid at the start

    # --- energy / stamina (v0.6: velocity-driven exponential drain) --
    # The W'-bucket of v0.5 is replaced by a normalised battery B in [0,1]
    # whose drain per step is  c * v * exposure * dt / stamina  (see
    # model._update_energy). Higher per-rider `stamina` => slower drain.
    energy_max=2200.0,       # (legacy, unused by v0.6 physics; kept for compat)
    aero_coeff=22.0,         # aero power = aero_coeff * (v / v_ref)^3
    v_ref=13.9,              # speed (m/s) at which the aero term == aero_coeff
    aer_power=17.0,          # sustainable aerobic power at stamina = 1.0
    drain_rate=1.0,          # (legacy, unused by v0.6 physics)
    recover_rate=0.8,        # (legacy, unused by v0.6 physics)
    fatigue_knee=0.25,       # (legacy, unused by v0.6 physics)
    drain_c=0.0003,          # battery drained per (m/s of speed * second) at
                             # full wind exposure and stamina = 1.0

    # --- v0.6 per-rider traits (replace the single `skill` scalar) ----
    # Max velocity: within a team ~Normal(mu_t, v_max_sd); across teams the
    # team mean mu_t is a high->low linear spread from v_max_hi to v_max_lo.
    v_max_hi=19.0,           # team-0 (strongest) mean max velocity (m/s)
    v_max_lo=16.0,           # last-team (weakest) mean max velocity (m/s)
    v_max_sd=0.5,            # within-team sd of max velocity (m/s)
    v_max_floor=14.0,        # truncation floor for sampled v_max (m/s)
    v_max_ceil=23.4,         # truncation ceiling for sampled v_max (m/s)
    # Stamina: endurance multiplier ~Normal(mean, sd), truncated.
    stamina_mean=1.0,
    stamina_sd=0.15,
    stamina_min=0.6,
    stamina_max=1.4,

    # --- sprint ------------------------------------------------------
    sprint_m=250.0,          # last metres where leftover energy buys top speed
    v_sprint_min=13.0,       # sprint speed on an empty battery (~47 km/h)
    v_sprint_max=20.0,       # sprint speed, full battery, top skill (~72 km/h)
    sprint_drain=120.0,      # energy burned per second while sprinting

    # --- field -------------------------------------------------------
    skill_mean=1.0,
    skill_sd=0.10,
    skill_min=0.75,
    skill_max=1.30,
)


def loop_length(params: dict) -> float:
    """Total arc-length of the stadium loop (m)."""
    return 2.0 * params["straight_m"] + 2.0 * math.pi * params["bend_radius_m"]
