#!/usr/bin/env bash
# hook-save-context.sh — postToolUse hook for Claude Code
# Saves EVERY tool use to CortexLLM hot memory.
# Called synchronously (fast — SQLite write takes ~5ms).
#
# Input (stdin): JSON with {tool, args, result, description}

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SAVE_SCRIPT="$SCRIPT_DIR/save-context.py"
LOCK_FILE="/tmp/cortexllm-save.lock"

# Serialize with flock — prevents concurrent read-modify-write clobber
exec 8>"$LOCK_FILE"
flock -x 8 || exit 1

# Read stdin — if nothing piped, exit silently
INPUT=$(cat /dev/stdin 2>/dev/null || echo "")
if [ -z "$INPUT" ]; then
    exit 0
fi

# Parse tool name
TOOL=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('tool', 'unknown'))
except:
    print('unknown')
" 2>/dev/null || echo "unknown")

# Parse description
DESC=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    desc = data.get('description', '') or ''
    if not desc:
        desc = data.get('tool', '')
        args = data.get('args', {})
        if isinstance(args, dict):
            for key in ['file_path', 'command', 'url', 'query', 'skill', 'target']:
                if key in args:
                    val = str(args[key])
                    if len(val) > 200:
                        val = val[:200] + '...'
                    desc += ' ' + val
                    break
    print(desc.strip()[:300])
except:
    print('')
" 2>/dev/null || echo "")

# Parse result summary
RESULT=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    result = data.get('result', '') or ''
    if isinstance(result, str):
        if len(result) > 200:
            result = result[:200] + '...'
    else:
        result = str(result)[:200]
    print(result.strip())
except:
    print('')
" 2>/dev/null || echo "")

# Build context message
if [ -n "$RESULT" ]; then
    CONTEXT="[$TOOL] $DESC → $RESULT"
else
    CONTEXT="[$TOOL] $DESC"
fi

# Save to hot memory (synchronous, fast)
python3 "$SAVE_SCRIPT" --role assistant --platform claude "$CONTEXT" 2>/dev/null || true
