#!/usr/bin/env python3
"""
OpenClaw Memory Hook - Direct CortexLLM Integration
No gateway required for session management
Writes directly to ~/.config/cortexllm/memory/
"""
import sys
import json
from pathlib import Path
from datetime import datetime

# Import CortexLLM Memory Manager
sys.path.insert(0, str(Path.home() / ".config/cortexllm"))
from memory_manager import manager

class MemoryHook:
    """Direct CortexLLM integration - no gateway needed"""
    
    def __init__(self):
        self.platform = "openclaw"
        
    def on_command(self, command: str, context: dict = None):
        """Save command directly to CortexLLM hot memory"""
        manager.add_to_hot(
            platform=self.platform,
            content=command,
            role="user",
            metadata={"context": context or {}, "type": "command"}
        )
        self._analyze_for_cold(command, context)
        return command
    
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
    
    def on_knowledge_discovered(self, category: str, knowledge: dict):
        """Save immediately to CortexLLM cold storage"""
        manager.save_to_cold(category, knowledge, immediate=True)
        return knowledge
    
    def _analyze_for_cold(self, command: str, context: dict = None):
        """Auto-save useful patterns to cold"""
        patterns = {
            "workflow": ["workflow", "process", "steps"],
            "configuration": ["config", "setting", "setup"],
            "api_endpoint": ["endpoint", "api", "url"],
            "error_solution": ["error", "fix", "solution"]
        }
        
        for category, keywords in patterns.items():
            if any(kw in command.lower() for kw in keywords):
                manager.save_to_cold(category, {
                    "command": command,
                    "context": context or {},
                    "discovered_at": datetime.now().isoformat()
                }, immediate=True)
                break
    
    def get_context(self, limit: int = 50):
        """Get context from CortexLLM warm memory (both platforms)"""
        return manager.get_warm_messages(limit=limit)
    
    def get_resume(self):
        """Get last command for session resume"""
        return manager.get_session_resume(self.platform)

# Auto-load hook
hook = MemoryHook()
print("✓ OpenClaw using CortexLLM memory directly - no gateway required")
