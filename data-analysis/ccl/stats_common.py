"""Shared effect-size statistics used across the ccl analysis scripts.

`analyze_data.py` (large per-frame samples, normal-approximation
Mann-Whitney) and `load_analysis.py` (small per-run samples, exact
permutation Mann-Whitney) use different significance tests for good
reason -- the sample-size regimes are genuinely different. But both need
the same effect-size measure on top of whichever test they run, so that
part lives here once.
"""
from __future__ import annotations

CLIFFS_DELTA_THRESHOLDS = (0.147, 0.33, 0.474)


def cliffs_delta(x: list, y: list) -> float:
    """Cliff's delta effect size in [-1, 1].

    delta = (# of x>y - # of x<y) / (n_x * n_y)
    Convention: positive delta means X tends to be larger than Y.
    """
    n_x, n_y = len(x), len(y)
    if n_x == 0 or n_y == 0:
        return float("nan")
    greater = less = 0
    for xv in x:
        for yv in y:
            if xv > yv:
                greater += 1
            elif xv < yv:
                less += 1
    return (greater - less) / float(n_x * n_y)


def cliffs_delta_effect_size(delta: float) -> str:
    """Romano et al. (2006) thresholds for |delta|."""
    a = abs(delta)
    if a < CLIFFS_DELTA_THRESHOLDS[0]:
        return "negligible"
    if a < CLIFFS_DELTA_THRESHOLDS[1]:
        return "small"
    if a < CLIFFS_DELTA_THRESHOLDS[2]:
        return "medium"
    return "large"
