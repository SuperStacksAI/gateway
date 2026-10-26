#!/usr/bin/env python3
"""Minimal OpenAI-compatible stub used to validate routing with no GPU.

Stands in for the GPU box/SGLang during the zero-GPU pipeline test:
LiteLLM -> relay (Tailscale) -> this stub. Stdlib only, no dependencies.

Run:  python3 stub_server.py            # listens on 0.0.0.0:30000
      HOST=127.0.0.1 PORT=30000 python3 stub_server.py
"""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def _json(self, code, payload):
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.rstrip("/")
        if path == "/health":
            self._json(200, {"status": "ok"})
        elif path == "/v1/models":
            self._json(
                200,
                {"object": "list", "data": [{"id": "stub-model", "object": "model"}]},
            )
        else:
            self._json(404, {"error": {"message": "not found"}})

    def do_POST(self):
        path = self.path.rstrip("/")
        if path not in ("/v1/chat/completions", "/chat/completions"):
            self._json(404, {"error": {"message": "not found"}})
            return

        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            req = json.loads(raw or b"{}")
        except ValueError:
            req = {}

        self._json(
            200,
            {
                "id": "chatcmpl-stub",
                "object": "chat.completion",
                "created": 0,
                "model": req.get("model", "stub-model"),
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "STUB: routing OK"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 3,
                    "total_tokens": 4,
                },
            },
        )

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "30000"))
    print(f"stub listening on {host}:{port}", flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()
