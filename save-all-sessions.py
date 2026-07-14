#!/usr/bin/env python3
"""
Universal Session Saver for CortexLLM Memory
Saves sessions from ALL AI agents to hot memory:
- OpenClaw agents (brain, main, ops, and any new ones)
- Claude Code sessions
- OpenCode sessions
- Any other agent with JSONL session files
"""
import sys
import json
import os
import hashlib
from pathlib import Path
from datetime import datetime

# Also write to SQLite for CortexLLM memory system
try:
    sys.path.insert(0, str(Path.home() / ".openclaw/cortexllm"))
    from memory_manager import manager
    SQLITE_AVAILABLE = True
except Exception:
    SQLITE_AVAILABLE = False

# CortexLLM paths
CORTEXLLM_DIR = Path.home() / ".config/cortexllm"
HOT_DIR = CORTEXLLM_DIR / "memory/hot"
WARM_DIR = CORTEXLLM_DIR / "memory/warm"
STATE_FILE = CORTEXLLM_DIR / "saved_sessions_v2.json"

HOT_LIMIT = 500  # Per platform
WARM_LIMIT = 2000

# Banned content filter - messages containing these terms are NEVER saved
BANNED_TERMS = [
    "freecash", "quickrewards", "taskpulse", "2captcha",
    "freecash.com", "quickrewards.net", "taskpul.se",
]

# Agent configurations — override via CORTEXLLM_AGENT_SOURCES env var (JSON)
AGENT_SOURCES = json.loads(os.environ.get("CORTEXLLM_AGENT_SOURCES", '{}'))
if not AGENT_SOURCES:
    AGENT_SOURCES = {
        "openclaw": {
            "base": str(Path.home() / ".openclaw/agents"),
            "pattern": "*/sessions/*.jsonl",
            "exclude": ["trajectory", "lock", "corrupt"],
            "extract_from": "message.content"
        },
        "claude": {
            "base": str(Path.home() / ".claude/projects"),
            "pattern": "*.jsonl",
            "exclude": ["tool-results"],
            "extract_from": "top_level"
        },
        "opencode": {
            "base": str(Path.home() / ".opencode"),
            "pattern": "sessions/*.jsonl",
            "exclude": [],
            "extract_from": "message.content"
        }
    }

def get_platform_from_path(path, source_name):
    """Extract platform/agent name from file path"""
    if source_name == "openclaw":
        # Path like: ~/.openclaw/agents/brain/sessions/xxx.jsonl
        parts = path.parts
        if "agents" in parts:
            idx = parts.index("agents")
            if idx + 1 < len(parts):
                return f"openclaw/{parts[idx + 1]}"  # e.g., openclaw/brain
    elif source_name == "claude":
        return "claude"
    elif source_name == "opencode":
        return "opencode"
    return source_name

def find_all_sessions():
    """Find all session files from all agents"""
    sessions = []
    for source_name, config in AGENT_SOURCES.items():
        base = config["base"]
        if not base.exists():
            continue
        for session_file in base.glob(config["pattern"]):
            if not session_file.is_file():
                continue
            # Check exclusions
            excluded = any(ex in session_file.name for ex in config["exclude"])
            if excluded:
                continue
            sessions.append((session_file, source_name))
    return sessions

def extract_messages(session_file, source_name):
    """Extract messages from a session file"""
    config = AGENT_SOURCES[source_name]
    messages = []

    try:
        content = session_file.read_text()
        lines = content.strip().split('\n')

        for line in lines[-200:]:  # Last 200 lines
            try:
                msg = json.loads(line)

                if source_name == "claude":
                    # Claude format: top-level id, type, message
                    if msg.get('type') != 'message':
                        continue
                    message = msg.get('message', {})
                    msg_id = msg.get('id', '')
                else:
                    # OpenClaw/OpenCode format
                    if msg.get('type') != 'message':
                        continue
                    message = msg.get('message', {})
                    msg_id = msg.get('id', '')

                role = message.get('role')
                if not role or not msg_id:
                    continue

                # Extract text content
                text = ""
                content_parts = message.get('content', [])
                if isinstance(content_parts, str):
                    text = content_parts
                elif isinstance(content_parts, list):
                    for part in content_parts:
                        if isinstance(part, dict) and part.get('type') == 'text':
                            text += part.get('text', '')
                        elif isinstance(part, str):
                            text += part

                text = text.strip()
                if not text:
                    continue

                # FILTER: Skip messages containing banned terms
                text_lower = text.lower()
                if any(term in text_lower for term in BANNED_TERMS):
                    continue

                # Create unique ID
                unique_id = f"{session_file.stem}:{msg_id}"

                messages.append({
                    "role": role,
                    "content": text[:10000],
                    "unique_id": unique_id,
                    "source_file": str(session_file),
                    "timestamp": msg.get('timestamp', datetime.now().isoformat())
                })

            except json.JSONDecodeError:
                continue
            except Exception as e:
                continue

    except Exception as e:
        print(f"Error reading {session_file}: {e}")

    return messages

