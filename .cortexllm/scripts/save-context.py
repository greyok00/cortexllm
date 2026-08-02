#!/usr/bin/env python3
"""
save-context.py — Save current context to CortexLLM memory.
Writes to SQLite (primary) and NDJSON (append-only fallback).
No locks needed — NDJSON is append-only, SQLite handles concurrency natively.

Usage:
  python3 save-context.py "What I'm working on right now"
  echo "context" | python3 save-context.py
  python3 save-context.py --file context.txt --platform claude
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# ─── Configuration ───────────────────────────────────────────────────────────
CORTEXLLM_DIR = Path.home() / ".config/cortexllm"
HOT_DIR = CORTEXLLM_DIR / "memory/hot"
PLATFORM = os.environ.get("CORTEXLLM_PLATFORM", "claude")
HOT_LIMIT = 500  # Max messages per platform file

# Try to use SQLite (primary storage)
try:
    sys.path.insert(0, str(Path.home() / ".openclaw/cortexllm"))
    from cortexllm_db import db
    HAS_SQLITE = True
except ImportError:
    HAS_SQLITE = False


def _trim_ndjson(file_path: Path, limit: int = HOT_LIMIT):
    """If NDJSON file exceeds limit, trim to last N lines (rare)."""
    try:
        lines = file_path.read_text().strip().split('\n')
        if len(lines) > limit + 50:  # buffer before trimming
            file_path.write_text('\n'.join(lines[-limit:]) + '\n')
    except (OSError, ValueError):
        pass


def save_to_memory(content: str, role: str = "user", platform: str = PLATFORM):
    """Save content to both SQLite and NDJSON memory. No locks needed."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = {
        "role": role,
        "content": content,
        "timestamp": timestamp,
    }

    # Write to SQLite (primary) — safe, handles concurrency natively
    if HAS_SQLITE:
        try:
            conn = db.writer
            conn.execute(
                "INSERT INTO Memory_Hot (profile, role, content, platform, metadata) "
                "VALUES (?, ?, ?, ?, ?)",
                (f"platform:{platform}", role, content, platform, "{}")
            )
            conn.commit()
        except Exception as e:
            print(f"[save-context] SQLite write failed: {e}", file=sys.stderr)

    # Write to NDJSON file (append-only fallback) — no lock needed
    hot_file = HOT_DIR / f"{platform}.jsonl"
    hot_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(hot_file, 'a') as f:
            f.write(json.dumps(message) + '\n')
        _trim_ndjson(hot_file, HOT_LIMIT)
    except OSError as e:
        print(f"[save-context] NDJSON write failed: {e}", file=sys.stderr)

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
