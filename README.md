# CortexLLM

**Unified AI Control for Your Terminal**

[![Go Build](https://img.shields.io/badge/go-1.24+-00ADD8?logo=go)](https://go.dev)
[![Python](https://img.shields.io/badge/python-3.8+-3776AB?logo=python)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

CortexLLM is a fast local AI control system built for task execution and continuous learning. It keeps recent context in hot memory, promotes durable knowledge into cold storage, and uses a heartbeat to recover sessions and rehydrate context automatically. The result is that it can move through repetitive or high-volume work much faster than wiki-style memory systems, while still learning over time instead of starting from scratch each session.

> **Status:** TUI is currently **Work in Progress**. Memory system and integrations are production-ready.

![Mission Control Overview](./docs/images/mission-control-overview.png)

---

## Features

| Feature | Description |
|---------|-------------|
| 🧠 **Unified Memory** | Hot/Warm/Cold tiers with atomic persistence |
| ⚡ **Fast TUI** | Bubble Tea interface with multiple themes |
| 🔌 **Platform Agnostic** | OpenClaw, OpenCode, Ollama, or direct API |
| 🤖 **Agent System** | Brain orchestrator + specialized workers |
| 💾 **Auto-Save** | Every 2 seconds + on quit |
| 🎨 **Multiple Themes** | Professional color schemes |

---

## Quick Install

### One-Line Install
```bash
curl -fsSL https://raw.githubusercontent.com/greyok00/cortexllm/main/scripts/install.sh | bash
```

### From Source
```bash
git clone https://github.com/greyok00/cortexllm.git
cd cortexllm
make install
```

### Verify Installation
```bash
cortexllm --version
cortexllm
```

---

## Requirements

### Minimum
- **Go 1.24+** (for TUI binary)
- **Python 3.8+** (for workers)
- **Ollama** running on port 11434

### Optional
- **OpenClaw Gateway** on port 18789 (for agent features)
- **Brave Browser CDP** on port 9222 (for browser automation)
- **Searxng** on port 8888 (for web search)

---

## Usage

### Launch TUI
```bash
cortexllm
```

### Keyboard Controls
| Key | Action |
|-----|--------|
| `Tab` | Switch platform |
| `↑/↓` | Scroll messages |
| `Enter` | Send message |
| `Ctrl+T` | Theme picker |
| `Ctrl+P` | Config overlay |
| `Ctrl+C` | Quit (auto-saves) |

### CLI Commands
```bash
# Send a message
cortexllm send "research Python async patterns"

# Check memory status
cortexllm memory status

# List recent tasks
cortexllm tasks list
```

---

## Configuration

### Config File Location
`~/.config/cortexllm/config.json`

### Example Configuration
```json
{
  "system": {
    "name": "CortexLLM",
    "version": "1.0.0"
  },
  "platforms": {
    "openclaw": {
      "enabled": true,
      "mode": "cli",
      "token_env": "OPENCLAW_GATEWAY_TOKEN"
    },
    "opencode": {
      "enabled": true,
      "mode": "ollama",
      "endpoint": "http://127.0.0.1:11434"
    }
  },
  "model": {
    "primary": "ollama/qwen3.5:cloud",
    "fallback": "ollama/llama3.1:8b"
  },
  "memory": {
    "hot_limit": 500,
    "warm_limit": 2000,
    "auto_rotate": true
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
  }
}
```

### Environment Variables
```bash
# Optional: OpenClaw authentication
export OPENCLAW_GATEWAY_TOKEN=your_token_here

# Optional: Custom config path
export CORTEXLLM_CONFIG_PATH=~/.config/cortexllm/config.json

# Optional: Ollama endpoint
export OLLAMA_HOST=127.0.0.1:11434
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    CORTEXLLM SYSTEM                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   ┌─────────────┐    ┌─────────────┐                   │
│   │  OpenCode   │    │  OpenClaw   │                   │
│   │  (Ollama)   │    │  (Gateway)  │                   │
│   └──────┬──────┘    └──────┬──────┘                   │
│          │                  │                          │
│          └────────┬─────────┘                          │
│                   │                                    │
│          ┌────────┴────────┐                          │
│          │  BRAIN AGENT    │                          │
│          │  (Orchestrator) │                          │
│          └────────┬────────┘                          │
│                   │                                    │
│          ┌────────┴────────┐                          │
│          │  WORKERS        │                          │
│          │  (Tech, OSINT,  │                          │
│          │   Business,     │                          │
│          │   Earner)       │                          │
│          └────────┬────────┘                          │
│                   │                                    │
│          ┌────────┴────────┐                          │
│          │  MEMORY SYSTEM  │                          │
│          │  Hot/Warm/Cold  │                          │
│          └─────────────────┘                          │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Memory Tiers

| Tier | Location | Limit | Purpose |
|------|----------|-------|---------|
| **HOT** | `~/.config/cortexllm/memory/hot/` | 500 msgs | Active sessions |
| **WARM** | `~/.config/cortexllm/memory/warm/` | 2000 msgs | Shared context with buffer |
| **COLD** | `~/.config/cortexllm/memory/cold/` | Unlimited | Permanent knowledge |

### Buffer Algorithm

The warm memory tier uses a 70/30 buffer algorithm:
- **70% Recent** (1400 messages) - Weighted by platform usage
- **30% Buffer** (600 messages) - Always preserved from both platforms (300 each)

This ensures neither OpenCode nor OpenClaw ever loses context, even if one platform is used exclusively for extended periods.

---

## Themes

Press `Ctrl+T` to open the theme picker:

| Theme | Description | Colors |
|-------|-------------|--------|
| Cyber Pastel | Modern terminal aesthetic | Blue/Purple/Mint |
| Ocean Breeze | Calm sea-inspired tones | Cyan/Indigo/Teal |
| Forest Mist | Natural earth tones | Sage/Seafoam/Sun |

More themes coming in future releases.

---

## Platform Support

### OpenClaw Mode
Uses OpenClaw CLI for full agent capabilities:
```bash
openclaw agent --agent brain --message "research Python async"
```

### OpenCode Mode
Direct Ollama API integration:
```bash
curl http://127.0.0.1:11434/api/generate -d '{"model":"qwen3.5:cloud","prompt":"hello"}'
```

### Standalone Mode
Works with just Ollama - no OpenClaw required:
```json
{
  "platforms": {
    "openclaw": { "enabled": false },
    "opencode": { "enabled": true, "mode": "ollama" }
  }
}
```

### Adding New Platforms
To add Claude, OpenAI, or other providers, update config:
```json
{
  "platforms": {
    "claude": {
      "enabled": true,
      "mode": "api",
      "endpoint": "https://api.anthropic.com/v1/messages",
      "auth_env": "ANTHROPIC_API_KEY"
    }
  }
}
```

---

## Development

### Build from Source
```bash
# Build Go TUI
cd cortexllm
go build -o ~/.local/bin/cortexllm ./main.go

# Install Python workers
pip3 install -e .
```

### Project Structure
```
cortexllm/
├── main.go                    # Go TUI (Bubble Tea)
├── proxy/main.go              # Message proxy
├── cortexllm/                 # Python package
│   ├── core/
│   │   ├── brain.py           # Task orchestration
│   │   ├── memory.py          # Atomic persistence
│   │   ├── config.py          # Configuration
│   │   └── orchestrator.py    # Worker routing
│   ├── workers/
│   │   └── __init__.py        # Worker definitions
│   └── cli/
│       └── unified.py         # CLI tools
├── configs/
│   └── default.json           # Default configuration
├── docs/                      # Documentation
├── scripts/                   # Install/release scripts
└── .github/                   # GitHub Actions
```

### Testing
```bash
# Test memory system
python3 -c "from cortexllm.core.memory import Memory; m = Memory(); print('OK')"

# Test Go TUI build
go build -o /tmp/cortexllm ./main.go && /tmp/cortexllm

# Run full test suite
make test
```

---

## Troubleshooting

### TUI Won't Start
```bash
# Check binary
~/.local/bin/cortexllm

# Check Ollama
curl http://127.0.0.1:11434/api/tags

# Check memory directory
ls -la ~/.config/cortexllm/memory/
```

### OpenClaw Integration Fails
```bash
# Check gateway
curl http://127.0.0.1:18789/health

# Check token
echo $OPENCLAW_GATEWAY_TOKEN

# Restart gateway
systemctl --user restart openclaw-gateway
```

### Memory Not Saving
```bash
# Check permissions
chmod 755 ~/.config/cortexllm

# Verify JSON
cat ~/.config/cortexllm/memory/hot/opencode.json | jq

# Check disk space
df -h ~/.config
```

---

## Security

- **Token Auth**: Gateway requires `GATEWAY_TOKEN` environment variable
- **Local Only**: All services bind to localhost/LAN by default
- **No Cloud**: Data stays on your machine
- **Atomic Writes**: Temp file + rename prevents corruption

---

## License

MIT License - See [LICENSE](LICENSE) file for details.

---

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

---

## Support

- **Documentation**: See `docs/` directory
- **Issues**: https://github.com/greyok00/cortexllm/issues
- **Discussions**: https://github.com/greyok00/cortexllm/discussions

---

**Built by [@greyok00](https://github.com/greyok00)**

*Terminal-native AI for the modern developer*
