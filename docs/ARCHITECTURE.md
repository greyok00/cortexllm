# Architecture Guide

## System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                     CORTEXLLM SYSTEM                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                    Go TUI (main.go)                        │  │
│  │  - 60 FPS Bubble Tea rendering                             │  │
│  │  - Platform switching (Tab key)                            │  │
│  │  - Theme system (7 themes)                             │  │
│  │  - Config/theme overlays                                   │  │
│  └────────────────────────────────────────────────────────────┘  │
│                              │                                    │
│         ┌────────────────────┼────────────────────┐              │
│         │                    │                    │              │
│         ▼                    ▼                    ▼              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │  OpenClaw   │    │  OpenCode   │    │   Ollama    │         │
│  │  (CLI)      │    │  (Ollama)   │    │   (Direct)  │         │
│  │             │    │             │    │             │         │
│  │ ┌─────────┐ │    │ ┌─────────┐ │    │ ┌─────────┐ │         │
│  │ │ Brain   │ │    │ │ qwen3.5 │ │    │ │ qwen3.5 │ │         │
│  │ │ Agent   │ │    │ │ :cloud  │ │    │ │ :cloud  │ │         │
│  │ └─────────┘ │    │ └─────────┘ │    │ └─────────┘ │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│         │                    │                    │              │
│         └────────────────────┼────────────────────┘              │
│                              │                                    │
│                              ▼                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                  Memory System                              │  │
│  │  - Hot:  ~/.config/cortexllm/memory/hot/{platform}.json    │  │
│  │  - Warm: ~/.config/cortexllm/memory/warm/                  │  │
│  │  - Cold: ~/.config/cortexllm/memory/cold/                  │  │
│  │  - Atomic writes (temp file + rename)                      │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Go TUI (`main.go`)

**Responsibilities:**
- Terminal UI rendering at 60 FPS
- Platform status monitoring
- Message display and input
- Theme/config overlays
- Auto-save every 2 seconds

**Key Functions:**
```go
// Platform injection
injectToOpenClaw(message, platform)  // OpenClaw CLI
sendToOpenCode(message)              // OpenCode via Ollama
sendToOllamaDirect(message, model)   // Direct Ollama API

// Persistence
saveMessages(memPath, platform, messages)  // Atomic write
loadMemoryData(memPath)                    // Load on startup

// Rendering
buildChatContent()    // Format messages
renderSidebar()       // Platform status, memory stats
```

### 2. Memory System

**Three-Tier Architecture:**

| Tier | Location | Limit | Purpose |
|------|----------|-------|---------|
| HOT | `~/.config/cortexllm/memory/hot/` | 50 msgs | Active conversations |
| WARM | `~/.config/cortexllm/memory/warm/` | 20 msgs | Shared context |
| COLD | `~/.config/cortexllm/memory/cold/` | Unlimited | Archived sessions |

**Atomic Write Pattern:**
```python
def save_hot(messages, platform):
    """Atomic write: temp file + rename"""
    tmp_path = hot_path + ".tmp"
    with open(tmp_path, 'w') as f:
        json.dump(messages, f)
    os.rename(tmp_path, hot_path)  # Atomic on POSIX
```

### 3. Platform Abstraction

**Config-Driven Selection:**
```json
{
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
  }
}
```

**Platform Modes:**
- `cli` - External CLI tool (OpenClaw)
- `ollama` - Ollama API (OpenCode)
- `api` - Direct HTTP API (Claude, OpenAI - future)

### 4. Message Flow

```
User Input (Enter key)
       │
       ▼
┌─────────────────┐
│  Go TUI (main)  │
└────────┬────────┘
         │
         ├─────────────────┬─────────────────┐
         │                 │                 │
         ▼                 ▼                 ▼
  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
  │ OpenClaw    │  │ OpenCode    │  │ Ollama      │
  │ CLI inject  │  │ Ollama API  │  │ Direct API  │
  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
         │                 │                 │
         └─────────────────┼─────────────────┘
                           │
                           ▼
                  ┌────────────────┐
                  │ Response Msg   │
                  └────────┬───────┘
                           │
                           ▼
                  ┌────────────────┐
                  │ Display + Save │
                  └────────────────┘
```

## Data Structures

### Message
```go
type Message struct {
    Platform  string      // "opencode" | "openclaw" | "ollama"
    Content   string      // Message text
    IsUser    bool        // true = user, false = assistant
    Time      time.Time   // Timestamp
    TokensIn  int         // Input tokens (future)
    TokensOut int         // Output tokens (future)
}
```

### PlatformConfig
```go
type PlatformConfig struct {
    Enabled       bool   `json:"enabled"`
    Mode          string `json:"mode"`           // "cli" | "ollama" | "api"
    Endpoint      string `json:"endpoint"`       // API URL
    TokenEnv      string `json:"token_env"`      // Auth env var
    SessionPrefix string `json:"session_prefix"` // Session key prefix
}
```

## Configuration System

### Config Locations
- **Default:** `~/.config/cortexllm/config.json`
- **Override:** `$CORTEXLLM_CONFIG_PATH`
- **Environment:** `$OPENCLAW_GATEWAY_TOKEN`, `$OLLAMA_HOST`

### Config Schema
```json
{
  "system": { "name": "CortexLLM", "version": "2.0.0" },
  "platforms": { ... },
  "model": { "primary": "ollama/qwen3.5:cloud" },
  "memory": { "hot_limit": 50, "warm_limit": 20 },
  "gateway": { "port": 18789 },
  "browser": { "enabled": true, "cdp_url": "..." },
  "search": { "enabled": true, "provider": "searxng" }
}
```

## Security Model

### Authentication
- OpenClaw: `OPENCLAW_GATEWAY_TOKEN` environment variable
- Token never hardcoded in source
- Config file permissions: `0644` (user-readable only)

### Network Binding
- All services bind to localhost/LAN by default
- No cloud connectivity required
- Optional external APIs (Searxng, CDP) configurable

## Extension Points

### Adding New Platforms

1. Add to config:
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

2. Add send function in `main.go`:
```go
func sendToClaude(message string) tea.Cmd {
    return func() tea.Msg {
        // HTTP request to Claude API
        // Parse response
        // Return Message
    }
}
```

### Adding Themes

Add to `colorThemes` slice in `main.go`:
```go
{
    Name: "Custom",
    Description: "Your theme description",
    Palette: Palette{
        Primary: "#FF0000",
        // ...
    },
    Icon: "🎨",
}
```

## Performance Characteristics

| Operation | Frequency | Latency |
|-----------|-----------|---------|
| TUI render | 60 FPS | <16ms |
| Platform ping | 2 sec | ~50ms |
| Auto-save | 2 sec | <10ms |
| Memory rotate | On limit | <50ms |
| CLI injection | Per message | 500ms-5s |

## Failure Modes

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Ollama down | HTTP timeout | Retry on next message |
| OpenClaw CLI missing | exec.Command error | Show error in TUI |
| Memory dir missing | os.Stat error | Create on startup |
| Config invalid | JSON parse error | Use defaults |
