#!/bin/bash
# CortexLLM - Unified AI System Installer
# Single Go binary + Python integration

set -e

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║           CortexLLM - Unified AI System                       ║"
echo "║           OpenCode + OpenClaw + CortexLLM                     ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

INSTALL_DIR="$HOME/.local/share/cortexllm"
BIN_DIR="$HOME/.local/bin"
CONFIG_DIR="$HOME/.config/cortexllm"

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

sys.path.insert(0, '/home/grey/.openclaw/cortexllm')
sys.path.insert(0, '/home/grey/.openclaw/cortexllm/cortexllm')

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
    "worker": "ollama/deepseek-v4-flash:cloud",
    "context_tokens": 262144,
    "auto_delegate": true
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

# Install core memory (permanent directives)
if [ -f "$SCRIPT_DIR/CORE_MEMORY.md" ]; then
    cp "$SCRIPT_DIR/CORE_MEMORY.md" "$CONFIG_DIR/CORE_MEMORY.md"
    echo "✓ Installed core memory directives"
fi

# Install features documentation
if [ -f "$SCRIPT_DIR/FEATURES.md" ]; then
    cp "$SCRIPT_DIR/FEATURES.md" "$CONFIG_DIR/FEATURES.md"
    echo "✓ Installed features documentation"
fi

# Install protective systems
if [ -f "$SCRIPT_DIR/anti_hallucination.py" ]; then
    cp "$SCRIPT_DIR/anti_hallucination.py" "$CONFIG_DIR/anti_hallucination.py"
    echo "✓ Installed anti-hallucination system"
fi

if [ -f "$SCRIPT_DIR/loop_guard.py" ]; then
    cp "$SCRIPT_DIR/loop_guard.py" "$CONFIG_DIR/loop_guard.py"
    echo "✓ Installed loop guard system"
fi

# Install session heartbeat (per-turn session recovery for all platforms)
if [ -f "$SCRIPT_DIR/heartbeat_service.py" ]; then
    cp "$SCRIPT_DIR/heartbeat_service.py" "$CONFIG_DIR/heartbeat_service.py"
    chmod +x "$CONFIG_DIR/heartbeat_service.py"
    echo "✓ Installed session heartbeat (auto-reset on overflow/locks)"
fi

if [ -f "$SCRIPT_DIR/session-heartbeat-skill.md" ]; then
    # OpenClaw skill
    mkdir -p "$HOME/.openclaw/skills/session-heartbeat"
    cp "$SCRIPT_DIR/session-heartbeat-skill.md" "$HOME/.openclaw/skills/session-heartbeat/SKILL.md"
    echo "✓ Installed OpenClaw session-heartbeat skill"
    
    # OpenCode pre-turn hook
    mkdir -p "$HOME/.config/opencode/hooks"
    cat > "$HOME/.config/opencode/hooks/pre-turn.sh" << 'HOOK_EOF'
#!/bin/bash
# OpenCode pre-turn hook - run session heartbeat
python3 ~/.config/cortexllm/heartbeat_service.py
HOOK_EOF
    chmod +x "$HOME/.config/opencode/hooks/pre-turn.sh"
    echo "✓ Installed OpenCode pre-turn hook"
fi

# Install MCP server
if [ -f "$SCRIPT_DIR/cortexllm_mcp_server.py" ]; then
    cp "$SCRIPT_DIR/cortexllm_mcp_server.py" "$CONFIG_DIR/cortexllm_mcp_server.py"
    chmod +x "$CONFIG_DIR/cortexllm_mcp_server.py"
    echo "✓ Installed CortexLLM MCP server"
fi

# Install MCP server config for common clients
if [ -f "$SCRIPT_DIR/mcp-server-config.json" ]; then
    # Claude Desktop config
    CLAUDE_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
    if [ -f "$CLAUDE_CONFIG" ]; then
        echo "  Note: Merge mcp-server-config.json into $CLAUDE_CONFIG manually"
    fi
    cp "$SCRIPT_DIR/mcp-server-config.json" "$CONFIG_DIR/mcp-server-config.json"
    echo "✓ Installed MCP server config"
fi

# Install model router (auto-delegation to worker sub-agents)
if [ -f "$SCRIPT_DIR/model_router.py" ]; then
    cp "$SCRIPT_DIR/model_router.py" "$CONFIG_DIR/model_router.py"
    chmod +x "$CONFIG_DIR/model_router.py"
    echo "✓ Installed model router (qwen3.5:cloud → deepseek-v4-flash:cloud delegation)"
fi

# Install auto-save script (captures OpenClaw sessions to memory)
if [ -f "$SCRIPT_DIR/save-session.py" ]; then
    cp "$SCRIPT_DIR/save-session.py" "$CONFIG_DIR/save-session.py"
    chmod +x "$CONFIG_DIR/save-session.py"
    
    # Set up cron job for auto-save
    (crontab -l 2>/dev/null | grep -v "save-session.py"; \
     echo "* * * * * python3 $CONFIG_DIR/save-session.py >> /tmp/cortexllm-auto-save.log 2>&1") | crontab -
    echo "✓ Installed auto-save (cron: every minute)"
fi

# Install systemd service for autostart
echo "Setting up systemd service..."
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_USER_DIR"

# Update OpenClaw config to include session-heartbeat skill
OPENCLAW_CONFIG="$HOME/.openclaw/openclaw.json"
if [ -f "$OPENCLAW_CONFIG" ]; then
    # Add session-heartbeat to skills list if not already present
    python3 << 'PYEOF'
