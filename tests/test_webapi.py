import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FAILS = []
def check(name, ok):
    print(("ok   " if ok else "FAIL ") + name)
    if not ok:
        FAILS.append(name)

from engram.providers import FakeLLM, HashEmbedder
from engram.webapi import (BUSY_MESSAGE, MAX_MESSAGE_CHARS, ProviderBusy,
                           SEED_EPISODES, WebApiError, handle_chat,
                           handle_sleep, providers_from_env, run_handler,
                           seed_store)

emb = HashEmbedder()

check("webapi: six seed episodes", len(SEED_EPISODES) == 6)
s = seed_store(emb)
check("webapi: seed store built", len(s.episodes) == 6 and len(s.facts) == 0)

# Null store -> seeded; refusal path with an empty FakeLLM (fake mode behavior).
out = handle_chat({"store": None, "t": 0.0, "message": "explain quantum chromodynamics"},
                  FakeLLM([]), emb)
check("chat: refusal reply shape", out["reply"]["refused"] is True
      and out["reply"]["citations"] == [])
check("chat: store echoed with seeds + observed question",
      len(out["store"]["episodes"]) == 7)
check("chat: clock advanced", out["t"] > 0.0)
check("chat: graph present", "nodes" in out["graph"] and "edges" in out["graph"])

# Grounded path: seeded store with a known id, scripted grounded reply.
# (Machine-verified: query top-1 = seed episode 0, score 0.408, margin 0.264.)
s2 = seed_store(emb)
s2.episodes[0].id = "aaaa1111"
payload = {"store": json.loads(s2.to_json()), "t": 0.0,
           "message": "what terrier did I name Biscuit"}
out2 = handle_chat(payload, FakeLLM(["You named the terrier Biscuit [aaaa1111]."]), emb)
check("chat: grounded reply cites the seed", not out2["reply"]["refused"]
      and out2["reply"]["citations"] == ["aaaa1111"])
check("chat: round-tripped store keeps the patched id",
      any(e["id"] == "aaaa1111" for e in out2["store"]["episodes"]))

# Validation errors.
def expect_error(fn, payload, status):
    try:
        fn(payload, FakeLLM([]), emb)
        return False
    except WebApiError as e:
        return e.status == status

check("chat: empty message 400", expect_error(handle_chat, {"store": None, "t": 0, "message": "  "}, 400))
check("chat: missing message 400", expect_error(handle_chat, {"store": None, "t": 0}, 400))
check("chat: long message 400",
      expect_error(handle_chat, {"store": None, "t": 0, "message": "x" * (MAX_MESSAGE_CHARS + 1)}, 400))
check("chat: non-numeric t 400", expect_error(handle_chat, {"store": None, "t": "now", "message": "hi"}, 400))
check("chat: malformed store 400",
      expect_error(handle_chat, {"store": {"episodes": [{"bogus": 1}], "facts": []}, "t": 0, "message": "hi"}, 400))
check("chat: non-object store 400",
      expect_error(handle_chat, {"store": [1, 2], "t": 0, "message": "hi"}, 400))

# Sleep: seeds, consolidates (fake llm distills nothing -> zero facts), reports.
out3 = handle_sleep({"store": None, "t": 0.0}, FakeLLM([]), emb)
check("sleep: advances to next day", out3["t"] == 1.0)
check("sleep: report shape", set(out3["report"]) >= {"day", "learned", "strengthened",
                                                     "superseded", "went_dormant",
                                                     "episodes_consolidated"})
check("sleep: seeds consolidated", out3["report"]["episodes_consolidated"] == 6)

# run_handler: JSON plumbing and error mapping.
env = {"ENGRAM_FAKE": "1"}
status, data = run_handler("chat", json.dumps({"store": None, "t": 0, "message": "hello there"}).encode(), env)
check("run_handler: chat 200", status == 200 and "reply" in data)
status, data = run_handler("sleep", json.dumps({"store": None, "t": 0}).encode(), env)
check("run_handler: sleep 200", status == 200 and "report" in data)
status, data = run_handler("chat", b"not json", env)
check("run_handler: bad json 400", status == 400 and "error" in data)
status, data = run_handler("chat", json.dumps(["list"]).encode(), env)
check("run_handler: non-object body 400", status == 400)
status, data = run_handler("nope", json.dumps({}).encode(), env)
check("run_handler: unknown endpoint 404", status == 404)
status, data = run_handler("chat", json.dumps({"store": None, "t": 0, "message": ""}).encode(), env)
check("run_handler: WebApiError mapped", status == 400 and "error" in data)

# ProviderBusy -> 503 with the honest message.
class BusyLLM:
    def complete(self, prompt, max_tokens=1000):
        raise ProviderBusy()
class BusyEmb:
    def embed(self, text):
        raise ProviderBusy()
import engram.webapi as wa
_real = wa.providers_from_env
wa.providers_from_env = lambda environ: (BusyLLM(), BusyEmb())
status, data = wa.run_handler("chat", json.dumps({"store": None, "t": 0, "message": "hi"}).encode(), {})
wa.providers_from_env = _real
check("run_handler: ProviderBusy -> 503 busy message", status == 503 and data["error"] == BUSY_MESSAGE)

# providers_from_env: fake mode returns the offline pair.
llm, e2 = providers_from_env({"ENGRAM_FAKE": "1"})
check("providers_from_env: fake mode", isinstance(llm, FakeLLM) and isinstance(e2, HashEmbedder))

print(f"\n{'RED' if FAILS else 'GREEN'}: {len(FAILS)} failing")
sys.exit(1 if FAILS else 0)
