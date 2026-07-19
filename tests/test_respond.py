import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FAILS = []
def check(name, ok):
    print(("ok   " if ok else "FAIL ") + name)
    if not ok:
        FAILS.append(name)

from engram.store import MemoryStore
from engram.providers import FakeLLM, HashEmbedder
from engram.respond import respond, Reply, REFUSAL_TEXT

emb = HashEmbedder()

def seeded():
    s = MemoryStore()
    ep = s.add_episode("the dog is called Bruno", "user", emb.embed("the dog is called Bruno"), now=0.0)
    ep.id = "aaaa1111"  # deterministic id for scripted replies
    return s, ep

# Empty store -> refuse, LLM never called.
llm = FakeLLM(["should never be used"])
r = respond(MemoryStore(), llm, emb, "what is the dog called", now=0.0)
check("respond: empty store refuses", r.refused and r.text == REFUSAL_TEXT and r.citations == [])
check("respond: refusal skips the LLM", llm.prompts == [])

# Unrelated question -> below threshold -> refuse.
s, ep = seeded()
r = respond(s, FakeLLM(["x"]), emb, "explain quantum chromodynamics lagrangian", now=0.0)
check("respond: low score refuses", r.refused)

# Grounded answer with a valid citation.
s, ep = seeded()
llm = FakeLLM(["The dog is called Bruno [aaaa1111]."])
r = respond(s, llm, emb, "what is the dog called", now=0.0)
check("respond: grounded answer not refused", not r.refused)
check("respond: citation extracted", r.citations == ["aaaa1111"])
check("respond: prompt carries memory id and text",
      "aaaa1111" in llm.prompts[0] and "Bruno" in llm.prompts[0])
check("respond: cited memory boosted", ep.access_count == 1)

# Unknown citation id -> retry once -> good second answer passes.
s, ep = seeded()
llm = FakeLLM(["The dog is called Bruno [deadbeef].", "The dog is called Bruno [aaaa1111]."])
r = respond(s, llm, emb, "what is the dog called", now=0.0)
check("respond: bad citation retries then succeeds", not r.refused and r.citations == ["aaaa1111"])
check("respond: retry actually called twice", len(llm.prompts) == 2)

# Citation whose sentence shares no content words with the memory -> fails; both tries bad -> refuse.
s, ep = seeded()
llm = FakeLLM(["Purple elephants juggle nicely [aaaa1111].",
               "Purple elephants juggle nicely [aaaa1111]."])
r = respond(s, llm, emb, "what is the dog called", now=0.0)
check("respond: unsupported claim refused after retry", r.refused and r.text == REFUSAL_TEXT)
check("respond: failed verification boosts nothing", ep.access_count == 0)

# A reply with no citations at all is not grounded -> retry -> refuse.
s, ep = seeded()
llm = FakeLLM(["The dog is called Bruno.", "The dog is called Bruno."])
r = respond(s, llm, emb, "what is the dog called", now=0.0)
check("respond: citation-free reply refused", r.refused)

print(f"\n{'RED' if FAILS else 'GREEN'}: {len(FAILS)} failing")
sys.exit(1 if FAILS else 0)
