# CortexLLM

> Universal Memory System for AI Agents

[![Version](https://img.shields.io/badge/version-2026.6.29-blue)](https://github.com/yourusername/cortexllm)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## What is CortexLLM?

CortexLLM is a cross-platform session persistence and memory system that enables AI agents to:

- **Maintain persistent memory** across sessions and platforms
- **Share context** between different AI systems (OpenClaw, Claude Desktop, OpenCode)
- **Auto-recover** from session errors and context overflow
- **Prevent hallucinations** through verification systems
- **Detect failure loops** before wasting tokens

## Quick Start

```bash
# Install
cd ~/.openclaw/production/cortexllm
./install.sh

# Verify installation
cortexllm-watch
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   CortexLLM Core                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Session    │  │    Memory    │  │   Heartbeat  │  │
│  │  Heartbeat   │  │    Manager   │  │   Service    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │    Model     │  │   Anti-      │  │    Loop      │  │
│  │    Router    │  │ Hallucination│  │    Guard     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
   ┌──────────┐   ┌──────────┐   ┌──────────┐
   │ OpenClaw │   │  Claude  │   │ OpenCode │
   │ (MCP)    │   │ Desktop  │   │  (MCP)   │
   └──────────┘   └──────────┘   └──────────┘
```

### Memory Tiers

| Tier | Location | Purpose |
|------|----------|---------|
| **Hot** | `~/.config/cortexllm/memory/hot/{platform}.json` | Active session per platform |
| **Warm** | `~/.config/cortexllm/memory/warm/unified.json` | Merged cross-platform context |
| **Cold** | `~/.config/cortexllm/memory/cold/{category}.json` | Archived/permanent knowledge |

## Core Features

### 1. Session Heartbeat
Runs before every agent turn to:
- Detect context overflow before failures
- Auto-rotate sessions when corrupted
- Rehydrate context from warm memory
- Handle file lock conflicts

### 2. Anti-Hallucination System
Verifies before acting:
- Files exist and are readable
- Services are running (port + process)
- Commands exist in PATH
- User claims match reality

### 3. Loop Guard
Prevents wasted tokens:
- Detects repetitive failure patterns
- Blocks after 3 failures or 2 same-approach failures
- Forces strategy change

### 4. Model Router
Automatic delegation:
- Primary model for reasoning/planning
- Worker model for simple tasks
- Transparent sub-agent spawning

### 5. MCP Server
Universal memory access:
- `memory_read`, `memory_write`, `memory_search`
- Any MCP-compatible client can connect
- Shared context across all platforms

## Installation

```bash
cd ~/.openclaw/production/cortexllm
./install.sh
```

Installs:
- CortexLLM Python package
- MCP server and systemd services
- Session heartbeat (all platforms)
- Anti-hallucination and loop guard
- Auto-save cron job

## Configuration

**Location:** `~/.config/cortexllm/config.json`

```json
{
  "brain": {
    "heartbeat_interval": 30,
    "task_timeout": 300
  },
  "browser": {
    "cdp_url": "http://127.0.0.1:9222"
  },
  "search": {
    "base_url": "http://127.0.0.1:8888"
  }
}
```

## Platform Support

| Platform | Heartbeat | Memory | MCP |
|----------|-----------|--------|-----|
| OpenClaw | ✅ Skill | ✅ Hot/Warm | ✅ |
| Claude Desktop | ✅ MCP | ✅ Hot/Warm | ✅ |
| OpenCode | ✅ Pre-turn hook | ✅ Hot/Warm | ✅ |

## Files

### Source
- `~/.openclaw/production/cortexllm/` - Master repository

### Installed To
- `~/.config/cortexllm/` - Config and memory
- `~/.local/bin/` - Binaries
- `~/.openclaw/skills/` - OpenClaw skills
- `~/.config/opencode/hooks/` - OpenCode hooks

## Services

### systemd
- `cortexllm.service` - Main memory sync
- `cortexllm-heartbeat.service` - Health monitoring (5-min)
- `cortexllm-mcp.service` - MCP server

### Cron
- Auto-save: `* * * * *` - Captures sessions every minute

## Development

```bash
# Run tests
python3 -m pytest

# Type check
mypy cortexllm/
```

## License

MIT - See [LICENSE](LICENSE)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
