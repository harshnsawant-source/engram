"""Local API server for UI development and pre-deploy checks.

  ENGRAM_FAKE=1 python scripts/dev_server.py   # offline fakes (refusals by design)
  python scripts/dev_server.py                 # local Ollama models
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engram.webapi import run_handler

PORT = 8787


class DevHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        name = self.path.rstrip("/").rsplit("/", 1)[-1]
        length = int(self.headers.get("Content-Length", 0))
        status, data = run_handler(name, self.rfile.read(length), os.environ)
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        print(f"[dev] {fmt % args}", flush=True)


if __name__ == "__main__":
    print(f"engram dev api on http://localhost:{PORT} "
          f"(fake={bool(os.environ.get('ENGRAM_FAKE'))})", flush=True)
    HTTPServer(("127.0.0.1", PORT), DevHandler).serve_forever()
