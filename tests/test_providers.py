import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FAILS = []
def check(name, ok):
    print(("ok   " if ok else "FAIL ") + name)
    if not ok:
        FAILS.append(name)

from engram.providers import FakeLLM, HashEmbedder

llm = FakeLLM(["first", "second"])
check("fakellm: pops in order", llm.complete("p1") == "first" and llm.complete("p2") == "second")
check("fakellm: records prompts", llm.prompts == ["p1", "p2"])
check("fakellm: empty when exhausted", llm.complete("p3") == "")

emb = HashEmbedder()
v = emb.embed("Bruno the dog")
check("hashembed: deterministic", v == emb.embed("Bruno the dog"))
check("hashembed: 256 dims", len(v) == 256)
check("hashembed: unit norm", abs(sum(x * x for x in v) - 1.0) < 1e-9)
check("hashembed: empty text is zero vector", sum(HashEmbedder().embed("") ) == 0.0)

def cos(a, b):
    return sum(x * y for x, y in zip(a, b))

dog_q = emb.embed("what is the dog called")
dog_m = emb.embed("the dog is called Bruno")
car_m = emb.embed("my car needs new tyres soon")
check("hashembed: related text scores higher", cos(dog_q, dog_m) > cos(dog_q, car_m))

print(f"\n{'RED' if FAILS else 'GREEN'}: {len(FAILS)} failing")
sys.exit(1 if FAILS else 0)
