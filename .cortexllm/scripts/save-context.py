#!/usr/bin/env python3
"""
save-context.py — Save current context to CortexLLM memory.
Writes directly to SQLite (primary) and JSON (fallback) so the local model
can immediately access the most recent context.

Usage:
  python3 save-context.py "What I'm working on right now"
  echo "context" | python3 save-context.py
  python3 save-context.py --file context.txt --platform claude
"""

import os
import sys
import json
import argparse
import fcntl
from pathlib import Path
from datetime import datetime

# ─── Configuration ───────────────────────────────────────────────────────────
CORTEXLLM_DIR = Path.home() / ".config/cortexllm"
HOT_DIR = CORTEXLLM_DIR / "memory/hot"
PLATFORM = os.environ.get("CORTEXLLM_PLATFORM", "claude")

# Try to use SQLite (primary storage)
try:
    sys.path.insert(0, str(Path.home() / ".openclaw/cortexllm"))
    from cortexllm_db import db
    HAS_SQLITE = True
except ImportError:
    HAS_SQLITE = False


LOCK_FILE = Path("/tmp/cortexllm-save.lock")


def _acquire_lock():
    """Acquire exclusive lock on LOCK_FILE (blocking)."""
    lock_path = str(LOCK_FILE)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def _release_lock(fd):
    """Release lock and close fd."""
    fcntl.flock(fd, fcntl.LOCK_UN)
    os.close(fd)


def save_to_memory(content: str, role: str = "user", platform: str = PLATFORM):
    """Save content to both SQLite and JSON memory."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = {
        "role": role,
        "content": content,
        "timestamp": timestamp,
    }

    # Write to SQLite (primary) — safe, uses single-writer connection
    if HAS_SQLITE:
        try:
            conn = db.writer
            conn.execute(
                "INSERT INTO Memory_Hot (profile, role, content, platform, metadata) "
                "VALUES (?, ?, ?, ?, ?)",
                (f"platform:{platform}", role, content, platform, "{}")
            )
            conn.commit()
            print(f"[save-context] Written to SQLite (platform: {platform})", file=sys.stderr)
        except Exception as e:
            print(f"[save-context] SQLite write failed: {e}", file=sys.stderr)

    # Also write to JSON file (fallback) — lock to prevent concurrent clobber
    lock_fd = _acquire_lock()
    try:
        hot_file = HOT_DIR / f"{platform}.json"
        hot_file.parent.mkdir(parents=True, exist_ok=True)

        data = {"platform": platform, "messages": []}
        if hot_file.exists():
            try:
                data = json.loads(hot_file.read_text())
            except:
                pass

        messages = data.get("messages", [])
        messages.append(message)
        messages = messages[-500:]  # Keep last 500
        data["messages"] = messages
        hot_file.write_text(json.dumps(data, indent=2))
        print(f"[save-context] Written to JSON ({hot_file})", file=sys.stderr)
    finally:
        _release_lock(lock_fd)

    print(f"[save-context] Saved: {content[:80]}...", file=sys.stderr)
    return True


# ─── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Save context to CortexLLM memory")
    parser.add_argument("content", nargs="?", help="Context text to save")
    parser.add_argument("--file", "-f", help="Read context from file")
    parser.add_argument("--platform", "-p", default=PLATFORM, help="Platform name")
    parser.add_argument("--role", "-r", default="user", choices=["user", "assistant", "system"],
                        help="Message role")
    parser.add_argument("--stdin", action="store_true", help="Read from stdin")
    args = parser.parse_args()

    # Read content
    content = None
    if args.file:
        with open(args.file) as f:
            content = f.read()
    elif args.content:
        content = args.content
    elif args.stdin or not sys.stdin.isatty():
        content = sys.stdin.read()

    if not content:
        print("Error: No content provided. Pass as argument, use --file, or pipe input.", file=sys.stderr)
        sys.exit(1)

    save_to_memory(content.strip(), args.role, args.platform)
