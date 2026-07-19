"""Scored retrieval over live memories: similarity x strength."""

import math

from . import config
from .decay import current_strength, is_dormant


def cosine(a, b):
    num = sum(x * y for x, y in zip(a, b))
    da = math.sqrt(sum(x * x for x in a))
    db = math.sqrt(sum(x * x for x in b))
    return num / (da * db) if da and db else 0.0


def retrieval_score(mem, qvec, now):
    return cosine(qvec, mem.embedding) * (0.5 + 0.5 * current_strength(mem, now))


def recall(store, qvec, now, k=config.TOP_K):
    live = [f for f in store.facts if f.superseded_by is None and not is_dormant(f, now)]
    live += [e for e in store.episodes if not is_dormant(e, now)]
    scored = [(retrieval_score(m, qvec, now), m) for m in live]
    scored.sort(key=lambda pair: -pair[0])  # stable: facts stay ahead on ties
    return scored[:k]
