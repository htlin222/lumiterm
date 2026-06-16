# Demo .zshrc  —  inherits the REAL dotfiles (PATHs, modules, functions,
# completions, lazy-loaded tools) so everything works, but swaps the heavy
# powerlevel10k prompt for the bundled LIGHT theme and drops the Warp-only
# early-return + p10k-instant-prompt blocks (irrelevant inside ttyd).
#
# Loaded only when ZDOTDIR points here, so it sits ALONGSIDE ~/.zshrc rather
# than replacing it.

#############################
### General configuration ###
#############################
setopt no_beep interactive_comments prompt_subst
setopt auto_cd auto_pushd pushd_ignore_dups pushd_minus pushd_silent
setopt append_history inc_append_history extended_history
setopt hist_expire_dups_first hist_ignore_all_dups hist_ignore_dups
setopt hist_ignore_space share_history
unsetopt hup
setopt long_list_jobs notify
unsetopt nomatch

HISTFILE="$ZDOTDIR/.demo_history"
HISTSIZE=10000
SAVEHIST=10000

# Platform flags the real modules rely on (normally set elsewhere in the env)
[[ "$OSTYPE" == darwin* ]] && export IS_MAC=1
[[ "$OSTYPE" == linux*  ]] && export IS_LINUX=1

# Ensure DOTFILES is set even in non-login shells
export DOTFILES="${DOTFILES:-$HOME/.dotfiles}"

# Deduplicate PATH/fpath automatically
typeset -U path PATH fpath FPATH

#############################
### Completion settings    ###
#############################
ZSH_CACHE_DIR="${ZSH_CACHE_DIR:-$HOME/.cache/zsh}"
mkdir -p "$ZSH_CACHE_DIR"
ZSH_COMPDUMP="$ZSH_CACHE_DIR/.zcompdump-$SHORT_HOST-$ZSH_VERSION"
skip_global_compinit=1
zstyle ':completion:*' rehash true
zstyle ':completion:*' menu select
zstyle ':completion:*:default' list-colors ''
zstyle ':completion:*' matcher-list 'm:{a-zA-Z}={A-Za-z}' 'r:|[._-]=* r:|=*' 'l:|=* r:|=*'
zstyle ':completion:*' completer _complete _approximate
zstyle ':completion:*:approximate:*' max-errors 1 numeric
zstyle -e ':completion:*:approximate:*' max-errors 'reply=($((($#PREFIX+$#SUFFIX)/3))numeric)'

#############################
### Oh-My-Zsh (light theme) ##
#############################
[[ ! -f ~/.p10k.zsh ]] || true   # intentionally NOT sourcing p10k

export ZSH="$HOME/.oh-my-zsh"
# Keep the REAL custom dir so your custom plugins (fast-syntax-highlighting,
# zsh-autosuggestions, pnpm, ...) resolve. We load the bundled `light` theme
# by sourcing it directly after OMZ (ZSH_THEME="" disables OMZ theme loading),
# so nothing is written into ~/.oh-my-zsh/custom.
ulimit -n 4096
DISABLE_AUTO_UPDATE="true"
DISABLE_MAGIC_FUNCTIONS="true"
ZSH_DISABLE_COMPFIX="true"
ZSH_THEME=""

# Autosuggest tuning (kept from the real config)
ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE='fg=30'
ZSH_AUTOSUGGEST_BUFFER_MAX_SIZE=20
ZSH_AUTOSUGGEST_USE_ASYNC=1
ZSH_AUTOSUGGEST_STRATEGY=(history completion)

# web-search engines (kept from the real config)
ZSH_WEB_SEARCH_ENGINES=(
  google-pdf "https://www.google.com/search?q=filetype%3Apdf+"
)

plugins=(
  git
  fast-syntax-highlighting
  zsh-autosuggestions
  colored-man-pages
  copyfile
  gitignore
  jsontools
  man
  sudo
  web-search
  pnpm
  wd
)

if [[ -f "$ZSH/oh-my-zsh.sh" ]]; then
  source "$ZSH/oh-my-zsh.sh"
else
  echo "Warning: oh-my-zsh not found at $ZSH" >&2
fi

# Load the bundled LIGHT theme (overrides any prompt OMZ may have set).
source "$ZDOTDIR/omz-custom/themes/light.zsh-theme"

#############################
### carapace completions   ###
#############################
if command -v carapace >/dev/null 2>&1; then
  zstyle ':completion:*' format $'\e[2;37m%d\e[m'
  zstyle ':completion:*:descriptions' format '[%d]'
  source <(carapace _carapace)
fi

