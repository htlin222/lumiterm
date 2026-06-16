#!/usr/bin/env bash
# serve.sh — launch the light-themed demo terminal as a polished localhost page.
#   • ttyd serves the zsh session (bound to 127.0.0.1, light xterm theme)
#   • a tiny static server serves index.html (the macOS window-card wrapper)
# Open  http://localhost:8080  in your browser for the framed, padded view.

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Ports + font come from config.json (single source of truth); env vars still win.
CFG="$DIR/config.json"
if [[ -f "$CFG" ]]; then
  eval "$(python3 -c "import json;c=json.load(open('$CFG'));print('CFG_TTYD=%s\nCFG_WEB=%s\nCFG_FONT=%s'%(c.get('ttydPort',7682),c.get('webPort',8088),c.get('fontSize',18)))")"
fi
TTYD_PORT="${TTYD_PORT:-${CFG_TTYD:-7682}}"
WEB_PORT="${WEB_PORT:-${CFG_WEB:-8088}}"
FONT_SIZE="${CFG_FONT:-18}"

# Light xterm theme — keep --background in sync with --term-bg in index.html.
THEME='{"background":"#fbfbfd","foreground":"#2e2e35","cursor":"#0a84ff","cursorAccent":"#fbfbfd","selectionBackground":"#cfe3ff","selectionForeground":"#1d1d1f","black":"#3b3f45","red":"#d1453b","green":"#2e8b57","yellow":"#b58900","blue":"#2563eb","magenta":"#a626a4","cyan":"#0e7490","white":"#c8c8c8","brightBlack":"#6b7178","brightRed":"#e0483c","brightGreen":"#3aa564","brightYellow":"#c98a00","brightBlue":"#3b82f6","brightMagenta":"#b83bb6","brightCyan":"#1597b3","brightWhite":"#fbfbfd"}'

pids=()
cleanup() { for p in "${pids[@]:-}"; do kill "$p" 2>/dev/null || true; done; }
trap cleanup EXIT INT TERM

# Custom index.html embeds the Nerd Font (built by scripts/build-index.py);
# fall back to the default UI if it hasn't been built yet.
INDEX_ARG=()
if [[ -f "$DIR/ttyd-index.html" ]]; then
  INDEX_ARG=(-I "$DIR/ttyd-index.html")
else
  echo "⚠ ttyd-index.html missing — run 'make fonts' for Nerd Font glyphs" >&2
fi

echo "▶ ttyd   → http://127.0.0.1:${TTYD_PORT}  (terminal)"
ttyd -i 127.0.0.1 -p "$TTYD_PORT" -W \
  "${INDEX_ARG[@]}" \
  -t fontSize="$FONT_SIZE" \
  -t 'fontFamily="JetBrainsMono NF", SFMono-Regular, Menlo, monospace' \
  -t lineHeight=1.35 \
  -t cursorStyle=bar \
  -t cursorBlink=true \
  -t scrollback=5000 \
  -t disableLeaveAlert=true \
  -t "theme=${THEME}" \
  env ZDOTDIR="$DIR" zsh &
pids+=($!)

echo "▶ page   → http://localhost:${WEB_PORT}  ← open this one"
python3 "$DIR/server.py" "$WEB_PORT" &
pids+=($!)

# Give servers a beat, then open the framed page (skip with NO_OPEN=1).
if [[ -z "${NO_OPEN:-}" ]]; then
  ( sleep 1; command open "http://localhost:${WEB_PORT}" >/dev/null 2>&1 || true ) &
fi

wait
