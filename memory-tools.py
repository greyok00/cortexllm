#!/usr/bin/env python3
"""
CortexLLM Memory Tools for OpenClaw
Read/write memory in CortexLLM format with automatic Markdown↔JSON conversion
Supports staggered multi-platform saves (OpenClaw/OpenCode take turns updating warm memory)
"""

import json
import os
import fcntl
from pathlib import Path
from datetime import datetime, timedelta

# Paths
CORTEXLLM_ROOT = Path.home() / ".config/cortexllm"
HOT_OPENCLAW = CORTEXLLM_ROOT / "memory/hot/openclaw.json"
HOT_OPCODE = CORTEXLLM_ROOT / "memory/hot/opencode.json"
WARM_MEMORY = CORTEXLLM_ROOT / "memory/warm/unified.json"
COLD_MEMORY_DIR = CORTEXLLM_ROOT / "memory/cold"
STATE_FILE = CORTEXLLM_ROOT / "memory/state.json"

# Platform identification
PLATFORM = "openclaw"  # Set via env or argument: openclaw|opencode

def get_platform():
    """Get current platform from env or default"""
    return os.environ.get("CORTEXLLM_PLATFORM", "openclaw")

def get_hot_path(platform=None):
    """Get hot memory path for specified platform"""
    plat = platform or get_platform()
    if plat == "opencode":
        return HOT_OPCODE
    return HOT_OPENCLAW

def ensure_dirs():
    """Ensure all memory directories exist"""
    (CORTEXLLM_ROOT / "memory/hot").mkdir(parents=True, exist_ok=True)
    (CORTEXLLM_ROOT / "memory/warm").mkdir(parents=True, exist_ok=True)
    (CORTEXLLM_ROOT / "memory/cold").mkdir(parents=True, exist_ok=True)

def load_state():
    """Load staggered save state"""
    if not STATE_FILE.exists():
        return {
            "last_save": {"openclaw": None, "opencode": None},
            "next_turn": "openclaw",  # Which platform saves to warm next
            "turn_interval_minutes": 2
        }
    with open(STATE_FILE) as f:
        return json.load(f)

def save_state(state):
    """Save staggered save state atomically"""
    ensure_dirs()
    tmp = STATE_FILE.with_suffix('.tmp')
    with open(tmp, 'w') as f:
        json.dump(state, f, indent=2)
    tmp.replace(STATE_FILE)

def can_save_to_warm(platform=None):
    """Check if this platform can save to warm memory (staggered turns)"""
    plat = platform or get_platform()
    state = load_state()
    
    now = datetime.now()
    last_save = state["last_save"].get(plat)
    
    # If never saved, can save
    if last_save is None:
        return True
    
    # Check if enough time passed (2 minutes per platform = 4 min cycle)
    last_time = datetime.fromisoformat(last_save)
    elapsed = (now - last_time).total_seconds() / 60
    
    # Can save if it's been 2+ minutes since our last save
    return elapsed >= state["turn_interval_minutes"]

def should_save_to_warm_now(platform=None):
    """Check if it's this platform's turn to save to warm"""
    plat = platform or get_platform()
    state = load_state()
    
    # Simple round-robin: check whose turn it is
    return state["next_turn"] == plat

def record_save(platform=None):
    """Record that this platform just saved to warm memory"""
    plat = platform or get_platform()
    state = load_state()
    
    state["last_save"][plat] = datetime.now().isoformat()
    # Switch turn to other platform
    state["next_turn"] = "opencode" if plat == "openclaw" else "openclaw"
    
    save_state(state)

def load_hot(platform=None):
    """Load hot memory session for specified platform"""
    hot_path = get_hot_path(platform)
    
    if not hot_path.exists():
        plat = platform or get_platform()
        return {
            "Platform": plat,
            "SessionID": f"{plat}_{int(datetime.now().timestamp())}",
            "Messages": [],
            "CreatedAt": datetime.now().isoformat(),
            "UpdatedAt": datetime.now().isoformat(),
            "TotalTokens": 0,
            "IsDirty": False
        }

    with open(hot_path) as f:
        data = json.load(f)

    # Handle CortexLLM list format (convert to dict)
    if isinstance(data, list):
        messages = []
        for entry in data:
            msg = {
                "Platform": entry.get("platform", "openclaw"),
                "Content": entry.get("content", ""),
                "IsUser": entry.get("role", "") == "user",
                "IsSystem": entry.get("role", "") == "assistant",
                "IsError": False,
                "Time": entry.get("timestamp", datetime.now().isoformat()),
                "TokensIn": entry.get("tokens_in", 0),
                "TokensOut": entry.get("tokens_out", 0),
                "Latency": 0
            }
            messages.append(msg)

        return {
            "Platform": get_platform() if platform is None else platform,
            "SessionID": f"{get_platform() if platform is None else platform}_{int(datetime.now().timestamp())}",
            "Messages": messages,
            "CreatedAt": datetime.now().isoformat(),
            "UpdatedAt": datetime.now().isoformat(),
            "TotalTokens": 0,
            "IsDirty": False
        }

    return data

