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

# Ollama providers: constructible offline with the documented defaults.
# (No network calls in tests — the live path is scripts/live_demo.py.)
from engram.providers_ollama import OllamaLLM, OllamaEmbedder

ollm = OllamaLLM()
oemb = OllamaEmbedder()
check("ollama: llm defaults", ollm.model == "nemotron-3-nano:4b"
      and ollm.host == "http://localhost:11434" and ollm.timeout == 180)
check("ollama: embedder defaults", oemb.model == "nomic-embed-text"
      and oemb.host == "http://localhost:11434" and oemb.timeout == 60)
check("ollama: provider surface", callable(ollm.complete) and callable(oemb.embed))

# Hardening: trailing-slash hosts normalize; 200-with-error JSON surfaces loudly.
import engram.providers_ollama as po

check("ollama: trailing slash stripped", po.OllamaLLM(host="http://x:1/").host == "http://x:1"
      and po.OllamaEmbedder(host="http://x:1///").host == "http://x:1")

_real_post = po._post
po._post = lambda url, payload, timeout: {"error": "model not found"}
try:
    po.OllamaLLM().complete("hi")
    llm_raised = False
except RuntimeError:
    llm_raised = True
try:
    po.OllamaEmbedder().embed("hi")
    emb_raised = False
except RuntimeError:
    emb_raised = True
po._post = _real_post
check("ollama: error JSON raises for llm", llm_raised)
check("ollama: error JSON raises for embedder", emb_raised)

# Gemini providers: offline construction, defensive parsers, 429 -> ProviderBusy.
import engram.providers_gemini as pg
from engram.webapi import ProviderBusy

glm = pg.GeminiLLM("k")
gem = pg.GeminiEmbedder("k")
check("gemini: llm defaults", glm.model == "gemini-flash-lite-latest" and glm.timeout == 60)
check("gemini: embedder defaults", gem.model == "gemini-embedding-001" and gem.dims == 256)

check("gemini: parse candidates text", pg._parse_text(
    {"candidates": [{"content": {"parts": [{"text": "a"}, {"text": "b"}]}}]}) == "ab")
check("gemini: parse empty candidates", pg._parse_text({"candidates": []}) == ""
      and pg._parse_text({}) == "")
check("gemini: parse embedding.values",
      pg._parse_embedding({"embedding": {"values": [1.0, 2.0]}}) == [1.0, 2.0])
check("gemini: parse embeddings[0].values",
      pg._parse_embedding({"embeddings": [{"values": [3.0]}]}) == [3.0])
check("gemini: parse embeddings[0].value",
      pg._parse_embedding({"embeddings": [{"value": [4.0]}]}) == [4.0])
check("gemini: parse unknown shape is empty", pg._parse_embedding({}) == [])

import urllib.error
_real_gpost = pg._post
def _busy(url, payload, headers, timeout):
    raise urllib.error.HTTPError(url, 429, "quota", {}, None)
pg._post = _busy
try:
    glm.complete("hi")
    busy_llm = False
except ProviderBusy:
    busy_llm = True
try:
    gem.embed("hi")
    busy_emb = False
except ProviderBusy:
    busy_emb = True
pg._post = _real_gpost
check("gemini: 429 raises ProviderBusy (llm + embedder)", busy_llm and busy_emb)

# 2026-11-12: Google moved gemini-flash-lite-latest to gemini-3.5-flash-lite, which
# rejects thinkingConfig.thinkingBudget with 400 INVALID_ARGUMENT but accepts
# thinkingLevel. The LLM must try the current setting first and fall back, so the
# next alias move can't take the demo down again.
_sent = []
def _picky(url, payload, headers, timeout):
    thinking = payload["generationConfig"].get("thinkingConfig")
    _sent.append(thinking)
    if thinking != {"thinkingBudget": 0}:  # an older model: only accepts the budget form
        raise urllib.error.HTTPError(url, 400, "INVALID_ARGUMENT", {}, None)
    return {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}
pg._post = _picky
try:
    fell_back = glm.complete("hi") == "ok"
except Exception:
    fell_back = False
check("gemini: 400 on one thinking form falls back to the next", fell_back and len(_sent) >= 2)
check("gemini: tries thinkingLevel=minimal first", bool(_sent) and _sent[0] == {"thinkingLevel": "minimal"})

def _new_model(url, payload, headers, timeout):
    if payload["generationConfig"].get("thinkingConfig") == {"thinkingBudget": 0}:
        raise urllib.error.HTTPError(url, 400, "INVALID_ARGUMENT", {}, None)
    return {"candidates": [{"content": {"parts": [{"text": "new"}]}}]}
pg._post = _new_model
check("gemini: works on the new model (thinkingLevel accepted)", glm.complete("hi") == "new")

def _always_400(url, payload, headers, timeout):
    raise urllib.error.HTTPError(url, 400, "INVALID_ARGUMENT", {}, None)
pg._post = _always_400
try:
    glm.complete("hi")
    raised = False
except urllib.error.HTTPError as exc:
    raised = exc.code == 400
check("gemini: a 400 on every form still raises (no silent empty reply)", raised)

def _forbidden(url, payload, headers, timeout):
    raise urllib.error.HTTPError(url, 403, "forbidden", {}, None)
_calls = {"n": 0}
def _count_forbidden(url, payload, headers, timeout):
    _calls["n"] += 1
    return _forbidden(url, payload, headers, timeout)
pg._post = _count_forbidden
try:
    glm.complete("hi")
except urllib.error.HTTPError:
    pass
check("gemini: non-400 errors are not retried", _calls["n"] == 1)
pg._post = _real_gpost

print(f"\n{'RED' if FAILS else 'GREEN'}: {len(FAILS)} failing")
sys.exit(1 if FAILS else 0)
