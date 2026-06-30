---
name: "session-heartbeat"
description: "Auto-run heartbeat service before every turn to detect/handle context overflow and session file locks"
platforms: ["openclaw", "opencode", "claude-desktop"]
---

# Session Heartbeat - Per-Turn Session Recovery

## Purpose
Automatically run the CortexLLM heartbeat service before every agent turn to:
- Detect context window overflow before it causes failures
- Handle session file lock conflicts
- Auto-rotate sessions when errors or overflow detected
- Rehydrate context from warm memory after rotation
- Ensure continuous worker operation without manual session reset commands

## Platform Support

### OpenClaw
- **Integration**: Installed as OpenClaw skill
- **Location**: `~/.openclaw/skills/session-heartbeat/SKILL.md`
- **Trigger**: Runs automatically before every agent turn
- **Config**: Add to agent's skill list in `~/.openclaw/openclaw.json`

### OpenCode
- **Integration**: Runs via pre-execution hook
- **Location**: `~/.config/cortexllm/hooks/pre-turn.sh`
- **Trigger**: Called before each turn
- **Config**: Enable in config with pre-turn hook path

### Claude Desktop (via MCP)
- **Integration**: MCP server health check tool
- **Location**: Built into MCP server
- **Trigger**: Called on each MCP tool invocation
- **Config**: Add to Claude Desktop MCP config

## Procedure

### 1. Run Heartbeat Service
```bash
python3 ~/.openclaw/cortexllm/heartbeat_service.py
```

### 2. Check Result
The heartbeat service outputs:
- `Heartbeat OK` - Session healthy, continue normally
- `Heartbeat Warning` - Issues detected, review actions taken
- `Auto-reset: Session rotated` - Session was overflowed/corrupted, auto-rotated

### 3. Auto-Reset Behavior
When the heartbeat detects:
- Context overflow (>100 messages or >200K tokens)
- Multiple errors in recent messages (3+)
- Session file corruption or lock conflicts
- Stale session (>10 minutes since last message)

It automatically:
1. Archives current session as `.archived.jsonl`
2. Clears the session file (avoids lock issues)
3. Generates new session ID in `sessions.json`
4. Rehydrates context from warm memory
5. Continues working without user interruption

## Files Involved
- `~/.openclaw/cortexllm/heartbeat_service.py` - Main heartbeat logic
- `~/.openclaw/agents/*/sessions/*.jsonl` - Session files
- `~/.openclaw/agents/*/sessions/sessions.json` - Session registry
- `~/.config/cortexllm/memory/warm/unified.json` - Context rehydration source
- `~/.config/cortexllm/heartbeat_state.json` - Last heartbeat status

## Error Handling

### Session File Lock Conflicts
The heartbeat handles lock conflicts by:
1. Waiting 500ms for lock release
2. Copying (not moving) to archive
3. Truncating file instead of deleting
4. Updating sessions.json atomically

### Context Overflow
When context exceeds model limits:
1. Detects overflow during health check
2. Archives current session
3. Rotates to new session ID
4. Rehydrates last 20 messages from warm memory
5. Continues without user needing to reset

## Testing
Run manually to verify:
```bash
python3 ~/.openclaw/cortexllm/heartbeat_service.py
```

Expected output shows session status and any auto-corrections applied.

## Notes
- This skill is **silent by default** - only outputs if there are issues
- Auto-reset is enabled by default
- Heartbeat runs before anti-hallucination check and model routing
- Does not replace the 5-minute systemd heartbeat (that's for system health monitoring)
