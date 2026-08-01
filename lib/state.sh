#!/bin/bash
# state.sh — small state helpers for cortexllm hooks.
# State lives under $XDG_CACHE_HOME/cortexllm (or ~/.cache/cortexllm).
# Sourced by hooks; not executed directly.

_cortexllm_state_dir() {
  local base="${XDG_CACHE_HOME:-$HOME/.cache}"
  echo "${base}/cortexllm"
}

cc_state_init() {
  mkdir -p "$(_cortexllm_state_dir)"
}

cc_save_last_prompt() {
  local prompt="$1"
  cc_state_init
  # Keep the most recent prompt only (for replay-on-compact).
  printf '%s' "$prompt" > "$(_cortexllm_state_dir)/last-prompt"
}

cc_read_last_prompt() {
  local f="$(_cortexllm_state_dir)/last-prompt"
  [ -f "$f" ] && cat "$f" || true
}
