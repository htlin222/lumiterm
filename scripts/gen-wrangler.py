#!/usr/bin/env python3
"""Generate ask/wrangler.jsonc from the root config.json (single source of truth).

Run via `make deploy` / `make test-e2e`; you should never hand-edit wrangler.jsonc.
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

wj = {
    "name": cfg.get("askWorkerName", "ask-live-comments"),
    "main": "src/index.ts",
    "compatibility_date": "2025-05-01",
    "observability": {"enabled": True},
    "durable_objects": {"bindings": [{"name": "ROOM", "class_name": "Room"}]},
    "migrations": [{"tag": "v1", "new_sqlite_classes": ["Room"]}],
    "routes": [{"pattern": cfg.get("askHost", "ask.example.com"), "custom_domain": True}],
}

out = ROOT / "ask" / "wrangler.jsonc"
out.write_text(
    "// GENERATED from ../config.json by scripts/gen-wrangler.py — edit config.json, not here.\n"
    + json.dumps(wj, indent=2) + "\n",
    encoding="utf-8",
)
print(f"wrote {out.relative_to(ROOT)}  (name={wj['name']}, host={wj['routes'][0]['pattern']})")
