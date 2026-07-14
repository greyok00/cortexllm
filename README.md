# CortexLLM

**Unified memory layer for AI agents.** SQLite-based hot/warm/cold memory tiers. Designed for OpenClaw + Ollama Cloud, but forkable to any agentic AI platform.

CortexLLM is a drop-in memory system that gives AI agents persistent, structured memory across sessions. It runs as a local SQLite database with three tiers — hot (active session), warm (shared context), cold (permanent facts) — and exposes them via an MCP server any agent can connect to.

## Quick Start

```bash
# Clone and run
git clone https://github.com/greyok00/cortexllm.git
cd cortexllm

# Database auto-initializes on first use
python3 -c "from cortexllm_db import db; db.initialize(); print('OK')"

# Run the MCP server (for Claude Code, Cursor, etc.)
python3 cortexllm_mcp_server.py
```

## Features

| Feature | Description |
|---------|-------------|
| **Three-tier memory** | Hot (active session), Warm (shared context), Cold (permanent facts) |
| **SQLite-native** | WAL mode, single-writer, indexed queries. No JSON files for state |
| **MCP server** | Exposes `memory_read`, `memory_write`, `memory_search`, `memory_clear` |
| **Platform-agnostic** | Works with Claude Code, Cursor, any MCP-compatible agent |
| **Per-profile isolation** | Each platform gets its own hot memory scope. Warm/cold are shared |
| **Cold distiller** | Background process distills warm memory into cold with confidence scores |
| **Session recovery** | On restart, reads the last checkpoint and resumes from the last command |
| **Read-only heartbeat** | Monitors session health without touching session files |

## Setup

```bash
# Run setup (creates database, config, directories)
python3 setup.py

# Or do it manually:
python3 -c "from cortexllm_db import db; db.initialize(); print('OK')"

# Run the MCP server (for Claude Code, Cursor, etc.)
python3 cortexllm_mcp_server.py
```

## Files

| File | Purpose |
|------|---------|
| `cortexllm_db.py` | SQLite database layer (WAL mode, single-writer, multi-reader) |
| `cortexllm_mcp_server.py` | MCP server exposing memory tools to any MCP client |
| `cortexllm_models.py` | Data models, schemas, and enums |
| `memory_manager.py` | 3-tier memory manager (hot/warm/cold) |
| `memory_hook.py` | Memory integration hooks for agents |
| `memory-tools.py` | CLI tools for memory operations |
| `heartbeat_service.py` | Read-only session health monitor |
| `save-all-sessions.py` | Extract agent sessions into memory |
| `cold_distiller.py` | Background process for warm→cold memory distillation |
| `profiles.py` | Per-profile isolated workspaces |
| `gateway_client.py` | HTTP client for agent gateway integration |
| `migrate_to_sqlite.py` | JSON → SQLite migration tool |
| `anti_hallucination.py` | Pre-execution verification |
| `setup.py` | First-time setup script |
| `config/default.json` | Default configuration template |
| `mcp-server-config.json` | MCP server configuration |

## Database

```
~/.config/cortexllm/cortexllm.db

Memory_Hot   → Per-platform active session, FIFO capped at 300/profile
Memory_Warm  → Shared context buffer, rolling 2000
Memory_Cold  → Permanent distilled facts, never expires
Logs         → Event log for observability
Checkpoints  → Session resume points
```

## License

MIT