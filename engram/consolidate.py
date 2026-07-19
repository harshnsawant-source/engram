"""The sleep cycle: episodes cluster, an LLM distills them into semantic
facts with provenance, near-duplicates strengthen existing facts, and
contradictions supersede them. Facts are created ONLY here, never by chat."""

from dataclasses import dataclass, field
from typing import List

from . import config
from .recall import cosine


@dataclass
class DreamReport:
    day: float
    learned: List[dict] = field(default_factory=list)        # {"id", "statement"}
    strengthened: List[dict] = field(default_factory=list)   # {"id", "statement"}
    superseded: List[dict] = field(default_factory=list)     # {"new_id", "old_id", "statement"}
    went_dormant: List[str] = field(default_factory=list)    # memory ids
    episodes_consolidated: int = 0


def cluster_episodes(episodes, threshold):
    clusters = []
    for ep in episodes:
        placed = False
        for cl in clusters:
            if any(cosine(ep.embedding, m.embedding) > threshold for m in cl):
                cl.append(ep)
                placed = True
                break
        if not placed:
            clusters.append([ep])
    return clusters


def parse_facts(reply):
    facts = []
    for line in reply.splitlines():
        s = line.strip()
        if s.startswith("- ") and s[2:].strip():
            facts.append(s[2:].strip())
    return facts


def distill_prompt(cluster):
    lines = "\n".join(f"[{e.id}] {e.text}" for e in cluster)
    return (
        "You are consolidating a user's memories during sleep. Below are "
        "related episodes from the user's recent days. Distill them into "
        "concise factual statements about the user or their world. Rules: "
        "only facts directly supported by the episodes; each fact on its own "
        'line starting with "- "; if nothing is worth keeping, reply NONE.'
        f"\n\nEpisodes:\n{lines}\n\nFacts:"
    )


def contradiction_prompt(a, b):
    return (
        "Do these two statements contradict each other?\n"
        f"A: {a}\nB: {b}\n"
        "Answer only YES or NO.\nAnswer:"
    )


def _best_live_match(facts, embedding):
    best, best_cos = None, config.MERGE_THRESHOLD
    for f in facts:
        if f.superseded_by is None:
            c = cosine(embedding, f.embedding)
            if c > best_cos:
                best, best_cos = f, c
    return best


def _contradicts(llm, existing_statement, new_statement):
    reply = llm.complete(contradiction_prompt(existing_statement, new_statement))
    return reply.strip().upper().startswith("YES")


def sleep(store, llm, embedder, clock):
    from .decay import boost, is_dormant  # local import keeps module deps one-way

    pre = clock.now()
    live_before = {m.id for m in store.episodes + store.facts
                   if not is_dormant(m, pre)}
    clock.advance_to_next_day()
    now = clock.now()
    report = DreamReport(day=now)

    pending = [e for e in store.episodes
               if not e.consolidated and not is_dormant(e, now)]
    for cluster in cluster_episodes(pending, config.CLUSTER_THRESHOLD):
        cluster_ids = [e.id for e in cluster]
        for stmt in parse_facts(llm.complete(distill_prompt(cluster))):
            emb = embedder.embed(stmt)
            match = _best_live_match(store.facts, emb)
            if match is None:
                new = store.add_fact(stmt, emb, now, provenance=cluster_ids)
                report.learned.append({"id": new.id, "statement": new.statement})
            elif _contradicts(llm, match.statement, stmt):
                new = store.add_fact(stmt, emb, now, provenance=cluster_ids)
                match.superseded_by = new.id
                report.superseded.append({"new_id": new.id, "old_id": match.id,
                                          "statement": new.statement})
            else:
                boost(match, now)
                match.provenance = list(dict.fromkeys(match.provenance + cluster_ids))
                report.strengthened.append({"id": match.id,
                                            "statement": match.statement})
        for e in cluster:
            e.consolidated = True
        report.episodes_consolidated += len(cluster)

    report.went_dormant = [mid for mid in sorted(live_before)
                           if store.get(mid) is not None
                           and is_dormant(store.get(mid), now)]
    return report
