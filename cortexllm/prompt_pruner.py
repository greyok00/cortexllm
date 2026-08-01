#!/usr/bin/env python3
"""
Prompt Pruning Layer — deterministic 4-pass pipeline
Collapses, deduplicates, restores dependencies, and enforces token budget.
No LLM call — zero token cost. Stdlib only.
"""
import json
import re
from pathlib import Path
from typing import Any

# Rough token estimation (4 chars per token)
def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)

class PruneResult:
    def __init__(self, cold: dict, warm: list, stats: dict):
        self.cold = cold
        self.warm = warm
        self.cold_text = self._dict_to_text(cold)
        self.warm_text = "\n".join(warm)
        self.token_count = estimate_tokens(self.cold_text) + estimate_tokens(self.warm_text)
        self.stats = stats

    @staticmethod
    def _dict_to_text(d: dict) -> str:
        lines = []
        for name, entries in sorted(d.items()):
            for e in entries:
                if isinstance(e, dict):
                    for k, v in e.items():
                        if isinstance(v, list):
                            lines.append(f"{k}: {'; '.join(str(x) for x in v)}")
                        elif isinstance(v, str) and len(v) > 200:
                            lines.append(f"{k}: {v[:200]}...")
                        else:
                            lines.append(f"{k}: {v}")
                else:
                    lines.append(str(e))
        return "\n".join(lines)


def collapse_cold(args: dict) -> dict:
    """
    Pass 1 — Collapse: strip JSON boilerplate, drop metadata, condense verbose fields.
    Input: raw cold dict {name: [{k: v, ...}, ...]}
    Output: collapsed dict with same structure but compressed content
    """
    result = {}
    for name, entries in args.items():
        compressed = []
        for e in entries:
            if not isinstance(e, dict):
                compressed.append(str(e)[:200])
                continue
            collapsed = {}
            for k, v in e.items():
                # Strip metadata fields
                if k in ('last_updated', 'category', 'total_entries', 'created_at', 'timestamp', 'id'):
                    continue
                # Collapse lists to compact format
                if isinstance(v, list):
                    collapsed[k] = '; '.join(str(x) for x in v[:8])
                    if len(v) > 8:
                        collapsed[k] += f' [+{len(v)-8} more]'
                elif isinstance(v, str) and len(v) > 200:
                    collapsed[k] = v[:200] + '...'
                else:
                    collapsed[k] = v
            if collapsed:
                compressed.append(collapsed)
        if compressed:
            result[name] = compressed
    return result


def dedup_messages(messages: list) -> list:
    """
    Pass 2 — Dedup: normalize whitespace/casing, keep first occurrence of each unique passage.
    Also dedup same-key tool results (keep newest).
    """
    seen = set()
    deduped = []
    tool_keys = {}  # key -> (content, index)

    for m in messages:
        norm = re.sub(r'\s+', ' ', m.strip()).lower()
        if norm in seen:
            continue
        seen.add(norm)

        # Check for tool result with same key
        key_match = re.match(r'^\[.*?\] (.*?):', m)
        if key_match:
            key = key_match.group(1).strip()
            if key in tool_keys:
                # Replace older entry with newer
                old_idx = tool_keys[key]
                deduped[old_idx] = m
                continue
            tool_keys[key] = len(deduped)

        deduped.append(m)

    return deduped


def restore_dependencies(messages: list, cold: dict) -> tuple:
    """
    Pass 3 — Dependency Restore: if a kept message references a DEFINE tag
    that was pruned, restore the DEFINE entry.
    Returns (updated_messages, updated_cold).
    """
    # Collect all DEFINE tags still present
    defined = set()
    for m in messages:
        for match in re.finditer(r'DEFINE:(\w+)', m):
            defined.add(match.group(1))

    # Collect all REF tags in kept messages
    referenced = set()
    for m in messages:
        for match in re.finditer(r'REF:(\w+)', m):
            referenced.add(match.group(1))

    # Find missing DEFINEs that are referenced
    missing = referenced - defined

    if not missing:
        return messages, cold

    # Check cold memory for DEFINE entries to restore
    restored = []
    seen = set()
    for name, entries in cold.items():
        for e in entries:
            if isinstance(e, dict):
                for v in e.values():
                    if isinstance(v, str):
                        for tag in missing:
                            if f'DEFINE:{tag}' in v and v not in seen:
                                seen.add(v)
                                restored.append(v)

    return messages + restored, cold


