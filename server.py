#!/usr/bin/env python3
"""server.py — static file server for the demo + a tiny Groq proxy.

Replaces `python3 -m http.server`. Serves index.html / fonts / etc., and adds:

  POST /api/eli5   {"text": "<selected CLI text>"}
      -> reads GROQ_API_KEY from ./.env, asks Groq to ELI5 it in Traditional
         Chinese, returns {"text": "<explanation>", "model": "..."}.

The key stays server-side (never shipped to the browser), which also avoids
the browser-CORS problem of calling api.groq.com directly.

Usage: python3 server.py [PORT]   (binds 127.0.0.1)
"""
import json
import os
import pathlib
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from functools import partial

ROOT = pathlib.Path(__file__).resolve().parent
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"
DB = ROOT / "eli5_history.db"


def init_db():
    con = sqlite3.connect(DB)
    con.execute(
        """CREATE TABLE IF NOT EXISTS eli5(
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             created_at TEXT DEFAULT (datetime('now','localtime')),
             model TEXT,
             selection TEXT NOT NULL,
             answer TEXT NOT NULL)"""
    )
    con.commit()
    con.close()


def record(selection, answer, model):
    """Persist one (selection, answer) pair; never fail the request over logging."""
    try:
        con = sqlite3.connect(DB)
        con.execute(
            "INSERT INTO eli5(model, selection, answer) VALUES (?, ?, ?)",
            (model, selection, answer),
        )
        con.commit()
        con.close()
    except Exception:  # noqa: BLE001
        pass

# Fallback persona, used only if prompt.json is missing/unreadable.
FALLBACK_SYSTEM = (
    "你是『大蜥蜴老師』🦎，要像一隻蜥蜴一樣說話："
    "慵懶、愛曬太陽，偶爾「嘶～」一下、吐吐舌頭，但其實很博學。"
    "使用者會貼上一段終端機指令或文字，請用「繁體中文（台灣用語，zh-TW）」"
    "像對五歲小孩一樣（ELI5）解釋：它在做什麼、用白話比喻、會有什麼實際效果。"
    "保持大蜥蜴的口吻與角色感，但內容要正確、好懂。"
    "回答要簡潔（約 3–6 句），可用條列。只輸出繁體中文，不要加英文前言。"
)


def load_prompt() -> dict:
    """Read prompt.json each call so edits apply without a restart."""
    try:
        cfg = json.loads((ROOT / "prompt.json").read_text(encoding="utf-8"))
        return cfg if isinstance(cfg, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def load_env() -> dict:
    env = {}
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if self.path.split("?")[0] == "/api/history":
            return self._history()
        return super().do_GET()

    def _history(self):
        try:
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            limit = max(1, min(int(q.get("limit", ["50"])[0]), 500))
            con = sqlite3.connect(DB)
            con.row_factory = sqlite3.Row
            rows = con.execute(
                "SELECT id, created_at, model, selection, answer "
                "FROM eli5 ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            con.close()
            return self._json(200, {"items": [dict(r) for r in rows]})
        except Exception as e:  # noqa: BLE001
            return self._json(500, {"error": str(e)})

    def do_POST(self):
        if self.path.split("?")[0] != "/api/eli5":
            self.send_error(404)
            return
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            text = (body.get("text") or "").strip()
            if not text:
                return self._json(400, {"error": "empty selection"})
            if len(text) > 4000:
                text = text[:4000]

            env = load_env()
            key = env.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
            if not key:
                return self._json(500, {"error": "GROQ_API_KEY not set — add it to ./.env"})

            cfg = load_prompt()
            system = cfg.get("system") or FALLBACK_SYSTEM
            model = cfg.get("model") or env.get("GROQ_MODEL") or DEFAULT_MODEL
            temperature = cfg.get("temperature", 0.3)

            payload = {
                "model": model,
                "temperature": temperature,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": text},
                ],
            }
            req = urllib.request.Request(
                GROQ_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Authorization": "Bearer " + key,
                         "Content-Type": "application/json",
                         "User-Agent": "demo-ttyd-light/1.0"},
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read())
            out = data["choices"][0]["message"]["content"].strip()
            record(text, out, model)
            return self._json(200, {"text": out, "model": model})
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            return self._json(502, {"error": f"Groq HTTP {e.code}: {detail}"})
        except Exception as e:  # noqa: BLE001
            return self._json(500, {"error": str(e)})

    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):  # quiet
        pass


if __name__ == "__main__":
    PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8088
    init_db()
    handler = partial(Handler, directory=str(ROOT))
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), handler)
    print(f"serving {ROOT} on http://127.0.0.1:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
