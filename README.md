# CortexLLM — v0.3.0 (2026-07-01)

**Unified memory system for AI agents.** Single model architecture — `deepseek-v4-flash:cloud`.

## Architecture

![CortexLLM Architecture](cortexllm/architecture.svg)

See [cortexllm/README.md](cortexllm/README.md) for full feature list, data flow, and details.

## Quick Start

```bash
python3 save-all-sessions.py              # Save sessions to memory
python3 memory-tools.py append "text"      # Add to hot memory
python3 memory-tools.py search "query"     # Search memory
watcher status                             # Token dashboard
```

## What It Does

- **Persistent memory** across sessions (hot/warm/cold 3-tier)
- **Sub-agent delegation** using same model (splits compute)
- **Health monitoring** — heartbeat, loop guard, anti-hallucination
- **Token tracking** — real usage from session files
- **Background tasks** — scheduler for recurring work

## Model

- **Only model**: `deepseek-v4-flash:cloud` via Ollama
- No OpenAI, Anthropic, or other models
- Sub-agents use the same model

## Structure

```
cortexllm/           → Engine (10 .py files)
save-*.py            → Session savers
memory-tools.py      → CLI tools
platforms/           → Platform configs
```

## Install

```bash
cp -r cortexllm/ ~/.openclaw/cortexllm/
cp save-session.py memory-tools.py ~/.local/bin/
```

Requires: Python 3, Ollama at http://127.0.0.1:11434
