# CortexLLM

**Local-first AI orchestration. Persistent memory. Multi-agent task routing. Terminal-native.**

[![Version](https://img.shields.io/badge/version-0.3.0-brightgreen)](https://github.com/greyok00/cortexllm/releases)
[![Go Build](https://img.shields.io/badge/go-1.24+-00ADD8?logo=go)](https://go.dev)
[![Python](https://img.shields.io/badge/python-3.10+-3776AB?logo=python)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Status](https://img.shields.io/badge/status-active%20development-orange)](#)

CortexLLM is a terminal-based AI control system that coordinates multiple AI agents under a central Brain, routes tasks to the right model at the right cost, and keeps everything it learns across sessions. Instead of starting from scratch every time, it maintains hot/warm/cold memory tiers so context is always available. Instead of using one model for everything, it routes heavy reasoning to a capable model and high-volume work to a cheaper, faster worker — configurable per task.

> ⚠️ **Active Development — v0.3.0.** Core memory system and worker routing are functional. TUI improvements are ongoing. See [ROADMAP.md](ROADMAP.md) for what's planned.

---

## What It Does

| Feature | Description |
|---------|-------------|
| **Multi-agent orchestration** | A central Brain routes tasks to specialized workers (OpenCode, OpenClaw, or custom agents) |
| **Configurable model routing** | Each worker slot targets cloud or local Ollama models independently via env/config |
| **Automatic downstepping** | Heavy reasoning → primary model; high-volume text tasks → cheaper worker with per-slot token caps |
| **Three-tier memory** | Hot (active session), Warm (recent cross-session), Cold (permanent vault) — all atomic JSON writes |
| **DOM pruning** | Browser/scraper workers strip scripts, ads, SVGs, and headers before content hits the context window |
| **Heartbeat + session recovery** | Synchronous heartbeat runs before every agent turn to rehydrate context and recover stale sessions |
| **Background promoter** | Async "dreamer" worker scans warm memory and promotes durable facts to cold vault |
| **Anti-hallucination protocol** | Workers must verify CLI flags, service health, and grep source before generating or executing code |
| **Atomic writes** | All memory updates use temp-file + rename to prevent corruption on crash |
| **Terminal UI** | Bubble Tea TUI with chat, workers dashboard, and token usage widget |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        CORTEXLLM                             │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌──────────────────────────────────────────────────────┐  │
│   │                   BRAIN (Orchestrator)                │  │
│   │   Reasoning Slot          Worker Slot                 │  │
│   │   (qwen/qwen3.5 cloud)    (deepseek/deepseek-chat)    │  │
│   └────────────────────────┬─────────────────────────────┘  │
│                            │                                 │
│        ┌───────────────────┼───────────────────┐            │
│        ▼                   ▼                   ▼            │
│   ┌─────────┐        ┌──────────┐        ┌──────────┐       │
│   │OpenCode │        │OpenClaw  │        │ Custom   │       │
│   │Planner  │        │Executor  │        │ Workers  │       │
│   └────┬────┘        └────┬─────┘        └────┬─────┘       │
│        │                  │                   │             │
│        └──────────────────┼───────────────────┘            │
│                           │                                 │
│                  ┌────────▼────────┐                        │
│                  │  MEMORY SYSTEM  │                        │
│                  │  HOT/WARM/COLD  │                        │
│                  └─────────────────┘                        │
│                           │                                 │
│          ┌────────────────┴────────────────┐               │
│          ▼                                 ▼               │
│   ┌─────────────────┐             ┌─────────────────┐      │
│   │  SessionHeart-  │             │  Background     │      │
│   │  beat (sync)    │             │  Promoter       │      │
│   │  runs before    │             │  (async dreamer)│      │
│   │  every turn     │             │  promotes warm  │      │
│   └─────────────────┘             │  → cold vault   │      │
│                                   └─────────────────┘      │
└──────────────────────────────────────────────────────────────┘
```

### Agents

- **Brain** — Central orchestrator. Manages sessions, routes tasks between reasoning and worker slots, and enforces the SEARCH FIRST anti-hallucination protocol.
- **OpenCode (Planner)** — Handles high-level reasoning, code generation, and strategic analysis. Targets the reasoning model slot.
- **OpenClaw (Executor)** — Handles browser automation via CDP (port 9222), shell commands, and local file operations. Targets the worker slot.
- **Custom Workers** — Additional named workers can be defined and routed independently. Each has its own kill command, model config, and per-slot token cap.

### Model Routing

Each slot is configured independently in `config.json` or via environment variables:

```
Reasoning Slot → qwen/qwen3.5 (cloud)
Worker Slot    → deepseek/deepseek-chat (cloud)
```

Override either slot to a local Ollama instance without touching the other.

---

## Memory Tiers

| Tier | Location | Default Limit | Purpose |
|------|----------|---------------|---------|
| **HOT** | `~/.config/cortexllm/memory/hot/` | 50 msgs | Active session context, flushed to disk atomically |
| **WARM** | `~/.config/cortexllm/memory/warm/` | Dynamic (scales with number of active models) | Recent cross-session context; 70/30 split keeps buffer for all platforms |
| **COLD** | `~/.config/cortexllm/memory/cold/` | Unlimited | Permanent knowledge vault — facts, workflows, decisions, lessons |

**Warm memory scales automatically.** With 2 models it splits 70/30 (each gets 30% guaranteed buffer); with 3 it becomes roughly 70/10/10/10; the system auto-adjusts the per-model buffer floor as you add or remove workers.

**COLD vault schema** (every record is structured):
- `id`, `entity`, `record_type` (fact / preference / workflow / decision / lesson)
- `summary`, `detail`, `source_kind`, `confidence`, `confirmation_count`
- `tags`, `status` (active / superseded / stale), `created_at`, `last_seen_at`

---

## Quick Install

### One-Line Install
```bash
curl -fsSL https://raw.githubusercontent.com/greyok00/cortexllm/main/install.sh | bash
```

### From Source
```bash
git clone https://github.com/greyok00/cortexllm.git
cd cortexllm
bash install.sh
```

### Verify
```bash
cortexllm --version
cortexllm
```

---

## Requirements

### Core
- **Go 1.24+** — TUI binary
- **Python 3.10+** — Worker backend
- **Ollama** running on port 11434 (optional — only needed if using local model overrides)

### Optional
- **OpenClaw Gateway** on port 18789 — agent/executor features
- **Brave Browser (CDP)** on port 9222 — browser automation
- **Searxng** on port 8888 — web search integration

---

## Configuration

Config file: `~/.config/cortexllm/config.json`

```json
{
  "system": {
    "name": "CortexLLM",
    "version": "0.3.0"
  },
  "router": {
    "reasoning_model": "qwen/qwen3.5",
    "reasoning_host": "https://openrouter.ai/api/v1",
    "worker_model": "deepseek/deepseek-chat",
    "worker_host": "https://api.deepseek.com",
    "reasoning_token_cap": 8192,
    "worker_token_cap": 4096
  },
  "platforms": {
    "openclaw": {
      "enabled": true,
      "mode": "cli",
      "token_env": "OPENCLAW_GATEWAY_TOKEN"
    },
    "opencode": {
      "enabled": true,
      "mode": "cloud",
      "endpoint": "https://openrouter.ai/api/v1"
    }
  },
  "memory": {
    "path": "~/.config/cortexllm/memory",
    "hot_limit": 50,
    "warm_buffer_pct": 30,
    "auto_rotate": true,
    "auto_compact": true,
    "write_interval": 2
  },
  "gateway": {
    "port": 18789,
    "bind": "lan"
  },
  "browser": {
    "enabled": true,
    "cdp_url": "http://127.0.0.1:9222"
  },
  "search": {
    "enabled": true,
    "provider": "searxng",
    "base_url": "http://127.0.0.1:8888"
  },
  "userStyle": {
    "path": "~/.config/cortexllm/USER_STYLE.md",
    "enforce": true
  }
}
```

### Environment Variables
```bash
export OPENCLAW_GATEWAY_TOKEN=your_token_here
export OPENROUTER_API_KEY=your_openrouter_key_here   # for Qwen reasoning slot
export DEEPSEEK_API_KEY=your_deepseek_key_here       # for DeepSeek worker slot
export CORTEXLLM_CONFIG_PATH=~/.config/cortexllm/config.json
# Local Ollama override (optional — replaces cloud defaults)
export OLLAMA_HOST=127.0.0.1:11434
```

---

## Usage

### Launch TUI
```bash
cortexllm
```

### Keyboard Controls
| Key | Action |
|-----|--------|
| `Tab` | Switch platform / move focus |
| `↑ / ↓` | Scroll messages |
| `Enter` | Send message |
| `Ctrl+T` | Theme picker |
| `Ctrl+P` | Config overlay |
| `Ctrl+C` | Quit (auto-saves) |

### CLI Commands
```bash
cortexllm send "research Python async patterns"
cortexllm memory status
cortexllm tasks list
```

### Python Backend (Headless)
```bash
# Run without TUI
python3 -m cortexllm.cli.unified

# Watch backend status
python3 watch.py
```

---

## SEARCH FIRST Protocol (Anti-Hallucination)

Every worker must complete these steps **before** generating or executing code:

1. Verify CLI flags via `--help`
2. Check service health (e.g., `curl <port>/health`)
3. Search local source code for existing patterns with `grep`
4. Show research results to the user

This is enforced at the Brain level — workers that skip verification are retried.

---

## Project Structure

```
cortexllm/
├── main.go                     # Go TUI (Bubble Tea)
├── proxy/main.go               # Message proxy
├── install.sh                  # Installer
├── watch.py                    # Backend status monitor
├── memory-tools.py             # Memory CLI utilities
├── migrate-*.py                # Memory migration scripts
├── cortexllm/                  # Python package
│   ├── core/
│   │   ├── brain.py            # Task orchestration + queue drain
│   │   ├── memory.py           # Atomic persistence
│   │   ├── config.py           # Configuration loader
│   │   └── orchestrator.py     # Worker routing
│   ├── workers/
│   │   └── __init__.py         # Worker definitions
│   └── cli/
│       └── unified.py          # Headless CLI
├── configs/
│   └── default.json
├── docs/
├── scripts/
└── .github/                    # CI/CD
```

---

## Troubleshooting

### TUI Won't Start
```bash
~/.local/bin/cortexllm         # run binary directly to see error
curl http://127.0.0.1:11434/api/tags   # check Ollama (if using local override)
ls -la ~/.config/cortexllm/memory/    # check memory dir
```

### OpenClaw Integration Fails
```bash
curl http://127.0.0.1:18789/health
echo $OPENCLAW_GATEWAY_TOKEN
systemctl --user restart openclaw-gateway
```

### Memory Not Saving
```bash
chmod 755 ~/.config/cortexllm
cat ~/.config/cortexllm/memory/hot/opencode.json | jq
df -h ~/.config
```

---

## Security

- **Token Auth** — Gateway requires `GATEWAY_TOKEN` env variable
- **Local Only** — All services bind to localhost/LAN by default
- **No Cloud by Default** — Data stays on your machine; cloud models require explicit config
- **Atomic Writes** — Temp-file + rename on every memory update

---

## Android / Termux

CortexLLM can run on Android via Termux:

```bash
# Install Termux from F-Droid (preferred) or Play Store
# Do NOT mix F-Droid and Play Store installs on the same device

pkg install golang python
git clone https://github.com/greyok00/cortexllm.git
cd cortexllm && bash install.sh
```

For a cross-compiled TUI binary (no Termux required at runtime):
```bash
GOOS=android GOARCH=arm64 go build -o cortex-tui ./main.go
```

See [ROADMAP.md](ROADMAP.md) for the Android wrapper app milestone.

---

## Roadmap

See [ROADMAP.md](ROADMAP.md) for the full feature roadmap with milestones and implementation checklists.

---

## Development

```bash
# Build Go TUI
go build -o ~/.local/bin/cortexllm ./main.go

# Install Python workers (editable)
pip3 install -e .

# Test memory system
python3 -c "from cortexllm.core.memory import Memory; m = Memory(); print('OK')"

# Run test suite
make test
```

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m 'Add feature'`
4. Push: `git push origin feature/my-feature`
5. Open a Pull Request

---

## License

MIT — see [LICENSE](LICENSE).

---

**Built by [@greyok00](https://github.com/greyok00)**  
*Terminal-native AI orchestration for the modern developer*