def save_hot(session, platform=None):
    """Save hot memory atomically for specified platform - converts to CortexLLM list format"""
    ensure_dirs()
    hot_path = get_hot_path(platform)

    # Convert to CortexLLM list format for compatibility with Go TUI
    cortexllm_format = []
    for msg in session.get("Messages", []):
        entry = {
            "timestamp": msg.get("Time", datetime.now().isoformat()),
            "role": "user" if msg.get("IsUser", False) else "assistant",
            "content": msg.get("Content", ""),
            "tokens_in": msg.get("TokensIn", 0),
            "tokens_out": msg.get("TokensOut", 0),
            "platform": msg.get("Platform", get_platform() if platform is None else platform)
        }
        cortexllm_format.append(entry)

    # Atomic write with file lock
    tmp = hot_path.with_suffix('.tmp')
    with open(tmp, 'w') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        json.dump(cortexllm_format, f, indent=2)
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    tmp.replace(hot_path)

def load_warm():
    """Load warm (unified) memory - merged from both platforms"""
    if not WARM_MEMORY.exists():
        return []
    
    with open(WARM_MEMORY) as f:
        return json.load(f)

def save_warm(messages, platform=None):
    """Save warm memory (last 40 messages to accommodate both platforms)"""
    ensure_dirs()
    
    # Keep more messages in warm since it's merged from both platforms
    warm_messages = messages[-40:] if len(messages) > 40 else messages
    
    tmp = WARM_MEMORY.with_suffix('.tmp')
    with open(tmp, 'w') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        json.dump(warm_messages, f, indent=2)
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    tmp.replace(WARM_MEMORY)

def md_to_message(content, is_user=False, platform=None):
    """Convert markdown content to CortexLLM message format"""
    plat = platform or get_platform()
    return {
        "Platform": plat,
        "Content": content,
        "IsUser": is_user,
        "IsSystem": not is_user,
        "IsError": False,
        "Time": datetime.now().isoformat(),
        "TokensIn": 0,
        "TokensOut": 0,
        "Latency": 0
    }

def message_to_md(message):
    """Convert CortexLLM message to markdown string"""
    content = message.get("Content", "")
    
    # Add metadata header for system messages
    if not message.get("IsUser", False):
        time_str = message.get("Time", "")[:19].replace("T", " ")
        platform = message.get("Platform", "?")
        content = f"[{time_str}] [{platform}] {content}"
    
    return content

def append_message(content, is_user=False, platform=None, force_warm=False):
    """
    Append a message to hot memory and optionally update warm.
    
    Args:
        content: Message content
        is_user: True if user message
        platform: Override platform (default from env)
        force_warm: Force save to warm even if not our turn (for important messages)
    """
    plat = platform or get_platform()
    session = load_hot(platform)
    
    msg = md_to_message(content, is_user, platform)
    session["Messages"].append(msg)
    
    # Enforce 50 message limit per platform hot memory
    if len(session["Messages"]) > 50:
        archived = session["Messages"][:len(session["Messages"]) - 50]
        session["Messages"] = session["Messages"][-50:]
        archive_to_cold(archived, session["SessionID"], platform)
    
    save_hot(session, platform)
    
    # Staggered warm memory update
    if force_warm or can_save_to_warm(platform):
        # Merge both hot memories for warm storage
        all_messages = session["Messages"].copy()
        
        # Load other platform's hot memory and merge
        other_plat = "opencode" if plat == "openclaw" else "openclaw"
        try:
            other_session = load_hot(other_plat)
            all_messages.extend(other_session.get("Messages", []))
        except:
            pass  # Other platform may not have hot memory yet
        
        # Sort by timestamp and save merged to warm
        all_messages.sort(key=lambda m: m.get("Time", ""))
        save_warm(all_messages, platform)
        record_save(platform)
    
    return msg

def get_recent(limit=20, platform=None):
    """Get recent messages from this platform's hot memory"""
    session = load_hot(platform)
    messages = session["Messages"][-limit:]
    return [message_to_md(m) for m in messages]

def get_all_recent(limit=40):
    """Get recent messages from both platforms merged"""
    all_messages = []
    
    for plat in ["openclaw", "opencode"]:
        try:
            session = load_hot(plat)
            all_messages.extend(session.get("Messages", []))
        except:
            pass
    
    # Sort by timestamp
    all_messages.sort(key=lambda m: m.get("Time", ""))
    return [message_to_md(m) for m in all_messages[-limit:]]

