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
