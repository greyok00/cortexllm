#!/usr/bin/env python3
"""
Migrate OpenClaw memory files to CortexLLM unified memory format
"""

import json
from pathlib import Path
from datetime import datetime

HOT_LIMIT = 200
WARM_LIMIT = 500

OPENCLAW_MEMORY_DIR = Path.home() / ".openclaw/shared-agents/brain-agent/memory"
OPENCLAW_MEMORY_FILE = Path.home() / ".openclaw/shared-agents/brain-agent/MEMORY.md"
CORTEXLLM_HOT = Path.home() / ".config/cortexllm/memory/hot"
CORTEXLLM_WARM = Path.home() / ".config/cortexllm/memory/warm"
CORTEXLLM_COLD = Path.home() / ".config/cortexllm/memory/cold"


def md_to_message(content, source="openclaw-migration"):
    return {
        "Platform": "openclaw",
        "Content": content,
        "IsUser": False,
        "IsSystem": True,
        "IsError": False,
        "Time": datetime.now().isoformat(),
        "TokensIn": 0,
        "TokensOut": 0,
        "Latency": 0
    }


def migrate_daily_notes():
    messages = []
    if not OPENCLAW_MEMORY_DIR.exists():
        print("No OpenClaw daily memory directory found")
        return messages
    for daily_file in sorted(OPENCLAW_MEMORY_DIR.glob("*.md")):
        try:
            with open(daily_file) as f:
                content = f.read().strip()
            if content:
                msg = md_to_message(f"[Daily Note {daily_file.stem}]\n{content}", source=f"daily:{daily_file.name}")
                messages.append(msg)
                print(f"\u2713 Migrated {daily_file.name}")
        except (OSError, IOError) as e:
            print(f"\u2717 Error reading {daily_file}: {e}")
    return messages


def migrate_memory_md():
    if not OPENCLAW_MEMORY_FILE.exists():
        print("No MEMORY.md found")
        return []
    try:
        with open(OPENCLAW_MEMORY_FILE) as f:
            content = f.read().strip()
        if content:
            msg = md_to_message(f"[Long-term Memory]\n{content}", source="memory-md")
            print("\u2713 Migrated MEMORY.md")
            return [msg]
    except (OSError, IOError) as e:
        print(f"\u2717 Error reading MEMORY.md: {e}")
    return []


def write_hot_memory(messages):
    """Atomically write to hot memory. Cap at HOT_LIMIT."""
    capped = messages[-HOT_LIMIT:] if len(messages) > HOT_LIMIT else messages
    hot_file = CORTEXLLM_HOT / "openclaw.json"
    tmp_file = hot_file.with_suffix(".tmp")
    session_data = {
        "Platform": "openclaw",
        "SessionID": f"openclaw_{int(datetime.now().timestamp())}",
        "Messages": capped,
        "CreatedAt": datetime.now().isoformat(),
        "UpdatedAt": datetime.now().isoformat(),
        "TotalTokens": 0,
        "IsDirty": False
    }
    hot_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_file.write_text(json.dumps(session_data, indent=2))
    tmp_file.replace(hot_file)
    print(f"\u2713 Written {len(capped)} messages to hot memory (cap {HOT_LIMIT})")
    return session_data


def write_warm_memory(messages):
    """Atomically write to warm memory. Cap at WARM_LIMIT."""
    capped = messages[-WARM_LIMIT:] if len(messages) > WARM_LIMIT else messages
    warm_file = CORTEXLLM_WARM / "unified.json"
    tmp_file = warm_file.with_suffix(".tmp")
    warm_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_file.write_text(json.dumps(capped, indent=2))
    tmp_file.replace(warm_file)
    print(f"\u2713 Written {len(capped)} messages to warm memory (cap {WARM_LIMIT})")


def main():
    print("=== OpenClaw \u2192 CortexLLM Memory Migration ===\n")
    CORTEXLLM_HOT.mkdir(parents=True, exist_ok=True)
    CORTEXLLM_WARM.mkdir(parents=True, exist_ok=True)
    CORTEXLLM_COLD.mkdir(parents=True, exist_ok=True)
    all_messages = []
    print("Migrating daily notes...")
    all_messages.extend(migrate_daily_notes())
    print("\nMigrating MEMORY.md...")
    all_messages.extend(migrate_memory_md())
    if not all_messages:
        print("\n\u26a0 No memory content to migrate")
        write_hot_memory([])
        write_warm_memory([])
        return
    print(f"\nTotal messages to migrate: {len(all_messages)}")
    print("\nWriting hot memory...")
    write_hot_memory(all_messages)
    print("\nWriting warm memory...")
    write_warm_memory(all_messages)
    print("\n=== Migration Complete ===")
    print(f"Hot:  {CORTEXLLM_HOT}/openclaw.json")
    print(f"Warm: {CORTEXLLM_WARM}/unified.json")


if __name__ == "__main__":
    main()
