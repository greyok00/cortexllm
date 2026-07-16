# CortexLLM

**Unified memory layer for AI agents.** SQLite-based hot/warm/cold memory tiers. Designed for OpenClaw + Ollama Cloud, but forkable to any agentic AI platform.

CortexLLM is a drop-in memory system that gives AI agents persistent, structured memory across sessions. It runs as a local SQLite database with three tiers — hot (active session), warm (shared context), cold (permanent facts) — and exposes them via an MCP server any agent can connect to.

The primary implementation targets OpenClaw running on Ollama Cloud (`deepseek-v4-flash:cloud`), but the architecture is platform-agnostic. The MCP server speaks the standard Model Context Protocol, so any MCP-compatible agent (Claude Code, Cursor, custom agents) can read and write memory. The SQLite schema and memory manager are pure Python with no OpenClaw-specific dependencies — fork it, point it at your own database path, and it works.

## Features

| Feature | Description |
|---------|-------------|
| **Three-tier memory** | Hot (1,900+ rows), Warm (890+), Cold (22,000+) — automatically promoted from session buffer to permanent storage |
| **SQLite-native** | WAL mode, single-writer, indexed queries. No JSON files for state |
| **MCP server** | Exposes `memory_read`, `memory_write`, `memory_search`, `memory_clear` to any MCP-compatible client |
| **Platform-agnostic** | Works with Claude Code, Cursor, custom agents — anything that speaks MCP |
| **Per-profile isolation** | Each platform gets its own hot memory scope. Warm and cold are shared by default |
| **Cold distiller** | Background process that reads warm memory, identifies useful facts, and writes them to cold with confidence scores |
| **Session recovery** | On restart, reads the last checkpoint and resumes from the last command |
| **Isolated heartbeat** | 30-minute interval, runs in its own session, never bleeds model context into the main session |
| **Read-only health monitor** | Checks session health without touching session files — no race conditions |
| **Single model** | `deepseek-v4-flash:cloud` via Ollama Cloud. No OpenAI, Anthropic, or other providers |

## Database

```
~/.config/cortexllm/cortexllm.db  (15MB, WAL mode)

Memory_Hot   → 1,900+ rows  → Per-platform active session, FIFO capped at 300/profile
Memory_Warm  → 890+ rows    → Shared context buffer, rolling 2000
Memory_Cold  → 22,000+ rows → Permanent distilled facts, never expires
Logs         → 300+ entries → Event log for observability
Checkpoints  → 470+ entries → Session resume points
```

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Ollama Cloud API                          │
│                    deepseek-v4-flash:cloud                        │
│                    (262K context, fast mode)                      │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                    OpenClaw Gateway (18789)                       │
│                                                                  │
│  ┌─────────────────────┐    ┌────────────────────────────────┐   │
│  │  Heartbeat (30m)    │    │  Memory: memory-core plugin    │   │
│  │  isolated session   │    │  (built-in, no custom scripts) │   │
│  │  /compact >70%      │    │                                │   │
│  │  /new >90%          │    │                                │   │
│  └─────────────────────┘    └────────────────────────────────┘   │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                    CortexLLM SQLite Database                      │
│              ~/.config/cortexllm/cortexllm.db                     │
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐   │
│  │    Hot   │───▶│   Warm   │───▶│   Cold   │    │   Logs   │   │
│  │ Memory   │    │ Memory   │    │ Memory   │    │          │   │
│  │ 1,900+   │    │ 890+     │    │ 22,000+  │    │ 300+     │   │
│  │ rows     │    │ rows     │    │ rows     │    │ entries  │   │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘   │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                   CortexLLM MCP Server                            │
│               cortexllm_mcp_server.py                             │
│                                                                  │
│  Tools: memory_read · memory_write · memory_search · memory_clear│
│  Connected to: Claude Code, OpenClaw Gateway, any MCP client     │
└──────────────────────────────────────────────────────────────────┘
```

## Forking

To adapt CortexLLM for another agent platform:

1. Copy `cortexllm/` to your project
2. Set `CORTEXLLM_DB_PATH` to your desired database location
3. Run `cortexllm_mcp_server.py` as an MCP server — any MCP-compatible agent can connect
4. The SQLite schema auto-initializes on first use. No migrations needed.

## Directory Structure

```
github/                 ← This repository (clean code only)
└── cortexllm/          ← Core engine files

~/.openclaw/cortexllm/  ← Installed engine (runtime)
~/.config/cortexllm/    ← Memory storage (gitignored)
```

## Setup

```bash
cp -r cortexllm/ ~/.openclaw/cortexllm/
# Database auto-initializes on first use
```

## Integrations

- **OpenClaw Gateway**: Memory via `memory-core` plugin + `heartbeat` config
- **Claude Code**: Memory via `cortexllm` MCP server
- **Any MCP client**: Connect to `cortexllm_mcp_server.py` for memory read/write/search

## License

MIT