#############################
### Source dotfile modules ##
#############################
# This is the part that makes "all the functions work".
for _m in alias fzf note_related \
          fn_navigation fn_git fn_fzf fn_utils fn_dev \
          fn_notes fn_media fn_secrets fn_cookbook; do
  [[ -f "$DOTFILES/zsh/modules/$_m.zsh" ]] && source "$DOTFILES/zsh/modules/$_m.zsh"
done
unset _m
[[ -n "$IS_MAC" && -f "$DOTFILES/zsh/modules/fn_macos.zsh" ]] && source "$DOTFILES/zsh/modules/fn_macos.zsh"
[[ -f "$HOME/.uvv" ]] && source "$HOME/.uvv"

#############################
### PATHs (inherited)      ###
#############################
export PATH=~/.npm-global/bin:$PATH
export PATH="$HOME/.antigravity/antigravity/bin:$PATH"
export PATH="$HOME/.local/bin:$PATH"
export PATH=/usr/local/go/bin:$PATH
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"
export PATH="$HOME/.kimi-code/bin:$PATH"

# pnpm (OS-aware, as in the real config)
if [[ -n "$IS_MAC" ]]; then
  [[ -d "$HOME/Library/pnpm" ]] && export PNPM_HOME="$HOME/Library/pnpm"
else
  [[ -d "$HOME/.local/share/pnpm" ]] && export PNPM_HOME="$HOME/.local/share/pnpm"
fi
if [[ -n "$PNPM_HOME" ]]; then
  case ":$PATH:" in
    *":$PNPM_HOME:"*) ;;
    *) export PATH="$PNPM_HOME:$PATH" ;;
  esac
fi

#############################
### Secrets & integrations ##
#############################
# Localhost-only, writable terminal -> these populate env vars some functions
# need. ttyd is bound to 127.0.0.1 in serve.sh so this is not LAN-exposed.
# Comment out this whole block if you'd rather demo without secrets loaded.
[[ -f "$HOME/.config/op/plugins.sh" ]] && source "$HOME/.config/op/plugins.sh"
[[ -f "$HOME/.HTTPCONFIG" ]] && source "$HOME/.HTTPCONFIG"
if [[ -f "$DOTFILES/.env" ]]; then
  set -a; source "$DOTFILES/.env"; set +a
fi

export RUST_LOG=himalaya=error
export ENABLE_LSP_TOOLS=1

# bun completions
[[ -s "$HOME/.bun/_bun" ]] && source "$HOME/.bun/_bun"

#############################
### Lazy-loaded tools      ###
#############################
# zoxide
_init_zoxide() {
  unfunction _init_zoxide z zi 2>/dev/null
  command -v zoxide >/dev/null 2>&1 && eval "$(zoxide init zsh)"
}
z()  { _init_zoxide; z "$@" }
zi() { _init_zoxide; zi "$@" }

# atuin (Ctrl-R / Up)
_atuin_loaded=0
_init_atuin() {
  (( _atuin_loaded )) && return
  _atuin_loaded=1
  [[ -f "$HOME/.atuin/bin/env" ]] && . "$HOME/.atuin/bin/env"
  command -v atuin >/dev/null 2>&1 && eval "$(atuin init zsh)"
}
_atuin_up()     { _init_atuin; (( $+functions[_atuin_up_search_widget] )) && _atuin_up_search_widget || zle up-line-or-history }
_atuin_search() { _init_atuin; (( $+functions[_atuin_search_widget] )) && _atuin_search_widget || zle history-incremental-search-backward }
zle -N _atuin_up; zle -N _atuin_search
bindkey '^[[A' _atuin_up; bindkey '^[OA' _atuin_up; bindkey '^r' _atuin_search

# direnv (on cd / if .envrc present)
_direnv_loaded=0
_init_direnv() {
  (( _direnv_loaded )) && return
  _direnv_loaded=1
  command -v direnv >/dev/null 2>&1 && eval "$(direnv hook zsh)"
}
autoload -Uz add-zsh-hook
add-zsh-hook chpwd _init_direnv

# forgit + fzf
if command -v brew >/dev/null 2>&1; then
  _fp="$(brew --prefix)/share/forgit/forgit.plugin.zsh"
  [[ -f "$_fp" ]] && source "$_fp"; unset _fp
fi
[[ -f ~/.fzf.zsh ]] && source ~/.fzf.zsh

#############################
### Cursor + welcome       ###
#############################
echo -ne '\e[2 q'   # solid block cursor

_demo_welcome() {
  print -P ""
  print -P "  %F{31}❯%f  %Bwelcome to the demo terminal%b"
  print -P "  %F{245}light theme · oh-my-zsh · your dotfiles & functions are loaded%f"
  print -P ""
}
_demo_welcome

# Start in the tidy playground so `ls` looks great in the demo.
cd "$ZDOTDIR/playground" 2>/dev/null || true
