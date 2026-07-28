# CortexLLM

**Unified memory layer for AI agents.** SQLite-based hot/warm/cold memory tiers with a wiki layer, conflict resolution, freshness tracking, dual persistence, and model routing. Designed for OpenClaw + Ollama, but forkable to any agentic AI platform.

CortexLLM is a drop-in memory system that gives AI agents persistent, structured memory across sessions. It runs as a local SQLite database with three tiers — hot (active session), warm (shared context), cold (permanent facts) — and exposes them via an MCP server any agent can connect to.

The primary implementation targets OpenClaw running on Ollama (`deepseek-v4-flash:cloud`), but the architecture is platform-agnostic. The MCP server speaks the standard Model Context Protocol, so any MCP-compatible agent (Claude Code, Cursor, custom agents) can read and write memory. The SQLite schema and memory manager are pure Python with no OpenClaw-specific dependencies — fork it, point it at your own database path, and it works.

## Features

| Feature | Description |
|---------|-------------|
| **Three-tier memory** | Hot (per-platform FIFO, capped at 300), Warm (shared context buffer), Cold (permanent distilled facts) |
| **Wiki layer** | Structured facts inside Memory_Cold — entity, attribute, claim, evidence (JSON array), provenance, contradiction tracking |
| **Conflict resolution** | SQLite UPSERT keyed on (entity, attribute, provenance). Older row flagged, superseded_by points to new row. Both preserved for provenance |
| **Freshness tracking** | Decay-weighted freshness score at query time from `last_verified`. Facts stale after 30 days (configurable) but never auto-deleted |
| **Dual persistence** | Write-through to per-platform flat files alongside SQLite. SQLite is canonical. Reduces memory rewrite/corruption risk |
| **Model routing** | `memory_search` and `memory_read` routed to a small local Ollama model (1B-3B). Configurable via env var. Graceful fallback to primary model |
| **Context pruning** | Pre-assembly stage strips low-value tokens, RAG-retrieves relevant rows, sliding-window turn-summarization. Fully local |
| **DOM pruning** | Session-aware DOM structure stripping for browser/tool-use contexts. Cached per-session within a task. Fully local |
| **SQLite-native** | WAL mode, single-writer, indexed queries. No JSON files for state |
| **MCP server** | Exposes `memory_read`, `memory_write`, `memory_search`, `memory_clear`, plus wiki tools |
| **Platform-agnostic** | Works with Claude Code, Cursor, custom agents — anything that speaks MCP |
| **Per-profile isolation** | Each platform gets its own hot memory scope. Warm and cold are shared by default |
| **Cold distiller** | Background process that reads warm memory, identifies useful facts, and writes them to cold with confidence scores |
| **Session recovery** | On restart, reads the last checkpoint and resumes from the last command |
| **Isolated heartbeat** | 30-minute interval, runs in its own session, includes wiki contradiction reconciliation pass |
| **Single model** | `deepseek-v4-flash:cloud` via Ollama. No OpenAI, Anthropic, or other providers |

## Database

```
~/.config/cortexllm/cortexllm.db  (WAL mode)

Memory_Hot   → Per-platform active session, FIFO capped at 300/profile
Memory_Warm  → Shared context buffer, rolling 2000
Memory_Cold  → Permanent distilled facts + wiki layer, never expires
  ├── entity, attribute, claim     — structured wiki fact
  ├── evidence (JSON array)        — supporting references
  ├── provenance                   — "openclaw" or "claude"
  ├── contradiction_flag           — flagged when superseded
  ├── superseded_by (FK)          — points to newer row
  └── last_verified                — freshness timestamp
Logs         → Event log for observability
Checkpoints  → Session resume points
```

### Wiki Layer Schema

The wiki layer lives inside the existing `Memory_Cold` table using SQLite's native JSON1 functions. No separate database or file.

