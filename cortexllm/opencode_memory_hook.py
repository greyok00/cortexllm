#!/usr/bin/env python3
"""
OpenCode Memory Hook - Direct CortexLLM Integration
No separate session management needed
Writes directly to ~/.config/cortexllm/memory/
"""
import sys
import json
from pathlib import Path
from datetime import datetime

# Import CortexLLM Memory Manager (try multiple paths)
for _p in [str(Path.home() / ".openclaw/cortexllm"), str(Path.home() / ".openclaw"), str(Path.home() / ".local/bin")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
from memory_manager import manager

class MemoryHook:
    """Direct CortexLLM integration"""
    
    def __init__(self):
        self.platform = "opencode"
        
    def on_prompt(self, prompt: str, context: dict = None):
        """Save prompt directly to CortexLLM hot memory"""
        manager.add_to_hot(
            platform=self.platform,
            content=prompt,
            role="user",
            metadata={"context": context or {}, "type": "prompt"}
        )
        return prompt
    
    def on_response(self, response: str, tokens_in: int = 0, tokens_out: int = 0):
        """Save response directly to CortexLLM hot memory"""
        manager.add_to_hot(
            platform=self.platform,
            content=response,
            role="assistant",
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            metadata={"type": "response"}
        )
        return response
    
    def get_context(self, limit: int = 50):
        """Get context from CortexLLM warm memory"""
        return manager.get_warm_messages(limit=limit)
    
    def get_resume(self):
        """Get last prompt for session resume"""
        return manager.get_session_resume(self.platform)

# Auto-load hook
hook = MemoryHook()
print("✓ OpenCode using CortexLLM memory directly")