def search_memory(query, platform=None):
    """Simple text search in memory"""
    if platform:
        session = load_hot(platform)
        sessions = [(platform, session)]
    else:
        # Search both platforms
        sessions = []
        for plat in ["openclaw", "opencode"]:
            try:
                sessions.append((plat, load_hot(plat)))
            except:
                pass
    
    results = []
    query_lower = query.lower()
    
    for plat, session in sessions:
        for i, msg in enumerate(session.get("Messages", [])):
            content = msg.get("Content", "").lower()
            if query_lower in content:
                results.append({
                    "platform": plat,
                    "index": i,
                    "content": msg.get("Content", ""),
                    "time": msg.get("Time", ""),
                    "is_user": msg.get("IsUser", False)
                })
    
    return results

def archive_to_cold(messages, session_id, platform=None):
    """Archive messages to cold storage"""
    plat = platform or get_platform()
    timestamp = int(datetime.now().timestamp())
    cold_file = COLD_MEMORY_DIR / f"{plat}_{session_id}_{timestamp}.json"

    archive_data = {
        "SessionID": session_id,
        "Platform": plat,
        "ArchivedAt": datetime.now().isoformat(),
        "MessageCount": len(messages),
        "Messages": messages
    }

    with open(cold_file, 'w') as f:
        json.dump(archive_data, f, indent=2)

def read_inbox():
    """Read messages from OpenClaw inbox (sent from CortexLLM TUI)"""
    inbox_dir = Path.home() / ".openclaw" / "inbox"
    if not inbox_dir.exists():
        return []

    messages = []
    for f in sorted(inbox_dir.glob("msg_*.json")):
        try:
            with open(f) as fp:
                data = json.load(fp)
                messages.append({
                    "file": str(f),
                    "from": data.get("from", "unknown"),
                    "to": data.get("to", "brain"),
                    "content": data.get("content", ""),
                    "timestamp": data.get("timestamp", 0),
                    "priority": data.get("priority", "normal")
                })
        except:
            pass
    return messages

def process_inbox():
    """Process inbox messages and append to hot memory"""
    messages = read_inbox()
    processed = []

    for msg in messages:
        append_message(msg["content"], is_user=True)
        try:
            os.remove(msg["file"])
        except:
            pass
        processed.append(msg)

    return processed

def clear_session(platform=None):
    """Start a new session for specified platform"""
    plat = platform or get_platform()
    old_session = load_hot(platform)
    
    # Archive current session
    if old_session.get("Messages"):
        archive_to_cold(old_session["Messages"], old_session["SessionID"], platform)
    
    # Create new session
    new_session = {
        "Platform": plat,
        "SessionID": f"{plat}_{int(datetime.now().timestamp())}",
        "Messages": [],
        "CreatedAt": datetime.now().isoformat(),
        "UpdatedAt": datetime.now().isoformat(),
        "TotalTokens": 0,
        "IsDirty": False
    }
    
    save_hot(new_session, platform)
    
    # Don't clear warm memory - it's shared
    return new_session["SessionID"]

def status():
    """Show memory status for all platforms"""
    result = []
    
    for plat in ["openclaw", "opencode"]:
        try:
            session = load_hot(plat)
            result.append(f"{plat} hot memory: {len(session['Messages'])} messages")
        except Exception as e:
            result.append(f"{plat} hot memory: error - {e}")
    
    try:
        warm = load_warm()
        result.append(f"Warm memory (merged): {len(warm)} messages")
    except Exception as e:
        result.append(f"Warm memory: error - {e}")
    
    state = load_state()
    result.append(f"Next turn: {state['next_turn']}")
    result.append(f"Last saves: {state['last_save']}")
    
    return "\n".join(result)

# CLI interface
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: memory-tools.py {append|get|search|clear|status|inbox|process-inbox|all}")
        print("  Environment: CORTEXLLM_PLATFORM=openclaw|opencode")
        sys.exit(1)

    cmd = sys.argv[1]
    platform = os.environ.get("CORTEXLLM_PLATFORM", "openclaw")

    if cmd == "append":
        content = " ".join(sys.argv[2:])
        msg = append_message(content, is_user=False)
        print(f"✓ Added message to {platform} hot memory")

    elif cmd == "get":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        msgs = get_recent(limit)
        for m in msgs:
            print(m)

    elif cmd == "all":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 40
        msgs = get_all_recent(limit)
        for m in msgs:
            print(m)

    elif cmd == "search":
        query = " ".join(sys.argv[2:])
        results = search_memory(query)
        for r in results:
            print(f"[{r['platform']}] [{r['time'][:19]}] {r['content'][:100]}...")

    elif cmd == "clear":
        new_id = clear_session()
        print(f"✓ New session started for {platform}: {new_id}")

    elif cmd == "status":
        print(status())

    elif cmd == "inbox":
        msgs = read_inbox()
        if not msgs:
            print("Inbox empty")
        else:
            for m in msgs:
                print(f"[{m['from']} -> {m['to']}] {m['content'][:60]}")

    elif cmd == "process-inbox":
        processed = process_inbox()
        if not processed:
            print("No messages to process")
        else:
            print(f"✓ Processed {len(processed)} inbox messages")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
