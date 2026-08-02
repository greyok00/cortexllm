```text
                 ██████╗ ██████╗ ██████╗ ████████╗███████╗██╗  ██╗██╗     ██╗     ███╗   ███╗
                ██╔════╝██╔═══██╗██╔══██╗╚══██╔══╝██╔════╝╚██╗██╔╝██║     ██║     ████╗ ████║
                ██║     ██║   ██║██████╔╝   ██║   █████╗   ╚███╔╝ ██║     ██║     ██╔████╔██║
                ██║     ██║   ██║██╔══██╗   ██║   ██╔══╝   ██╔██╗ ██║     ██║     ██║╚██╔╝██║
                ╚██████╗╚██████╔╝██║  ██║   ██║   ███████╗██╔╝ ██╗███████╗███████╗██║ ╚═╝ ██║
                 ╚═════╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝╚═╝     ╚═╝

    ╔══════════════════════════════════════════════════════════════════╗
    ║  Memory Layer for AI Agents — SQLite · MCP · Ollama              ║
    ║  Hot/Warm/Cold Tiers · Wiki Layer · Conflict Resolution         ║
    ║  Freshness Tracking · Dual Persistence · Model Routing          ║
    ╚══════════════════════════════════════════════════════════════════╝
```

Your AI agents shouldn't forget everything the moment a conversation ends. CortexLLM gives them a shared memory that works across sessions, across platforms, and across any AI model you throw at it.

**One database. One MCP server. Persistent memory for any agent.**

---

## What You Get

### 🧠 Memory That Actually Sticks
Three tiers that work together automatically. Hot memory holds your current session. Warm memory keeps recent context across sessions. Cold memory stores important facts forever. Your agents pick up right where they left off.

### 📚 A Wiki Your Agents Write Themselves
Structured facts with provenance tracking — your agents can record what they learn, cite their sources, and flag contradictions. No more guessing where a fact came from or whether it's still current.

### ⚡ Works With Any AI Model
Ollama, Claude, GPT, local models — doesn't matter. CortexLLM is model-agnostic. The MCP server speaks standard protocol, so any MCP-compatible agent connects instantly.

### 🔄 Never Loses Data
Dual persistence writes to both SQLite and NDJSON files simultaneously. If one goes down, the other saves you. SQLite is the source of truth; NDJSON append is the safety net — no locks, no races.

### 🎯 Smarter Memory, Less Noise
Built-in pruning strips out low-value content before it reaches your model. Context pruning trims the fat. DOM pruning strips web page clutter. Your model gets clean, relevant context every time.

### 🔍 Search That Uses AI
Memory search routes through a small local model that ranks results by relevance and freshness. Recent, verified facts rank higher. Stale facts are flagged but never deleted — you decide what to keep.

---

## How It Works

```
Your Agent → MCP Server → Memory Manager → SQLite Database
                              ↕
                         Flat Files (backup)
```

Three tiers, one flow:

| Tier | What | Lifetime | Who Sees It |
|------|------|----------|-------------|
| **Hot** | Current conversation | This session | Just your platform |
| **Warm** | Recent history | Rolling buffer | All platforms |
| **Cold** | Important facts | Forever | All platforms |

Facts flow Hot → Warm → Cold automatically. The cold distiller reads warm memory periodically, identifies what's worth keeping, and writes it to cold with a confidence score. Cold facts never expire.

---

## Benchmarks

Run `python3 benchmark.py` to reproduce. Results from a standard workstation (SQLite WAL, SSD):

| Operation | P50 | P95 | P99 | Throughput |
|-----------|-----|-----|-----|------------|
| **Write** (wiki_add) | 10.4 ms | 20.7 ms | 23.8 ms | 85 ops/sec |
| **Read** (wiki_get) | 7.9 ms | 11.1 ms | 12.0 ms | 123 ops/sec |
| **Search** (wiki_search) | 14.9 ms | 21.4 ms | 22.6 ms | 64 ops/sec |

**Scale degradation** (search latency as store grows):
| Store size | P50 | P95 |
|------------|-----|-----|
| 10 entries | 15.1 ms | 19.6 ms |
| 100 entries | 15.0 ms | 18.9 ms |
| 1,000 entries | 18.9 ms | 33.2 ms |

**Recall**: 100% with 500 distractor entries. **Persistence**: PASS (data survives write/read roundtrip). **Concurrency**: 100/100 writes retained under sequential load.

---

## How It Compares

| Feature | CortexLLM | Mem0 | Letta (MemGPT) | Zep |
|---------|-----------|------|----------------|-----|
| **Architecture** | SQLite hot/warm/cold + wiki | Vector store + graph | OS-inspired 3-tier | Temporal knowledge graph |
| **Self-hosted** | ✅ One command | ✅ Docker | ✅ Docker | ✅ Docker |
| **Model agnostic** | ✅ Any MCP agent | ✅ Any LLM | ❌ Own runtime | ✅ Any LLM |
| **Conflict resolution** | ✅ SQLite UPSERT | ❌ Recency scoring | ❌ Agent-driven | ❌ Last-write-wins |
| **Freshness tracking** | ✅ Decay-weighted | ❌ Manual delete | ❌ None | ❌ None |
| **Dual persistence** | ✅ SQLite + NDJSON append | ❌ Single store | ❌ Single store | ❌ Single store |
| **Context pruning** | ✅ Built-in | ❌ None | ✅ Agent-driven | ❌ None |
| **DOM pruning** | ✅ Built-in | ❌ None | ❌ None | ❌ None |
| **Wiki layer** | ✅ Structured facts | ❌ Opaque vectors | ❌ Raw text | ❌ Graph only |
| **Provenance tracking** | ✅ Per-fact | ❌ None | ❌ None | ❌ None |
| **MCP support** | ✅ Native | ❌ REST only | ❌ REST only | ❌ REST only |
| **Open source** | ✅ MIT | ✅ Apache 2.0 | ✅ Apache 2.0 | ✅ Apache 2.0 |
| **Pricing** | Free | Free tier → $249/mo | Free tier → Cloud | Free tier → $299/mo |
| **GitHub stars** | — | 48K+ | 21K+ | 12K+ |

