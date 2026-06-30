#!/bin/bash
# CortexLLM Production Preparation Script
# Removes PII and user data before committing to production

set -e

CORTEXLLM_DIR="$HOME/.config/cortexllm"
MEMORY_DIR="$CORTEXLLM_DIR/memory"
BACKUP_DIR="$HOME/.openclaw/cortexllm/backup-$(date +%Y%m%d-%H%M%S)"

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║     CortexLLM Production Preparation                      ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo

# Create backup
echo "📦 Creating backup of current state..."
mkdir -p "$BACKUP_DIR"
cp -r "$MEMORY_DIR" "$BACKUP_DIR/" 2>/dev/null || true
cp "$CORTEXLLM_DIR/saved_messages.json" "$BACKUP_DIR/" 2>/dev/null || true
cp "$CORTEXLLM_DIR/memory_state.json" "$BACKUP_DIR/" 2>/dev/null || true
echo "   Backup saved to: $BACKUP_DIR"
echo

# Clean memory files
echo "🧹 Cleaning memory files..."

# Hot memory - keep structure, remove messages
for platform in openclaw opencode system; do
    hot_file="$MEMORY_DIR/hot/${platform}.json"
    if [ -f "$hot_file" ]; then
        echo "   Cleaning $platform hot memory..."
        python3 << EOF
import json
from pathlib import Path
hot_file = Path("$hot_file")
try:
    data = json.loads(hot_file.read_text())
    if isinstance(data, dict):
        data["messages"] = []
        data["session_id"] = ""
    else:
        data = {"platform": "$platform", "messages": [], "session_id": ""}
    hot_file.write_text(json.dumps(data, indent=2))
    print(f"      ✓ Cleaned {len(data.get('messages', []))} messages")
except Exception as e:
    print(f"      ✗ Error: {e}")
EOF
    fi
done

# Warm memory - clear completely
warm_file="$MEMORY_DIR/warm/unified.json"
if [ -f "$warm_file" ]; then
    echo "   Clearing warm memory..."
    echo '[]' > "$warm_file"
    echo "      ✓ Cleared"
fi

# Cold memory - keep structure, anonymize entries
echo "   Processing cold memory..."
for cold_file in "$MEMORY_DIR/cold/"*.json; do
    if [ -f "$cold_file" ]; then
        filename=$(basename "$cold_file")
        case "$filename" in
            education.json)
                # Keep education (generally not PII)
                echo "      Keeping education.json"
                ;;
            bookmarks.json)
                # Remove personal URLs
                echo "      Anonymizing bookmarks.json..."
                python3 << EOF
import json
from pathlib import Path
file = Path("$cold_file")
try:
    data = json.loads(file.read_text())
    # Keep only public/project URLs, remove personal ones
    if "entries" in data:
        for entry in data["entries"]:
            if "knowledge" in entry and "urls" in entry["knowledge"]:
                urls = entry["knowledge"]["urls"]
                # Filter to keep only GitHub/LinkedIn/public URLs
                filtered = [u for u in urls if any(x in u for x in ['github.com', 'linkedin.com'])]
                entry["knowledge"]["urls"] = filtered[:5]  # Limit to 5
    file.write_text(json.dumps(data, indent=2))
except Exception as e:
    print(f"Error: {e}")
EOF
                ;;
            user_context.json)
                # Remove PII but keep structure
                echo "      Anonymizing user_context.json..."
                python3 << EOF
import json
from pathlib import Path
file = Path("$cold_file")
try:
    data = json.loads(file.read_text())
    # Remove emails, keep name structure
    if "entries" in data:
        for entry in data["entries"]:
            if "knowledge" in entry:
                knowledge = entry["knowledge"]
                # Keep name, remove emails
                if "emails" in knowledge:
                    del knowledge["emails"]
    file.write_text(json.dumps(data, indent=2))
except Exception as e:
    print(f"Error: {e}")
EOF
                ;;
            *)
                echo "      Removing $filename..."
                rm "$cold_file"
                ;;
        esac
    fi
done

# Runtime state files - remove completely
echo
echo "🗑️  Removing runtime state files..."
rm -f "$CORTEXLLM_DIR/saved_messages.json"
rm -f "$CORTEXLLM_DIR/memory_state.json"
echo "   ✓ Removed saved_messages.json"
echo "   ✓ Removed memory_state.json"

# Verify clean state
echo
echo "✅ Verification:"
python3 << EOF
import json
from pathlib import Path

memory_dir = Path("$MEMORY_DIR")

# Check hot memory
for platform in ['openclaw', 'opencode', 'system']:
    f = memory_dir / 'hot' / f'{platform}.json'
    if f.exists():
        d = json.loads(f.read_text())
        msgs = d.get('messages', []) if isinstance(d, dict) else d
        status = "✓" if len(msgs) == 0 else "✗"
        print(f"   {status} Hot/{platform}.json: {len(msgs)} messages")

# Check warm memory
f = memory_dir / 'warm' / 'unified.json'
if f.exists():
    d = json.loads(f.read_text())
    msgs = d if isinstance(d, list) else d.get('messages', [])
    status = "✓" if len(msgs) == 0 else "✗"
    print(f"   {status} Warm/unified.json: {len(msgs)} messages")

# Check runtime state
if not Path("$CORTEXLLM_DIR/saved_messages.json").exists():
    print("   ✓ saved_messages.json removed")
else:
    print("   ✗ saved_messages.json still exists!")
    
if not Path("$CORTEXLLM_DIR/memory_state.json").exists():
    print("   ✓ memory_state.json removed")
else:
    print("   ✗ memory_state.json still exists!")
EOF

echo
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║  Production preparation complete!                         ║"
echo "║                                                           ║"
echo "║  Ready to commit. Files to include:                       ║"
echo "║    • memory_manager.py                                    ║"
echo "║    • save-session.py                                      ║"
echo "║    • memory_hook.py                                       ║"
echo "║    • cortexllm_mcp_server.py                              ║"
echo "║    • INSTALL-MEMORY-SYSTEM.md                             ║"
echo "║                                                           ║"
echo "║  Files to exclude (.gitignore):                           ║"
echo "║    • ~/.config/cortexllm/memory/hot/*.json                ║"
echo "║    • ~/.config/cortexllm/memory/warm/*.json               ║"
echo "║    • ~/.config/cortexllm/memory/cold/*.json               ║"
echo "║    • saved_messages.json                                  ║"
echo "║    • memory_state.json                                    ║"
echo "╚═══════════════════════════════════════════════════════════╝"
