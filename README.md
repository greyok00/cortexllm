# CortexLLM

<p align="center">
<pre>
  █▄        ▄█
  ███▄▄▄▄▄▄███
   ██ ▀██▀ ██
   ███▀▀▀▀███
  ▄██████████▄
  ██▀██████▀██
     ██████
    ▄█▀  ▀█▄
</pre>
  <em>Unified memory for local AI agents</em>
</p>

SQLite-backed hot/warm/cold memory tiers with an MCP interface. Designed for
local AI agents that need persistent, recoverable context without a cloud
dependency.

## Features

- **Three memory tiers:** Hot (FIFO 300), Warm (2000 cap, 70/30 buffer), Cold (distilled facts)
- **SQLite storage:** Single-file database with WAL mode, no external services
- **MCP interface:** stdio MCP server exposes memory_read/write/search/clear/stats
- **Session recovery:** Auto-injects last request + recent memory on startup
- **Auto-save:** Hooks save every prompt/response through the memory pipeline
- **Context replay:** Last prompt replayed after auto-compact
- **Minified prompts:** CLAUDE.md and AGENT.md stripped to essential signal

## Requirements

- Python 3.10+
- `claude` (Claude Code) CLI on PATH

## Install

```bash
git clone https://github.com/greyok00/cortexllm.git ~/.cortexllm
cd ~/.cortexllm
bash install.sh
```

## CLI usage

```bash
cortexllm_call.py recent --limit 12
cortexllm_call.py write --role user --content "your prompt"
cortexllm_call.py search "query" --limit 10
```

## MCP tools

| Tool | Description |
|---|---|
| `memory_read` | Read hot/warm/cold memory |
| `memory_write` | Write a message or fact |
| `memory_search` | Search warm memory |
| `memory_stats` | Show memory counts |
| `memory_clear` | Clear hot or warm memory |

## Project layout

```
cortexllm/
├── memory/                    # SQLite memory core + MCP server
│   ├── db.py
│   ├── manager.py
│   └── mcp_server.py
├── lib/                       # CLI shim, state helpers
├── config/                    # CLAUDE.md, AGENT.md, settings/templates
├── hooks/                     # SessionStart, UserPromptSubmit, Stop
├── install.sh
└── README.md
```

## Dependencies

**stdlib-only Python.** Nothing is installed from PyPI.

## License

MIT — see [LICENSE](LICENSE).
