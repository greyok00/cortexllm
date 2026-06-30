# CortexLLM Features

Complete feature list for CortexLLM universal memory system.

## Core Features

### 1. Universal Memory System

**Three-tier memory architecture:**

- **Hot Memory** - Per-platform active sessions
  - `~/.config/cortexllm/memory/hot/openclaw.json`
  - `~/.config/cortexllm/memory/hot/claude.json`
  - `~/.config/cortexllm/memory/hot/opencode.json`

- **Warm Memory** - Unified cross-platform context
  - `~/.config/cortexllm/memory/warm/unified.json`
  - Merged context from all platforms
  - Staggered updates prevent conflicts

- **Cold Memory** - Permanent knowledge storage
  - `~/.config/cortexllm/memory/cold/{category}.json`
  - Archived sessions and learned patterns

### 2. MCP Server Integration

- Universal memory access for any MCP-compatible AI agent
- Tools: `memory_read`, `memory_write`, `memory_search`, `memory_clear`
- Supported clients: Claude Desktop, OpenClaw, OpenCode, VSCode with MCP

### 3. Session Heartbeat

**Runs before every agent turn on all platforms:**

- Detects context window overflow before it causes failures
- Handles session file lock conflicts automatically
- Auto-rotates sessions when errors or overflow detected
- Rehydrates context from warm memory after rotation
- No user action needed - continuous worker operation

**Platform integrations:**
- OpenClaw: Installed as skill
- OpenCode: Pre-turn hook
- Claude Desktop: MCP health check

### 4. Anti-Hallucination System

Verification functions:
- `verify_file_exists(path)` - Check files actually exist
- `verify_process_running(name)` - Check processes are running
- `verify_service_active(name)` - Check systemd services
- `verify_command_exists(cmd)` - Check commands in PATH
- `get_service_status(name)` - Get actual service status

### 5. Loop Guard System

Prevents repetitive failure loops:
- `record(task, approach, success, error)` - Log each attempt
- `check(task, approach)` - Detect if in failure loop
- Auto-blocks after 3 failures or 2 same-approach failures
- Forces strategy change when loop detected

### 6. Model Router

- Automatic delegation to worker sub-agents
- Primary model for reasoning and planning
- Worker model for simple, repetitive tasks
- Transparent sub-agent spawning for fetch/run/list/search tasks

### 7. Auto-Save System

- Captures CLI sessions to CortexLLM memory
- Runs every minute via cron
- Preserves conversation history across sessions
- Integrates with warm memory for cross-platform context

## Platform Support

### OpenClaw
- Session heartbeat skill (per-turn auto-reset)
- Auto-save to hot memory
- Model router integration
- MCP client support

### OpenCode
- Pre-turn heartbeat hook
- Hot memory integration
- Warm memory sync (staggered)

### Claude Desktop
- MCP server connection
- Memory-tools access
- Heartbeat via MCP health checks

## Installation

Single installer includes everything:

```bash
cd ~/.openclaw/production/cortexllm
./install.sh
```

**Installs:**
- CortexLLM Python package
- MCP server
- Session heartbeat (all platforms)
- Anti-hallucination system
- Loop guard
- Model router
- Auto-save cron job
- Systemd services (autostart)
- OpenClaw skills
- OpenCode hooks
- Claude Desktop MCP config

## Services

### systemd Services
- `cortexllm.service` - Main memory sync
- `cortexllm-heartbeat.service` - System health monitoring (5-min intervals)
- `cortexllm-mcp.service` - MCP server (on-demand)

### Cron Jobs
- Auto-save: `* * * * *` - Captures sessions every minute

### Per-Turn Hooks
- OpenClaw: `session-heartbeat` skill
- OpenCode: `pre-turn.sh` hook
- Claude Desktop: MCP health check

## Files

### Source Code
- `~/.openclaw/production/cortexllm/` - Master repository

### Installed To
- `~/.config/cortexllm/` - Config and memory
- `~/.local/bin/` - Binaries
- `~/.openclaw/skills/` - OpenClaw skills
- `~/.config/opencode/hooks/` - OpenCode hooks

### Memory Locations
- Hot: `~/.config/cortexllm/memory/hot/{platform}.json`
- Warm: `~/.config/cortexllm/memory/warm/unified.json`
- Cold: `~/.config/cortexllm/memory/cold/{category}.json`

## Key Benefits

1. **No Manual Session Management** - Heartbeat auto-resets on overflow
2. **Cross-Platform Memory** - All AI agents share unified context
3. **Hallucination Prevention** - Verifies claims before acting
4. **Failure Loop Prevention** - Detects and breaks retry cycles
5. **Automatic Worker Delegation** - Simple tasks use fast worker model
6. **Persistent History** - Sessions auto-saved to memory
7. **Universal Access** - Any MCP-compatible agent can use shared memory

---

*Last updated: 2026-06-29*
