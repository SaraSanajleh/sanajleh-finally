"""
ReTour Retriever — Ranking helpers (used by the retrieval engine, B5)
====================================================================

Two pieces:
  1. rrf_fuse       — Reciprocal Rank Fusion over ranked lists (ranks, not scores).
  2. spatial_score  — piecewise distance decay (flat -> gentle linear -> exponential),
                      tuned to Jordan road distances. Used to weight a nearby
                      restaurant/hotel/event by how close it is to an anchor POI.

Design decisions:
  - RRF (k=60) fuses dense + BM25 by RANK, sidestepping score-scale incompatibility.
  - spatial_score is a WEIGHT, not a gate: fitness (wizard) already gated the
    candidate; proximity then competes with fitness in the final ordering, so a
    perfect-but-2-hours-away restaurant sinks below a good-enough adjacent one.
"""

from math import exp
from typing import List, Dict


# ---------------------------------------------------------------------
# 1. Reciprocal Rank Fusion
# ---------------------------------------------------------------------

def rrf_fuse(ranked_lists: List[List[str]], k: int = 60) -> List[str]:
    """Fuse several ranked ID lists into one, by RRF.

    ranked_lists: each is a list of ids ordered best->worst (rank 0 = best).
    Returns ids ordered by summed RRF score (highest first).
    An id that ranks well in MORE lists rises; a single-channel fluke sinks.
    """
    scores: Dict[str, float] = {}
    for lst in ranked_lists:
        for rank, _id in enumerate(lst):
            scores[_id] = scores.get(_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=lambda i: scores[i], reverse=True)


# ---------------------------------------------------------------------
# 2. Spatial score — piecewise distance decay (Jordan-tuned)
# ---------------------------------------------------------------------

# Thresholds (km) — starting values, tuned later by measurement.
_D_COMFORT = 15.0    # <= this: no penalty (same town / short hop)
_D_GENTLE = 40.0     # comfort..this: gentle LINEAR drop (still acceptable)
_S_AT_GENTLE = 0.6   # score at the gentle boundary
_DECAY = 0.03        # exponential rate beyond gentle zone (per km)


def spatial_score(distance_km: float) -> float:
    """Map an anchor->candidate distance to a proximity weight in [0, 1].

    Zone 1 (<=15 km)      : 1.0            (comfortable)
    Zone 2 (15..40 km)    : linear 1.0->0.6 (gentle — 'quiet for a while')
    Zone 3 (>40 km)       : exponential from 0.6 downward (breaks the day)
    """
    d = max(0.0, distance_km)
    if d <= _D_COMFORT:
        return 1.0
    if d <= _D_GENTLE:
        # linear interpolation from 1.0 (at 15) down to 0.6 (at 40)
        frac = (d - _D_COMFORT) / (_D_GENTLE - _D_COMFORT)
        return 1.0 - frac * (1.0 - _S_AT_GENTLE)
    # beyond gentle: exponential decay anchored at 0.6
    return _S_AT_GENTLE * exp(-_DECAY * (d - _D_GENTLE))


def combine_fitness_proximity(fitness: float, distance_km: float,
                              w_fitness: float = 0.6,
                              w_proximity: float = 0.4) -> float:
    """Final weight for a nearby candidate: blend wizard-fitness with proximity.

    fitness in [0,1] (from the ranker), proximity from spatial_score.
    Weights are a starting point, tuned by measurement.
    """
    return w_fitness * fitness + w_proximity * spatial_score(distance_km)


# ---------------------------------------------------------------------
# Self-check
# ---------------------------------------------------------------------
if __name__ == "__main__":
    # RRF: an id ranked well in both lists beats one ranked well in only one.
    a = ["x", "y", "z"]      # x best here
    b = ["y", "x", "w"]      # y best here, x second
    fused = rrf_fuse([a, b])
    assert fused[0] in ("x", "y") and "w" in fused and "z" in fused
    # x appears high in both -> should top or tie-top
    assert fused[0] == "x", fused

    # spatial score zones
    assert spatial_score(5) == 1.0
    assert spatial_score(10) == 1.0
    assert abs(spatial_score(40) - 0.6) < 1e-9
    s25 = spatial_score(25); assert 0.7 < s25 < 0.9, s25   # gentle middle
    s150 = spatial_score(150); assert s150 < 0.1, s150     # 2h away -> collapses
    # monotonic decreasing
    xs = [spatial_score(d) for d in range(0, 200, 5)]
    assert all(xs[i] >= xs[i+1] - 1e-9 for i in range(len(xs)-1))

    # combine: perfect-but-far sinks below good-enough-near
    far_perfect = combine_fitness_proximity(1.0, 150)   # fitness 1.0, 2h away
    near_good = combine_fitness_proximity(0.7, 8)        # fitness 0.7, adjacent
    assert near_good > far_perfect, (near_good, far_perfect)

    print("All checks passed — RRF + spatial scoring work correctly.")