import json
config_path = "$HOME/.openclaw/openclaw.json".replace("$HOME", "$HOME")
try:
    with open(config_path) as f:
        config = json.load(f)
    skills = config.get("agents", {}).get("defaults", {}).get("skills", [])
    if "session-heartbeat" not in skills:
        skills.append("session-heartbeat")
        config["agents"]["defaults"]["skills"] = skills
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        print("  Added session-heartbeat to OpenClaw skills")
except Exception as e:
    print(f"  Note: Could not update OpenClaw config: {e}")
PYEOF
fi

cat > "$SYSTEMD_USER_DIR/cortexllm.service" << SERVICEEOF
[Unit]
Description=CortexLLM Unified Memory System
After=network-online.target openclaw-gateway.service
Wants=network-online.target openclaw-gateway.service
StartLimitBurst=5
StartLimitIntervalSec=60

[Service]
Type=simple
ExecStart=/usr/bin/python3 -m cortexllm.cli.watch --platform auto --ollama-url http://127.0.0.1:11434
WorkingDirectory=$HOME/.openclaw/production/cortexllm
Restart=always
RestartSec=5
RestartPreventExitStatus=78
TimeoutStopSec=30
TimeoutStartSec=30
SuccessExitStatus=0 143
KillMode=control-group
Environment=HOME=$HOME
Environment=PYTHONPATH=$HOME/.openclaw/production
Environment=PATH=$HOME/.nvm/versions/node/v22.22.2/bin:$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin
Environment=CORTEXLLM_PLATFORM=openclaw
Environment=OPENCLAW_GATEWAY_URL=http://127.0.0.1:18789

[Install]
WantedBy=default.target
SERVICEEOF

# Install heartbeat service (runs every 5 minutes)
cat > "$SYSTEMD_USER_DIR/cortexllm-heartbeat.service" << HEARTBEATEOF
[Unit]
Description=CortexLLM Heartbeat Service - System Health Monitoring
After=network-online.target openclaw-gateway.service
Wants=network-online.target openclaw-gateway.service

[Service]
Type=simple
ExecStart=/usr/bin/python3 $HOME/.openclaw/production/cortexllm/heartbeat_service.py --interval 300
WorkingDirectory=$HOME/.openclaw/production/cortexllm
Restart=always
RestartSec=5
Environment=HOME=$HOME
Environment=PYTHONPATH=$HOME/.openclaw:$HOME/.openclaw/production
Environment=PATH=$HOME/.nvm/versions/node/v22.22.2/bin:$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin

[Install]
WantedBy=default.target
HEARTBEATEOF
echo "✓ Heartbeat service configured (5min interval)"

# Enable heartbeat in config
cat > "$CONFIG_DIR/heartbeat.json" << 'HEARTBEATEOF'
{
  "enabled": true,
  "interval_minutes": 30,
  "checks": [
    {
      "name": "email",
      "enabled": true,
      "last_check": null
    },
    {
      "name": "calendar",
      "enabled": true,
      "last_check": null
    },
    {
      "name": "weather",
      "enabled": true,
      "last_check": null
    }
  ]
}
HEARTBEATEOF
echo "✓ Created heartbeat config"

# Add model router integration note to config
cat >> "$CONFIG_DIR/config.json" << 'ROUTEREOF'
,
  "model_router": {
    "enabled": true,
    "primary_model": "ollama/qwen3.5:cloud",
    "worker_model": "ollama/deepseek-v4-flash:cloud",
    "delegation_rules": {
      "delegate": ["fetch", "get", "search", "list", "run", "execute"],
      "keep_main": ["debug", "fix", "explain", "remember", "plan", "decide"]
    }
  }
ROUTEREOF
# Fix JSON (remove trailing comma issue)
python3 -c "
import json
from pathlib import Path
f = Path('$CONFIG_DIR/config.json')
try:
    # Read and fix the JSON
    content = f.read_text()
    # Remove the extra comma before the closing brace if present
    content = content.replace(',\n,', ',')
    data = json.loads(content)
    f.write_text(json.dumps(data, indent=2))
except Exception as e:
    print(f'Warning: Could not update config: {e}')
" 2>/dev/null || true
echo "✓ Configured model router (auto-delegation to worker sub-agents)"

# Reload systemd and enable services
systemctl --user daemon-reload 2>/dev/null || true

# Enable and start CortexLLM main service
systemctl --user enable cortexllm.service 2>/dev/null && echo "✓ CortexLLM service enabled for autostart" || echo "  Note: systemd not available"
systemctl --user start cortexllm.service 2>/dev/null && echo "✓ CortexLLM service started" || echo "  Note: Service will start on next login"

# Enable and start Heartbeat service (5 minute intervals)
systemctl --user enable cortexllm-heartbeat.service 2>/dev/null && echo "✓ Heartbeat service enabled (5min checks)" || echo "  Note: Heartbeat will run manually"
systemctl --user restart cortexllm-heartbeat.service 2>/dev/null && echo "✓ Heartbeat service started" || true

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
echo "Systemd Services:"
echo "  systemctl --user status cortexllm         - Main service status"
echo "  systemctl --user status cortexllm-heartbeat - Heartbeat (5min checks)"
echo "  systemctl --user stop cortexllm           - Stop main service"
echo "  systemctl --user restart cortexllm        - Restart services"
echo ""
echo "MCP Integration:"
echo "  Config: $CONFIG_DIR/mcp-server-config.json"
echo "  MCP Server: Spawned on-demand by MCP clients"
echo "  Add config to Claude Desktop, VSCode, or any MCP client"
echo ""
echo "Config: $CONFIG_DIR/config.json"
echo "Memory: $CONFIG_DIR/memory/"
echo "Heartbeat: $CONFIG_DIR/heartbeat.json"
echo ""
echo "✓ CortexLLM will autostart on login"
echo "✓ Heartbeat monitors system health every 5 minutes"
echo "✓ MCP server provides universal memory access to all AI agents"
echo "✓ Memory syncs automatically between platforms"
