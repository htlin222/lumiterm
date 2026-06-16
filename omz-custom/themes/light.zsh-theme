# light.zsh-theme
# A clean oh-my-zsh theme tuned for LIGHT backgrounds.
# Modified from the minimal "refined" style: dark text + soft accents,
# ASCII-only glyphs (no Nerd Font required) so it renders perfectly in ttyd.

setopt prompt_subst

# --- palette (256-color, chosen for contrast on a near-white bg) ---
typeset -g _LT_PATH="%F{31}"    # teal-blue   -> current directory
typeset -g _LT_GIT="%F{29}"     # green-teal  -> branch name
typeset -g _LT_MUTE="%F{245}"   # soft gray   -> connective words
typeset -g _LT_DIRTY="%F{166}"  # warm orange -> dirty worktree
typeset -g _LT_CLEAN="%F{29}"   # green       -> clean worktree
typeset -g _LT_OK="%F{32}"      # blue arrow  -> last cmd succeeded
typeset -g _LT_ERR="%F{160}"    # red arrow   -> last cmd failed

# --- git segment ---
ZSH_THEME_GIT_PROMPT_PREFIX="${_LT_MUTE}on ${_LT_GIT}"
ZSH_THEME_GIT_PROMPT_SUFFIX="%f"
ZSH_THEME_GIT_PROMPT_DIRTY=" ${_LT_DIRTY}✗%f"
ZSH_THEME_GIT_PROMPT_CLEAN=" ${_LT_CLEAN}✔%f"

# --- prompt ---
#   ~/demo on main ✔ ❯
# Arrow turns red when the previous command exited non-zero.
PROMPT='${_LT_PATH}%~%f $(git_prompt_info)%(?.${_LT_OK}.${_LT_ERR})❯%f '

# Right side: show the time, muted, so demos read like a real session.
RPROMPT='${_LT_MUTE}%T%f'
