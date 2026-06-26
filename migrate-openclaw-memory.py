#!/usr/bin/env python3
"""
Migrate OpenClaw memory files to CortexLLM unified memory format
"""

import json
import os
from pathlib import Path
from datetime import datetime

# Paths
OPENCLAW_MEMORY_DIR = Path.home() / ".openclaw/shared-agents/brain-agent/memory"
OPENCLAW_MEMORY_FILE = Path.home() / ".openclaw/shared-agents/brain-agent/MEMORY.md"
CORTEXLLM_HOT = Path.home() / ".config/cortexllm/memory/hot"
CORTEXLLM_WARM = Path.home() / ".config/cortexllm/memory/warm"
CORTEXLLM_COLD = Path.home() / ".config/cortexllm/memory/cold"

def md_to_message(content, source="openclaw-migration"):
    """Convert markdown memory entry to CortexLLM message format"""
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
    """Migrate daily memory files"""
    messages = []
    
    if not OPENCLAW_MEMORY_DIR.exists():
        print("No OpenClaw daily memory directory found")
        return messages
    
    for daily_file in sorted(OPENCLAW_MEMORY_DIR.glob("*.md")):
        try:
            with open(daily_file) as f:
                content = f.read().strip()
            
            if content:
                # Create a message from the daily note
                msg = md_to_message(
                    f"[Daily Note {daily_file.stem}]\n{content}",
                    source=f"daily:{daily_file.name}"
                )
                messages.append(msg)
                print(f"✓ Migrated {daily_file.name}")
        except Exception as e:
            print(f"✗ Error reading {daily_file}: {e}")
    
    return messages

def migrate_memory_md():
    """Migrate MEMORY.md if it exists"""
    if not OPENCLAW_MEMORY_FILE.exists():
        print("No MEMORY.md found")
        return []
    
    try:
        with open(OPENCLAW_MEMORY_FILE) as f:
            content = f.read().strip()
        
        if content:
            msg = md_to_message(
                f"[Long-term Memory]\n{content}",
                source="memory-md"
            )
            print(f"✓ Migrated MEMORY.md")
            return [msg]
    except Exception as e:
        print(f"✗ Error reading MEMORY.md: {e}")
    
    return []

def write_hot_memory(messages):
    """Write migrated messages to hot memory"""
    hot_file = CORTEXLLM_HOT / "openclaw.json"
    
    session_data = {
        "Platform": "openclaw",
        "SessionID": f"openclaw_{int(datetime.now().timestamp())}",
        "Messages": messages,
        "CreatedAt": datetime.now().isoformat(),
        "UpdatedAt": datetime.now().isoformat(),
        "TotalTokens": 0,
        "IsDirty": False
    }
    
    hot_file.parent.mkdir(parents=True, exist_ok=True)
    with open(hot_file, 'w') as f:
        json.dump(session_data, f, indent=2)
    
    print(f"✓ Written {len(messages)} messages to hot memory")
    return session_data

def write_warm_memory(messages):
    """Write unified warm memory (last 20 messages)"""
    warm_file = CORTEXLLM_WARM / "unified.json"
    
    # Take last 20 messages for warm memory
    warm_messages = messages[-20:] if len(messages) > 20 else messages
    
    warm_file.parent.mkdir(parents=True, exist_ok=True)
    with open(warm_file, 'w') as f:
        json.dump(warm_messages, f, indent=2)
    
    print(f"✓ Written {len(warm_messages)} messages to warm memory")

def main():
    print("=== OpenClaw → CortexLLM Memory Migration ===\n")
    
    # Ensure directories exist
    CORTEXLLM_HOT.mkdir(parents=True, exist_ok=True)
    CORTEXLLM_WARM.mkdir(parents=True, exist_ok=True)
    CORTEXLLM_COLD.mkdir(parents=True, exist_ok=True)
    
    # Collect all messages
    all_messages = []
    
    print("Migrating daily notes...")
    all_messages.extend(migrate_daily_notes())
    
    print("\nMigrating MEMORY.md...")
    all_messages.extend(migrate_memory_md())
    
    if not all_messages:
        print("\n⚠ No memory content to migrate")
        # Still create empty session files
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
