# CortexLLM Memory System Configuration

**Date:** 2026-06-24  
**Status:** PRODUCTION READY - CortexLLM ONLY

## Overview

This system uses **CortexLLM unified memory exclusively**. OpenClaw's native memory system is disabled.

## Memory Location

All memory is stored in: `~/.config/cortexllm/memory/`

- **Hot:** `~/.config/cortexllm/memory/hot/openclaw.json` (active session, 50 messages max)
- **Warm:** `~/.config/cortexllm/memory/warm/unified.json` (shared context, 20 messages)
- **Cold:** `~/.config/cortexllm/memory/cold/` (archived sessions)

## Memory Operations

**ALL memory operations use:** `python3 ~/.openclaw/cortexllm/memory-tools.py`

### Commands

```bash
# Append to memory
python3 ~/.openclaw/cortexllm/memory-tools.py append "content to remember"

# Search memory
python3 ~/.openclaw/cortexllm/memory-tools.py search "query"

# Get recent messages
python3 ~/.openclaw/cortexllm/memory-tools.py get 20

# Clear session (start fresh)
python3 ~/.openclaw/cortexllm/memory-tools.py clear
```

## What's Disabled

❌ **OpenClaw Native Memory:**
- `memory_search` tool (deprecated)
- `openclaw memory index` command (deprecated)
- `~/.openclaw/memory/` directory (deprecated)
- `~/.openclaw/shared-agents/brain-agent/memory/` directory (deprecated)
- `agents.defaults.memorySearch` config (removed)
- `agents.list[].memorySearch` config (removed)

## Why CortexLLM Only?

1. **Unified across platforms** - Same memory for OpenClaw, Claude, Discord, etc.
2. **No API dependencies** - Uses Ollama embeddings, not OpenAI
3. **Simpler architecture** - One memory system, not two
4. **Production ready** - Tested and stable

## Configuration Files

- **CortexLLM config:** `~/.config/cortexllm/config.json`
- **OpenClaw config:** `~/.openclaw/openclaw.json` (memorySearch removed)
- **Agent instructions:** `~/.openclaw/shared-agents/brain-agent/AGENTS.md` (updated for CortexLLM-only)

## Embedding Provider

- **Provider:** Ollama
- **Model:** nomic-embed-text (via Ollama)
- **No OpenAI API key required**

---

**Last Updated:** 2026-06-24 11:12 MST
