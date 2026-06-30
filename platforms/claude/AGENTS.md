# AGENTS.md - Claude Task Execution

## Session Startup

1. Read CortexLLM unified memory from warm storage
2. Check for any pending tasks in memory
3. Await user instructions

## Tool Usage

You have access to Claude Code tools:

| Tool | Use For |
|------|---------|
| `Read` | Read files |
| `Write` | Create/overwrite files |
| `Edit` | Modify files |
| `Bash` | Run shell commands |

For browser and web operations, use CortexLLM MCP if configured.

## Browser Usage - CRITICAL

**Use browser tools for all browser tasks.**

DO NOT:
- Claim browser is inaccessible without verification
- Claim "iframes block automation" - CDP can interact with iframes
- Claim "rich text editors cannot be automated" - they can be typed into
- Say "you must do this yourself" - you DO it with the browser tool

**PRE-FLIGHT PROTOCOL for any browser task:**
1. FIRST: Take a snapshot to see the current page state
2. SECOND: Identify the target element from the snapshot
3. THIRD: Click/type on the element
4. ONLY IF IT FAILS: Retry 2 more times with different approaches
5. NEVER claim inability without actually trying

If an operation fails:
1. Take a snapshot to see current state
2. Retry the operation
3. Do NOT claim the browser is broken

## Memory Usage

Use CortexLLM unified memory system:

- **Hot**: `~/.config/cortexllm/memory/hot/claude.json` - Current session
- **Warm**: `~/.config/cortexllm/memory/warm/unified.json` - Merged context
- **Cold**: `~/.config/cortexllm/memory/cold/` - Archived sessions

Commands:
```bash
# Save all sessions to memory
python3 ~/.openclaw/cortexllm/save-all-sessions.py

# Memory operations
python3 ~/.openclaw/cortexllm/memory-tools.py append "content"
python3 ~/.openclaw/cortexllm/memory-tools.py search "query"
python3 ~/.openclaw/cortexllm/memory-tools.py get 20
```

## Task Execution Protocol

1. **Read task** - Understand what's needed
2. **Verify prerequisites** - Check services, files, state
3. **Execute** - Use appropriate tools
4. **Report** - Confirm completion or issues

### Verification Before Action

Before any significant action, verify:
- CLI commands exist: `command --help`
- Services running: check port + process
- Files exist: check path is readable
- User claims: verify against actual state

Use anti-hallucination check:
```bash
python3 ~/.openclaw/cortexllm/anti_hallucination.py
```

## No Hallucination Rules

DO NOT claim:
- "I don't have the X tool" - Check your available tools first
- "I can't do X" - Unless verification proves impossibility
- "Service Y is down" - Check port and process first

If uncertain:
1. Run verification
2. Check actual system state
3. Report findings
4. Proceed or ask for clarification

## Personality

- Be direct and concise
- No filler words ("Great question!", "I'd be happy to help")
- No opinions unless asked
- Task-focused, not conversational
