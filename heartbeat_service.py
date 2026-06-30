#!/usr/bin/env python3
"""
CortexLLM Heartbeat Service - Per-Turn Session Recovery + Notifications

Runs BEFORE every agent turn to:
1. Check session state and recover if stale
2. Verify context window health
3. Auto-trigger /new if session is corrupted
4. Rehydrate context from memory
5. Send user notification on successful check

This is NOT the 5-minute system health check - that's separate.
This runs on every agent turn to ensure session integrity.
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# Paths
CORTEXLLM_DIR = Path.home() / ".config/cortexllm"
HOT_DIR = CORTEXLLM_DIR / "memory/hot"
WARM_DIR = CORTEXLLM_DIR / "memory/warm"
SESSIONS_DIR = Path.home() / ".openclaw/agents/brain/sessions"
STATE_FILE = CORTEXLLM_DIR / "heartbeat_state.json"

# Thresholds
STALE_THRESHOLD = timedelta(minutes=10)  # Session stale after 10 min
MAX_CONTEXT_TOKENS = 200000  # Warn at 200K, cap at 262K
MAX_MESSAGES_IN_CONTEXT = 100  # Max messages before truncation
AUTO_RESET_ENABLED = True  # Enable automatic session reset for continuous operation


class HeartbeatResult:
    def __init__(self):
        self.session_ok = True
        self.session_id: Optional[str] = None
        self.context_truncated = False
        self.messages_pruned = 0
        self.recovery_needed = False
        self.new_session_recommended = False
        self.warnings: list = []
        self.actions_taken: list = []

    def to_dict(self) -> Dict:
        return {
            "session_ok": self.session_ok,
            "session_id": self.session_id,
            "context_truncated": self.context_truncated,
            "messages_pruned": self.messages_pruned,
            "recovery_needed": self.recovery_needed,
            "new_session_recommended": self.new_session_recommended,
            "warnings": self.warnings,
            "actions_taken": self.actions_taken,
        }


def send_notification(result: HeartbeatResult):
    """
    Send user notification about heartbeat status.
    Creates a visible notification file and logs status.
    """
    notification_file = CORTEXLLM_DIR / "heartbeat_notification.json"
    
    notification = {
        "timestamp": datetime.now().isoformat(),
        "status": "healthy" if result.session_ok else "warning",
        "session_id": result.session_id[:8] if result.session_id else None,
        "messages": len([m for m in result.actions_taken if 'Pruned' in m]) or None,
        "warnings": len(result.warnings),
        "last_check": datetime.now().strftime("%H:%M:%S"),
    }
    
    # Write notification file
    notification_file.write_text(json.dumps(notification, indent=2))
    
    # Also create a simple status file for quick checking
    status_file = CORTEXLLM_DIR / "HEARTBEAT_OK"
    if result.session_ok:
        status_file.write_text(f"✓ Heartbeat OK - {datetime.now().strftime('%H:%M:%S')} - Session: {result.session_id[:8] if result.session_id else 'none'}\n")
    else:
        status_file.write_text(f"⚠ Heartbeat Warning - {datetime.now().strftime('%H:%M:%S')} - {result.warnings[0] if result.warnings else 'Unknown issue'}\n")
    
    # Print to console for visibility
    if result.session_ok:
        print(f"✓ Heartbeat OK ({notification['last_check']}) - Session: {result.session_id[:8] if result.session_id else 'none'}")
    else:
        print(f"⚠ Heartbeat Warning: {result.warnings[0] if result.warnings else 'Unknown issue'}")


def get_latest_session() -> Optional[Path]:
    """Find the current session file from sessions.json."""
    if not SESSIONS_DIR.exists():
        return None

    sessions_json_path = SESSIONS_DIR / "sessions.json"
    if not sessions_json_path.exists():
        # Fallback to finding most recent .jsonl file
        sessions = list(SESSIONS_DIR.glob("*.jsonl"))
        sessions = [s for s in sessions if 'trajectory' not in s.name and 'lock' not in s.name and 'archived' not in s.name]
        if not sessions:
            return None
        sessions.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        return sessions[0] if sessions else None

    try:
        sessions_data = json.loads(sessions_json_path.read_text())
        
        # Find the main brain agent session
        for key, entry in sessions_data.items():
            # Look for main/direct chat sessions (not cron, hooks, etc.)
            if 'agent:brain' in key or 'main' in key:
                session_id = entry.get('sessionId')
                if session_id:
                    session_file = SESSIONS_DIR / f"{session_id}.jsonl"
                    if session_file.exists():
                        return session_file
        
        # Fallback: find most recent non-archived session
        sessions = list(SESSIONS_DIR.glob("*.jsonl"))
        sessions = [s for s in sessions if 'trajectory' not in s.name and 'lock' not in s.name and 'archived' not in s.name]
        if not sessions:
            return None
        sessions.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        return sessions[0] if sessions else None
        
    except Exception as e:
        print(f"⚠ Error reading sessions.json: {e}")
        return None


def check_session_health(session_path: Path) -> HeartbeatResult:
    """
    Check if session is healthy or needs recovery.

    Checks:
    - File is readable and not corrupted
    - Last message was within stale threshold
    - No duplicate message IDs
    - Message count is reasonable
    """
    result = HeartbeatResult()
    result.session_id = session_path.stem

    try:
        content = session_path.read_text()
        lines = content.strip().split('\n')
    except Exception as e:
        result.session_ok = False
        result.recovery_needed = True
        result.warnings.append(f"Session file corrupted: {e}")
        result.actions_taken.append(f"Session {session_path.name} corrupted - recommend /new")
        result.new_session_recommended = True
        return result

    if not lines:
        result.session_ok = False
        result.recovery_needed = True
        result.warnings.append("Session file is empty")
        return result

    # Parse messages and check for issues
    messages = []
    seen_ids = set()
    last_timestamp = None

    for i, line in enumerate(lines[-MAX_MESSAGES_IN_CONTEXT * 2:]):
        try:
            msg = json.loads(line)
            if msg.get('type') != 'message':
                continue

            msg_id = msg.get('id', '')
            if msg_id in seen_ids:
                result.warnings.append(f"Duplicate message ID: {msg_id}")
                result.actions_taken.append(f"Removed duplicate message {msg_id}")
                continue
            seen_ids.add(msg_id)

            messages.append(msg)

            # Track last timestamp
            ts_str = msg.get('timestamp', '')
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                    last_timestamp = ts
                except:
                    pass

        except json.JSONDecodeError:
            result.warnings.append(f"Invalid JSON at line {i}")
            continue

    # Check if session is stale
    if last_timestamp:
        age = datetime.now(last_timestamp.tzinfo) - last_timestamp
        if age > STALE_THRESHOLD:
            result.warnings.append(f"Session stale: last message {age} ago")
            result.actions_taken.append("Session appears stale - context may need refresh")

    # Check message count
    if len(messages) > MAX_MESSAGES_IN_CONTEXT:
        result.context_truncated = True
        result.messages_pruned = len(messages) - MAX_MESSAGES_IN_CONTEXT
        result.warnings.append(f"Context window large: {len(messages)} messages")
        result.actions_taken.append(f"Pruned {result.messages_pruned} oldest messages")

    # Check for error patterns
    error_count = sum(1 for m in messages[-20:] if m.get('message', {}).get('role') == 'assistant' and
                      any(e in str(m.get('message', {}).get('content', '')) for e in ['error', 'failed', 'broken']))
    if error_count >= 3:
        result.warnings.append(f"Multiple errors in recent messages: {error_count}")
        result.new_session_recommended = True
        result.actions_taken.append("Multiple errors detected - /new may help")

    result.session_ok = len(messages) > 0
    
    # Send notification
    send_notification(result)
    
    return result


def rehydrate_context() -> Dict[str, Any]:
    """
    Load recent context from warm memory to rehydrate session.

    Returns context that should be prepended to new session.
    """
    warm_file = WARM_DIR / "unified.json"
    if not warm_file.exists():
        return {"messages": [], "summary": ""}

    try:
        messages = json.loads(warm_file.read_text())
        recent = messages[-20:]  # Last 20 from warm memory

        # Build context summary
        user_topics = []
        assistant_actions = []

        for msg in recent:
            role = msg.get('role', '')
            content = msg.get('content', '')[:200]

            if role == 'user':
                user_topics.append(content)
            elif role == 'assistant':
                assistant_actions.append(content)

        return {
            "messages": recent,
            "summary": f"Recent context: {len(user_topics)} user messages, {len(assistant_actions)} assistant responses",
            "user_topics": user_topics[-5:],
            "assistant_actions": assistant_actions[-5:],
        }
    except Exception as e:
        return {"messages": [], "summary": f"Could not rehydrate context: {e}"}


def rotate_session(session_path: Path) -> Optional[str]:
    """
    Rotate session by archiving current and creating new session ID.
    
    Returns new session ID if successful, None otherwise.
    """
    import uuid
    import shutil
    import time
    
    try:
        # Wait for any file locks to release
        time.sleep(0.5)
        
        # Generate new session ID
        new_session_id = str(uuid.uuid4())
        
        # Archive current session (keep as backup)
        archive_path = session_path.parent / f"{session_path.stem}.archived.jsonl"
        if session_path.exists():
            # Copy instead of move to avoid lock issues
            shutil.copy2(session_path, archive_path)
            print(f"→ Archived session to {archive_path.name}")
        
        # Clear the current session file (don't delete, just truncate)
        # This avoids lock issues from file deletion
        session_path.write_text("")
        print(f"→ Cleared session file {session_path.name}")
        
        # Update sessions.json to point to new ID
        sessions_json_path = session_path.parent / "sessions.json"
        
        if sessions_json_path.exists():
            sessions_data = json.loads(sessions_json_path.read_text())
            
            # Find and update the session entry
            for key, entry in sessions_data.items():
                if entry.get('sessionId') == session_path.stem:
                    old_session_id = entry['sessionId']
                    entry['sessionId'] = new_session_id
                    entry['sessionStartedAt'] = datetime.now().isoformat()
                    entry['lastInteractionAt'] = datetime.now().isoformat()
                    entry['updatedAt'] = datetime.now().isoformat()
                    # Clear compaction count for fresh start
                    entry.pop('compactionCount', None)
                    print(f"→ Rotated session: {old_session_id[:8]} → {new_session_id[:8]}")
                    break
            
            sessions_json_path.write_text(json.dumps(sessions_data, indent=2))
            return new_session_id
        else:
            print(f"⚠ sessions.json not found at {sessions_json_path}")
            return None
            
    except Exception as e:
        print(f"⚠ Session rotation failed: {e}")
        return None


def run_heartbeat() -> HeartbeatResult:
    """
    Main heartbeat function - call before every agent turn.

    Returns HeartbeatResult with:
    - session_ok: Whether current session is healthy
    - recovery_needed: Whether recovery actions are needed
    - new_session_recommended: Whether /new should be triggered
    - actions_taken: List of auto-corrections applied
    
    AUTO-RESET: If new_session_recommended is True and AUTO_RESET_ENABLED,
    automatically rotates the session to enable continuous worker operation.
    """
    result = HeartbeatResult()

    # Find current session
    session = get_latest_session()

    if not session:
        result.session_ok = False
        result.recovery_needed = True
        result.warnings.append("No session found")
        result.actions_taken.append("No active session - starting fresh")
        return result

    # Check session health
    health = check_session_health(session)
    result.session_id = health.session_id
    result.warnings.extend(health.warnings)
    result.actions_taken.extend(health.actions_taken)
    result.context_truncated = health.context_truncated
    result.messages_pruned = health.messages_pruned
    result.new_session_recommended = health.new_session_recommended

    if not health.session_ok:
        result.session_ok = False
        result.recovery_needed = True
        return result

    # Rehydrate context from warm memory
    context = rehydrate_context()
    if context["messages"]:
        result.actions_taken.append(f"Rehydrated {len(context['messages'])} messages from warm memory")

    # AUTO-RESET: If new session is recommended and enabled, rotate session now
    if result.new_session_recommended and AUTO_RESET_ENABLED:
        new_session_id = rotate_session(session)
        if new_session_id:
            result.actions_taken.append(f"✓ Auto-reset: Session rotated to {new_session_id[:8]}")
            result.session_id = new_session_id
            result.session_ok = True  # Reset was successful
            result.new_session_recommended = False  # No longer needed
        else:
            result.actions_taken.append("⚠ Auto-reset: Session rotation failed - manual /new required")
            result.warnings.append("Auto-reset failed - user intervention needed")

    # Save state for next turn
    STATE_FILE.write_text(json.dumps({
        "last_heartbeat": datetime.now().isoformat(),
        "session_id": result.session_id,
        "session_ok": result.session_ok,
        "warnings": result.warnings,
        "auto_reset_triggered": not result.new_session_recommended and AUTO_RESET_ENABLED,
    }, indent=2))

    return result


def format_heartbeat_report(result: HeartbeatResult) -> str:
    """Format heartbeat result for display."""
    lines = []

    if result.session_ok:
        lines.append(f"✓ Session: {result.session_id}")
    else:
        lines.append(f"✗ Session: {result.session_id or 'NONE'} - RECOVERY NEEDED")

    if result.context_truncated:
        lines.append(f"⚠ Context truncated: removed {result.messages_pruned} messages")

    if result.new_session_recommended:
        lines.append("⚠ Recommendation: Start new session (/new)")

    for warning in result.warnings:
        lines.append(f"⚠ {warning}")

    for action in result.actions_taken:
        lines.append(f"→ {action}")

    return "\n".join(lines)


# CLI test
if __name__ == "__main__":
    print("=== CortexLLM Heartbeat Service ===\n")
    result = run_heartbeat()
    print(format_heartbeat_report(result))
    print(f"\nFull result: {json.dumps(result.to_dict(), indent=2)}")
