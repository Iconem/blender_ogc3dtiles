"""budget.py — cap on the points and vertices shown, by coarsening the SSE.

Neither backend can drop part of a selection without leaving holes, so the cap
works as feedback: while the visible tiles hold more elements than the cap, the
screen-space error of every tileset is multiplied by a growing factor; once the
view has finished loading well under the cap, the factor relaxes back to 1.
"""
from __future__ import annotations

import math

MAX_FACTOR = 64.0
RELAX_BELOW = 0.8       # share of the cap under which detail may come back


def cap_factor(factor: float, total: float, cap: float, settled: bool = True) -> float:
    """Next SSE multiplier. ``total``: elements visible now; ``cap``: the limit
    (0 or less: no cap); ``settled``: nothing is loading, so a low total is the
    real one and not a view still filling."""
    if cap <= 0:
        return 1.0
    if total > cap:         # elements fall roughly with the square of the SSE
        return min(MAX_FACTOR, factor * min(2.0, max(1.05, math.sqrt(total / cap))))
    if settled and factor > 1.0 and total < RELAX_BELOW * cap:
        return max(1.0, factor * max(0.8, math.sqrt(max(total, 1.0) / cap)))
    return factor