def save_to_hot(platform, messages):
    """Save messages to platform hot memory"""
    HOT_DIR.mkdir(parents=True, exist_ok=True)
    hot_file = HOT_DIR / f"{platform.replace('/', '_')}.json"

    # Load existing
    existing = []
    if hot_file.exists():
        try:
            data = json.loads(hot_file.read_text())
            existing = data.get("messages", []) if isinstance(data, dict) else data
        except:
            existing = []

    # Add new messages
    for msg in messages:
        existing.append({
            "timestamp": msg["timestamp"],
            "role": msg["role"],
            "content": msg["content"],
            "platform": platform
        })

    # Trim to limit
    existing = existing[-HOT_LIMIT:]

    # Save as dict with messages key (required by cortexllm daemon)
    tmp_file = hot_file.with_suffix('.tmp')
    tmp_file.write_text(json.dumps({"platform": platform, "messages": existing}, indent=2))
    tmp_file.replace(hot_file)

    # Also write to SQLite for CortexLLM memory system
    if SQLITE_AVAILABLE:
        try:
            for msg in messages:
                manager.add_to_hot(
                    platform=platform.replace("/", "_"),
                    content=msg["content"],
                    role=msg["role"],
                    metadata={"source": "save-all-sessions", "timestamp": msg.get("timestamp", "")}
                )
        except Exception:
            pass  # Non-critical - JSON files are the primary store

    return len(messages)

def update_warm():
    """Merge all hot memories into warm per-profile memory"""
    WARM_DIR.mkdir(parents=True, exist_ok=True)
    warm_file = WARM_DIR / "per_profile.json"

    all_messages = []
    for hot_file in HOT_DIR.glob("*.json"):
        try:
            data = json.loads(hot_file.read_text())
            msgs = data.get("messages", []) if isinstance(data, dict) else data
            all_messages.extend(msgs[-200:])
        except:
            continue

    # Sort by timestamp
    all_messages.sort(key=lambda x: x.get("timestamp", ""))
    all_messages = all_messages[-WARM_LIMIT:]

    tmp_file = warm_file.with_suffix('.tmp')
    tmp_file.write_text(json.dumps({"messages": all_messages}, indent=2))
    tmp_file.replace(warm_file)

def main():
    # Load saved state
    saved_ids = set()
    if STATE_FILE.exists():
        try:
            saved_ids = set(json.loads(STATE_FILE.read_text()))
        except:
            saved_ids = set()

    # Find all sessions
    sessions = find_all_sessions()
    if not sessions:
        print("No session files found")
        return

    print(f"Found {len(sessions)} session file(s)")

    total_saved = 0
    platforms_processed = set()

    for session_file, source_name in sessions:
        platform = get_platform_from_path(session_file, source_name)
        platforms_processed.add(platform)

        messages = extract_messages(session_file, source_name)

        # Filter out already saved
        new_messages = [m for m in messages if m["unique_id"] not in saved_ids]

        if new_messages:
            count = save_to_hot(platform, new_messages)
            total_saved += count

            # Update saved IDs
            for m in new_messages:
                saved_ids.add(m["unique_id"])

            print(f"  {platform}: saved {count} new messages from {session_file.name}")
        else:
            print(f"  {platform}: no new messages in {session_file.name}")

    # Update warm memory
    if total_saved > 0:
        update_warm()

        # Trim saved IDs to prevent bloat
        saved_list = list(saved_ids)[-50000:]
        STATE_FILE.write_text(json.dumps(saved_list))

        print(f"\nTotal: saved {total_saved} new messages")
        print(f"Tracking {len(saved_list)} message IDs")
    else:
        print("\nNo new messages to save")

    # Summary
    print(f"\nPlatforms with hot memory:")
    for hot_file in HOT_DIR.glob("*.json"):
        try:
            data = json.loads(hot_file.read_text())
            msgs = data.get("messages", []) if isinstance(data, dict) else []
            print(f"  {hot_file.stem}: {len(msgs)} messages")
        except Exception as e:
            print(f"  {hot_file.stem}: {e}")

if __name__ == "__main__":
    main()
