# Quick Start Guide

Get CortexLLM running in under 5 minutes.

## Prerequisites

- **Go 1.24+** installed
- **Python 3.8+** installed
- **Ollama** running (`ollama serve`)

## Installation

### Option 1: One-Line Install
```bash
curl -fsSL https://raw.githubusercontent.com/greyok00/cortexllm/main/scripts/install.sh | bash
```

### Option 2: Manual Install
```bash
# Clone the repository
git clone https://github.com/greyok00/cortexllm.git
cd cortexllm

# Build the Go TUI
go build -o ~/.local/bin/cortexllm ./main.go

# Install Python dependencies (optional, for workers)
pip3 install -e .
```

### Verify Installation
```bash
cortexllm --version
cortexllm
```

## First Run

### 1. Start Ollama
```bash
ollama serve
# In another terminal:
ollama pull qwen3.5:cloud
```

### 2. Configure (Optional)
Create config file at `~/.config/cortexllm/config.json`:
```json
{
  "platforms": {
    "openclaw": { "enabled": false },
    "opencode": { "enabled": true, "mode": "ollama" }
  },
  "model": {
    "primary": "ollama/qwen3.5:cloud"
  }
}
```

### 3. Set Environment Variables (Optional)
```bash
# For OpenClaw integration
export OPENCLAW_GATEWAY_TOKEN=your_token_here

# Add to ~/.bashrc or ~/.zshrc for persistence
```

### 4. Launch
```bash
cortexllm
```

## Keyboard Controls

| Key | Action |
|-----|--------|
| `Tab` | Switch platform (OpenCode ↔ OpenClaw) |
| `↑/↓` | Scroll messages |
| `Enter` | Send message |
| `Ctrl+T` | Theme picker |
| `Ctrl+P` | Config overlay |
| `Ctrl+C` | Quit (auto-saves) |

## Themes

Press `Ctrl+T` to cycle through 7 themes:
- **
- **
- **
- **Aviator** - Orange/Blue
- **Aquanaut** - Cyan/Navy
- **Industrialist** - Brass/Copper
- **Astronaut** - White/Blue

## Next Steps

- [Architecture Guide](ARCHITECTURE.md) - Understand how it works
- [Configuration Guide](CONFIGURATION.md) - Customize settings
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues
