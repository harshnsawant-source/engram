import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FAILS = []
def check(name, ok):
    print(("ok   " if ok else "FAIL ") + name)
    if not ok:
        FAILS.append(name)

from engram.store import MemoryStore
from engram.providers import HashEmbedder
from engram.consolidate import (cluster_episodes, parse_facts, distill_prompt,
                                contradiction_prompt, DreamReport)
from engram import config

check("config: slice-2 constants", config.CLUSTER_THRESHOLD == 0.6
      and config.MERGE_THRESHOLD == 0.8)

emb = HashEmbedder()
s = MemoryStore()
# Machine-verified: e1~e2 cosine 0.833 (> 0.6); e3 vs both 0.0 (< 0.6).
e1 = s.add_episode("the puppy Bruno chewed a shoe", "user", emb.embed("the puppy Bruno chewed a shoe"), now=0.1)
e2 = s.add_episode("the puppy Bruno chewed a slipper", "user", emb.embed("the puppy Bruno chewed a slipper"), now=0.2)
e3 = s.add_episode("my sister Meera lives in Delhi", "user", emb.embed("my sister Meera lives in Delhi"), now=0.3)

clusters = cluster_episodes([e1, e2, e3], config.CLUSTER_THRESHOLD)
check("cluster: related episodes grouped", [[m.id for m in c] for c in clusters]
      == [[e1.id, e2.id], [e3.id]])
check("cluster: empty input", cluster_episodes([], config.CLUSTER_THRESHOLD) == [])

check("parse: bullet lines extracted",
      parse_facts("- The user has a puppy named Bruno\n- The puppy chews footwear")
      == ["The user has a puppy named Bruno", "The puppy chews footwear"])
check("parse: NONE and noise ignored",
      parse_facts("NONE") == [] and parse_facts("Sure! Here are the facts:\n- One fact") == ["One fact"])
check("parse: empty bullet ignored", parse_facts("- \n-") == [])

p = distill_prompt([e1, e2])
check("distill prompt: carries episode ids and texts",
      e1.id in p and e2.id in p and "chewed a shoe" in p and "chewed a slipper" in p)
check("distill prompt: instructs bullet format and NONE", '"- "' in p and "NONE" in p)

cp = contradiction_prompt("A dog named Bruno", "A cat named Bruno")
check("contradiction prompt: carries both statements and YES/NO instruction",
      "A dog named Bruno" in cp and "A cat named Bruno" in cp and "YES or NO" in cp)

r = DreamReport(day=1.0, learned=[], strengthened=[], superseded=[],
                went_dormant=[], episodes_consolidated=0)
check("dreamreport: constructible with empty fields", r.day == 1.0 and r.learned == [])

# --- Three-night scenario (all sentence pairs machine-verified) ---
from engram.store import MemoryStore as _MS
from engram.providers import FakeLLM
from engram.engine import SimClock
from engram.consolidate import sleep
from engram.recall import recall
from engram.decay import is_dormant

emb2 = HashEmbedder()
st = _MS()
clock = SimClock()
a1 = st.add_episode("the puppy Bruno chewed a shoe", "user", emb2.embed("the puppy Bruno chewed a shoe"), now=0.1)
a2 = st.add_episode("the puppy Bruno chewed a slipper", "user", emb2.embed("the puppy Bruno chewed a slipper"), now=0.2)
a3 = st.add_episode("my sister Meera lives in Delhi", "user", emb2.embed("my sister Meera lives in Delhi"), now=0.3)

# Night 1: two clusters -> two distill calls -> two new facts.
llm = FakeLLM(["- The user's puppy Bruno chews things",
               "- The user's sister Meera lives in Delhi"])
r1 = sleep(st, llm, emb2, clock)
check("sleep1: clock advanced to day 1", clock.now() == 1.0)
check("sleep1: two facts learned", len(r1.learned) == 2 and len(st.facts) == 2)
check("sleep1: provenance carries cluster episodes",
      st.facts[0].provenance == [a1.id, a2.id] and st.facts[1].provenance == [a3.id])
check("sleep1: episodes marked consolidated",
      all(e.consolidated for e in [a1, a2, a3]) and r1.episodes_consolidated == 3)
check("sleep1: two LLM calls (distill only)", len(llm.prompts) == 2)

# Night 2: identical re-distilled statement -> merge/strengthen, no new fact.
b1 = st.add_episode("the puppy Bruno chewed a sandal", "user", emb2.embed("the puppy Bruno chewed a sandal"), now=1.1)
puppy_fact = st.facts[0]
before_prov = list(puppy_fact.provenance)
llm = FakeLLM(["- The user's puppy Bruno chews things",   # distill (identical -> cosine 1.0)
               "NO"])                                      # contradiction check
r2 = sleep(st, llm, emb2, clock)
check("sleep2: strengthened not duplicated", len(st.facts) == 2 and len(r2.strengthened) == 1
      and r2.strengthened[0]["id"] == puppy_fact.id)
check("sleep2: provenance union grew", set(before_prov) < set(puppy_fact.provenance)
      and b1.id in puppy_fact.provenance)
check("sleep2: boost applied", puppy_fact.access_count == 1)
check("sleep2: two LLM calls (distill + contradiction)", len(llm.prompts) == 2)

# Night 3: contradictory statement (cosine 0.857 > 0.8) -> supersede.
st.add_episode("my sister Meera lives in Mumbai now", "user", emb2.embed("my sister Meera lives in Mumbai now"), now=2.1)
delhi_fact = st.facts[1]
llm = FakeLLM(["- The user's sister Meera lives in Mumbai",
               "YES"])
r3 = sleep(st, llm, emb2, clock)
check("sleep3: supersede recorded", len(r3.superseded) == 1
      and r3.superseded[0]["old_id"] == delhi_fact.id)
check("sleep3: old fact marked superseded", delhi_fact.superseded_by == r3.superseded[0]["new_id"])
mumbai_hits = recall(st, emb2.embed("where does sister Meera live"), clock.now())
check("sleep3: recall prefers the new fact",
      mumbai_hits and mumbai_hits[0][1].id == r3.superseded[0]["new_id"])

# --- Dormancy reporting + empty-pending makes zero LLM calls ---
st2 = _MS()
clock2 = SimClock()
p1 = st2.add_episode("the parrot said hello twice today", "user", emb2.embed("the parrot said hello twice today"), now=0.5)
llm2 = FakeLLM(["- The user's parrot can talk"])
sleep(st2, llm2, emb2, clock2)              # night 1: consolidates p1 (half-life drops to 1)
calls_after_night1 = len(llm2.prompts)
sleep(st2, llm2, emb2, clock2)              # night 2: nothing pending
sleep(st2, llm2, emb2, clock2)              # night 3
check("sleep: empty pending makes zero LLM calls", len(llm2.prompts) == calls_after_night1)
r6 = sleep(st2, llm2, emb2, clock2)         # night 4: p1 strength 2^-3.5 ~ 0.088 < 0.15
check("sleep: consolidated episode reported dormant", p1.id in r6.went_dormant)
check("sleep: fact still live", not is_dormant(st2.facts[0], clock2.now()))

print(f"\n{'RED' if FAILS else 'GREEN'}: {len(FAILS)} failing")
sys.exit(1 if FAILS else 0)
