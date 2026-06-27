#!/usr/bin/env python3
"""
Migrate external memory files (Claude, OpenCode) to CortexLLM unified memory
"""

import json
from pathlib import Path
from datetime import datetime

# Paths
CORTEXLLM_HOT = Path.home() / ".config/cortexllm/memory/hot"
CORTEXLLM_WARM = Path.home() / ".config/cortexllm/memory/warm"

# External memory sources
CLAUDE_MEMORY_DIR = Path.home() / ".claude/projects/-home-grey/memory"
OPENCODE_MEMORY = Path.home() / ".opencode/session-memory.md"


def md_to_message(content, source="migration"):
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


def load_claude_memory():
    messages = []

    if not CLAUDE_MEMORY_DIR.exists():
        print("No Claude memory directory found")
        return messages

    memory_index = CLAUDE_MEMORY_DIR / "MEMORY.md"
    if memory_index.exists():
        with open(memory_index) as f:
            content = f.read().strip()
        messages.append({"source": "claude/MEMORY.md", "content": f"[Claude Memory Index]\n{content}"})
        print("\u2713 Loaded Claude MEMORY.md")

    for md_file in sorted(CLAUDE_MEMORY_DIR.glob("*.md")):
        if md_file.name == "MEMORY.md":
            continue
        try:
            with open(md_file) as f:
                content = f.read().strip()
            if content:
                messages.append({"source": f"claude/{md_file.name}", "content": f"[Claude Memory: {md_file.stem}]\n{content}"})
                print(f"\u2713 Loaded Claude {md_file.name}")
        except (OSError, IOError) as e:
            print(f"\u2717 Error reading {md_file}: {e}")

    return messages


def load_opencode_memory():
    if not OPENCODE_MEMORY.exists():
        print("No OpenCode memory found")
        return []

    try:
        with open(OPENCODE_MEMORY) as f:
            content = f.read().strip()
        return [{"source": "opencode/session-memory.md", "content": f"[OpenCode Session Memory]\n{content}"}]
    except (OSError, IOError) as e:
        print(f"\u2717 Error reading OpenCode memory: {e}")
        return []


def save_to_hot(messages):
    """Atomically save migrated messages to hot memory with unique session ID to avoid overwriting prior migrations"""
    session_id = f"openclaw_migrated_{int(datetime.now().timestamp())}"
    hot_file = CORTEXLLM_HOT / f"{session_id}.json"
    tmp_file = hot_file.with_suffix(".tmp")

    session_data = {
        "Platform": "openclaw",
        "SessionID": session_id,
        "Messages": [md_to_message(m["content"], source=m["source"]) for m in messages],
        "CreatedAt": datetime.now().isoformat(),
        "UpdatedAt": datetime.now().isoformat(),
        "TotalTokens": 0,
        "IsDirty": False
    }

    CORTEXLLM_HOT.mkdir(parents=True, exist_ok=True)
    tmp_file.write_text(json.dumps(session_data, indent=2))
    tmp_file.replace(hot_file)

    print(f"\u2713 Written {len(messages)} messages to hot memory → {hot_file.name}")
    return session_data


def save_to_warm(messages):
    warm_file = CORTEXLLM_WARM / "unified.json"
    tmp_file = warm_file.with_suffix(".tmp")

    warm_messages = messages[-20:] if len(messages) > 20 else messages

    CORTEXLLM_WARM.mkdir(parents=True, exist_ok=True)
    tmp_file.write_text(json.dumps([md_to_message(m["content"], source=m["source"]) for m in warm_messages], indent=2))
    tmp_file.replace(warm_file)

    print(f"\u2713 Written {len(warm_messages)} messages to warm memory")


def main():
    print("=== External Memory Migration (Claude + OpenCode) ===\n")

    all_messages = []

    print("Loading Claude memory...")
    all_messages.extend(load_claude_memory())

    print("\nLoading OpenCode memory...")
    all_messages.extend(load_opencode_memory())

    if not all_messages:
        print("\n\u26a0 No external memory content to migrate")
        return

    print(f"\nTotal messages to migrate: {len(all_messages)}")

    print("\nSaving to CortexLLM...")
    save_to_hot(all_messages)
    save_to_warm(all_messages)

    print("\n=== Migration Complete ===")
    print(f"Hot:  {CORTEXLLM_HOT}/")
    print(f"Warm: {CORTEXLLM_WARM}/unified.json")


if __name__ == "__main__":
    main()
