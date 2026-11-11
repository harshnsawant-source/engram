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

# Citation whose sentence shares no content words with the memory -> fails; no surviving memories -> refuse.
s, ep = seeded()
llm = FakeLLM(["Purple elephants juggle nicely [aaaa1111]."])
r = respond(s, llm, emb, "what is the dog called", now=0.0)
check("respond: unsupported claim with no surviving memories refuses", r.refused and r.text == REFUSAL_TEXT)
check("respond: failed verification boosts nothing", ep.access_count == 0)

# A reply with no citations at all is not grounded -> retry -> refuse.
s, ep = seeded()
llm = FakeLLM(["The dog is called Bruno.", "The dog is called Bruno."])
r = respond(s, llm, emb, "what is the dog called", now=0.0)
check("respond: citation-free reply refused", r.refused)

# Narrowed-context retry: first citation fails, OTHER memories survive,
# a genuine second LLM call answers from the smaller context.
s = MemoryStore()
a = s.add_episode("the dog is called Bruno", "user", emb.embed("the dog is called Bruno"), now=0.0)
a.id = "aaaa1111"
b = s.add_episode("the dog likes long walks", "user", emb.embed("the dog likes long walks"), now=0.0)
b.id = "bbbb2222"
llm = FakeLLM(["Purple elephants juggle nicely [aaaa1111].",
               "The dog likes long walks [bbbb2222]."])
r = respond(s, llm, emb, "what is the dog called", now=0.0)
check("respond: narrowed retry succeeds citing a survivor",
      not r.refused and r.citations == ["bbbb2222"])
check("respond: narrowed retry made a second LLM call", len(llm.prompts) == 2)
check("respond: failed memory removed from retry context",
      "aaaa1111" not in llm.prompts[1])
check("respond: survivor boosted, failed memory not",
      b.access_count == 1 and a.access_count == 0)

# Empty-text episode in the retrieved set must not crash prompt building.
s, ep = seeded()
s.add_episode("", "user", emb.embed(""), now=0.0)
llm = FakeLLM(["The dog is called Bruno [aaaa1111]."])
r = respond(s, llm, emb, "what is the dog called", now=0.0)
check("respond: empty-text episode does not crash prompting", not r.refused)

# 2026-11-12 (external review, reproduced first): a cited sentence used to carry an
# uncited claim along with it. Every non-empty sentence must now cite a memory.
from engram.respond import _verify


class _M:
    def __init__(self, i, t):
        self.id, self.text = i, t


_allergy = {"aaaa1111": _M("aaaa1111", "The user is allergic to peanuts")}
_ok, _failed = _verify("The user is allergic to peanuts [aaaa1111]. Their birthday is in May.", _allergy)
check("verify: uncited extra sentence fails verification", bool(_failed))
_ok, _failed = _verify("The user is allergic to peanuts [aaaa1111].", _allergy)
check("verify: fully cited answer still passes", _ok == ["aaaa1111"] and not _failed)
_ok, _failed = _verify("The user is allergic to peanuts [aaaa1111]. ", _allergy)
check("verify: trailing whitespace is not an uncited sentence", not _failed)
# Known, documented limit: this is a structural check, not entailment.
_ok, _failed = _verify("The user is not allergic to peanuts [aaaa1111].", _allergy)
check("verify: negation still passes (documented limit, not a guarantee)", not _failed)

print(f"\n{'RED' if FAILS else 'GREEN'}: {len(FAILS)} failing")
sys.exit(1 if FAILS else 0)
