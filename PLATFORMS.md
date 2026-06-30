# CortexLLM Multi-Platform Agent Configuration

This directory contains agent configurations for all supported platforms.

## Directory Structure

```
platforms/
├── openclaw/
│   ├── SOUL.md      - Core agent rules for OpenClaw
│   └── AGENTS.md    - Tool usage and task execution
├── claude/
│   ├── SOUL.md      - Core agent rules for Claude
│   └── AGENTS.md    - Tool usage and task execution
└── opencode/
    ├── SOUL.md      - Core agent rules for OpenCode
    └── AGENTS.md    - Tool usage and task execution
```

## Platform-Specific Notes

### OpenClaw

- Full tool profile available
- Browser integration via CDP
- Web search via SearXNG
- Gateway control available

### Claude

- Claude Code tools: Read, Write, Edit, Bash
- Browser via CortexLLM MCP (if configured)
- Memory via CortexLLM session capture

### OpenCode

- OpenCode tools: read, write, edit, bash
- Browser via CortexLLM MCP server
- Memory via CortexLLM session capture

## Shared Configuration

All platforms use:
- CortexLLM unified memory (hot/warm/cold)
- Anti-hallucination verification
- Same task execution protocol
- Task-focused behavior

## Memory Paths

```
~/.config/cortexllm/memory/
├── hot/
│   ├── openclaw.json   - OpenClaw active session
│   ├── claude.json     - Claude active session
│   └── opencode.json   - OpenCode active session
├── warm/
│   └── unified.json    - Merged context from all platforms
└── cold/
    └── *.json          - Archived sessions
```

## Updating Agent Behavior

1. Edit the platform-specific `SOUL.md` for core rules
2. Edit the platform-specific `AGENTS.md` for tool usage
3. Restart the platform's session to pick up changes

## Production Deployment

Copy the `platforms/` directory to your production location:

```bash
# For OpenClaw
cp -r ~/.openclaw/production/platforms/openclaw/* ~/.openclaw/workspace/

# For Claude (configure in Claude settings)
# Point Claude to ~/.openclaw/production/platforms/claude/

# For OpenCode (configure in OpenCode config)
# Point OpenCode to ~/.openclaw/production/platforms/opencode/
```
