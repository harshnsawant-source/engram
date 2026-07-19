"""Strength decay and reinforcement (ACT-R-inspired, not a faithful model).

A memory's `strength` field is its value at time `last_access` (the anchor).
Current strength halves every half-life of sim-time since the anchor.
Retrieval boosts strength and re-anchors — rehearsal fights forgetting.
Dormant memories are excluded from recall but never deleted: forgetting
is retrieval failure.
"""

from . import config


def half_life_of(mem):
    if hasattr(mem, "provenance"):  # SemanticFact (duck-typed to avoid import cycle)
        return config.HALF_LIFE_FACT
    if mem.consolidated:
        return config.HALF_LIFE_EPISODE_CONSOLIDATED
    return config.HALF_LIFE_EPISODE


def current_strength(mem, now):
    dt = max(0.0, now - mem.last_access)
    return mem.strength * 2 ** (-dt / half_life_of(mem))


def boost(mem, now):
    mem.strength = min(config.STRENGTH_CAP,
                       current_strength(mem, now) + config.RETRIEVAL_BOOST)
    mem.last_access = now
    mem.access_count += 1


def is_dormant(mem, now):
    return current_strength(mem, now) < config.DORMANT_THRESHOLD
