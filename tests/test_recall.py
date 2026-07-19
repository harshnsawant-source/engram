import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FAILS = []
def check(name, ok):
    print(("ok   " if ok else "FAIL ") + name)
    if not ok:
        FAILS.append(name)

from engram.store import MemoryStore
from engram.recall import cosine, retrieval_score, recall
from engram.providers import HashEmbedder
from engram import config

check("cosine: identical", abs(cosine([1.0, 0.0], [1.0, 0.0]) - 1.0) < 1e-9)
check("cosine: orthogonal", cosine([1.0, 0.0], [0.0, 1.0]) == 0.0)
check("cosine: zero vector safe", cosine([0.0, 0.0], [1.0, 0.0]) == 0.0)

emb = HashEmbedder()
s = MemoryStore()
dog = s.add_episode("the dog is called Bruno", "user", emb.embed("the dog is called Bruno"), now=0.0)
car = s.add_episode("my car needs new tyres soon", "user", emb.embed("my car needs new tyres soon"), now=0.0)
q = emb.embed("what is the dog called")

hits = recall(s, q, now=0.0)
check("recall: related memory ranks first", hits and hits[0][1] is dog)
check("recall: returns (score, memory) sorted desc",
      all(hits[i][0] >= hits[i + 1][0] for i in range(len(hits) - 1)))

# Strength discounts: same text, but one memory nearly dormant.
s2 = MemoryStore()
fresh = s2.add_episode("the dog is called Bruno", "user", emb.embed("the dog is called Bruno"), now=8.0)
old = s2.add_episode("the dog is called Bruno", "user", emb.embed("the dog is called Bruno"), now=0.0)
h2 = recall(s2, q, now=8.0)
check("recall: fresher memory outranks decayed twin", h2[0][1] is fresh and h2[1][1] is old)

# Dormant excluded entirely (episode dormant by day 9).
h3 = recall(s2, q, now=9.0)
check("recall: dormant excluded", all(m is not old for _, m in h3))

# Superseded facts excluded; live fact beats equal episode on ties (facts scanned first).
s3 = MemoryStore()
f_old = s3.add_fact("The user's dog is called Rex", emb.embed("the dog is called Bruno"), now=0.0, provenance=[])
f_new = s3.add_fact("The user's dog is called Bruno", emb.embed("the dog is called Bruno"), now=0.0, provenance=[])
f_old.superseded_by = f_new.id
h4 = recall(s3, q, now=0.0)
check("recall: superseded fact excluded", all(m is not f_old for _, m in h4))
check("recall: live fact returned", any(m is f_new for _, m in h4))

# k cap.
s4 = MemoryStore()
for i in range(10):
    s4.add_episode("the dog is called Bruno", "user", emb.embed("the dog is called Bruno"), now=0.0)
check("recall: top-k cap", len(recall(s4, q, now=0.0)) == config.TOP_K)
check("recall: explicit k", len(recall(s4, q, now=0.0, k=2)) == 2)

print(f"\n{'RED' if FAILS else 'GREEN'}: {len(FAILS)} failing")
sys.exit(1 if FAILS else 0)
