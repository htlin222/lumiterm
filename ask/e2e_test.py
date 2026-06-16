"""End-to-end test for the ask live-comment worker.

Boots `wrangler dev` locally (Miniflare, real Durable Object + WebSocket), then:
  1. HTTP round-trip: POST /api/comment -> GET /api/comments shows it (DO sqlite)
  2. real-time: open /present, POST a comment, assert it pops as a notification

Run:  uvx --with playwright python ask/e2e_test.py
"""
import json
import os
import pathlib
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

ASK = pathlib.Path(__file__).resolve().parent
PORT = 8799
BASE = f"http://127.0.0.1:{PORT}"


def req(path, method="GET", obj=None):
    data = json.dumps(obj).encode() if obj is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def main():
    log = open("/tmp/wrangler-dev-e2e.log", "w")
    proc = subprocess.Popen(
        ["wrangler", "dev", "--port", str(PORT), "--ip", "127.0.0.1"],
        cwd=str(ASK), stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
    )
    try:
        # readiness: only MY worker returns 200 + {items:[]} on /api/comments
        ready = False
        for _ in range(120):
            try:
                s, b = req("/api/comments")
                if s == 200 and "items" in b:
                    ready = True
                    break
            except Exception:
                pass
            time.sleep(1)
        if not ready:
            print("FAIL: wrangler dev worker never became ready (see /tmp/wrangler-dev-e2e.log)")
            return 1

        # 1) HTTP round-trip + persistence
        s, b = req("/api/comment", "POST", {"name": "e2e", "text": "round-trip-ok"})
        assert s == 200 and b.get("ok") is True, f"post failed: {s} {b}"
        s, b = req("/api/comments")
        assert any(i["text"] == "round-trip-ok" for i in b["items"]), "comment not persisted"
        s, b = req("/api/comment", "POST", {"text": "   "})
        assert s == 400 and b.get("error"), f"empty should be 400: {s} {b}"
        print("PASS: HTTP round-trip + persistence + empty-validation")

        # 2) real-time delivery to the presenter page over WebSocket
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            br = p.chromium.launch(headless=True)
            pg = br.new_page()
            pg.goto(BASE + "/present", wait_until="load")
            pg.wait_for_timeout(1500)  # let the WS connect
            req("/api/comment", "POST", {"name": "realtime", "text": "hello-live-42"})
            pg.wait_for_selector(".note", timeout=6000)
            txt = pg.inner_text("#stack")
            assert "hello-live-42" in txt, f"notification not shown; got: {txt!r}"
            br.close()
        print("PASS: real-time WebSocket delivery")
        print("E2E PASS ✅")
        return 0
    finally:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:
            proc.terminate()
        log.close()


if __name__ == "__main__":
    sys.exit(main())
