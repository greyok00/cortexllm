# CortexLLM — v0.3.0 (2026-07-01)

**Unified memory system for AI agents.** Single model architecture powered by `deepseek-v4-flash:cloud`.

## Architecture

![CortexLLM Architecture](architecture.svg)

```
┌─────────────────────────────────────────────────────┐
│                    OPENCLAW                          │
│         (AI agent — primary platform)                │
└──────────┬──────────────────────────────┬───────────┘
           │  memory_hook.py              │ openclaw-inject
           ▼                              ▼
┌─────────────────────────────────────────────────────┐
│              CORTEXLLM ENGINE                        │
│                                                      │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │ Memory Mgr  │  │ Model Router │  │ Loop Guard │  │
│  │ (3-tier)    │  │ (single mdl) │  │ (fail det) │  │
│  └──────┬──────┘  └──────────────┘  └────────────┘  │
│         │                                            │
│  ┌──────▼──────┐  ┌──────────────┐  ┌────────────┐  │
│  │ Heartbeat   │  │ Anti-Halluc  │  │ MCP Server │  │
│  │ (health)    │  │ (verifier)   │  │ (on-demand)│  │
│  └─────────────┘  └──────────────┘  └────────────┘  │
│                                                      │
│  ┌─────────────┐  ┌──────────────┐                   │
│  │ Watcher     │  │ Scheduler   │                    │
│  │ (dashboard) │  │ (background) │                   │
│  └─────────────┘  └──────────────┘                   │
└──────────┬───────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────┐
│              MEMORY SYSTEM (3-tier)                  │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ HOT      │  │ WARM     │  │ COLD             │   │
│  │ (current │  │ (recent  │  │ (permanent       │   │
│  │ session) │  │ sessions)│  │  knowledge)      │   │
│  └──────────┘  └──────────┘  └──────────────────┘   │
│  ~/.config/cortexllm/memory/                         │
└─────────────────────────────────────────────────────┘
```

## Features

### Core Engine (10 files in `cortexllm/`)

| # | Subsystem | File | What It Does |
|---|-----------|------|-------------|
| 1 | **Memory Manager** | `memory_manager.py` | 3-tier hot/warm/cold memory persistence. Hot = current session, Warm = recent context, Cold = permanent knowledge |
| 2 | **MCP Server** | `cortexllm_mcp_server.py` | Model Context Protocol server — exposes memory via stdio, started on-demand by agents |
| 3 | **Heartbeat** | `heartbeat_service.py` | Per-session health check — monitors context size, message count, token usage, auto-resets on overflow |
| 4 | **Anti-Hallucination** | `anti_hallucination.py` | Pre-execution verification — checks files exist, commands work, URLs resolve before acting |
| 5 | **Loop Guard** | `loop_guard.py` | Failure loop detection — tracks repeated failures per task, kills infinite retry loops, cools off |
| 6 | **Model Router** | `model_router.py` | Single model routing — sub-agent delegation using same model (deepseek). No secondary models |
| 7 | **Memory Hook** | `memory_hook.py` | OpenClaw integration — hooks into session lifecycle to auto-save context to hot memory |
| 8 | **OpenCode Hook** | `opencode_memory_hook.py` | OpenCode integration — same memory hooks for the OpenCode platform |
| 9 | **Platform Configs** | `platforms/` | AGENTS.md, SOUL.md, TOOLS.md, USER.md per platform (openclaw, opencode, claude) |
| 10 | **CLI Tools** | `cortexllm-tools/` | `cli-memory.py`, `cli-save-all.py`, `cli-save-session.py` — user-facing scripts |

### Supporting Systems

| # | Subsystem | Location | Status |
|---|-----------|----------|--------|
| 11 | **Watcher** | `~/.local/bin/watcher` | ✓ CLI dashboard — live token usage from session files |
| 12 | **Scheduler** | `~/.config/cortexllm/scheduler/` | ✓ Background task scheduling daemon |
| 13 | **Homework Checker** | `canvas_homework_checker.py` | ✓ Canvas integration for coursework |
| 14 | **Loop Scripts** | `~/.local/bin/` | ✓ watcher-raw, scheduler, todos, openclaw-inject |

## Model Configuration

**Only model installed and configured:**
- `deepseek-v4-flash:cloud` via Ollama

No OpenAI, Anthropic, Qwen, Gemma, Nemotron, or other models.
No fallbacks — single model handles everything.
Sub-agents use the same model (splits compute, not model type).

## Memory System

```
HOT:   ~/.config/cortexllm/memory/hot/   ← Current session context
WARM:  ~/.config/cortexllm/memory/warm/  ← Recent session summaries
COLD:  ~/.config/cortexllm/memory/cold/  ← Permanent knowledge (never removed)
```

Memory is **local only** — never committed to git. Gitignored at every level.

## Versioning

Date-based: `v0.3.0` corresponds to `2026-07-01`.
All git commits use format: `vYYYY-MM-DD: description`.

## File Structure

```
/home/grey/
├── cortexllm/                     ← Engine source (10 .py files)
│   ├── memory_manager.py          Memory (3-tier)
│   ├── model_router.py            Routing (single model)
│   ├── heartbeat_service.py       Health checks
│   ├── anti_hallucination.py      Pre-exec verification
│   ├── loop_guard.py              Failure detection
│   ├── memory_hook.py             OpenClaw integration
│   ├── opencode_memory_hook.py    OpenCode integration
│   ├── cortexllm_mcp_server.py    MCP protocol server
│   ├── README.md                  Engine docs
│   └── USER-PREFERENCES.md        User config
├── cortexllm-tools/               CLI tools (cli-memory, cli-save-all, cli-save-session)
├── platforms/                     Platform configs
└── .gitignore                     Blocks memory data
```

## Quick Start

```bash
# Save current sessions to memory
python3 cortexllm-tools/cli-save-all.py

# Append to hot memory
python3 cortexllm-tools/cli-memory.py append "your content here"

# Search memory
python3 cortexllm-tools/cli-memory.py search "query"

# Check token usage
watcher status
```

## Data Flow

```
User message → OpenClaw → memory_hook.py → MemoryManager → HOT storage
                  ↓
            model_router.py → should_delegate? → main session OR sub-agent
                  ↓
            LoopGuard monitors for failure loops
                  ↓
            Anti-Hallucination verifies before actions
                  ↓
            Heartbeat checks context health each turn
                  ↓
            cli-save-all.py → HOT → WARM (on save)
                  ↓
            Manual save → COLD (permanent knowledge)
```