**Key differentiators:**
- **Only system with built-in wiki + provenance** — facts aren't opaque vectors, they're structured with entity/attribute/claim/evidence
- **Only system with conflict resolution** — SQLite UPSERT means contradictory facts are caught at the database layer, not via fuzzy matching
- **Only system with dual persistence** — SQLite + flat files means no single point of failure
- **Only system with MCP-native protocol** — no REST wrapper needed, any MCP agent connects instantly
- **Only system with context + DOM pruning** — your model gets clean, relevant context every time

---

```bash
# Copy to your OpenClaw installation
cp -r . ~/.openclaw/cortexllm/

# Start the MCP server
python3 cortexllm_mcp_server.py

# Connect any MCP agent and go. Database auto-initializes on first use.
```

---

## Model Setup

CortexLLM works with any AI provider. The model router handles memory search separately from your main reasoning model.

**Ollama (default):**
```bash
export CORTEXLLM_SMALL_MODEL="qwen3.6:1.5b"
```

**Anthropic / OpenAI / anything else:**
No special config needed. Just point your MCP client at `cortexllm_mcp_server.py`. The MCP server is model-agnostic — your agent handles the AI, CortexLLM handles the memory.

**Disable the model router (uses simple text matching):**
```bash
unset CORTEXLLM_SMALL_MODEL
```

### Environment Variables

| Variable | Default | What it does |
|----------|---------|-------------|
| `CORTEXLLM_SMALL_MODEL` | `qwen3.6:1.5b` | Small model for memory search. Any Ollama model name works |
| `CORTEXLLM_SMALL_MODEL_URL` | `http://127.0.0.1:11434/api/generate` | Ollama endpoint for the small model |
| `CORTEXLLM_DB_PATH` | `~/.config/cortexllm/cortexllm.db` | Where to store the database |

---

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

The wiki layer lives inside `Memory_Cold` using SQLite's JSON1 functions. No separate database or file.

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

---

## Files

| File | What it does |
|------|-------------|
| `cortexllm_db.py` | Database — schema, migrations, wiki layer, conflict resolution, freshness |
| `cortexllm_mcp_server.py` | MCP server — connects any agent to memory and wiki tools |
| `cortexllm_models.py` | Data models for memory and wiki facts |
| `memory_manager.py` | Manages hot/warm/cold tiers + dual persistence |
| `model_router.py` | Routes memory search to a small local model |
| `context_pruner.py` | Strips low-value content before it reaches your model |
| `dom_pruner.py` | Cleans up web page DOM for browser-use agents |
| `prompt_pruner.py` | Compresses prompts to fit token budgets |
| `heartbeat_service.py` | Health monitoring + wiki contradiction checks |
| `anti_hallucination.py` | Verifies claims before code generation |
| `benchmark.py` | Performance benchmark suite — latency, throughput, recall, scale |
| `hard-memory-templates/` | Starter templates for dual persistence |

---

## Integrations

- **OpenClaw** — Memory via `memory-core` plugin + heartbeat
- **Claude Code** — Memory via MCP server in `~/.claude/mcp.json`
- **Cursor** — Memory via MCP server config
- **Any MCP client** — Connect to `cortexllm_mcp_server.py`

---

## Changelog

### v3.2.0 — Atomic NDJSON, Session Resume, Visual Output
- **Atomic NDJSON append** — hot memory switched from read-modify-write+flock to append-only NDJSON. No locks, no races, no timeouts.
- **Lock-free hooks** — removed all `flock`/`fcntl` from hook scripts and writers. Hooks complete instantly.
- **Session resume** — new CLAUDE.md rules: "continue"/"go"/"retry" triggers memory read + verbatim last prompt quote.
- **Visual startup dashboard** — cold/hot/warm memory shown in tables with emojis. Hard rules extracted and displayed prominently.
- **Response style overhaul** — default to tables > charts > checklists > lists > emojis. Never dump raw tool names.
- **Hard Rules → Cold Memory** — user-stated rules saved to cold memory instead of editing CLAUDE.md.
- **CLAUDE.md minified** — global: 9763B → 3743B (62% smaller). CortexAgent: 1101B. Both locked read-only.
- **Auto-update disabled** — `CLAUDE_CODE_DISABLE_UPDATE=1` in wrapper. `chattr +i` + `chmod 444` protection.
- **All writers migrated** — `save-context.py`, `save-session.py` (x2), `browser_memory_hook.py`, `scheduler/core.py`, `canvas_homework_checker.py`, `cortexllm_mcp_server.py` all use NDJSON append.
- **25 legacy .json files migrated** to .jsonl and cleaned up.

## License

MIT
