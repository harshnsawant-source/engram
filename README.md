# Engram

A cognitive memory engine for LLM agents: episodic-to-semantic
consolidation, a real forgetting curve, and provenance-grounded recall
that cites its memories or refuses.

**Live demo: https://engram-blue.vercel.app** — chat with it, then press
Sleep and watch your conversation consolidate into memory.

Most "agent memory" is a vector store that only ever grows. Engram is a
memory *system*: raw episodes consolidate into semantic facts during a
sleep cycle, unused memories fade (and rehearsed ones strengthen), every
answer cites the exact memories it came from, and when the engine has no
grounded answer it says "I don't remember anything about that." instead
of guessing.

## Measured, not vibes

All numbers come from the deterministic offline eval harness
(`python evals/run_evals.py`), which runs as part of the test battery.
The harness uses a scripted fake LLM and a hash embedder, so these numbers
test the engine's logic. They are not a measurement of a live model, and
the live demo has not been scored this way.

| Eval | Result |
|---|---|
| Grounding: unanswerable questions against a confabulating LLM (the engine refuses at retrieval or the verifier blocks the fabricated citation) | **20/20 refused, 0 confabulations** |
| Retrieval: seeded questions ranking the correct memory first | **10/10** |
| Provenance: consolidated facts fully traceable to real episodes | **3/3** |
| Forgetting curve: untouched episode dormant by sim-day 9, untouched fact by day 39, weekly-rehearsed fact alive at day 42 | **asserted from the decay math** |

## How it works

- **Episodes vs facts.** Chat turns append raw episodes. Semantic facts
  are created ONLY by consolidation — never directly by chat.
- **Sleep.** `engine.sleep()` advances a sim-day: related episodes
  cluster, an LLM distills each cluster into facts carrying the episode
  ids as provenance, duplicate facts strengthen the original,
  contradictions supersede the old fact (history kept), and a
  `DreamReport` records everything that was learned, strengthened,
  superseded, or forgotten overnight.
- **Forgetting is retrieval failure.** Every memory's strength decays
  exponentially (episode half-life 3 sim-days — 1 after consolidation,
  facts 14) and is boosted on retrieval. Below threshold, memories go
  dormant: excluded from recall, never deleted. Inspired by ACT-R's
  activation model; not claimed as a faithful simulation.
- **Refusal over confabulation.** Answers must cite memory ids, and every
  sentence must carry a citation. Each citation is checked against its
  memory by id and by shared content words. No grounded support means a
  verbatim refusal. This is a structural check, not proof that a sentence
  follows from its memory: a negated sentence can still pass, and so can a
  lead-in line that ends in a colon.

## Quickstart

Pure Python stdlib — no dependencies.

```python
from engram import MemoryEngine, MemoryStore, SimClock
from engram.providers_ollama import OllamaLLM, OllamaEmbedder  # local, free

engine = MemoryEngine(MemoryStore(), OllamaLLM(), OllamaEmbedder(), SimClock())
engine.observe("I adopted a puppy today and named him Bruno")
reply = engine.respond("what is my puppy called?")   # cited or refused
report = engine.sleep()                              # consolidation + DreamReport
```

Runs against any LLM/embedder pair implementing
`complete(prompt, max_tokens)` / `embed(text)` — local Ollama models by
default; deterministic fakes power the entire test battery
(`python run_tests.py`, 9/9 suites, fully offline).

## Roadmap

- ~~Live web demo~~ — shipped: [the demo above](https://engram-blue.vercel.app)
  runs this engine behind two stateless serverless functions; your memory
  store lives in your browser, so every visitor is isolated by construction.

Built by [Harsh Sawant](mailto:harshnsawant@gmail.com).
