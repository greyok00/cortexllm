# CortexLLM — unified memory for local AI agents. No cloud.

## Rules
- No `/home/<user>` in shipped code; use env vars.
- No push/publish/delete without explicit approval.
- Report failures plainly; don't claim done if partial.
- Self-contained: don't pull from `~/.claude/CLAUDE.md`.

## Memory
- Auto-saved each turn to hot memory; recent memory injected on start/clear/compact.
- Use `mcp__cortexllm__memory_*` tools for durable facts:
  - `memory_search` — find prior task context.
  - `memory_write` — save high-signal decisions/root-causes (warm).
  - `memory_read` — if search is insufficient.
- Keep entries short and dense; writes auto-prune/dedup.
