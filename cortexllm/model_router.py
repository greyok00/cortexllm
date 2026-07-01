#!/usr/bin/env python3
"""
CortexLLM Model Router (2026-07-01)
Single model routing — deepseek-v4-flash:cloud for everything.
Sub-agents use the same model, no delegation to secondary models.
"""

import json
from pathlib import Path
from typing import Tuple, Optional, Dict, List

# Single model for all sessions (main + sub-agents)
PRIMARY_MODEL = "ollama/deepseek-v4-flash:cloud"
SUBAGENT_MODEL = "ollama/deepseek-v4-flash:cloud"  # Same model for sub-agents

def should_delegate(task: str) -> bool:
    """
    Determine if a task should run in a sub-agent.
    Uses the same model — splits compute, not model type.
    
    Delegates when task is long-running or independent.
    """
    # Delegate for these task types
    delegate_keywords = [
        "search", "fetch", "monitor", "watch", "scrape",
        "background", "batch", "bulk", "long", "heavy",
        "file_operation", "data_processing"
    ]
    task_lower = task.lower()
    for kw in delegate_keywords:
        if kw in task_lower:
            return True
    return False


def create_worker_task(task: str, label: str = "worker") -> Dict:
    """Create sub-agent task config — uses deepseek."""
    return {
        "task": task,
        "model": SUBAGENT_MODEL,
        "label": label,
        "runtime": "subagent"
    }


def classify_and_delegate(task: str) -> Tuple[bool, Optional[Dict]]:
    """
    Decide: run in main session or spawn sub-agent.
    Both use deepseek-v4-flash:cloud.
    
    Returns:
        (False, None) — run in main session
        (True, task_config) — spawn sub-agent
    """
    if should_delegate(task):
        return True, create_worker_task(task)
    return False, None


# Test
if __name__ == "__main__":
    test_cases = [
        "Find my calendar events for this week",
        "Search for job postings",
        "Fix the broken memory integration",
        "Monitor the uptime of my server",
        "Explain to the user what happened",
    ]
    
    print(f"Model Router v0.3.0 (2026-07-01)")
    print(f"Sub-agents use same model: {SUBAGENT_MODEL}")
    print()
    for task in test_cases:
        delegate, cfg = classify_and_delegate(task)
        if delegate:
            print(f"  ⤵ {task} → sub-agent")
        else:
            print(f"  →  {task} → main session")
