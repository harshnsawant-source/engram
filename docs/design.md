# Engram — technical design

A cognitive memory engine: a memory-augmented conversational agent with
episodic-to-semantic consolidation, forgetting and reinforcement, and
provenance-grounded recall that refuses to confabulate.

## Non-goals

- Not a world model (no prediction or simulation of environments).
- Not a brain simulation. All cognitive-science language is "inspired by"
  (ACT-R activation, consolidation during sleep) — never claimed as
  faithful modeling.
- No accounts, no server-side persistence, no third-party dependencies,
  no vector database.

## Engine (`engram/`)

Pure Python, stdlib only. One facade:

```python
MemoryEngine(store, llm, embedder, clock)
  .observe(text, actor)      # append an episode
  .respond(message)          # -> Reply(text, citations, refused)
  .sleep()                   # consolidation cycle -> DreamReport
  .graph()                   # -> {nodes, edges} for a UI
```

Providers are duck-typed (`llm.complete(prompt, max_tokens)`,
`embedder.embed(text)`): Ollama locally, deterministic fakes
(`FakeLLM`, 256-dim `HashEmbedder`) for the entire offline test battery.
Time is sim-days (float) and is always passed in — nothing inside the
engine reads the wall clock, so decay is testable and time-warpable.

### Data model (JSON-serializable `MemoryStore`)

- **Episode** (append-only): raw record of a turn — `id, t, actor, text,
  embedding, strength, last_access, access_count, consolidated`.
- **SemanticFact**: distilled belief — `id, statement, confidence,
  embedding, strength, last_access, access_count,
  provenance: [episode_ids], born_t, superseded_by`.
- Facts are created ONLY by consolidation, never directly by chat. The
  episodic/semantic separation is the core claim: raw experience and
  distilled belief are different stores with different lifetimes.

### Forgetting and reinforcement (ACT-R-inspired)

- `strength(t) = strength_last * 2 ** (-(t - t_last) / half_life)`;
  retrieval boosts strength (+0.3, capped at 1.0) and re-anchors.
- Half-lives (sim-days): episode 3.0, consolidated episode 1.0 (the gist
  survives, the detail fades), fact 14.0.
- Retrieval score = `cosine * (0.5 + 0.5 * strength)`.
- Strength < 0.15 → **dormant**: excluded from recall, never deleted.
  Forgetting is retrieval failure.

### Consolidation (`sleep()`)

1. Advance the clock to the next sim-day.
2. Cluster unconsolidated, non-dormant episodes by embedding similarity
   (greedy single-link).
3. One LLM call distills each cluster into fact statements carrying the
   cluster's episode ids as provenance.
4. Merge: a statement matching an existing live fact strengthens it
   (boost + provenance union); a contradiction (LLM judge) creates the
   new fact and marks the old one superseded — history kept, recall
   prefers the newer.
5. Consolidated episodes decay faster; a **DreamReport** records what was
   learned, strengthened, superseded, and what went dormant overnight.

### Grounded recall and refusal (`respond()`)

1. Recall runs BEFORE the message is stored (otherwise the just-stored
   question outranks real memories and gets cited back at the user).
2. Best retrieval score below threshold → verbatim refusal:
   "I don't remember anything about that."
3. Otherwise the LLM answers only from retrieved memories, citing ids
   inline; every citation is verified against its memory. Failed
   citations get one retry with the failing memories removed, then
   refusal. Cited memories are boosted — rehearsal strengthens.

## Evals (`evals/run_evals.py`, battery suite)

Deterministic and offline; the README table is this harness's output:

- **Grounding**: 20 unanswerable questions against a confabulating LLM →
  20/20 refused (threshold or verifier), 0 confabulations.
- **Retrieval**: 10 seeded questions → 10/10 rank the correct memory
  first.
- **Provenance**: every consolidated fact fully traceable to real
  episodes.
- **Decay**: untouched episode dormant by day 9, untouched fact by day 39
  (`half_life * log2(1/0.15)`), weekly-rehearsed fact alive at day 42.

## Roadmap: live web demo

Stateless-server architecture: the memory store travels as JSON in the
visitor's browser; serverless functions run one engine step per request
(chat) or one consolidation cycle (a "sleep" button that advances a
sim-day). Each visitor is isolated by construction, no database. UI:
chat beside a memory panel — graph (nodes sized/faded by strength,
provenance and supersedes edges), episodes, facts, and the DreamReport
animated after each sleep.
