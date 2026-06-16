# Makefile — light-themed ttyd demo terminal.
#   make            # build assets if needed, start servers, open the page
#   make up         # start if not running, no browser (used by .envrc on cd)
#   make stop       # stop the demo's servers
#   make restart    # stop + start
#   make status     # is it up?
#   make fonts      # (re)subset Nerd Font -> woff2
#   make index      # (re)build the ttyd index with the font embedded
#   make logs       # tail the server log
#   make clean      # stop + remove generated assets

SHELL := /bin/bash
DIR   := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))

TTYD_PORT ?= 7682
WEB_PORT  ?= 8088
URL       := http://localhost:$(WEB_PORT)
LOG       := /tmp/demo-ttyd-light.log
SRCFONTS  := $(HOME)/Library/Fonts
RANGES    := U+0020-007E,U+00A0-00FF,U+0100-017F,U+2010-2027,U+2030-205E,U+2070-209F,U+20A0-20BF,U+2190-21FF,U+2200-22FF,U+2300-23FF,U+2500-25FF,U+2600-26FF,U+2700-27BF,U+2B00-2BFF,U+E000-F8FF,U+FE00-FE0F,U+F0000-F1FFF

WOFF2 := fonts/jbmono-nf-regular.woff2 fonts/jbmono-nf-bold.woff2

.DEFAULT_GOAL := start
.PHONY: start up stop restart status doctor fonts index assets compile logs history test test-e2e deploy clean help

## start: ensure assets + compiled rc, start if down, open the page
start: assets compile up
	@command open "$(URL)" >/dev/null 2>&1 || true
	@echo "→ $(URL)"

## up: start servers if not already running (no browser); used by .envrc
up: assets
	@if curl -s -o /dev/null "http://127.0.0.1:$(WEB_PORT)/" 2>/dev/null; then \
	  echo "already running → $(URL)"; \
	else \
	  echo "starting demo terminal…"; \
	  cd "$(DIR)" && NO_OPEN=1 TTYD_PORT=$(TTYD_PORT) WEB_PORT=$(WEB_PORT) \
	    nohup ./serve.sh > "$(LOG)" 2>&1 & \
	  for i in $$(seq 1 25); do \
	    curl -s -o /dev/null "http://127.0.0.1:$(WEB_PORT)/" 2>/dev/null && break; sleep 0.2; \
	  done; \
	  echo "up → $(URL)"; \
	fi

## stop: kill this demo's ttyd + static server (leaves other ttyd instances alone)
stop:
	@pkill -f "ttyd -i 127.0.0.1 -p $(TTYD_PORT)" 2>/dev/null && echo "stopped ttyd" || echo "ttyd not running"
	@pkill -f "http.server $(WEB_PORT)" 2>/dev/null && echo "stopped web" || echo "web not running"
	@pkill -f "$(DIR)/serve.sh" 2>/dev/null || true

restart: stop
	@$(MAKE) --no-print-directory up
	@command open "$(URL)" >/dev/null 2>&1 || true

## status: report whether the page is reachable
status:
	@if curl -s -o /dev/null "http://127.0.0.1:$(WEB_PORT)/" 2>/dev/null; then \
	  echo "UP   → $(URL)  (ttyd :$(TTYD_PORT))"; \
	else echo "DOWN"; fi

FONT_SRC := fonts/src
FONT_ZIP := https://github.com/ryanoasis/nerd-fonts/releases/latest/download/JetBrainsMono.zip

## doctor: check prerequisites and print install hints
doctor:
	@echo "Prerequisites:"
	@command -v ttyd    >/dev/null 2>&1 && echo "  ttyd      ✓" || echo "  ttyd      ✗  → brew install ttyd   (Linux: see github.com/tsl0922/ttyd)"
	@command -v zsh     >/dev/null 2>&1 && echo "  zsh       ✓" || echo "  zsh       ✗  → install zsh"
	@[ -d "$$HOME/.oh-my-zsh" ]          && echo "  oh-my-zsh ✓" || echo "  oh-my-zsh ✗  → sh -c \"\$$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)\""
	@command -v python3 >/dev/null 2>&1 && echo "  python3   ✓" || echo "  python3   ✗  → install python3"
	@command -v curl    >/dev/null 2>&1 && echo "  curl      ✓" || echo "  curl      ✗"
	@command -v uv      >/dev/null 2>&1 && echo "  uv        ✓  (for: make fonts)" || echo "  uv        ✗  → curl -LsSf https://astral.sh/uv/install.sh | sh   (only for: make fonts)"
	@command -v wrangler>/dev/null 2>&1 && echo "  wrangler  ✓  (for: ask/ deploy)" || echo "  wrangler  ✗  → npm i -g wrangler   (only to deploy the comment worker)"

