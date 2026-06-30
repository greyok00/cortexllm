# CortexLLM Setup Guide

Complete setup instructions for CortexLLM with multi-platform integration.

---

## Prerequisites

| Component | Required For | Default Endpoint |
|-----------|--------------|------------------|
| **Ollama** | Local LLM inference | `http://127.0.0.1:11434` |
| **OpenClaw Gateway** | OpenClaw integration | `http://127.0.0.1:18789` |
| **Brave Browser** | Web automation | `http://127.0.0.1:9222` |
| **SearXNG** | Web search | `http://127.0.0.1:8888` |

---

## Quick Start

### 1. Install Ollama

```bash
# macOS/Linux
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama
ollama serve

# Pull a model
ollama pull llama3.2
```

**Verify:** `curl http://127.0.0.1:11434/api/tags`

---

### 2. Configure OpenClaw Gateway

```bash
# Start OpenClaw gateway
openclaw gateway
```

**Verify:** `curl http://127.0.0.1:18789/health`

---

### 3. Launch Brave with Remote Debugging

```bash
# Standard mode
brave-browser --remote-debugging-port=9222

# Or use the helper script
cortexllm-browser start
```

**Verify:** `curl http://127.0.0.1:9222/json/version`

---

### 4. Start SearXNG

```bash
# Docker (recommended)
docker run -d \
  --name searxng \
  -p 8888:8080 \
  -v "${PWD}/searxng:/etc/searxng" \
  searxng/searxng
```

**Verify:** `curl http://127.0.0.1:8888/healthz`

---

## Configuration

### Default Config Location

```
~/.config/cortexllm/config.json
```

### Minimal Config

```json
{
  "brain": {
    "heartbeat_interval": 30,
    "task_timeout": 300,
    "max_retries": 2
  },
  "workers": {
    "heartbeat_interval": 10,
    "max_concurrent": 10
  },
  "memory": {
    "path": "~/.config/cortexllm",
    "write_interval": 5
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
  "model": {
    "primary": "ollama/llama3.2",
    "context_tokens": 128000
  }
}
```

---

## Using CortexLLM Watch

### Start the Unified Monitor

```bash
# Auto-detect platforms
cortexllm-watch

# Specific platform
cortexllm-watch --platform opencode
cortexllm-watch --platform openclaw

# Custom Ollama URL
cortexllm-watch --ollama-url http://YOUR_IP:11434
```

### Commands

| Command | Description | Example |
|---------|-------------|---------|
| `send [platform] [msg]` | Send message to platform | `send opencode "Hello!"` |
| `switch [platform]` | Change default target | `switch openclaw` |
| `task [description]` | Submit brain task | `task "Research Python"` |
| `status` | Show platform status | `status` |
| `help` | Show help | `help` |
| `quit` / `exit` | Stop watching | `quit` |

---

## Troubleshooting

### Cannot connect to Ollama

**Problem:** Ollama not running or wrong URL

**Solution:**
```bash
# Check Ollama
curl http://127.0.0.1:11434/api/tags

# Start Ollama if needed
ollama serve

# Use custom URL
cortexllm-watch --ollama-url http://YOUR_IP:11434
```

---

### Cannot connect to OpenClaw Gateway

**Problem:** Gateway not running or wrong port

**Solution:**
```bash
# Check gateway
curl http://127.0.0.1:18789/health

# Start gateway
openclaw gateway --port 18789
```

---

### Browser automation not working

**Problem:** Brave not running with remote debugging

**Solution:**
```bash
# Kill existing Brave
pkill brave

# Start with debugging
brave-browser --remote-debugging-port=9222

# Verify
curl http://127.0.0.1:9222/json/version
```

---

### Search not working

**Problem:** SearXNG not running

**Solution:**
```bash
# Start searxng
docker start searxng

# Or disable in config:
# "search": {"enabled": false}
```

---

## Security Notes

- **Use 127.0.0.1** for local services
- **Never expose** Ollama API to the internet without authentication
- **Firewall rules:** Block ports 11434, 18789, 9222, 8888 from external access
- **API keys:** Store in environment variables, not in config files

---

## Getting Help

- **Check status:** `cortexllm-watch` → type `status`
- **Verbose mode:** Check logs in `~/.config/cortexllm/logs/`
- **GitHub Issues:** https://github.com/yourusername/cortexllm/issues

---

## Next Steps

1. Start `cortexllm-watch`
2. Verify platforms connect
3. Send test message: `send opencode "Hello from CortexLLM!"`
4. Submit brain task: `task "Research something fun"`
