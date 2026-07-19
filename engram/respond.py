"""Grounded reply generation: cite memories or refuse. Never guess."""

import re
from dataclasses import dataclass, field
from typing import List

from . import config
from .decay import boost
from .recall import recall

REFUSAL_TEXT = "I don't remember anything about that."

_CITE = re.compile(r"\[([0-9a-f]{8})\]")
_WORD = re.compile(r"[a-z0-9']+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_STOPWORDS = {
    "that", "this", "with", "from", "have", "been", "were", "will", "would",
    "could", "should", "your", "they", "them", "their", "there", "here",
    "what", "when", "where", "which", "about", "because", "does", "did",
    "doing", "into", "over", "very", "just", "some", "then", "than", "user",
}


@dataclass
class Reply:
    text: str
    citations: List[str] = field(default_factory=list)
    refused: bool = False


def _refusal():
    return Reply(REFUSAL_TEXT, [], True)


def strip_citations(text):
    return re.sub(r"\s*\[[0-9a-f]{8}\]", "", text)


def _memory_text(mem):
    return mem.text if hasattr(mem, "text") else mem.statement


def _content_words(text):
    return {w for w in _WORD.findall(text.lower())
            if len(w) >= 4 and w not in _STOPWORDS}


def _prompt(message, hits):
    lines = [f"[{m.id}] {_memory_text(m)}" for _, m in hits]
    return (
        "You are an assistant with a personal memory of this user. Answer ONLY "
        "from the memories below. Cite the id of every memory you use inline, "
        "like [ab12cd34]. If the memories do not answer the question, say you "
        "don't remember.\n\nMemories:\n" + "\n".join(lines)
        + f"\n\nUser: {message}\nAnswer:"
    )


def _verify(reply_text, allowed):
    """Return (cited_ok, failed). Every citation must reference a retrieved
    memory AND share >=1 content word with it inside its own sentence.
    No citations at all counts as failure (ungrounded reply)."""
    all_cited = _CITE.findall(reply_text)
    if not all_cited:
        return [], ["<none>"]
    failed = []
    for sentence in _SENTENCE_SPLIT.split(reply_text):
        for cid in _CITE.findall(sentence):
            mem = allowed.get(cid)
            if mem is None or not (_content_words(sentence) & _content_words(_memory_text(mem))):
                failed.append(cid)
    cited_ok = [c for c in dict.fromkeys(all_cited) if c not in failed]
    return cited_ok, failed


def respond(store, llm, embedder, message, now):
    qvec = embedder.embed(message)
    hits = recall(store, qvec, now)
    if not hits or hits[0][0] < config.REFUSAL_THRESHOLD:
        return _refusal()

    for attempt in range(2):
        allowed = {m.id: m for _, m in hits}
        reply_text = llm.complete(_prompt(message, hits))
        cited_ok, failed = _verify(reply_text, allowed)
        if not failed:
            for cid in cited_ok:
                boost(allowed[cid], now)
            return Reply(reply_text, cited_ok, False)
        # Retry once with the failing memories removed from the context.
        hits = [(s, m) for s, m in hits if m.id not in failed]
        if not hits:
            return _refusal()
    return _refusal()
