"""Local Ollama providers (stdlib urllib only). Never imported by tests'
offline paths beyond construction; the live check is scripts/live_demo.py."""

import json
import urllib.request


def _post(url, payload, timeout):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


class OllamaLLM:
    def __init__(self, model="nemotron-3-nano:4b",
                 host="http://localhost:11434", timeout=180):
        self.model = model
        self.host = host
        self.timeout = timeout

    def complete(self, prompt, max_tokens=1000):
        data = _post(self.host + "/api/generate",
                     {"model": self.model, "prompt": prompt, "stream": False,
                      "options": {"num_predict": max_tokens}},
                     self.timeout)
        return data.get("response", "")


class OllamaEmbedder:
    def __init__(self, model="nomic-embed-text",
                 host="http://localhost:11434", timeout=60):
        self.model = model
        self.host = host
        self.timeout = timeout

    def embed(self, text):
        data = _post(self.host + "/api/embeddings",
                     {"model": self.model, "prompt": text},
                     self.timeout)
        return data.get("embedding", [])
