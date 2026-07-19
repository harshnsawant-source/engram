"""Live end-to-end check against local Ollama: observe -> respond -> sleep.
Run manually: python scripts/live_demo.py  (needs nemotron-3-nano:4b and
nomic-embed-text pulled). Output quality depends on the 4B model; the check
is that the full cycle runs and the report is honest, not that the prose is
pretty."""

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engram import MemoryEngine, MemoryStore, SimClock
from engram.providers_ollama import OllamaLLM, OllamaEmbedder

eng = MemoryEngine(MemoryStore(), OllamaLLM(), OllamaEmbedder(), SimClock())
for text in ["I adopted a puppy today and named him Bruno",
             "Bruno chewed my running shoe this evening",
             "my sister Meera is moving to Delhi next month"]:
    eng.observe(text)
    print(f"observed: {text}")

r = eng.respond("what is my puppy called?")
print(f"\nrespond -> refused={r.refused}\n  {r.text}\n  citations={r.citations}")

rep = eng.sleep()
print(f"\nsleep -> day {rep.day}: {rep.episodes_consolidated} episodes consolidated")
for f in rep.learned:
    print(f"  learned: {f['statement']}")
for f in rep.strengthened:
    print(f"  strengthened: {f['statement']}")

r2 = eng.respond("tell me about my puppy")
print(f"\nrespond after sleep -> refused={r2.refused}\n  {r2.text}\n  citations={r2.citations}")
print(f"\nstore: {len(eng.store.episodes)} episodes, {len(eng.store.facts)} facts")
