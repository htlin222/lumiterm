---
name: setup
description: Set up, run, configure, and deploy this project (a light-themed ttyd web terminal + Slido-like live comment system). Use when bootstrapping the repo on a new machine, when the terminal/fonts/ELI5/comments aren't working, or when deploying the ask comment worker to Cloudflare.
---

# Setup guidebook — light ttyd demo terminal + live comments

## What this project is

Two things in one repo:

1. **A light-themed web terminal** — `ttyd` runs your real `zsh` (inheriting your
   dotfiles) and is shown in a macOS-window-card webpage with settings, spotlight,
   fullscreen, and an **ELI5-on-selection** feature (select a command → Groq explains
   it in Traditional Chinese; history saved to SQLite).
2. **`ask/`** — a Cloudflare Worker + Durable Object: a Slido-like live comment system.
   Audience submits comments from their phones; they pop as macOS-style notifications
   on the presenter page **and** overlaid on the terminal.

**`config.json` is the single source of truth** — edit only that for host/ports/font.

## Prerequisites

| Tool | Why | Install |
|------|-----|---------|
| `ttyd` | serves the terminal over WebSocket | `brew install ttyd` |
| `python3` | static server + Groq proxy + build scripts | system / `brew install python` |
| `uv` / `uvx` | font subsetting (`fonttools[woff]`) + Playwright tests | `brew install uv` |
| oh-my-zsh | the demo shell theme | https://ohmyz.sh |
| JetBrainsMono **Nerd Font** | embedded terminal font (the `Mono`-less "NF" TTFs in `~/Library/Fonts`) | `brew install --cask font-jetbrains-mono-nerd-font` |
| Groq API key | ELI5 feature only | https://console.groq.com |
| `wrangler` + Cloudflare account | `ask/` comment worker only | `npm i -g wrangler` / `pnpm add -g wrangler` |

Check: `for t in ttyd uv wrangler python3; do command -v $t || echo "$t MISSING"; done`

## Quick start (terminal only)

```bash
cp .env.example .env          # then put your GROQ_API_KEY in .env (optional, for ELI5)
# edit config.json if you want different ports/font
make                          # builds fonts + ttyd index, starts servers, opens the page
```

Open **http://localhost:8088** (the framed window). `make stop` to stop.
Or just `cd` into the repo after `direnv allow` — `.envrc` runs `make up` automatically.

First `make` runs `make fonts` (subsets the Nerd Font to WOFF2 via `uvx fonttools[woff]`)
and `make index` (harvests ttyd's default page and embeds the font + control JS). These
produce **generated, gitignored** files: `fonts/*.woff2`, `ttyd-index.html`,
`scripts/ttyd-default.html`.

## Configuration — `config.json` (edit this, nothing else)

```jsonc
{ "askHost": "ask.example.com",     // your deployed comment-worker hostname
  "askWorkerName": "ask-live-comments",
  "ttydPort": 7682, "webPort": 8088, "fontSize": 18 }
```

- `serve.sh` reads `ttydPort` / `webPort` / `fontSize` at launch.
- `index.html` does `fetch('/config.json')` at runtime for the comment-worker host.
- `ask/wrangler.jsonc` is **generated** from this by `scripts/gen-wrangler.py` (it is
  gitignored — never hand-edit it; run `make deploy` / `make test-e2e`).

Other config:
- `.env` — `GROQ_API_KEY` (and optional `GROQ_MODEL`); read server-side only.
- `prompt.json` — the ELI5 persona (`system`, optional `model`/`temperature`); read
  **per request**, so edits apply with no restart.

## Make targets

```
make / make start   build assets, start, open browser
make up              start if down, no browser (used by .envrc)
make stop|restart|status
make fonts           (re)subset JetBrainsMono NF -> fonts/*.woff2   (needs uv)
make index           (re)build ttyd-index.html with the font embedded
make compile         byte-compile .zshrc for faster shell start
make logs            tail the server log
make history         recent ELI5 selections+answers from eli5_history.db
make test            server.py unit tests
make test-e2e        boot ask worker locally + run e2e (needs uv)   [auto-gens wrangler.jsonc]
make deploy          gen ask/wrangler.jsonc from config.json, then `wrangler deploy`
make clean           stop + remove generated assets
```

## Deploying the comment system (`ask/`)

```bash
wrangler login                        # one time
# set askHost + askWorkerName in config.json (askHost must be a hostname on a
# Cloudflare zone you control; or remove routes in gen-wrangler.py for *.workers.dev)
make deploy                           # generates ask/wrangler.jsonc, deploys worker + custom domain
```

The Durable Object stores comments in its own SQLite; real-time fan-out is over
WebSocket. Audience page = `https://<askHost>/`, presenter page = `/present`. The local
terminal overlay auto-connects to `wss://<askHost>/ws` (from `config.json`).

## How the terminal pieces fit

- `serve.sh` → launches `ttyd` (127.0.0.1:`ttydPort`, light xterm theme, `-I ttyd-index.html`)
  running `env ZDOTDIR=. zsh`, plus `server.py` (127.0.0.1:`webPort`).
- `.zshrc` (loaded via `ZDOTDIR=.`) inherits your real dotfiles/modules/PATHs but swaps
  powerlevel10k for `omz-custom/themes/light.zsh-theme` and drops the Warp/p10k blocks.
- `server.py` serves the static site + `config.json`, `POST /api/eli5` (Groq proxy →
  records to `eli5_history.db`), `GET /api/history`.
- `index.html` = the macOS window card that iframes ttyd; adds settings, spotlight,
  CSS-maximize fullscreen, and the live-comments overlay.
- `scripts/build-index.py` harvests ttyd's page, base64-embeds the WOFF2 as `@font-face`,
  and injects a control script (font re-measure, settings/spotlight postMessage bridge,
  selection→ELI5).

## Tests

```bash
make test       # unit: env/prompt parsing, sqlite record+history, /api/eli5 (Groq mocked)
make test-e2e   # e2e: boots `wrangler dev`, checks HTTP round-trip + real-time WebSocket
```

## Troubleshooting

- **`make fonts` fails ("No module named brotli")** — use `uvx --from "fonttools[woff]"`
  (the Makefile already does); don't use Homebrew's plain `fonttools`.
- **Glyphs are tofu / spacing too wide** — the embedded font + a post-`fonts.ready`
  re-measure fix this; rebuild with `make index` and hard-refresh.
- **Port already in use** — another `ttyd` may hold 7681; this project defaults to 7682.
  Change `ttydPort`/`webPort` in `config.json`.
- **`ask.<domain>` won't resolve right after deploy** — stale local negative DNS cache:
  `sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder` (it resolves on
  1.1.1.1 immediately).
- **ELI5 returns "GROQ_API_KEY not set"** — add it to `.env` (copy from `.env.example`).
- **Comments overlay shows nothing locally** — `askHost` in `config.json` must be your
  deployed worker and resolve from this machine.
- **Secrets** — `.env` and `eli5_history.db` are gitignored; never commit them. ttyd binds
  to `127.0.0.1` only, so the secret-loading shell isn't exposed on the LAN.