## fonts: subset JetBrainsMono Nerd Font -> small woff2 (auto-downloads the font; needs uv)
fonts: $(WOFF2)
	@echo "fonts ready."
fonts/jbmono-nf-%.woff2:
	@mkdir -p fonts $(FONT_SRC)
	@case $* in regular) W=Regular;; bold) W=Bold;; esac; \
	  SRC=""; \
	  for d in "$(SRCFONTS)" "$(FONT_SRC)"; do \
	    [ -f "$$d/JetBrainsMonoNerdFont-$$W.ttf" ] && SRC="$$d/JetBrainsMonoNerdFont-$$W.ttf" && break; \
	  done; \
	  if [ -z "$$SRC" ]; then \
	    echo "JetBrainsMono Nerd Font not found locally — downloading…"; \
	    curl -fsSL -o "$(FONT_SRC)/JetBrainsMono.zip" "$(FONT_ZIP)" && \
	    ( cd "$(FONT_SRC)" && unzip -oq JetBrainsMono.zip 'JetBrainsMonoNerdFont-*.ttf' ); \
	    SRC="$(FONT_SRC)/JetBrainsMonoNerdFont-$$W.ttf"; \
	  fi; \
	  echo "subsetting $$W from $$SRC…"; \
	  uvx --from "fonttools[woff]" pyftsubset "$$SRC" \
	    --output-file="$@" --flavor=woff2 \
	    --layout-features='*' --glyph-names --unicodes="$(RANGES)" >/dev/null 2>&1

## index: harvest ttyd's default page + embed the fonts
index: ttyd-index.html
ttyd-index.html: scripts/build-index.py $(WOFF2) scripts/ttyd-default.html
	@python3 scripts/build-index.py
scripts/ttyd-default.html:
	@echo "harvesting ttyd default index (starting a throwaway ttyd)…"; \
	ttyd -i 127.0.0.1 -p 7699 -o /bin/echo >/dev/null 2>&1 & p=$$!; \
	for i in $$(seq 1 25); do curl -s -o "scripts/ttyd-default.html" "http://127.0.0.1:7699/" 2>/dev/null && [ -s scripts/ttyd-default.html ] && break; sleep 0.2; done; \
	kill $$p 2>/dev/null || true; echo "harvested."

# assets: everything ttyd needs before it can serve the pretty terminal
assets: fonts index

## compile: byte-compile the demo .zshrc for a faster shell start
compile:
	@zsh -fc 'zcompile -R -- "$(DIR)/.zshrc" "$(DIR)/.zshrc"' 2>/dev/null \
	  && echo "compiled .zshrc" || true

## logs: follow the server log
logs:
	@tail -f "$(LOG)"

## history: show recent ELI5 selections + answers from the local sqlite db
history:
	@sqlite3 -header -column eli5_history.db "SELECT id, created_at, substr(selection,1,34) AS selection, substr(replace(answer,char(10),' '),1,54) AS answer FROM eli5 ORDER BY id DESC LIMIT 20" 2>/dev/null || echo "no history yet (or sqlite3 missing)"

## test: run server.py unit tests
test:
	@python3 -m unittest discover -s tests -v

## test-e2e: boot the ask worker locally + run the end-to-end test (needs uv)
test-e2e: ask/wrangler.jsonc
	@uvx --with playwright python ask/e2e_test.py

## deploy: generate ask/wrangler.jsonc from config.json, then deploy the worker
deploy: ask/wrangler.jsonc
	@cd ask && wrangler deploy

ask/wrangler.jsonc: config.json scripts/gen-wrangler.py
	@python3 scripts/gen-wrangler.py

## clean: stop and remove generated assets
clean: stop
	@rip -f ttyd-index.html scripts/ttyd-default.html $(WOFF2) .zshrc.zwc 2>/dev/null || true
	@echo "cleaned."

help:
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/## //'
