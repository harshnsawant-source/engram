import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FAILS = []
def check(name, ok):
    print(("ok   " if ok else "FAIL ") + name)
    if not ok:
        FAILS.append(name)

from engram.store import MemoryStore, Episode, SemanticFact
from engram import config

s = MemoryStore()
e1 = s.add_episode("I adopted a dog named Bruno", "user", [1.0, 0.0], now=0.5)
e2 = s.add_episode("Bruno chewed my shoe", "user", [0.9, 0.1], now=0.6)
f1 = s.add_fact("The user has a dog named Bruno", [1.0, 0.0], now=1.0, provenance=[e1.id, e2.id])

check("store: episodes appended in order", [e.id for e in s.episodes] == [e1.id, e2.id])
check("store: episode fields", e1.actor == "user" and e1.t == 0.5 and e1.strength == 1.0
      and e1.last_access == 0.5 and e1.access_count == 0 and e1.consolidated is False)
check("store: fact fields", f1.provenance == [e1.id, e2.id] and f1.born_t == 1.0
      and f1.superseded_by is None and f1.confidence == 1.0)
check("store: ids unique", len({e1.id, e2.id, f1.id}) == 3)
check("store: get finds episode and fact", s.get(e2.id) is e2 and s.get(f1.id) is f1)
check("store: get miss is None", s.get("nope1234") is None)

s2 = MemoryStore.from_json(s.to_json())
check("store: json round-trip counts", len(s2.episodes) == 2 and len(s2.facts) == 1)
check("store: json round-trip episode equality", s2.episodes[0] == e1)
check("store: json round-trip fact equality", s2.facts[0] == f1)

cap = MemoryStore()
for i in range(config.MAX_EPISODES + 5):
    cap.add_episode(f"event {i}", "user", [1.0, 0.0], now=float(i) / 100)
check("store: cap enforced", len(cap.episodes) == config.MAX_EPISODES)
check("store: cap dropped oldest", cap.episodes[0].text != "event 0")

# Dormant-first eviction: at now=20 the 200 old episodes (t=0) are dormant
# (episode half-life 3 -> strength ~0.01), so the cap must evict a dormant
# one, not the freshly added live episode.
dorm = MemoryStore()
for i in range(config.MAX_EPISODES):
    dorm.add_episode(f"old event {i}", "user", [1.0, 0.0], now=0.0)
fresh = dorm.add_episode("fresh event", "user", [1.0, 0.0], now=20.0)
check("store: cap evicts a dormant episode first", len(dorm.episodes) == config.MAX_EPISODES
      and fresh in dorm.episodes and dorm.episodes[0].text != "old event 0")

check("config: spec defaults", config.HALF_LIFE_EPISODE == 3.0
      and config.HALF_LIFE_EPISODE_CONSOLIDATED == 1.0 and config.HALF_LIFE_FACT == 14.0
      and config.RETRIEVAL_BOOST == 0.3 and config.STRENGTH_CAP == 1.0
      and config.DORMANT_THRESHOLD == 0.15 and config.REFUSAL_THRESHOLD == 0.25
      and config.TOP_K == 6 and config.SIM_EDGE_THRESHOLD == 0.75 and config.MAX_EPISODES == 200)

print(f"\n{'RED' if FAILS else 'GREEN'}: {len(FAILS)} failing")
sys.exit(1 if FAILS else 0)
