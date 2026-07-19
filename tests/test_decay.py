import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FAILS = []
def check(name, ok):
    print(("ok   " if ok else "FAIL ") + name)
    if not ok:
        FAILS.append(name)

from engram.store import Episode, SemanticFact
from engram.decay import current_strength, half_life_of, boost, is_dormant
from engram import config

def ep(**kw):
    base = dict(id="ep000001", t=0.0, actor="user", text="x", embedding=[1.0],
                strength=1.0, last_access=0.0, access_count=0, consolidated=False)
    base.update(kw)
    return Episode(**base)

def fact(**kw):
    base = dict(id="fa000001", statement="x", confidence=1.0, embedding=[1.0],
                strength=1.0, last_access=0.0, access_count=0, provenance=[], born_t=0.0)
    base.update(kw)
    return SemanticFact(**base)

check("decay: half-life episode", half_life_of(ep()) == config.HALF_LIFE_EPISODE)
check("decay: half-life consolidated episode",
      half_life_of(ep(consolidated=True)) == config.HALF_LIFE_EPISODE_CONSOLIDATED)
check("decay: half-life fact", half_life_of(fact()) == config.HALF_LIFE_FACT)

check("decay: episode halves after one half-life",
      abs(current_strength(ep(), 3.0) - 0.5) < 1e-9)
check("decay: no time passed -> unchanged", current_strength(ep(), 0.0) == 1.0)
check("decay: clock going backwards never grows strength",
      current_strength(ep(), -5.0) == 1.0)
check("decay: consolidated episode fades faster",
      current_strength(ep(consolidated=True), 2.0) < current_strength(ep(), 2.0))
check("decay: fact fades slower than episode",
      current_strength(fact(), 2.0) > current_strength(ep(), 2.0))

# Spec eval numbers: untouched episode dormant by day 9 (live day 8);
# untouched fact dormant by day 39 (live day 38).
check("decay: episode live at day 8", not is_dormant(ep(), 8.0))
check("decay: episode dormant by day 9", is_dormant(ep(), 9.0))
check("decay: fact live at day 38", not is_dormant(fact(), 38.0))
check("decay: fact dormant by day 39", is_dormant(fact(), 39.0))

b = ep()
boost(b, 3.0)
check("decay: boost = decayed + BOOST, capped",
      abs(b.strength - min(config.STRENGTH_CAP, 0.5 + config.RETRIEVAL_BOOST)) < 1e-9)
check("decay: boost re-anchors last_access and counts", b.last_access == 3.0 and b.access_count == 1)

# Rehearsal keeps a fact alive past its untouched dormancy day.
r = fact()
for day in range(7, 43, 7):
    boost(r, float(day))
check("decay: fact rehearsed weekly still live at day 42", not is_dormant(r, 42.0))

print(f"\n{'RED' if FAILS else 'GREEN'}: {len(FAILS)} failing")
sys.exit(1 if FAILS else 0)
