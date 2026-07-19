import json
import uuid
from dataclasses import dataclass, field, asdict
from typing import List, Optional

from . import config
from .decay import current_strength


def _new_id():
    return uuid.uuid4().hex[:8]


@dataclass
class Episode:
    id: str
    t: float
    actor: str
    text: str
    embedding: List[float]
    strength: float = 1.0
    last_access: float = 0.0
    access_count: int = 0
    consolidated: bool = False


@dataclass
class SemanticFact:
    id: str
    statement: str
    confidence: float
    embedding: List[float]
    strength: float = 1.0
    last_access: float = 0.0
    access_count: int = 0
    provenance: List[str] = field(default_factory=list)
    born_t: float = 0.0
    superseded_by: Optional[str] = None


class MemoryStore:
    def __init__(self):
        self.episodes = []
        self.facts = []

    def add_episode(self, text, actor, embedding, now):
        ep = Episode(id=_new_id(), t=now, actor=actor, text=text,
                     embedding=list(embedding), last_access=now)
        self.episodes.append(ep)
        self._enforce_cap(now)
        return ep

    def add_fact(self, statement, embedding, now, provenance, confidence=1.0):
        fact = SemanticFact(id=_new_id(), statement=statement, confidence=confidence,
                            embedding=list(embedding), last_access=now,
                            provenance=list(provenance), born_t=now)
        self.facts.append(fact)
        return fact

    def get(self, mem_id):
        for m in self.episodes:
            if m.id == mem_id:
                return m
        for m in self.facts:
            if m.id == mem_id:
                return m
        return None

    def _enforce_cap(self, now):
        while len(self.episodes) > config.MAX_EPISODES:
            dormant = [e for e in self.episodes
                       if current_strength(e, now) < config.DORMANT_THRESHOLD]
            victim = dormant[0] if dormant else self.episodes[0]
            self.episodes.remove(victim)

    def to_json(self):
        return json.dumps({
            "episodes": [asdict(e) for e in self.episodes],
            "facts": [asdict(f) for f in self.facts],
        })

    @classmethod
    def from_json(cls, s):
        data = json.loads(s)
        store = cls()
        store.episodes = [Episode(**e) for e in data.get("episodes", [])]
        store.facts = [SemanticFact(**f) for f in data.get("facts", [])]
        return store
