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

print(f"\n{'RED' if FAILS else 'GREEN'}: {len(FAILS)} failing")
sys.exit(1 if FAILS else 0)
