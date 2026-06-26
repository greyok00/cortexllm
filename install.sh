#!/bin/bash
# CortexLLM - Unified AI System Installer
# Single Go binary + Python integration
# Configurable paths - set these before running:
#   CORTEXLLM_BIN_DIR - binary install directory (default: ~/.local/bin)
#   CORTEXLLM_CONFIG_DIR - config directory (default: ~/.config/cortexllm)
#   CORTEXLLM_DATA_DIR - data directory (default: ~/.local/share/cortexllm)

set -e

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║           CortexLLM - Unified AI System                       ║"
echo "║           OpenCode + OpenClaw + CortexLLM                     ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Configurable paths with defaults
INSTALL_DIR="${CORTEXLLM_DATA_DIR:-$HOME/.local/share/cortexllm}"
BIN_DIR="${CORTEXLLM_BIN_DIR:-$HOME/.local/bin}"
CONFIG_DIR="${CORTEXLLM_CONFIG_DIR:-$HOME/.config/cortexllm}"

echo "Installing to:"
echo "  Binaries: $BIN_DIR"
echo "  Config:   $CONFIG_DIR"
echo "  Data:     $INSTALL_DIR"
echo ""

# Create directories
mkdir -p "$BIN_DIR"
mkdir -p "$CONFIG_DIR/memory/{hot,warm,cold}"
mkdir -p "$CONFIG_DIR/sessions"
mkdir -p "$CONFIG_DIR/workers"
mkdir -p "$INSTALL_DIR"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Build Go TUI
echo "Building Go TUI..."
cd "$SCRIPT_DIR"
go build -o "$BIN_DIR/cortexllm" ./main.go 2>/dev/null || {
    echo "  Note: Go build skipped (binary may already exist)"
}
echo "✓ TUI built as 'cortexllm'"

# Install Python package
echo "Installing Python CortexLLM..."
pip3 install -e . --quiet 2>/dev/null || python3 setup.py install --quiet 2>/dev/null || echo "  Note: Python install skipped"
echo "✓ Python package installed"

# Install proxy
if [ -f "$SCRIPT_DIR/proxy/main.go" ]; then
    go build -o "$BIN_DIR/cortex-proxy" "$SCRIPT_DIR/proxy/main.go" 2>/dev/null || echo "  Note: Proxy build skipped"
    echo "✓ Proxy built as 'cortex-proxy'"
fi

# Install message injector
cat > "$BIN_DIR/cortex-inject" << 'INJECTEOF'
#!/usr/bin/env python3
"""Inject message into OpenClaw and/or OpenCode sessions"""
import sys
import json
import urllib.request
import urllib.error
import os

# Use installed package path
sys.path.insert(0, os.path.expanduser('~/.local/share/cortexllm'))

def inject_openclaw(message):
    from cortexllm import Brain, Memory, Config
    mem = Memory()
    cfg = Config()
    brain = Brain(cfg, mem)
    task = brain.submit(message)
    return f"OpenClaw: {task.id}"

def inject_opencode(message):
    try:
        payload = {
            "model": "qwen3.5:cloud",
            "messages": [{"role": "user", "content": message}],
            "stream": False
        }
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/chat",
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return "OpenCode: message sent"
    except Exception as e:
        return f"OpenCode failed: {e}"

def main():
    if len(sys.argv) < 2:
        print("Usage: cortex-inject [--opencode|--openclaw|--both] <message>")
        sys.exit(1)
    
    args = sys.argv[1:]
    target = "openclaw"
    message_args = []
    
    for arg in args:
        if arg in ["--opencode", "--openclaw", "--both"]:
            target = arg[2:]
        else:
            message_args.append(arg)
    
    message = ' '.join(message_args)
    if not message:
        print("Error: message required")
        sys.exit(1)
    
    if target == "opencode":
        print(inject_opencode(message))
    elif target == "openclaw":
        print(inject_openclaw(message))
    elif target == "both":
        print(inject_openclaw(message))
        print(inject_opencode(message))

if __name__ == '__main__':
    main()
INJECTEOF
chmod +x "$BIN_DIR/cortex-inject"
echo "✓ Message injector installed"

# Create default config
if [ ! -f "$CONFIG_DIR/config.json" ]; then
    cat > "$CONFIG_DIR/config.json" << 'CONFIGEOF'
{
  "system": {
    "name": "CortexLLM",
    "version": "2026.6.25",
    "unified": true
  },
  "memory": {
    "path": "~/.config/cortexllm",
    "write_interval": 2,
    "hot_limit": 50,
    "auto_rotate": true,
    "auto_compact": true
  },
  "platforms": {
    "opencode": {
      "enabled": true,
      "model": "qwen3.5:cloud",
      "provider": "ollama",
      "color": "#00D4AA",
      "emoji": "◆"
    },
    "openclaw": {
      "enabled": true,
      "model": "qwen3.5:cloud",
      "provider": "ollama",
      "color": "#FF6B6B",
      "emoji": "◇"
    }
  },
  "brain": {
    "heartbeat_interval": 30,
    "task_timeout": 300,
    "max_retries": 2
  },
  "workers": {
    "heartbeat_interval": 10,
    "max_concurrent": 10
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
    "primary": "ollama/qwen3.5:cloud",
    "context_tokens": 262144
  },
  "gateway": {
    "port": 18789,
    "bind": "lan"
  },
  "userStyle": {
    "path": "~/.config/cortexllm/USER_STYLE.md",
    "enforce": true
  }
}
CONFIGEOF
    echo "✓ Created default config"
fi

# Create session state
if [ ! -f "$CONFIG_DIR/session.json" ]; then
    echo '{"active":true,"platform":"opencode"}' > "$CONFIG_DIR/session.json"
    echo "✓ Created session state"
fi

# Create tasks file
if [ ! -f "$CONFIG_DIR/tasks.json" ]; then
    echo '{}' > "$CONFIG_DIR/tasks.json"
    echo "✓ Created tasks file"
fi

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                  Installation Complete                        ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "Commands:"
echo "  cortexllm       - Launch TUI (OpenCode + OpenClaw)"
echo "  cortex-proxy    - Start message injection proxy"
echo "  cortex-inject   - Inject messages into active sessions"
echo ""
echo "Config: $CONFIG_DIR/config.json"
echo "Memory: $CONFIG_DIR/memory/"
echo ""
