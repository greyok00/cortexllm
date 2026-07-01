# CortexLLM — v0.3.0 (2026-07-01)

**Unified memory system for AI agents (OpenClaw).**
Single model architecture — `ollama/deepseek-v4-flash:cloud` handles everything.

## Quick Start

```bash
# Check status
python3 ~/.openclaw/cortexllm/heartbeat_service.py

# Save session to memory
python3 ~/.openclaw/cortexllm/save-all-sessions.py

# Append to hot memory
python3 ~/.openclaw/cortexllm/memory-tools.py append "content"
```

## Structure

| Path | Purpose |
|------|---------|
| `~/.openclaw/cortexllm/` | Installed engine (14 .py files) |
| `~/.config/cortexllm/memory/` | Memory data (hot/warm/cold tiers) |
| `~/.local/bin/watcher` | CLI dashboard |
| `~/.openclaw/github/` | Clean repo copy for GitHub |

## Architecture (14 subsystems)

| # | Subsystem | File | Status |
|---|-----------|------|--------|
| 1 | **Memory Manager** | `memory_manager.py` | ✓ 3-tier hot/warm/cold |
| 2 | **MCP Server** | `cortexllm_mcp_server.py` | ✓ Started on demand |
| 3 | **Heartbeat** | `heartbeat_service.py` | · Disabled (on demand) |
| 4 | **Anti-Hallucination** | `anti_hallucination.py` | ✓ Pre-exec verification |
| 5 | **Loop Guard** | `loop_guard.py` | ✓ Failure detection |
| 6 | **Model Router** | `model_router.py` | ✓ Single model (no delegation) |
| 7 | **Session Auto-Save** | `save-all-sessions.py` | ✓ Cron-based |
| 8 | **Platform Hooks** | `memory_hook.py` | ✓ OpenClaw integration |
| 9 | **OpenCode Hook** | `opencode_memory_hook.py` | ✓ OpenCode integration |
| 10 | **CLI Tools** | `memory-tools.py` | ✓ Append/search |
| 11 | **Watcher** | `~/.local/bin/watcher` | ✓ Token usage dashboard |
| 12 | **Scheduler** | `~/.config/cortexllm/scheduler/` | ✓ Background tasks |
| 13 | **Homework Checker** | `canvas_homework_checker.py` | ✓ Canvas integration |
| 14 | **OpenClaw Bin Entries** | `openclaw-inject` + others | ✓ Utility scripts |

## Versioning

Date-based releases: v0.3.0 corresponds to 2026-07-01.
Git commits use date-based tags: `git commit -m "v2026-07-01: ..."`.

## Files

- 14 Python source files (all syntax-valid, all imports OK)
- 2 config files (valid JSON)
- 6 memory files (hot: 4, warm: 2, cold: 6) — local only, never committed
- 5 bin scripts (all syntax-valid)

## Model

- Only model: `ollama/deepseek-v4-flash:cloud`
- No OpenAI, Anthropic, or other models configured
- All references removed from code and config
