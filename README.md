# demo-ttyd-light

A beautiful, light-themed **ttyd** terminal for screen-sharing and presentations —
your real zsh/dotfiles, a clean light prompt, embedded Nerd Font, and a macOS
window-card UI with live controls.

## Prerequisites

Required: **ttyd**, **zsh** + **oh-my-zsh**, **python3**, **curl**.
Optional: **uv** (only for `make fonts`), **wrangler** (only to deploy the comment worker).

```bash
make doctor        # checks everything and prints install hints
```

macOS, the short version:

```bash
brew install ttyd
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"   # if you don't have oh-my-zsh
curl -LsSf https://astral.sh/uv/install.sh | sh                                                    # for make fonts
```

## Quickstart

```bash
git clone <repo> && cd demo-ttyd-light
make            # downloads/subsets the Nerd Font, builds assets, starts servers, opens the page
```

Open **http://localhost:8088** (the framed page). Stop with `make stop`.

> First `make` auto-downloads JetBrainsMono Nerd Font (if not already installed) and
> subsets it to a small WOFF2 — no manual font install needed.

| Command | What |
|---|---|
| `make` / `make start` | build + start + open browser |
| `make up` | start if down, no browser (used by `.envrc`) |
| `make stop` / `make restart` / `make status` | lifecycle |
| `make fonts` / `make index` | rebuild the embedded Nerd Font / ttyd page |
| `make logs` | tail the server log |

## On-screen controls

- **Full screen** — button top-right of the window (fades in on hover); or press `f`.
- **Settings** (bottom-right gear) — live font size, font family, and macOS-window
  width/height, plus Compact/Standard/Wide presets. Persisted in `localStorage`.
- **Spotlight** (bottom pill, or press `s`) — magnifies the current line to 200%,
  centers the cursor (both axes), and lays a white "focus" veil over the rest.
- **ELI5 繁中** — select any text in the terminal; a toolbar pops up above it. Click it
  to get a Traditional-Chinese, explain-like-I'm-5 explanation of the command, shown in
  a panel (Copy / 重新解釋). Needs a Groq key:

  ```bash
  cp .env.example .env      # then put your GROQ_API_KEY in .env
  ```

  The key is read **server-side** by `server.py` (`POST /api/eli5` proxies to Groq) and
  never reaches the browser. Optional `GROQ_MODEL` overrides the default.

  Edit the persona in **`prompt.json`** (`system`, plus optional `model`/`temperature`).
  It's read per request, so changes apply with no restart. Every answer is logged to
  `eli5_history.db`; see it with `make history` or `GET /api/history`.

## Live audience comments (`ask/`)

A Slido-like real-time feedback system in `ask/` (a Cloudflare Worker + Durable Object):

- Audience opens your deployed URL (e.g. **https://ask.example.com**) on their phones →
  enter a name, tap a quick snippet (`聽不太懂，想要再講一次` / `聽懂了` /
  `想要有一些練習時間`) or type a comment.
- Comments fan out in real time over WebSocket and pop as **macOS-style notifications
  top-right** — on the presenter page **/present** *and* overlaid on this demo terminal
  (the `#askStack` component). They stay until dismissed with `×`.
- Every comment is **persisted** in the Durable Object's SQLite store.

Configure & deploy — **everything lives in `config.json`** (the only file you edit):

```jsonc
{ "askHost": "ask.example.com", "askWorkerName": "ask-live-comments",
  "ttydPort": 7682, "webPort": 8088, "fontSize": 18 }
```

- `serve.sh` reads `ttydPort` / `webPort` / `fontSize` at launch.
- `index.html` fetches `/config.json` at runtime for the comment-worker host.
- `ask/wrangler.jsonc` is **generated** from it (don't hand-edit; it's gitignored).

```bash
make deploy        # regenerates ask/wrangler.jsonc from config.json, then deploys
```

Tests:

```bash
make test       # server.py unit tests (env/prompt/sqlite/eli5)
make test-e2e   # boots `wrangler dev` + drives the worker end-to-end (HTTP + WebSocket)
```

## How it works

- `serve.sh` runs **ttyd** on `127.0.0.1:7682` (light xterm theme, custom index) and a
  static server on `:8088` for `index.html` (the window-card wrapper that iframes ttyd).
- The shell is isolated via `ZDOTDIR=.` → `.zshrc` here, which **inherits your real
  dotfiles** (PATHs, modules, functions, plugins) but swaps powerlevel10k for the
  bundled `light` theme (`omz-custom/themes/light.zsh-theme`). Secrets load only because
  ttyd is bound to localhost.
- **Nerd Font**: `scripts/build-index.py` harvests ttyd's default page and injects
  `@font-face` for *JetBrainsMono NF* (Ghostty's font), with the subset WOFF2
  base64-embedded (no CORS). It also injects a small script that re-measures the
  terminal once fonts load (fixes wide-cell spacing) and bridges the settings/spotlight
  `postMessage` commands to xterm.

Generated files (`ttyd-index.html`, `fonts/*.woff2`, `scripts/ttyd-default.html`) are
rebuilt by `make` and removed by `make clean`.
