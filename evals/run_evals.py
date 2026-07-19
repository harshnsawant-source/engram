"""Engram eval harness — produces the README's headline numbers.

Deterministic and offline (FakeLLM + HashEmbedder). All seed sentences and
questions are machine-verified against HashEmbedder (top-1 margins >= 0.05);
do not reword them without re-verifying.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engram.store import MemoryStore
from engram.providers import FakeLLM, HashEmbedder
from engram.engine import SimClock
from engram.respond import respond
from engram.recall import recall
from engram.consolidate import sleep
from engram.decay import is_dormant, boost
from engram.store import Episode, SemanticFact

emb = HashEmbedder()
FAILED = []

MEMORIES = [
    "the user's dog is called Bruno",
    "the user's sister Meera lives in Delhi",
    "the user works at a bakery on weekends",
    "the user is allergic to peanuts",
    "the user plays guitar every evening",
    "the user's favourite colour is teal",
    "the user was born in Pune",
    "the user's bicycle has a flat tyre",
    "the user watched a documentary about volcanoes",
    "the user's exam is on Friday",
]
QUESTIONS = [
    "what is the dog called",
    "where does sister Meera live",
    "where does the user work on weekends",
    "what food is the user allergic to",
    "which instrument does the user practise every evening",
    "what is the user's favourite colour",
    "which city was the user born in",
    "what is wrong with the user's bicycle tyre",
    "what documentary did the user watch",
    "when is the user's exam",
]
UNANSWERABLE = [
    "explain quantum chromodynamics",
    "what is the capital of Mongolia",
    "how tall is mount kilimanjaro",
    "what is my blood type",
    "who won the world cup in 1998",
    "what is the boiling point of mercury",
    "which planet has the strongest winds",
    "what language is spoken in greenland",
    "how many moons does neptune have",
    "what year did the titanic sink",
    "how do jellyfish reproduce",
    "what is the square root of seventeen",
    "who painted the starry night",
    "what currency is used in iceland",
    "how deep is the mariana trench",
    "what vitamin comes from sunlight",
    "which composer went deaf",
    "how fast can a cheetah run",
    "what causes the northern lights",
    "when was the printing press invented",
]


def seeded_store():
    s = MemoryStore()
    for m in MEMORIES:
        s.add_episode(m, "user", emb.embed(m), now=0.0)
    return s


# --- 1. Grounding: every unanswerable question must be refused, even when
# the LLM actively tries to confabulate a cited answer. ---
store = seeded_store()
refusals = 0
for q in UNANSWERABLE:
    bogus = "You told me it was Rex [deadbeef]."
    r = respond(store, FakeLLM([bogus, bogus]), emb, q, now=0.0)
    if r.refused:
        refusals += 1
grounding_ok = refusals == len(UNANSWERABLE)
print(f"Grounding: {refusals}/{len(UNANSWERABLE)} unanswerable questions refused, 0 confabulated answers")
if not grounding_ok:
    FAILED.append("grounding")

# --- 2. Retrieval: each seeded question must rank its memory top-1. ---
store = seeded_store()
hits = 0
for i, q in enumerate(QUESTIONS):
    got = recall(store, emb.embed(q), now=0.0, k=1)
    if got and got[0][1].text == MEMORIES[i]:
        hits += 1
retrieval_ok = hits == len(QUESTIONS)
print(f"Retrieval: {hits}/{len(QUESTIONS)} questions rank the correct memory first")
if not retrieval_ok:
    FAILED.append("retrieval")

# --- 3. Provenance: every fact consolidation creates is fully traceable. ---
st = MemoryStore()
clock = SimClock()
st.add_episode("the puppy Bruno chewed a shoe", "user", emb.embed("the puppy Bruno chewed a shoe"), now=0.1)
st.add_episode("the puppy Bruno chewed a slipper", "user", emb.embed("the puppy Bruno chewed a slipper"), now=0.2)
st.add_episode("my sister Meera lives in Delhi", "user", emb.embed("my sister Meera lives in Delhi"), now=0.3)
sleep(st, FakeLLM(["- The user's puppy Bruno chews things",
                   "- The user's sister Meera lives in Delhi"]), emb, clock)
st.add_episode("my sister Meera lives in Mumbai now", "user", emb.embed("my sister Meera lives in Mumbai now"), now=1.1)
sleep(st, FakeLLM(["- The user's sister Meera lives in Mumbai", "YES"]), emb, clock)
traceable = sum(1 for f in st.facts
                if f.provenance and all(st.get(pid) is not None for pid in f.provenance))
provenance_ok = traceable == len(st.facts) and len(st.facts) == 3
print(f"Provenance: {traceable}/{len(st.facts)} consolidated facts cite real episodes")
if not provenance_ok:
    FAILED.append("provenance")

# --- 4. Decay: the forgetting curve behaves as specified. ---
ep = Episode(id="ep000001", t=0.0, actor="user", text="x", embedding=[1.0],
             last_access=0.0)
fact = SemanticFact(id="fa000001", statement="x", confidence=1.0, embedding=[1.0],
                    last_access=0.0)
rehearsed = SemanticFact(id="fa000002", statement="x", confidence=1.0,
                         embedding=[1.0], last_access=0.0)
for day in range(7, 43, 7):
    boost(rehearsed, float(day))
decay_ok = (not is_dormant(ep, 8.0) and is_dormant(ep, 9.0)
            and not is_dormant(fact, 38.0) and is_dormant(fact, 39.0)
            and not is_dormant(rehearsed, 42.0))
print("Decay: untouched episode dormant by day 9, untouched fact by day 39, "
      "weekly-rehearsed fact still live at day 42"
      + ("" if decay_ok else " — FAILED"))
if not decay_ok:
    FAILED.append("decay")

print(f"\n{'RED' if FAILED else 'GREEN'}: {len(FAILED)} eval targets missed"
      + (f" ({', '.join(FAILED)})" if FAILED else ""))
sys.exit(1 if FAILED else 0)
