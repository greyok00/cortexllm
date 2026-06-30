# CortexLLM Core Memory - Permanent Directives

## Operational Principles

### Execute Correctly First Time
When given an instruction:
1. Read and understand completely before acting
2. Verify your understanding matches the request
3. Execute correctly on the first attempt
4. Do not apologize and then fix - just do it correctly

## Enforced Systems

### Session Heartbeat (`heartbeat_service.py`)
Runs before every agent turn on all platforms:
- Detects context overflow before it causes failures
- Handles session file lock conflicts automatically
- Auto-rotates sessions when errors or overflow detected
- Rehydrates context from warm memory after rotation
- No user action needed - continuous worker operation

### Anti-Hallucination System (`anti_hallucination.py`)
Before making claims about system state, verify using:
- `verify_file_exists(path)` - Check files actually exist
- `verify_process_running(name)` - Check processes are running
- `verify_service_active(name)` - Check systemd services
- `verify_command_exists(cmd)` - Check commands in PATH
- `get_service_status(name)` - Get actual service status

### Loop Guard System (`loop_guard.py`)
Prevents repetitive failure loops:
- `record(task, approach, success, error)` - Log each attempt
- `check(task, approach)` - Detect if in failure loop
- Auto-blocks after 3 failures or 2 same-approach failures
- Forces strategy change when loop detected

## Architecture: MCP-Based Universal Memory

CortexLLM is an **MCP server** providing universal memory access to any AI agent.

### Memory Tiers
- **Hot** (`~/.config/cortexllm/memory/hot/{platform}.json`) - Per-platform active sessions
- **Warm** (`~/.config/cortexllm/memory/warm/unified.json`) - Unified cross-platform memory
- **Cold** (`~/.config/cortexllm/memory/cold/{category}.json`) - Permanent knowledge

### MCP Tools
- `memory_read` - Read from any tier
- `memory_write` - Write to any tier
- `memory_search` - Search across all tiers
- `memory_clear` - Clear memory (use with caution)

### Supported Clients
Any MCP-compatible agent can connect:
- Claude Desktop
- OpenClaw
- VSCode with MCP
- Custom agents

### Services
- `cortexllm.service` - Main memory sync
- `cortexllm-heartbeat.service` - Health monitoring (5-min)
- `cortexllm-mcp.service` - **MCP server (universal access)**

---

*This file is core memory - permanent operational directives that must be followed in every session.*
