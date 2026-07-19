import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FAILS = []
def check(name, ok):
    print(("ok   " if ok else "FAIL ") + name)
    if not ok:
        FAILS.append(name)

from engram import MemoryEngine, MemoryStore, SimClock, Reply
from engram.providers import FakeLLM, HashEmbedder

clock = SimClock()
check("clock: starts at 0", clock.now() == 0.0)
clock.advance_minutes(1)
check("clock: minute advance", abs(clock.now() - 1 / 1440) < 1e-12)
clock.advance_to_next_day()
check("clock: next day lands on integer", clock.now() == 1.0)
clock.advance_to_next_day()
check("clock: next day from integer boundary", clock.now() == 2.0)

emb = HashEmbedder()
eng = MemoryEngine(MemoryStore(), FakeLLM([]), emb, SimClock())
ep = eng.observe("the dog is called Bruno")
check("engine: observe appends episode", eng.store.episodes == [ep] and ep.actor == "user")

# Grounded respond: recall runs BEFORE the message is stored (self-match hazard),
# then both the user message and the agent reply become episodes.
eng.llm.responses = [f"The dog is called Bruno [{ep.id}]."]
r = eng.respond("what is the dog called")
check("engine: grounded reply", not r.refused and r.citations == [ep.id])
check("engine: clock advanced by the turn", eng.clock.now() > 0.0)
texts = [e.text for e in eng.store.episodes]
check("engine: message and reply observed",
      "what is the dog called" in texts and any("Bruno" in t for t in texts))
check("engine: observed agent reply has citation markers stripped",
      any(t == "The dog is called Bruno." for t in texts))
mem_block = eng.llm.prompts[-1].split("Memories:\n", 1)[1].split("\n\nUser:", 1)[0]
check("engine: recall ran before the question was stored (self-match guard)",
      "what is the dog called" not in mem_block)

# Refusal path: nothing relevant -> refusal, and the refusal text is NOT observed.
before = len(eng.store.episodes)
r2 = eng.respond("explain quantum chromodynamics lagrangian")
check("engine: refusal on unknown topic", r2.refused)
check("engine: refusal not stored as agent episode",
      len(eng.store.episodes) == before + 1)  # only the user message was observed

# graph(): nodes for episodes+facts, provenance/supersedes edges, similarity edges.
s = MemoryStore()
e1 = s.add_episode("Bruno is a labrador", "user", emb.embed("Bruno is a labrador"), now=0.0)
f1 = s.add_fact("The user's dog Bruno is a labrador",
                emb.embed("Bruno is a labrador"), now=0.0, provenance=[e1.id])
f2 = s.add_fact("The user's dog Bruno is a labrador retriever",
                emb.embed("Bruno is a labrador dog"), now=0.0, provenance=[])
f_old = s.add_fact("The user's dog is called Rex", emb.embed("dog called Rex"),
                   now=0.0, provenance=[])
f_old.superseded_by = f1.id
g = MemoryEngine(s, FakeLLM([]), emb, SimClock()).graph()
ids = {n["id"] for n in g["nodes"]}
check("graph: all memories present", ids == {e1.id, f1.id, f2.id, f_old.id})
kinds = {(d["source"], d["target"], d["kind"]) for d in g["edges"]}
check("graph: provenance edge", (f1.id, e1.id, "provenance") in kinds)
check("graph: supersedes edge points new -> old", (f1.id, f_old.id, "supersedes") in kinds)
check("graph: similarity edge between near-twin facts",
      any(k == "similar" and {a, b} == {f1.id, f2.id} for a, b, k in kinds))
node = next(n for n in g["nodes"] if n["id"] == f1.id)
check("graph: node shape", node["type"] == "fact" and len(node["label"]) <= 60
      and 0.0 <= node["strength"] <= 1.0 and node["dormant"] is False)

check("exports: Reply importable from package root", Reply is not None)

print(f"\n{'RED' if FAILS else 'GREEN'}: {len(FAILS)} failing")
sys.exit(1 if FAILS else 0)
