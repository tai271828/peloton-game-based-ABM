"""The stadium ("ellipse-like") track — pure geometry, no physics.

A *discorectangle*: two straights of length ``L`` joined by two semicircular
bends of radius ``R``. Riders carry an arc-length ``s in [0, S)`` plus a lateral
``lane`` offset; :meth:`StadiumTrack.xy` maps those to screen coordinates for the
animation and for drafting geometry.

Arc-length layout (counter-clockwise), starting at the right end of the bottom
straight, ``lane = 0`` on the centre-line:

    segment 0:  bottom straight   s in [0, L)            moving +x
    segment 1:  right bend        s in [L, L+piR)        turning left (CCW)
    segment 2:  top straight      s in [L+piR, 2L+piR)   moving -x
    segment 3:  left bend         s in [2L+piR, 2L+2piR) turning left (CCW)

A positive ``lane`` is to the rider's left (toward the inside of the loop), so
inner lanes are slightly shorter — but we ignore that arc-length difference
(lanes are a rendering / drafting nicety, not a distance advantage in v0.2).
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class StadiumTrack:
    straight_m: float
    bend_radius_m: float

    @property
    def length(self) -> float:
        """Total loop arc-length S (m), on the centre-line."""
        return 2.0 * self.straight_m + 2.0 * math.pi * self.bend_radius_m

    # -- segment boundaries (cached as properties for clarity) ----------
    @property
    def _b0(self) -> float:  # end of bottom straight
        return self.straight_m

    @property
    def _b1(self) -> float:  # end of right bend
        return self.straight_m + math.pi * self.bend_radius_m

    @property
    def _b2(self) -> float:  # end of top straight
        return 2.0 * self.straight_m + math.pi * self.bend_radius_m

    # -------------------------------------------------------------------
    def on_straight(self, s: float) -> bool:
        """True if arc-length ``s`` lies on one of the two straights."""
        s %= self.length
        return s < self._b0 or (self._b1 <= s < self._b2)

    def xy(self, s: float, lane: float = 0.0) -> tuple[float, float]:
        """Map (arc-length, lateral lane offset) to (x, y) in metres.

        The centre-line is laid out so the bottom straight runs left→right at
        ``y = -R`` and the top straight runs right→left at ``y = +R``; the
        rectangle of bend centres spans ``x in [0, L]``.
        """
        L, R = self.straight_m, self.bend_radius_m
        s %= self.length

        if s < self._b0:                      # bottom straight, +x, y = -R
            x = s
            y = -R
            # outward normal points down (-y); +lane (rider's left) -> +y
            return x, y + lane

        if s < self._b1:                      # right bend, centre (L, 0)
            theta = (s - self._b0) / R        # 0..pi, measured from -y (down)
            ang = -math.pi / 2 + theta        # start pointing down, sweep CCW
            r = R - lane                       # +lane = rider's left = toward inside
            x = L + r * math.cos(ang)
            y = r * math.sin(ang)
            return x, y

        if s < self._b2:                      # top straight, -x, y = +R
            x = L - (s - self._b1)
            y = R
            # outward normal points up (+y); +lane (rider's left) -> -y
            return x, y - lane

        # left bend, centre (0, 0)
        theta = (s - self._b2) / R            # 0..pi
        ang = math.pi / 2 + theta             # start pointing up, sweep CCW
        r = R - lane
        x = r * math.cos(ang)
        y = r * math.sin(ang)
        return x, y

    def heading(self, s: float) -> float:
        """Tangent direction (radians) of travel at arc-length ``s``."""
        eps = 0.5
        x0, y0 = self.xy(s - eps)
        x1, y1 = self.xy(s + eps)
        return math.atan2(y1 - y0, x1 - x0)

    def outline(self, n: int = 400, lane: float = 0.0) -> tuple[list[float], list[float]]:
        """Sampled (xs, ys) of a lane's closed loop, for plotting the track."""
        xs, ys = [], []
        S = self.length
        for i in range(n + 1):
            x, y = self.xy(S * i / n, lane)
            xs.append(x)
            ys.append(y)
        return xs, ys
