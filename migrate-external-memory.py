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
    """Convert markdown content to CortexLLM message format"""
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
    """Load all Claude memory files"""
    messages = []
    
    if not CLAUDE_MEMORY_DIR.exists():
        print("No Claude memory directory found")
        return messages
    
    # Read MEMORY.md index first
    memory_index = CLAUDE_MEMORY_DIR / "MEMORY.md"
    if memory_index.exists():
        with open(memory_index) as f:
            content = f.read().strip()
        messages.append({
            "source": "claude/MEMORY.md",
            "content": f"[Claude Memory Index]\n{content}"
        })
        print(f"✓ Loaded Claude MEMORY.md")
    
    # Read individual memory files
    for md_file in sorted(CLAUDE_MEMORY_DIR.glob("*.md")):
        if md_file.name == "MEMORY.md":
            continue
        
        try:
            with open(md_file) as f:
                content = f.read().strip()
            
            if content:
                messages.append({
                    "source": f"claude/{md_file.name}",
                    "content": f"[Claude Memory: {md_file.stem}]\n{content}"
                })
                print(f"✓ Loaded Claude {md_file.name}")
        except Exception as e:
            print(f"✗ Error reading {md_file}: {e}")
    
    return messages

def load_opencode_memory():
    """Load OpenCode session memory"""
    if not OPENCODE_MEMORY.exists():
        print("No OpenCode memory found")
        return []
    
    try:
        with open(OPENCODE_MEMORY) as f:
            content = f.read().strip()
        
        return [{
            "source": "opencode/session-memory.md",
            "content": f"[OpenCode Session Memory 2026-06-23]\n{content}"
        }]
    except Exception as e:
        print(f"✗ Error reading OpenCode memory: {e}")
        return []

def save_to_hot(messages):
    """Save migrated messages to hot memory"""
    hot_file = CORTEXLLM_HOT / "openclaw.json"
    
    session_data = {
        "Platform": "openclaw",
        "SessionID": f"openclaw_migrated_{int(datetime.now().timestamp())}",
        "Messages": [md_to_message(m["content"], source=m["source"]) for m in messages],
        "CreatedAt": datetime.now().isoformat(),
        "UpdatedAt": datetime.now().isoformat(),
        "TotalTokens": 0,
        "IsDirty": False
    }
    
    CORTEXLLM_HOT.mkdir(parents=True, exist_ok=True)
    with open(hot_file, 'w') as f:
        json.dump(session_data, f, indent=2)
    
    print(f"\n✓ Written {len(messages)} messages to hot memory")
    return session_data

def save_to_warm(messages):
    """Save unified warm memory (last 20 messages)"""
    warm_file = CORTEXLLM_WARM / "unified.json"
    
    warm_messages = messages[-20:] if len(messages) > 20 else messages
    
    CORTEXLLM_WARM.mkdir(parents=True, exist_ok=True)
    with open(warm_file, 'w') as f:
        json.dump([md_to_message(m["content"], source=m["source"]) for m in warm_messages], f, indent=2)
    
    print(f"✓ Written {len(warm_messages)} messages to warm memory")

def main():
    print("=== External Memory Migration (Claude + OpenCode) ===\n")
    
    # Collect all messages
    all_messages = []
    
    print("Loading Claude memory...")
    all_messages.extend(load_claude_memory())
    
    print("\nLoading OpenCode memory...")
    all_messages.extend(load_opencode_memory())
    
    if not all_messages:
        print("\n⚠ No external memory content to migrate")
        return
    
    print(f"\nTotal messages to migrate: {len(all_messages)}")
    
    print("\nSaving to CortexLLM...")
    save_to_hot(all_messages)
    save_to_warm(all_messages)
    
    print("\n=== Migration Complete ===")
    print(f"Hot:  {CORTEXLLM_HOT}/openclaw.json")
    print(f"Warm: {CORTEXLLM_WARM}/unified.json")

if __name__ == "__main__":
    main()
