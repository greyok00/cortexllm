# CortexLLM Memory System - Installation Guide

## Overview

The CortexLLM memory system provides automatic session capture and cross-platform memory synchronization for OpenClaw and OpenCode agents.

## Architecture

```
~/.config/cortexllm/memory/
├── hot/           # Active session memory (per-platform)
│   ├── openclaw.json
│   ├── opencode.json
│   └── system.json
├── warm/          # Merged cross-platform context
│   └── unified.json
├── cold/          # Permanent knowledge storage
│   ├── education.json
│   ├── bookmarks.json
│   └── user_context.json
└── state.json     # Save coordination state
```

## Installation

### 1. Create Directory Structure

```bash
mkdir -p ~/.config/cortexllm/memory/{hot,warm,cold}
chmod 700 ~/.config/cortexllm/memory
chmod 600 ~/.config/cortexllm/memory/*/*.json 2>/dev/null || true
```

### 2. Initialize Memory Files

```bash
# Hot memory (OpenClaw)
cat > ~/.config/cortexllm/memory/hot/openclaw.json << 'EOF'
{
  "platform": "openclaw",
  "messages": [],
  "session_id": ""
}
EOF

# Hot memory (OpenCode)
cat > ~/.config/cortexllm/memory/hot/opencode.json << 'EOF'
{
  "platform": "opencode",
  "messages": [],
  "session_id": ""
}
EOF

# Warm memory (unified)
echo '[]' > ~/.config/cortexllm/memory/warm/unified.json

# State file
cat > ~/.config/cortexllm/memory/state.json << 'EOF'
{
  "last_save": {
    "openclaw": null,
    "opencode": null
  },
  "next_turn": "openclaw",
  "turn_interval_minutes": 2
}
EOF
```

### 3. Install Auto-Save Script

Copy `save-session.py` to your CortexLLM directory:

```bash
cp save-session.py ~/.config/cortexllm/
chmod +x ~/.config/cortexllm/save-session.py
```

### 4. Configure Auto-Save

**Option A: Cron Job (Recommended)**

```bash
(crontab -l 2>/dev/null | grep -v "save-session.py"; \
 echo "* * * * * python3 ~/.config/cortexllm/save-session.py >> /tmp/cortexllm-auto-save.log 2>&1") | crontab -
```

**Option B: Systemd Service**

Create `/etc/systemd/system/cortexllm-auto-save.service`:

```ini
[Unit]
Description=CortexLLM Auto-Save Service
After=network.target

[Service]
Type=simple
User=%USER%
ExecStart=/usr/bin/python3 /home/%USER%/.config/cortexllm/save-session.py
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
```

Then enable it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable cortexllm-auto-save
sudo systemctl start cortexllm-auto-save
```

### 5. Verify Installation

```bash
# Test manual save
python3 ~/.config/cortexllm/save-session.py

# Check memory files exist
ls -la ~/.config/cortexllm/memory/*/

# Verify cron job
crontab -l | grep save-session

# Check logs
tail /tmp/cortexllm-auto-save.log
```

## Files Included in Default Install

### Core Files (Required)
- `memory_manager.py` - Core memory management logic
- `save-session.py` - Auto-save script
- `memory_hook.py` - OpenClaw integration hook
- `cortexllm_mcp_server.py` - MCP server

### Supporting Files (Recommended)
- `heartbeat_service.py` - System monitoring
- `anti_hallucination.py` - Verification tool
- `model_router.py` - Model selection/routing

### Files NOT Included (User Data)
- `~/.config/cortexllm/memory/hot/*.json` - Runtime session data
- `~/.config/cortexllm/memory/warm/unified.json` - Merged context
- `~/.config/cortexllm/memory/cold/*.json` - User knowledge
- `~/.config/cortexllm/saved_messages.json` - Runtime state

## Production Deployment Checklist

Before committing to production:

1. ✅ Remove all user session data from memory files
2. ✅ Remove PII from cold storage files
3. ✅ Clear saved_messages.json (runtime state)
4. ✅ Verify no personal paths in scripts
5. ✅ Test fresh installation on clean system
6. ✅ Document all configuration options
7. ✅ Add uninstall/cleanup script

## Troubleshooting

**Auto-save not running:**
```bash
# Check cron
crontab -l

# Check logs
tail /tmp/cortexllm-auto-save.log

# Test manually
python3 ~/.config/cortexllm/save-session.py
```

**Memory files missing:**
```bash
# Reinitialize
mkdir -p ~/.config/cortexllm/memory/{hot,warm,cold}
# Run initialization commands from step 2
```

**Permission errors:**
```bash
chmod 700 ~/.config/cortexllm/memory
chmod 600 ~/.config/cortexllm/memory/*/*.json
```

## Version History

- **v0.3.0** (2026-06-28): Auto-save integration, cron-based capture
- **v0.2.0**: Staggered multi-platform saves
- **v0.1.0**: Initial memory system