```sql
-- Composite unique key for UPSERT conflict resolution
CREATE UNIQUE INDEX idx_cold_entity_attr_provenance
  ON Memory_Cold(entity, attribute, provenance);

-- On conflict: flag old row, point superseded_by at new row
INSERT INTO Memory_Cold (entity, attribute, claim, evidence, provenance, last_verified)
VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(entity, attribute, provenance) DO UPDATE SET
  contradiction_flag = 1,
  superseded_by = excluded.id;

-- Freshness scoring at query time
SELECT *, confidence * MAX(0, 1 - (julianday('now') - julianday(COALESCE(last_verified, timestamp))) / 30.0) AS freshness_score
FROM Memory_Cold
WHERE contradiction_flag = 0 AND superseded_by IS NULL;
```

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Ollama API                                 │
│                    deepseek-v4-flash:cloud                        │
│                    (primary model for reasoning)                  │
│                    qwen3.6:1.5b (small model for memory ops)      │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                    CortexLLM Engine                               │
│                                                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │ Memory      │  │ Model Router │  │ Context/DOM Pruner     │  │
│  │ Manager     │  │ (small model)│  │ (pre-assembly stage)   │  │
│  │ + Dual      │  │              │  │                        │  │
│  │ Persistence │  │              │  │                        │  │
│  └──────┬──────┘  └──────────────┘  └────────────────────────┘  │
│         │                                                         │
│         ▼                                                         │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │              CortexLLM SQLite Database                      │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │   │
│  │  │    Hot   │→ │   Warm   │→ │   Cold   │  │   Hard   │   │   │
│  │  │ Memory   │  │ Memory   │  │ + Wiki   │  │ Files    │   │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │   │
│  └────────────────────────────────────────────────────────────┘   │
│                         │                                         │
│                         ▼                                         │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │              CortexLLM MCP Server                           │   │
│  │  Tools: memory_read · memory_write · memory_search          │   │
│  │         memory_clear · wiki_add · wiki_get · wiki_search    │   │
│  │         wiki_reconcile · wiki_verify · wiki_stale           │   │
│  │  Connected to: Claude Code, OpenClaw, any MCP client         │   │
│  └────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### Dual Persistence Design

On every `memory_write` to Memory_Hot or Memory_Warm, the write is synchronously mirrored to a per-platform flat file (Markdown-style) in `~/.config/cortexllm/memory/hard/`. This write-through layer empirically reduces memory rewrite/corruption issues by providing a stable file-based fallback that doesn't depend on SQLite WAL state.

- **SQLite is canonical** — the flat file is the write-through mirror, not the other way around
- **On startup/read**, if the two ever disagree, SQLite wins and the flat file is regenerated from it
- **GENERIC starter templates** are included in `hard-memory-templates/` for new users

## Files

| File | Purpose |
|------|---------|
| `cortexllm_db.py` | Database layer — schema, migrations, wiki layer, UPSERT, freshness tracking |
| `cortexllm_mcp_server.py` | MCP server — exposes all memory and wiki tools |
| `cortexllm_models.py` | Pydantic models — ColdFact, WikiFact, WikiSearchResult |
| `memory_manager.py` | Memory manager — hot/warm/cold operations, dual persistence write-through |
| `model_router.py` | Routes memory_search/read to small local Ollama model |
| `context_pruner.py` | Pre-assembly pruning — low-value token stripping, RAG retrieval, sliding-window summarization |
| `dom_pruner.py` | Session-aware DOM pruning for browser/tool-use contexts |
| `prompt_pruner.py` | Deterministic 4-pass prompt pruning pipeline |
| `heartbeat_service.py` | Session health monitor + wiki contradiction reconciliation pass |
| `anti_hallucination.py` | Post-response verification |
| `hard-memory-templates/` | GENERIC starter templates for dual persistence flat files |

## Setup

```bash
cp -r cortexllm/ ~/.openclaw/cortexllm/
# Database auto-initializes on first use
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CORTEXLLM_SMALL_MODEL` | `qwen3.6:1.5b` | Small Ollama model for memory operations |
| `CORTEXLLM_SMALL_MODEL_URL` | `http://127.0.0.1:11434/api/generate` | Ollama endpoint for small model |
| `CORTEXLLM_DB_PATH` | `~/.config/cortexllm/cortexllm.db` | Database location |

## Forking

To adapt CortexLLM for another agent platform:

1. Copy `cortexllm/` to your project
2. Set `CORTEXLLM_DB_PATH` to your desired database location
3. Run `cortexllm_mcp_server.py` as an MCP server — any MCP-compatible agent can connect
4. The SQLite schema auto-initializes on first use. No migrations needed.
5. Copy `hard-memory-templates/` to your config directory for dual persistence

## Integrations

- **OpenClaw**: Memory via `memory-core` plugin + `heartbeat` config
- **Claude Code**: Memory via `cortexllm` MCP server
- **Any MCP client**: Connect to `cortexllm_mcp_server.py` for memory read/write/search/wiki

## License

MIT
