#!/usr/bin/env python3
"""Save current OpenClaw session to CortexLLM memory"""
import sys
import json
from pathlib import Path
from datetime import datetime

CORTEXLLM_DIR = Path.home() / ".config/cortexllm"
HOT_DIR = CORTEXLLM_DIR / "memory/hot"
WARM_DIR = CORTEXLLM_DIR / "memory/warm"
SESSIONS_DIR = Path.home() / ".openclaw/agents/brain/sessions"
HOT_LIMIT = 500
WARM_LIMIT = 2000
PLATFORM = "openclaw"

# Find most recent session
def get_latest_session():
    sessions = list(SESSIONS_DIR.glob("*.jsonl"))
    if not sessions:
        return None
    sessions.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    for s in sessions:
        if 'trajectory' not in s.name and 'lock' not in s.name and 'corrupt' not in s.name:
            return s
    return None

# Load saved message IDs
saved_file = CORTEXLLM_DIR / "saved_messages.json"
saved_messages = set()
if saved_file.exists():
    try:
        saved_messages = set(json.loads(saved_file.read_text()))
    except:
        pass

def save_message(content, role, msg_id):
    hot_file = HOT_DIR / f"{PLATFORM}.json"
    data = {"platform": PLATFORM, "messages": []}
    if hot_file.exists():
        try:
            data = json.loads(hot_file.read_text())
        except:
            pass
    
    messages = data.get("messages", [])
    if msg_id in saved_messages:
        return False
    
    messages.append({
        "timestamp": datetime.now().isoformat(),
        "role": role,
        "content": content[:10000],
        "platform": PLATFORM
    })
    messages = messages[-HOT_LIMIT:]
    data["messages"] = messages
    
    hot_file.write_text(json.dumps(data, indent=2))
    saved_messages.add(msg_id)
    return True

def update_warm():
    warm_file = WARM_DIR / "unified.json"
    all_messages = []
    for pf in [HOT_DIR / "openclaw.json", HOT_DIR / "opencode.json"]:
        if pf.exists():
            try:
                d = json.loads(pf.read_text())
                msgs = d.get("messages", []) if isinstance(d, dict) else d
                all_messages.extend([{k:v for k,v in m.items() if k != 'message_id'} for m in msgs[-200:]])
            except:
                pass
    all_messages.sort(key=lambda x: x.get("timestamp", ""))
    warm_file.write_text(json.dumps(all_messages[-WARM_LIMIT:], indent=2))

# Process latest session
session = get_latest_session()
if not session:
    print("No session found")
    sys.exit(0)

print(f"Processing {session.name}...")
count = 0
try:
    lines = session.read_text().strip().split('\n')
    for line in lines[-100:]:
        try:
            msg = json.loads(line)
            if msg.get('type') != 'message':
                continue
            m = msg.get('message', {})
            role = m.get('role')
            msg_id = msg.get('id', '')  # ID is at top level, not in __openclaw
            if not role or not msg_id:
                continue
            
            text = ""
            for part in m.get('content', []):
                if isinstance(part, dict) and part.get('type') == 'text':
                    text += part.get('text', '')
            text = text.strip()
            if not text:
                continue
            
            if save_message(text, role, msg_id):
                count += 1
        except:
            continue
except Exception as e:
    print(f"Error: {e}")

if count > 0:
    update_warm()
    # Save state
    saved_file.write_text(json.dumps(list(saved_messages)[-10000:]))
    print(f"Saved {count} messages")
else:
    print("No new messages")
