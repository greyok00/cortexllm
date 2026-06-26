# Configuration Guide

## Config File Location

Default: `~/.config/cortexllm/config.json`

Override with environment variable:
```bash
export CORTEXLLM_CONFIG_PATH=/path/to/config.json
```

## Full Configuration Example

```json
{
  "system": {
    "name": "CortexLLM",
    "version": "2.0.0"
  },
  "platforms": {
    "openclaw": {
      "enabled": true,
      "mode": "cli",
      "token_env": "OPENCLAW_GATEWAY_TOKEN",
      "session_prefix": "cortexllm-"
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
    "hot_limit": 50,
    "warm_limit": 20,
    "auto_rotate": true,
    "path": "~/.config/cortexllm/memory"
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

## Configuration Options

### System
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | "CortexLLM" | System name |
| `version` | string | "2.0.0" | Version string |

### Platforms

Configure each platform independently. Enable/disable without restarting.

#### OpenClaw Platform
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | true | Enable OpenClaw integration |
| `mode` | string | "cli" | Must be "cli" for OpenClaw |
| `token_env` | string | "OPENCLAW_GATEWAY_TOKEN" | Environment variable for auth token |
| `session_prefix` | string | "cortexllm-" | Prefix for session keys |

#### OpenCode Platform
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | true | Enable OpenCode integration |
| `mode` | string | "ollama" | Must be "ollama" for OpenCode |
| `endpoint` | string | "http://127.0.0.1:11434" | Ollama API endpoint |

### Model
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `primary` | string | "ollama/qwen3.5:cloud" | Primary model to use |
| `fallback` | string | "ollama/llama3.1:8b" | Fallback if primary unavailable |

### Memory
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `hot_limit` | int | 50 | Max messages in hot tier |
| `warm_limit` | int | 20 | Max messages in warm tier |
| `auto_rotate` | bool | true | Auto-rotate old messages to warm |
| `path` | string | "~/.config/cortexllm/memory" | Memory directory |

### Gateway (OpenClaw)
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `port` | int | 18789 | Gateway port |
| `bind` | string | "lan" | Bind address: "localhost", "lan", or IP |

### Browser (Optional)
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | true | Enable browser automation |
| `cdp_url` | string | "http://127.0.0.1:9222" | Brave CDP endpoint |

### Search (Optional)
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | true | Enable web search |
| `provider` | string | "searxng" | Search provider |
| `base_url` | string | "http://127.0.0.1:8888" | Searxng instance URL |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CORTEXLLM_CONFIG_PATH` | Custom config path | `~/.config/cortexllm/config.json` |
| `OPENCLAW_GATEWAY_TOKEN` | OpenClaw authentication | (required for OpenClaw) |
| `OLLAMA_HOST` | Ollama endpoint | `http://127.0.0.1:11434` |
| `BRAVE_CDP_URL` | Browser CDP URL | `http://127.0.0.1:9222` |
| `SEARXNG_URL` | Search URL | `http://127.0.0.1:8888` |

## Minimal Configurations

### OpenClaw Only
```json
{
  "platforms": {
    "openclaw": {
      "enabled": true,
      "mode": "cli",
      "token_env": "OPENCLAW_GATEWAY_TOKEN"
    },
    "opencode": { "enabled": false }
  },
  "model": {
    "primary": "ollama/qwen3.5:cloud"
  }
}
```

### OpenCode Only
```json
{
  "platforms": {
    "openclaw": { "enabled": false },
    "opencode": {
      "enabled": true,
      "mode": "ollama",
      "endpoint": "http://127.0.0.1:11434"
    }
  },
  "model": {
    "primary": "ollama/qwen3.5:cloud"
  }
}
```

### Standalone Ollama (No OpenClaw/OpenCode)
```json
{
  "platforms": {
    "openclaw": { "enabled": false },
    "opencode": { "enabled": false }
  },
  "model": {
    "primary": "ollama/qwen3.5:cloud"
  }
}
```

## Platform-Specific Setup

### OpenClaw Setup

1. Install OpenClaw gateway:
```bash
git clone https://github.com/greyok00/openclaw.git
cd openclaw && npm install
systemctl --user start openclaw-gateway
```

2. Get your token:
```bash
# Token is in OpenClaw config or .env
cat ~/.openclaw/.env | grep GATEWAY_TOKEN
```

3. Set environment variable:
```bash
export OPENCLAW_GATEWAY_TOKEN=your_token_here
```

### OpenCode Setup

1. Ensure Ollama is running:
```bash
ollama serve
```

2. Pull required model:
```bash
ollama pull qwen3.5:cloud
```

3. Verify endpoint:
```bash
curl http://127.0.0.1:11434/api/tags
```

### Searxng Setup

1. Run Searxng Docker:
```bash
docker run -d -p 8888:8080 searxng/searxng
```

2. Update config:
```json
{
  "search": {
    "enabled": true,
    "provider": "searxng",
    "base_url": "http://127.0.0.1:8888"
  }
}
```

### Brave CDP Setup

1. Start Brave with CDP:
```bash
brave --remote-debugging-port=9222
```

2. Update config:
```json
{
  "browser": {
    "enabled": true,
    "cdp_url": "http://127.0.0.1:9222"
  }
}
```

## Validation

Check config is valid:
```bash
cat ~/.config/cortexllm/config.json | jq .
```

Verify platforms:
```bash
# OpenClaw
curl http://127.0.0.1:18789/health

# Ollama
curl http://127.0.0.1:11434/api/tags
```

## Troubleshooting

### Config Not Loading
```bash
# Check file exists
ls -la ~/.config/cortexllm/config.json

# Validate JSON
jq . ~/.config/cortexllm/config.json

# Check permissions
chmod 644 ~/.config/cortexllm/config.json
```

### Platform Not Connecting
1. Verify enabled in config
2. Check environment variables set
3. Test endpoint manually (curl)
4. Restart TUI after config changes

### Memory Issues
```bash
# Check directory exists
ls -la ~/.config/cortexllm/memory/

# Verify writable
touch ~/.config/cortexllm/memory/hot/test.json && rm ~/.config/cortexllm/memory/hot/test.json

# Check disk space
df -h ~/.config
```
