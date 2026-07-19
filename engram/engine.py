"""MemoryEngine facade + SimClock. Time is sim-days; nothing here reads
the wall clock. sleep()/consolidation arrives in slice 2."""

import math

from . import config
from .decay import current_strength, is_dormant
from .recall import cosine
from .respond import respond as _respond


class SimClock:
    def __init__(self, start=0.0):
        self._t = float(start)

    def now(self):
        return self._t

    def advance_minutes(self, minutes):
        self._t += minutes / 1440.0

    def advance_to_next_day(self):
        self._t = math.floor(self._t) + 1.0


class MemoryEngine:
    def __init__(self, store, llm, embedder, clock):
        self.store = store
        self.llm = llm
        self.embedder = embedder
        self.clock = clock

    def observe(self, text, actor="user"):
        return self.store.add_episode(text, actor,
                                      self.embedder.embed(text), self.clock.now())

    def respond(self, message):
        self.clock.advance_minutes(1)
        # Recall BEFORE storing the message: a just-stored question would
        # outrank real memories and get cited back at the user (self-match).
        reply = _respond(self.store, self.llm, self.embedder,
                         message, self.clock.now())
        self.observe(message, "user")
        if not reply.refused:
            self.observe(reply.text, "agent")
        return reply

    def graph(self):
        now = self.clock.now()
        nodes, edges = [], []
        for ep in self.store.episodes:
            nodes.append(self._node(ep, "episode", ep.text, now))
        live_facts = [f for f in self.store.facts if f.superseded_by is None]
        for f in self.store.facts:
            nodes.append(self._node(f, "fact", f.statement, now))
            for ep_id in f.provenance:
                edges.append({"source": f.id, "target": ep_id, "kind": "provenance"})
            if f.superseded_by:
                edges.append({"source": f.id, "target": f.superseded_by,
                              "kind": "supersedes"})
        for i, a in enumerate(live_facts):
            for b in live_facts[i + 1:]:
                if cosine(a.embedding, b.embedding) > config.SIM_EDGE_THRESHOLD:
                    edges.append({"source": a.id, "target": b.id, "kind": "similar"})
        return {"nodes": nodes, "edges": edges}

    @staticmethod
    def _node(mem, kind, label, now):
        return {"id": mem.id, "type": kind, "label": label[:60],
                "strength": round(current_strength(mem, now), 4),
                "dormant": is_dormant(mem, now)}
