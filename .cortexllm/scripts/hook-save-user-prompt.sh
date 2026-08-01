#!/usr/bin/env bash
# hook-save-user-prompt.sh — UserPromptSubmit hook for Claude Code
# Saves every user prompt to CortexLLM hot memory.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SAVE_SCRIPT="$SCRIPT_DIR/save-context.py"
LOCK_FILE="/tmp/cortexllm-save.lock"

# Serialize with flock — prevents concurrent read-modify-write clobber
exec 8>"$LOCK_FILE"
flock -x 8 || exit 1

INPUT=$(cat /dev/stdin 2>/dev/null || echo "")
if [ -z "$INPUT" ]; then
    exit 0
fi

# Extract the user's prompt text
PROMPT=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    # Try common fields for user prompt
    prompt = data.get('prompt', '') or data.get('text', '') or data.get('content', '') or ''
    if not prompt and 'args' in data:
        args = data['args']
        if isinstance(args, dict):
            prompt = str(args.get('prompt', args.get('text', args.get('content', ''))))
    if len(prompt) > 500:
        prompt = prompt[:500] + '...'
    print(prompt.strip())
except:
    print('')
" 2>/dev/null || echo "")

if [ -z "$PROMPT" ]; then
    exit 0
fi

python3 "$SAVE_SCRIPT" --role user --platform claude "[User] $PROMPT" 2>/dev/null || true
