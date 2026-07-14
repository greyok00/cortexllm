#!/usr/bin/env python3
"""
CortexLLM Heartbeat Service - OpenClaw Session Health Monitor

READ-ONLY: Never modifies session files. Only reports health status.
The agent (following session-heartbeat skill) decides what to do.

Checks:
1. OpenClaw session health (message count, file size)
2. Reports green/yellow/red status
3. Cleans stale lock files (safe - only removes dead .lock files)
"""

import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

# Paths — configurable via env vars, defaults to ~/.config/cortexllm
CORTEXLLM_DIR = Path(os.environ.get("CORTEXLLM_DIR", str(Path.home() / ".config/cortexllm")))
SESSIONS_DIR = Path(os.environ.get("CORTEXLLM_SESSIONS_DIR", str(CORTEXLLM_DIR / "sessions")))
STATE_FILE = CORTEXLLM_DIR / "heartbeat_state.json"
HEALTH_FILE = CORTEXLLM_DIR / "context_health.json"

# Thresholds - purely advisory, no auto-rotation
MAX_MESSAGES_WARN = 60    # Yellow: recommend /new
MAX_MESSAGES_CRIT = 100   # Red: strongly recommend /new
MAX_SIZE_MB_WARN = 2.0    # Yellow: file size warning
MAX_SIZE_MB_CRIT = 4.0    # Red: file size critical


def get_latest_session() -> Optional[Path]:
    """Find the current OpenClaw session file (read-only)."""
    if not SESSIONS_DIR.exists():
        return None

    # Try sessions.json first
    sessions_json = SESSIONS_DIR / "sessions.json"
    if sessions_json.exists():
        try:
            data = json.loads(sessions_json.read_text())
            for key, entry in data.items():
                session_id = entry.get("sessionId", "")
                if session_id:
                    session_file = SESSIONS_DIR / f"{session_id}.jsonl"
                    if session_file.exists() and session_file.stat().st_size > 0:
                        return session_file
        except:
            pass

    # Fallback: most recent non-empty .jsonl
    sessions = [f for f in SESSIONS_DIR.glob("*.jsonl")
                if 'trajectory' not in f.name and 'recovered' not in f.name
                and f.stat().st_size > 0]
    if not sessions:
        return None
    sessions.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return sessions[0]


def check_health(session_path: Path) -> dict:
    """Check session health. NEVER modifies files."""
    result = {
        "healthy": True,
        "session_id": session_path.stem,
        "message_count": 0,
        "file_size_kb": 0.0,
        "status": "green",
        "new_recommended": False,
        "warnings": [],
    }

    # File size
    try:
        size_kb = session_path.stat().st_size / 1024
        result["file_size_kb"] = round(size_kb, 1)
    except:
        result["healthy"] = False
        result["warnings"].append("Cannot read session file")
        return result

    # Count messages
    try:
        content = session_path.read_text()
        lines = content.strip().split('\n')
        count = 0
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
                if msg.get('type') == 'message':
                    count += 1
            except json.JSONDecodeError:
                pass
        result["message_count"] = count
    except:
        result["healthy"] = False
        result["warnings"].append("Cannot parse session file")
        return result

    # Determine status (advisory only)
    crit_reasons = []
    warn_reasons = []

    if count > MAX_MESSAGES_CRIT:
        crit_reasons.append(f"{count} msgs (limit {MAX_MESSAGES_CRIT})")
    elif count > MAX_MESSAGES_WARN:
        warn_reasons.append(f"{count} msgs")

    if size_kb > MAX_SIZE_MB_CRIT * 1024:
        crit_reasons.append(f"{size_kb:.0f}KB (limit {MAX_SIZE_MB_CRIT}MB)")
    elif size_kb > MAX_SIZE_MB_WARN * 1024:
        warn_reasons.append(f"{size_kb:.0f}KB")

    if crit_reasons:
        result["status"] = "red"
        result["new_recommended"] = True
        result["warnings"].append(f"CRITICAL: {', '.join(crit_reasons)}")
    elif warn_reasons:
        result["status"] = "yellow"
        result["warnings"].append(f"WARM: {', '.join(warn_reasons)}")
    else:
        result["status"] = "green"

    return result


def clean_stale_locks() -> int:
    """Safely remove lock files from dead processes. Only .lock files, never .jsonl."""
    cleaned = 0
    if not SESSIONS_DIR.exists():
        return 0

    for lock_file in SESSIONS_DIR.glob("*.lock"):
        try:
            age = time.time() - lock_file.stat().st_mtime
            if age > 120:  # Only clean locks older than 2 minutes
                lock_file.unlink()
                cleaned += 1
        except:
            pass
    return cleaned


def run_heartbeat() -> dict:
    """Main heartbeat - read-only health check."""
    result = {
        "timestamp": datetime.now().isoformat(),
        "healthy": True,
        "session_id": None,
        "message_count": 0,
        "file_size_kb": 0.0,
        "status": "green",
        "new_recommended": False,
        "warnings": [],
        "locks_cleaned": 0,
    }

    # Clean stale locks (safe operation)
    result["locks_cleaned"] = clean_stale_locks()

    # Find current session
    session = get_latest_session()
    if not session:
        result["healthy"] = False
        result["warnings"].append("No active session")
        HEALTH_FILE.write_text(json.dumps({
            "timestamp": result["timestamp"],
            "status": "no_session",
            "message": "No active OpenClaw session"
        }, indent=2))
        STATE_FILE.write_text(json.dumps(result, indent=2))
        return result

    # Check health (read-only)
    health = check_health(session)
    result.update(health)

    # Write health status (advisory only)
    CORTEXLLM_DIR.mkdir(parents=True, exist_ok=True)
    HEALTH_FILE.write_text(json.dumps({
        "timestamp": result["timestamp"],
        "status": result["status"],
        "session_id": result["session_id"][:8] if result["session_id"] else None,
        "message_count": result["message_count"],
        "file_size_kb": result["file_size_kb"],
        "new_recommended": result["new_recommended"],
        "warnings": result["warnings"][:3],
    }, indent=2))

    STATE_FILE.write_text(json.dumps(result, indent=2))
    return result


def format_report(result: dict) -> str:
    """Minimal output - agents read stdout."""
    icon = {"green": "✓", "yellow": "⚠", "red": "✗"}.get(result["status"], "?")
    lines = [f"[HEARTBEAT] {icon} {result['status'].upper()}"]
    lines.append(f"  Session: {result['session_id'][:8] if result['session_id'] else 'none'}")
    lines.append(f"  Messages: {result['message_count']} | Size: {result['file_size_kb']}KB")
    if result["new_recommended"]:
        lines.append(f"  ⚠ Run /new to reset context")
    if result["locks_cleaned"]:
        lines.append(f"  Cleaned {result['locks_cleaned']} stale lock(s)")
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CortexLLM Heartbeat")
    parser.add_argument("--interval", type=int, default=0,
                        help="Run as daemon with N-second interval (0 = run once)")
    args = parser.parse_args()

    if args.interval > 0:
        while True:
            result = run_heartbeat()
            print(format_report(result))
            if result["warnings"]:
                for w in result["warnings"]:
                    print(f"  ! {w}")
            time.sleep(args.interval)
    else:
        result = run_heartbeat()
        print(format_report(result))
        if result["warnings"]:
            for w in result["warnings"]:
                print(f"  ! {w}")
