# CortexLLM — 2026-07-01

Unified memory system for AI agents. Single model architecture.

## Structure

```
cortexllm/          ← Core engine files (14 .py, 2 .md)
scripts/            ← Entry point scripts
platforms/          ← Platform-specific config (openclaw, opencode, claude)
```

## Core Files (cortexllm/)

| File | Purpose |
|------|---------|
| `memory_manager.py` | 3-tier memory (hot/warm/cold) |
| `heartbeat_service.py` | Session health check |
| `cortexllm_mcp_server.py` | MCP server for memory access |
| `anti_hallucination.py` | Pre-execution verification |
| `loop_guard.py` | Failure loop detection |
| `model_router.py` | Single model routing (deepseek-v4-flash:cloud) |
| `memory_hook.py` | OpenClaw integration |
| `opencode_memory_hook.py` | OpenCode integration |
| `save-session.py` | Session to memory saver |
| `mcp-server-config.json` | MCP server configuration |

## Model

- **Only model**: `deepseek-v4-flash:cloud` via Ollama
- No OpenAI, Anthropic, or alternative models
## Versioning

Date-based releases only. Each release tag is the date (e.g. `2026-07-01`).
No semantic version numbers.

## Install

```bash
cp -r cortexllm/ ~/.openclaw/cortexllm/
cp scripts/* ~/.local/bin/
```

Requires: Python 3, Ollama running at http://127.0.0.1:11434
