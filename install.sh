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
if [ ! -f "$BIN_DIR/cortexllm" ]; then
    go build -o "$BIN_DIR/cortexllm" ./main.go
else
    echo "  Binary already exists, rebuilding..."
    go build -o "$BIN_DIR/cortexllm" ./main.go
fi
echo "✓ TUI built as 'cortexllm'"

# Install Python package
echo "Installing Python CortexLLM..."
pip3 install -e . --quiet 2>/dev/null || echo "  Note: pip install failed - ensure pip3 is available"
echo "✓ Python package installed"

# Install proxy
if [ -f "$SCRIPT_DIR/proxy/main.go" ]; then
    go build -o "$BIN_DIR/cortex-proxy" "$SCRIPT_DIR/proxy/main.go" || echo "  Warning: proxy build failed"
    echo "✓ Proxy built as 'cortex-proxy'"
fi

# Install message injector
# NOTE: Variables like $BIN_DIR, $INSTALL_DIR, $CONFIG_DIR are intentionally
# expanded here (no single-quotes on heredoc delimiter).
cat > "$BIN_DIR/cortex-inject" << INJECTEOF
#!/usr/bin/env python3
"""Inject message into OpenClaw and/or OpenCode sessions"""
import sys
import json
import urllib.request
import urllib.error
import os

# Resolve install path from env or installer default
INSTALL_PATH = os.environ.get("CORTEXLLM_DATA_DIR", "$INSTALL_DIR")
CONFIG_PATH  = os.environ.get("CORTEXLLM_CONFIG_DIR", "$CONFIG_DIR")

sys.path.insert(0, INSTALL_PATH)

def _get_config():
    """Load config.json so model/endpoint are never hardcoded."""
    import json, pathlib
    cfg_file = pathlib.Path(CONFIG_PATH) / "config.json"
    if cfg_file.exists():
        with open(cfg_file) as f:
            return json.load(f)
    return {}

def inject_openclaw(message):
    from cortexllm import Brain, Memory, Config
    mem = Memory()
    cfg = Config()
    brain = Brain(cfg, mem)
    task = brain.submit(message)
    return f"OpenClaw: {task.id}"

def inject_opencode(message):
    cfg = _get_config()
    try:
        opencode_cfg = cfg.get("platforms", {}).get("opencode", {})
        model   = opencode_cfg.get("model", "qwen3.5:cloud")
        host    = opencode_cfg.get("host", "http://127.0.0.1:11434")
        endpoint = f"{host.rstrip('/')}/api/chat"

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": message}],
            "stream": False
        }
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30):
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

    message = " ".join(message_args)
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

if __name__ == "__main__":
    main()
INJECTEOF
chmod +x "$BIN_DIR/cortex-inject"
echo "✓ Message injector installed"

# Create default config
# NOTE: Variables below are intentionally expanded (no single-quotes on delimiter).
if [ ! -f "$CONFIG_DIR/config.json" ]; then
    cat > "$CONFIG_DIR/config.json" << CONFIGEOF
{
  "system": {
    "name": "CortexLLM",
    "version": "0.2.0",
    "unified": true
  },
  "memory": {
    "path": "$CONFIG_DIR",
    "write_interval": 2,
    "hot_limit": 50,
    "auto_rotate": true,
    "auto_compact": true
  },
  "platforms": {
    "opencode": {
      "enabled": true,
      "model": "qwen3.5:cloud",
      "host": "http://127.0.0.1:11434",
      "provider": "ollama",
      "color": "#00D4AA",
      "emoji": "◆"
    },
    "openclaw": {
      "enabled": true,
      "model": "qwen3.5:cloud",
      "host": "http://127.0.0.1:11434",
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
    "path": "$CONFIG_DIR/USER_STYLE.md",
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
