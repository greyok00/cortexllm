#!/usr/bin/env python3
"""
CortexLLM Memory Manager v3
- Hot: Per-platform active session (500 messages each, independent)
- Warm: Buffer-based merge (2000 total) - preserves both but shifts with usage
- Cold: Permanent knowledge, shared, never expires

Warm Memory Algorithm:
  - 70% recent messages (weighted by platform activity)
  - 30% historical messages from BOTH platforms (preserved buffer)
  - Never completely loses either platform
"""
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

CORTEXLLM_DIR = Path.home() / ".config/cortexllm"
HOT_DIR = CORTEXLLM_DIR / "memory/hot"
WARM_DIR = CORTEXLLM_DIR / "memory/warm"
COLD_DIR = CORTEXLLM_DIR / "memory/cold"

HOT_LIMIT = 500  # Messages per platform in hot
WARM_LIMIT = 2000  # Total in warm
WARM_BUFFER_RATIO = 0.3  # 30% always preserved from BOTH platforms
WARM_RECENT_RATIO = 0.7  # 70% recent (shifts with usage)

class MemoryManager:
    def __init__(self):
        HOT_DIR.mkdir(parents=True, exist_ok=True)
        WARM_DIR.mkdir(parents=True, exist_ok=True)
        COLD_DIR.mkdir(parents=True, exist_ok=True)
        
        self.last_commands = {}
        self._load_state()
        
    def _load_state(self):
        """Load persistent state"""
        state_file = CORTEXLLM_DIR / "memory_state.json"
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text())
                self.last_commands = state.get("last_commands", {})
            except:
                self.last_commands = {}
    
    def _save_state(self):
        """Save persistent state"""
        state_file = CORTEXLLM_DIR / "memory_state.json"
        state = {
            "last_commands": self.last_commands,
            "updated": datetime.now().isoformat()
        }
        state_file.write_text(json.dumps(state, indent=2))
    
    def add_to_hot(self, platform: str, content: str, role: str = "user", 
                   tokens_in: int = 0, tokens_out: int = 0, metadata: Dict = None,
                   is_code: bool = False):
        """Add message to platform's hot file (independent per platform)"""
        # Skip code in hot memory
        if is_code:
            self._add_to_warm_direct(platform, content, role, tokens_in, tokens_out, metadata)
            return {"status": "saved_to_warm", "reason": "code_excluded_from_hot"}
        
        hot_file = HOT_DIR / f"{platform}.json"
        
        # Load existing messages for THIS PLATFORM ONLY
        messages = []
        if hot_file.exists():
            try:
                messages = json.loads(hot_file.read_text())
            except:
                messages = []
        
        # Create new message
        message = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "platform": platform,
            "metadata": metadata or {}
        }
        
        # Track last command for session resume
        if role == "user":
            self.last_commands[platform] = {
                "command": content,
                "timestamp": message["timestamp"],
                "context": metadata.get("context", {}) if metadata else {}
            }
            for m in messages:
                m.pop("is_last_command", None)
            message["is_last_command"] = True
        
        messages.append(message)
        messages = messages[-HOT_LIMIT:]
        
        # Write atomically
        tmp_file = hot_file.with_suffix('.tmp')
        tmp_file.write_text(json.dumps(messages, indent=2))
        tmp_file.replace(hot_file)
        
        # Update warm file with buffer algorithm
        self._update_warm_buffer()
        self._save_state()
        
        return message
    
    def _add_to_warm_direct(self, platform: str, content: str, role: str, 
                            tokens_in: int, tokens_out: int, metadata: Dict):
        """Add directly to warm (for code that skips hot)"""
        warm_file = WARM_DIR / "unified.json"
        
        messages = []
        if warm_file.exists():
            try:
                messages = json.loads(warm_file.read_text())
            except:
                messages = []
        
        message = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "platform": platform,
            "metadata": metadata or {},
            "source": "direct"
        }
        
        messages.append(message)
        messages = messages[-WARM_LIMIT:]
        
        tmp_file = warm_file.with_suffix('.tmp')
        tmp_file.write_text(json.dumps(messages, indent=2))
        tmp_file.replace(warm_file)
    
    def _update_warm_buffer(self):
        """
        Update warm file with BUFFER ALGORITHM:
        - 70% recent messages (weighted by platform usage)
        - 30% preserved buffer from BOTH platforms (never lost)
        
        This means:
        - If you use only OpenCode, warm gradually becomes mostly OpenCode
        - But OpenClaw messages are ALWAYS preserved in the 30% buffer
        - When you return to OpenClaw, context is still there
        """
        warm_file = WARM_DIR / "unified.json"
        
        # Load BOTH hot files
        opencode_hot = []
        openclaw_hot = []
        
        opencode_file = HOT_DIR / "opencode.json"
        if opencode_file.exists():
            try:
                opencode_hot = json.loads(opencode_file.read_text())
            except:
                pass
        
        openclaw_file = HOT_DIR / "openclaw.json"
        if openclaw_file.exists():
            try:
                openclaw_hot = json.loads(openclaw_file.read_text())
            except:
                pass
        
        # Load existing warm (preserves history)
        warm_messages = []
        if warm_file.exists():
            try:
                warm_messages = json.loads(warm_file.read_text())
            except:
                pass
        
        # Calculate buffer sizes
        buffer_size = int(WARM_LIMIT * WARM_BUFFER_RATIO)  # 30% = 600 messages
        recent_size = WARM_LIMIT - buffer_size  # 70% = 1400 messages
        
        # CRITICAL: Preserve buffer from BOTH platforms equally
        # This ensures neither platform is ever completely lost
        opencode_buffer = [m for m in warm_messages if m.get("platform") == "opencode"]
        openclaw_buffer = [m for m in warm_messages if m.get("platform") == "openclaw"]
        
        # Take oldest messages from each for buffer (preserve history)
        opencode_buffer = opencode_buffer[:buffer_size // 2]  # 300 from opencode
        openclaw_buffer = openclaw_buffer[:buffer_size // 2]  # 300 from openclaw
        
        # Recent messages from hot files (weighted by actual usage)
        # More active platform gets more recent slots naturally
        recent_messages = opencode_hot + openclaw_hot
        
        # Sort recent by timestamp (newest first)
        recent_messages.sort(key=lambda m: m.get("timestamp", ""), reverse=True)
        recent_messages = recent_messages[:recent_size]
        
        # Combine: buffer (old from both) + recent (weighted by usage)
        preserved = recent_messages + opencode_buffer + openclaw_buffer
        
        # Sort final by timestamp
        preserved.sort(key=lambda m: m.get("timestamp", ""), reverse=True)
        preserved = preserved[:WARM_LIMIT]
        
        # Write atomically
        tmp_file = warm_file.with_suffix('.tmp')
        tmp_file.write_text(json.dumps(preserved, indent=2))
        tmp_file.replace(warm_file)
        
        # Return stats
        opencode_count = len([m for m in preserved if m.get("platform") == "opencode"])
        openclaw_count = len([m for m in preserved if m.get("platform") == "openclaw"])
        
        return {"opencode": opencode_count, "openclaw": openclaw_count, "total": len(preserved)}
    
    def save_to_cold(self, category: str, knowledge: Dict, immediate: bool = True):
        """Save to cold storage - PERMANENT and SHARED"""
        cold_file = COLD_DIR / f"{category}.json"
        
        existing = {}
        if cold_file.exists():
            try:
                existing = json.loads(cold_file.read_text())
            except:
                existing = {"entries": []}
        
        if "entries" not in existing:
            existing = {"entries": [], "category": category}
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "knowledge": knowledge,
            "source": "auto-discovered" if immediate else "manual",
            "platform": "shared"
        }
        
        existing["entries"].append(entry)
        existing["last_updated"] = datetime.now().isoformat()
        existing["total_entries"] = len(existing["entries"])
        
        tmp_file = cold_file.with_suffix('.tmp')
        tmp_file.write_text(json.dumps(existing, indent=2))
        tmp_file.replace(cold_file)
        
        return entry
    
    def get_session_resume(self, platform: str = None) -> Dict:
        """Get last commands for session resume"""
        if platform:
            return self.last_commands.get(platform, {})
        return {"last_commands": self.last_commands, "updated": datetime.now().isoformat()}
    
    def get_hot_messages(self, platform: str, limit: int = 50) -> List[Dict]:
        """Get recent messages from specific platform's hot file"""
        hot_file = HOT_DIR / f"{platform}.json"
        if not hot_file.exists():
            return []
        try:
            messages = json.loads(hot_file.read_text())
            return messages[-limit:]
        except:
            return []
    
    def get_warm_messages(self, platform: str = None, limit: int = 100) -> List[Dict]:
        """Get messages from warm unified file"""
        warm_file = WARM_DIR / "unified.json"
        if not warm_file.exists():
            return []
        try:
            messages = json.loads(warm_file.read_text())
            if platform:
                messages = [m for m in messages if m.get("platform") == platform]
            return messages[-limit:]
        except:
            return []
    
    def get_cold_knowledge(self, category: str) -> Dict:
        """Get knowledge from cold storage (always shared)"""
        cold_file = COLD_DIR / f"{category}.json"
        if not cold_file.exists():
            return {}
        try:
            return json.loads(cold_file.read_text())
        except:
            return {}
    
    def get_all_cold_categories(self) -> List[str]:
        """List all cold storage categories"""
        if not COLD_DIR.exists():
            return []
        return [f.stem for f in COLD_DIR.glob("*.json")]
    
    def get_platform_stats(self) -> Dict:
        """Get statistics showing buffer preservation"""
        stats = {"opencode": {"hot": 0, "warm": 0}, "openclaw": {"hot": 0, "warm": 0}}
        
        for platform in ["opencode", "openclaw"]:
            hot_file = HOT_DIR / f"{platform}.json"
            if hot_file.exists():
                try:
                    messages = json.loads(hot_file.read_text())
                    stats[platform]["hot"] = len(messages)
                except:
                    pass
        
        warm_file = WARM_DIR / "unified.json"
        if warm_file.exists():
            try:
                messages = json.loads(warm_file.read_text())
                stats["opencode"]["warm"] = len([m for m in messages if m.get("platform") == "opencode"])
                stats["openclaw"]["warm"] = len([m for m in messages if m.get("platform") == "openclaw"])
                stats["warm_total"] = len(messages)
                
                # Calculate buffer ratio
                total = stats["warm_total"]
                if total > 0:
                    stats["opencode_ratio"] = round(stats["opencode"]["warm"] / total * 100, 1)
                    stats["openclaw_ratio"] = round(stats["openclaw"]["warm"] / total * 100, 1)
            except:
                pass
        
        cold_categories = self.get_all_cold_categories()
        stats["cold_categories"] = cold_categories
        stats["cold_total"] = sum(len(self.get_cold_knowledge(c).get("entries", [])) for c in cold_categories)
        
        return stats

# Create global instance
manager = MemoryManager()

def add_message(platform, content, role="user", **kwargs):
    return manager.add_to_hot(platform, content, role, **kwargs)

def save_knowledge(category, knowledge, immediate=True):
    return manager.save_to_cold(category, knowledge, immediate)

def get_resume(platform=None):
    return manager.get_session_resume(platform)

def get_stats():
    return manager.get_platform_stats()

if __name__ == "__main__":
    print("Testing Memory Manager v3 - BUFFER ALGORITHM\n")
    
    # Simulate heavy OpenCode usage
    print("Simulating heavy OpenCode usage (20 messages)...")
    for i in range(20):
        add_message("opencode", f"OpenCode message {i}", metadata={"test": "heavy_use"})
    
    # Light OpenClaw usage
    print("Simulating light OpenClaw usage (3 messages)...")
    for i in range(3):
        add_message("openclaw", f"OpenClaw message {i}", metadata={"test": "light_use"})
    
    # Save knowledge
    save_knowledge("buffer_test", {"algorithm": "70% recent + 30% preserved buffer"})
    
    # Show stats
    print("\n=== MEMORY STATS ===")
    stats = get_stats()
    print(f"OpenCode - Hot: {stats['opencode']['hot']}, Warm: {stats['opencode']['warm']} ({stats['opencode_ratio']}%)")
    print(f"OpenClaw - Hot: {stats['openclaw']['hot']}, Warm: {stats['openclaw']['warm']} ({stats['openclaw_ratio']}%)")
    print(f"Warm Total: {stats['warm_total']}")
    print(f"\nBuffer preserved: OpenClaw still has {stats['openclaw']['warm']} messages despite light use")
    print(f"Cold Categories: {stats['cold_categories']}")
    
    print("\n✓ Memory Manager v3 ready - Buffer algorithm preserves both platforms")