def enforce_budget(cold: dict, warm: list, task_prompt: str, token_budget: int) -> PruneResult:
    """
    Pass 4 — Budget Enforce: if total exceeds token_budget, apply priority:
    1. task-relevant @on_demand matches
    2. cold rules
    3. warm history (truncate oldest-first)
    """
    cold_text = PruneResult._dict_to_text(cold)
    warm_text = "\n".join(warm)
    total = estimate_tokens(cold_text) + estimate_tokens(warm_text)

    if total <= token_budget:
        stats = {
            'input_tokens': total,
            'output_tokens': total,
            'pruned': 0,
            'cold_entries': len(cold),
            'warm_entries': len(warm),
        }
        return PruneResult(cold, warm, stats)

    # Check for @on_demand keywords in task prompt
    task_lower = task_prompt.lower()
    on_demand_loaded = []

    # Prune cold: wrap long values, drop entries not matching task
    pruned_cold = {}
    for name, entries in cold.items():
        relevant = []
        for e in entries:
            if isinstance(e, dict):
                # Check if entry has @on_demand tags
                if '@on_demand' in str(e).lower():
                    # Only include if task mentions the keyword
                    keywords = re.findall(r'@on_demand:(\w+)', str(e).lower())
                    if keywords and not any(kw in task_lower for kw in keywords):
                        on_demand_loaded.append(name)
                        continue  # Skip this entry
            relevant.append(e)
        if relevant:
            pruned_cold[name] = relevant

    # Prune warm: keep most recent, drop oldest
    max_warm = max(10, token_budget // 40)  # ~40 tokens per warm message
    pruned_warm = warm[-max_warm:]

    stats = {
        'input_tokens': total,
        'output_tokens': estimate_tokens(PruneResult._dict_to_text(pruned_cold)) + estimate_tokens("\n".join(pruned_warm)),
        'pruned': len(warm) - len(pruned_warm),
        'cold_entries': len(pruned_cold),
        'warm_entries': len(pruned_warm),
        'on_demand_skipped': on_demand_loaded if on_demand_loaded else [],
    }
    return PruneResult(pruned_cold, pruned_warm, stats)


def prune(cold: dict, warm: list, task_prompt: str = "", token_budget: int = 2048) -> PruneResult:
    """
    Run the full 4-pass pruning pipeline.
    Deterministic: same input always same output.
    Idempotent: prune(prune(x)) == prune(x).
    """
    # Pass 1: Collapse
    collapsed = collapse_cold(cold)

    # Pass 2: Dedup
    deduped = dedup_messages(warm)

    # Pass 3: Dependency Restore
    restored_messages, restored_cold = restore_dependencies(deduped, collapsed)

    # Pass 4: Budget Enforce
    return enforce_budget(restored_cold, restored_messages, task_prompt, token_budget)


def prune_from_files(cold_dir: str, warm_file: str, task_prompt: str = "", token_budget: int = 2048) -> PruneResult:
    """Load from files, prune, return result."""
    cold = {}
    cold_path = Path(cold_dir)
    if cold_path.exists():
        for f in sorted(cold_path.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                name = f.stem
                if isinstance(data, dict):
                    entries = data.get("entries", [])
                    if entries:
                        cold[name] = [{k: v for k, v in e.items()
                                       if k not in ('id', 'last_updated', 'category', 'total_entries', 'created_at')}
                                      for e in entries]
                    else:
                        cold[name] = [{k: v for k, v in data.items()
                                       if k not in ('entries', 'category', 'last_updated', 'total_entries')}]
                elif isinstance(data, list):
                    cold[name] = data
            except Exception:
                pass

    warm = []
    warm_path = Path(warm_file)
    if warm_path.exists():
        try:
            data = json.loads(warm_path.read_text())
            if isinstance(data, dict):
                raw = data.get("messages", [])
            else:
                raw = data
            for m in raw:
                if isinstance(m, dict):
                    content = m.get("content", m.get("Content", ""))
                    role = m.get("role", m.get("Role", "?"))
                    ts = str(m.get("timestamp", m.get("Time", "")))[:19]
                    plat = m.get("platform", m.get("Platform", "?"))
                    warm.append(f"[{ts}] [{plat}] [{role}] {content}")
                elif isinstance(m, str):
                    warm.append(m)
        except Exception:
            pass

    return prune(cold, warm, task_prompt, token_budget)


if __name__ == "__main__":
    import sys
    cold_dir = sys.argv[1] if len(sys.argv) > 1 else str(Path.home() / ".cortexclaw/memory/cold")
    warm_file = sys.argv[2] if len(sys.argv) > 2 else str(Path.home() / ".cortexclaw/memory/warm/warm.json")
    task = sys.argv[3] if len(sys.argv) > 3 else ""
    budget = int(sys.argv[4]) if len(sys.argv) > 4 else 2048

    result = prune_from_files(cold_dir, warm_file, task, budget)
    print(f"Cold: {result.stats['cold_entries']} entries")
    print(f"Warm: {result.stats['warm_entries']} messages")
    print(f"Tokens: {result.token_count} (budget: {budget})")
    print(f"Pruned: {result.stats['pruned']} messages")
    if result.stats.get('on_demand_skipped'):
        print(f"@on_demand skipped: {', '.join(result.stats['on_demand_skipped'])}")
    print("---")
    print(result.cold_text)
    print("---")
    print(result.warm_text)