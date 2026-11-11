"""Gemini free-tier providers (stdlib urllib). Used by the hosted demo when
GEMINI_API_KEY is set; never imported by tests beyond parse/construction."""

import json
import urllib.error
import urllib.request

from .webapi import ProviderBusy

_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _post(url, payload, headers, timeout):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _call(url, payload, api_key, timeout):
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    try:
        return _post(url, payload, headers, timeout)
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise ProviderBusy()
        raise


def _parse_text(data):
    parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts)


def _parse_embedding(data):
    emb = data.get("embedding")
    if isinstance(emb, dict) and isinstance(emb.get("values"), list):
        return emb["values"]
    embs = data.get("embeddings")
    if isinstance(embs, list) and embs:
        first = embs[0]
        if isinstance(first.get("values"), list):
            return first["values"]
        if isinstance(first.get("value"), list):
            return first["value"]
    return []


class GeminiLLM:
    def __init__(self, api_key, model="gemini-flash-lite-latest", timeout=60):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    # Ways to keep thinking off, newest first. Grounded recall and distillation
    # don't need chain-of-thought, and thinking tokens eat the output budget
    # (empty replies on the flash-lite models). The "-latest" alias moves between
    # model generations, and each accepts a different form: on 2026-11-12 it moved
    # to gemini-3.5-flash-lite, which 400s on thinkingBudget but takes thinkingLevel.
    _THINKING_OFF = ({"thinkingLevel": "minimal"}, {"thinkingBudget": 0})

    def complete(self, prompt, max_tokens=1000):
        last = None
        for thinking in self._THINKING_OFF:
            try:
                data = _call(f"{_BASE}/{self.model}:generateContent",
                             {"contents": [{"parts": [{"text": prompt}]}],
                              "generationConfig": {"maxOutputTokens": max_tokens,
                                                   "thinkingConfig": thinking}},
                             self.api_key, self.timeout)
                return _parse_text(data)
            except urllib.error.HTTPError as exc:
                if exc.code != 400:
                    raise
                last = exc  # this model rejects that form; try the next one
        raise last


class GeminiEmbedder:
    def __init__(self, api_key, model="gemini-embedding-001", dims=256, timeout=30):
        self.api_key = api_key
        self.model = model
        self.dims = dims
        self.timeout = timeout

    def embed(self, text):
        data = _call(f"{_BASE}/{self.model}:embedContent",
                     {"model": f"models/{self.model}",
                      "content": {"parts": [{"text": text}]},
                      "outputDimensionality": self.dims},
                     self.api_key, self.timeout)
        return _parse_embedding(data)
