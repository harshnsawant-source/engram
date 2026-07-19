"""LLM and embedder implementations. Tests use only FakeLLM + HashEmbedder;
network providers (Ollama, Gemini) arrive in later slices behind the same
duck-typed surface: llm.complete(prompt, max_tokens) / embedder.embed(text)."""

import hashlib
import math
import re

_WORD = re.compile(r"[a-z0-9']+")
_DIMS = 256  # 64 dims has verified hash collisions (e.g. "quantum"/"the") that
             # erode the refusal-threshold margins the test suites depend on


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def complete(self, prompt, max_tokens=1000):
        self.prompts.append(prompt)
        return self.responses.pop(0) if self.responses else ""


class HashEmbedder:
    def embed(self, text):
        vec = [0.0] * _DIMS
        for w in _WORD.findall(text.lower()):
            h = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16)
            vec[h % _DIMS] += 1.0
        norm = math.sqrt(sum(x * x for x in vec))
        return [x / norm for x in vec] if norm else vec
