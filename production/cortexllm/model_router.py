#!/usr/bin/env python3
"""
CortexLLM Model Router - Sub-Agent Delegation
Automatically delegates tasks to worker sub-agents using deepseek-v4-flash.

Architecture:
- Main session (qwen3.5:cloud): Reasoning, planning, memory, user responses
- Worker sub-agents (deepseek-v4-flash): Fetch, search, run commands, simple code

Usage in agent:
    from model_router import should_delegate, create_worker_task
    
    # Check if task should be delegated
    if should_delegate(task):
        worker_config = create_worker_task(task)
        # Spawn via sessions_spawn with worker_config['model']
"""

import json
import re
from pathlib import Path
from typing import Tuple, Optional, Dict, List

# Model configuration
PRIMARY_MODEL = "ollama/qwen3.5:cloud"       # Main session - reasoning
WORKER_MODEL = "ollama/deepseek-v4-flash:cloud"  # Sub-agents - fast execution

# Task classification patterns
REASONING_PATTERNS = [
    r'\b(plan|decide|choose|strategy|orchestrate|coordinate)\b',
    r'\b(why|explain|analyze|evaluate|assess|diagnose)\b',
    r'\b(memory|remember|learn|lesson|insight|pattern)\b',
    r'\b(debug|fix|error|broken|wrong|incorrect|verify)\b',
    r'\b(should|could|would|might|uncertain|unsure)\b',
    r'\b(compare|trade.?off|pros|cons|alternative)\b',
    r'\b(explain to|tell (the )?user|respond to|reply)\b',
    r'\b(if.*then|conditional|depends on)\b',
    r'\b(first.*then|next.*then|finally|step.*step)\b',
]

WORKER_PATTERNS = [
    r'\b(fetch|get|retrieve|load|read|download|grab)\b',
    r'\b(search|find.*information|look.*up)\b',
    r'\b(list|enumerate|count|show.*all)\b',
    r'\b(convert|transform|format|parse)\b',
    r'\b(generate.*code|write.*function|create.*file)\b',
    r'\b(summarize|extract|pull.*data)\b',
    r'\b(run|execute|test|check.*status)\b',
    r'\b(copy|move|rename|delete.*file)\b',
    r'\b(grep|cat|ls|find|tail|head)\b',
]

# Never delegate these
DELEGATION_BLOCKERS = [
    'remember this', 'learn this', 'save to memory', 'append to memory',
    'explain to user', 'tell the user', 'respond to', 'reply to',
    'debug', 'fix', 'error', 'wrong', 'broken', 'not working',
    'should i', 'what do you think', 'which is better',
]

def should_delegate(task: str) -> bool:
    """
    Determine if a task should be delegated to a worker sub-agent.
    
    Returns True if task should use deepseek-v4-flash in a sub-agent.
    Returns False if task should stay in main session with qwen3.5:cloud.
    """
    task_lower = task.lower()
    
    # Check blockers first
    for blocker in DELEGATION_BLOCKERS:
        if blocker in task_lower:
            return False
    
    # Special case: "get messages" or "get memory" is just fetching data
    if re.search(r'\b(get|fetch|retrieve)\b.*\b(messages|memory|data)\b', task_lower):
        return True
    
    # Count pattern matches
    reasoning_score = sum(1 for p in REASONING_PATTERNS if re.search(p, task_lower))
    worker_score = sum(1 for p in WORKER_PATTERNS if re.search(p, task_lower))
    
    # Strong worker signals with no reasoning = delegate
    if worker_score >= 2 and reasoning_score == 0:
        return True
    
    # Single simple fetch/get/list command = delegate
    if worker_score >= 1 and reasoning_score == 0 and len(task.split()) < 20:
        return True
    
    # Command execution = delegate
    if any(cmd in task_lower for cmd in ['run ', 'execute ', 'python3 ', './', 'bash ']):
        return True
    
    # Default: keep in main session
    return False


def create_worker_task(task: str, label: str = "worker") -> Dict:
    """
    Create configuration for spawning a worker sub-agent.
    
    Returns dict suitable for sessions_spawn:
    {
        "task": "...",
        "model": "ollama/deepseek-v4-flash:cloud",
        "label": "worker:label",
        "thinking": "off",
        "cleanup": "delete"
    }
    """
    return {
        "task": task,
        "model": WORKER_MODEL,
        "label": f"worker:{label}",
        "thinking": "off",
        "cleanup": "delete",
        "runtime": "subagent",
    }


def classify_and_delegate(task: str) -> Tuple[bool, Optional[Dict]]:
    """
    Classify task and return delegation decision.
    
    Returns:
        (should_delegate: bool, worker_config: dict or None)
    
    If should_delegate is True, worker_config contains spawn parameters.
    If False, worker_config is None (run in main session).
    """
    if should_delegate(task):
        return True, create_worker_task(task)
    return False, None


# Integration helper for agents
def auto_delegate(task: str, spawn_func) -> str:
    """
    Automatically delegate task if appropriate.
    
    Args:
        task: Task description
        spawn_func: Function to spawn sub-agent (sessions_spawn)
    
    Returns:
        "delegated" if spawned worker, "direct" if running in main session
    """
    do_delegate, config = classify_and_delegate(task)
    
    if do_delegate and config:
        # Spawn worker sub-agent
        spawn_func(
            task=config["task"],
            model=config["model"],
            label=config["label"],
            thinking=config["thinking"],
            cleanup=config["cleanup"],
            runtime=config["runtime"],
        )
        return "delegated"
    
    return "direct"


# Test cases
if __name__ == "__main__":
    test_cases = [
        # (task, should_delegate)
        ("Find my calendar events for this week", True),
        ("Search for job postings and list them", True),
        ("Get the last 10 messages from hot memory", True),
        ("Run the save-all-sessions script", True),
        ("List all files in the directory", True),
        ("Fetch weather data for Phoenix", True),
        ("Why is the gateway not connecting", False),
        ("Should I apply to this job or wait", False),
        ("Fix the broken memory integration", False),
        ("Plan a multi-step approach to organize files", False),
        ("Explain to the user what happened", False),
        ("Remember this for later", False),
        ("What do you think I should do", False),
    ]
    
    print("Model Router Delegation Test\n")
    print(f"Primary: {PRIMARY_MODEL.split('/')[-1]}")
    print(f"Worker:  {WORKER_MODEL.split('/')[-1]}\n")
    
    passed = 0
    for task, expected in test_cases:
        result = should_delegate(task)
        status = "✓" if result == expected else "✗"
        if result == expected:
            passed += 1
        
        model = "deepseek (worker)" if result else "qwen3.5 (main)"
        print(f"{status} '{task[:50]}...'")
        print(f"   → {model}\n")
    
    print(f"Results: {passed}/{len(test_cases)} correct")
