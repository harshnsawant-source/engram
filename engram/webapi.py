"""Stateless request core for the web demo. The browser holds {store, t} and
posts it with every request; this module validates, runs one engine step, and
returns the new state. Pure logic — fully offline-testable; the files in api/
are thin HTTP wrappers around run_handler()."""

import json
from dataclasses import asdict

from .engine import MemoryEngine, SimClock
from .providers import FakeLLM, HashEmbedder
from .store import MemoryStore

MAX_MESSAGE_CHARS = 500
MAX_BODY_BYTES = 1_000_000
MAX_STORE_FACTS = 400
MAX_EMBEDDING_DIMS = 4096
BUSY_MESSAGE = "demo is busy, try again in a minute"

SEED_EPISODES = [
    "I adopted a scruffy terrier and named him Biscuit",
    "Biscuit buried my house key in a flowerpot",
    "my book club is reading a novel about lighthouses",
    "I finally fixed the squeaky hinge on the balcony door",
    "tried a new recipe: lemon rice with roasted peanuts",
    "my cousin Asha sent postcards from her trip to Ladakh",
]


class WebApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


class ProviderBusy(Exception):
    """Raised by providers when the upstream quota is exhausted (HTTP 429)."""


def seed_store(embedder, now=0.0):
    store = MemoryStore()
    for text in SEED_EPISODES:
        store.add_episode(text, "user", embedder.embed(text), now)
    return store


def _is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _valid_embedding(emb):
    return (isinstance(emb, list) and len(emb) <= MAX_EMBEDDING_DIMS
            and all(_is_num(x) for x in emb))


def _validate_store(obj):
    if not isinstance(obj, dict):
        raise WebApiError(400, "store must be an object")
    episodes = obj.get("episodes", [])
    facts = obj.get("facts", [])
    if not isinstance(episodes, list) or not isinstance(facts, list):
        raise WebApiError(400, "malformed store")
    from . import config
    if len(episodes) > config.MAX_EPISODES or len(facts) > MAX_STORE_FACTS:
        raise WebApiError(400, "store too large")
    try:
        store = MemoryStore.from_json(json.dumps(obj))
    except (KeyError, TypeError, ValueError):
        raise WebApiError(400, "malformed store")
    for e in store.episodes:
        if not (isinstance(e.id, str) and isinstance(e.actor, str)
                and isinstance(e.text, str) and isinstance(e.consolidated, bool)
                and _is_num(e.t) and _is_num(e.strength) and _is_num(e.last_access)
                and isinstance(e.access_count, int)
                and not isinstance(e.access_count, bool)
                and _valid_embedding(e.embedding)):
            raise WebApiError(400, "malformed store")
    for f in store.facts:
        if not (isinstance(f.id, str) and isinstance(f.statement, str)
                and _is_num(f.confidence) and _is_num(f.strength)
                and _is_num(f.last_access) and _is_num(f.born_t)
                and isinstance(f.access_count, int)
                and not isinstance(f.access_count, bool)
                and isinstance(f.provenance, list)
                and all(isinstance(p, str) for p in f.provenance)
                and (f.superseded_by is None or isinstance(f.superseded_by, str))
                and _valid_embedding(f.embedding)):
            raise WebApiError(400, "malformed store")
    return store


def _engine(payload, llm, embedder):
    t = payload.get("t", 0.0)
    if not isinstance(t, (int, float)) or isinstance(t, bool):
        raise WebApiError(400, "t must be a number")
    raw = payload.get("store")
    store = seed_store(embedder) if raw is None else _validate_store(raw)
    return MemoryEngine(store, llm, embedder, SimClock(start=float(t)))


def _state(engine):
    return {"store": json.loads(engine.store.to_json()), "t": engine.clock.now(),
            "graph": engine.graph()}


def handle_chat(payload, llm, embedder):
    message = payload.get("message")
    if not isinstance(message, str) or not message.strip():
        raise WebApiError(400, "message must be a non-empty string")
    if len(message) > MAX_MESSAGE_CHARS:
        raise WebApiError(400, f"message too long (max {MAX_MESSAGE_CHARS} chars)")
    engine = _engine(payload, llm, embedder)
    reply = engine.respond(message)
    out = _state(engine)
    out["reply"] = {"text": reply.text, "citations": reply.citations,
                    "refused": reply.refused}
    return out


def handle_sleep(payload, llm, embedder):
    engine = _engine(payload, llm, embedder)
    report = engine.sleep()
    out = _state(engine)
    out["report"] = asdict(report)
    return out


def providers_from_env(environ):
    if environ.get("ENGRAM_FAKE"):
        return FakeLLM([]), HashEmbedder()
    key = environ.get("GEMINI_API_KEY")
    if key:
        from .providers_gemini import GeminiEmbedder, GeminiLLM
        return GeminiLLM(key), GeminiEmbedder(key)
    from .providers_ollama import OllamaEmbedder, OllamaLLM
    return OllamaLLM(), OllamaEmbedder()


_HANDLERS = {"chat": handle_chat, "sleep": handle_sleep}


def run_handler(name, body_bytes, environ):
    if len(body_bytes) > MAX_BODY_BYTES:
        return 400, {"error": "body too large"}
    try:
        payload = json.loads(body_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        return 400, {"error": "body must be valid JSON"}
    if not isinstance(payload, dict):
        return 400, {"error": "body must be a JSON object"}
    fn = _HANDLERS.get(name)
    if fn is None:
        return 404, {"error": "unknown endpoint"}
    llm, embedder = providers_from_env(environ)
    try:
        return 200, fn(payload, llm, embedder)
    except WebApiError as exc:
        return exc.status, {"error": exc.message}
    except ProviderBusy:
        return 503, {"error": BUSY_MESSAGE}
    except Exception:
        return 500, {"error": "internal error"}
