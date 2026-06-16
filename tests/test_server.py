"""Unit tests for the local backend (server.py).

Run:  python3 -m unittest discover -s tests -v
Covers: .env parsing, prompt.json loading (+ fallback), sqlite recording &
history, and the /api/eli5 endpoint end-to-end with Groq mocked.
"""
import http.client
import json
import os
import pathlib
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.request
from functools import partial
from http.server import ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import server  # noqa: E402


class TestEnvAndPrompt(unittest.TestCase):
    def test_load_env_parses_kv(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d)
            (p / ".env").write_text('GROQ_API_KEY="abc123"\n# comment\nGROQ_MODEL=foo\n', encoding="utf-8")
            old = server.ROOT
            try:
                server.ROOT = p
                env = server.load_env()
            finally:
                server.ROOT = old
            self.assertEqual(env["GROQ_API_KEY"], "abc123")   # quotes stripped
            self.assertEqual(env["GROQ_MODEL"], "foo")

    def test_load_prompt_reads_json(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d)
            (p / "prompt.json").write_text(json.dumps({"system": "S", "temperature": 0.7}), encoding="utf-8")
            old = server.ROOT
            try:
                server.ROOT = p
                cfg = server.load_prompt()
            finally:
                server.ROOT = old
            self.assertEqual(cfg["system"], "S")
            self.assertEqual(cfg["temperature"], 0.7)

    def test_load_prompt_fallback_when_missing(self):
        with tempfile.TemporaryDirectory() as d:
            old = server.ROOT
            try:
                server.ROOT = pathlib.Path(d)   # no prompt.json here
                self.assertEqual(server.load_prompt(), {})
            finally:
                server.ROOT = old
            self.assertTrue(server.FALLBACK_SYSTEM.startswith("你是"))


class TestRecordHistory(unittest.TestCase):
    def test_record_and_query(self):
        with tempfile.TemporaryDirectory() as d:
            old = server.DB
            try:
                server.DB = pathlib.Path(d) / "t.db"
                server.init_db()
                server.record("ls -la", "🦎 列出檔案", "m1")
                server.record("git status", "🦎 看狀態", "m1")
                con = sqlite3.connect(server.DB)
                rows = con.execute("SELECT selection, answer, model FROM eli5 ORDER BY id").fetchall()
                con.close()
            finally:
                server.DB = old
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0], ("ls -la", "🦎 列出檔案", "m1"))


class FakeGroqResp:
    def __init__(self, content):
        self._b = json.dumps({"choices": [{"message": {"content": content}}]}).encode()
    def read(self):
        return self._b
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


class TestEli5Endpoint(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._env, self._urlopen, self._db = server.load_env, urllib.request.urlopen, server.DB
        server.load_env = lambda: {}
        os.environ["GROQ_API_KEY"] = "test-key"
        server.DB = pathlib.Path(self.tmp.name) / "hist.db"
        server.init_db()
        server.urllib.request.urlopen = lambda req, timeout=30: FakeGroqResp("🦎 嘶～ 這是測試解釋")
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), partial(server.Handler, directory=str(server.ROOT)))
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        server.load_env, urllib.request.urlopen, server.DB = self._env, self._urlopen, self._db
        os.environ.pop("GROQ_API_KEY", None)
        self.tmp.cleanup()

    def _post(self, path, payload):
        # use http.client so we don't hit the mocked urllib.request.urlopen
        c = http.client.HTTPConnection("127.0.0.1", self.port)
        c.request("POST", path, body=json.dumps(payload), headers={"Content-Type": "application/json"})
        r = c.getresponse()
        data = r.read()
        c.close()
        return r.status, json.loads(data)

    def test_eli5_success_and_records(self):
        code, body = self._post("/api/eli5", {"text": "git rebase -i HEAD~3"})
        self.assertEqual(code, 200)
        self.assertEqual(body["text"], "🦎 嘶～ 這是測試解釋")
        # persisted
        con = sqlite3.connect(server.DB)
        n = con.execute("SELECT COUNT(*) FROM eli5").fetchone()[0]
        con.close()
        self.assertEqual(n, 1)

    def test_eli5_empty_is_400(self):
        code, body = self._post("/api/eli5", {"text": "   "})
        self.assertEqual(code, 400)
        self.assertIn("error", body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
