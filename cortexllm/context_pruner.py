#!/usr/bin/env python3
"""
Context Pruner — pre-assembly pruning stage before any prompt reaches the primary model.

Strips low-value tokens/passages from retrieved memory before injection,
combines RAG-style retrieval (pull only relevant rows) with sliding-window
turn-summarization for anything not yet promoted to cold.

Fully local — no calls beyond the local Ollama instance (and even that is optional;
the deterministic passes are stdlib-only).
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Rough token estimation (4 chars per token)
def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# Low-value pattern definitions
# ---------------------------------------------------------------------------

# Patterns that add no semantic value and can be stripped
LOW_VALUE_PATTERNS = [
    # Filler phrases
    r"\b(?:I think|I believe|I feel|In my opinion|It seems|It appears|Basically|Actually|Honestly)\b",
    # Repeated punctuation
    r"[!?.]{3,}",
    # Excessive whitespace (4+ newlines stripped; 3+ normalized by collapse_whitespace)
    r"\n{4,}",
    # Trailing/leading whitespace on lines
    r"^\s+|\s+$",
]

# Metadata fields to strip from memory entries before injection
STRIP_METADATA_KEYS = {"id", "tokens_in", "tokens_out", "metadata", "platform"}


def strip_low_value(text: str) -> str:
    """Pass 1: Strip low-value tokens and patterns."""
    for pattern in LOW_VALUE_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return text.strip()


def collapse_whitespace(text: str) -> str:
    """Pass 2: Collapse excessive whitespace."""
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def truncate_verbose(text: str, max_chars: int = 500) -> str:
    """Pass 3: Truncate verbose passages, keeping first and last sentences."""
    if len(text) <= max_chars:
        return text
    sentences = re.split(r"(?<=[.!?])\s+", text)
    if len(sentences) <= 3:
        return text[:max_chars] + "..."
    # Keep first 2 and last 1 sentences
    return " ".join(sentences[:2] + ["..."]) + " " + sentences[-1]


# ---------------------------------------------------------------------------
# RAG-style retrieval: pull only relevant rows from warm memory
# ---------------------------------------------------------------------------

def retrieve_relevant_warm(query: str, warm_entries: List[Dict],
                           max_entries: int = 10) -> List[Dict]:
    """Pull only warm memory rows relevant to the current query.

    Uses simple keyword overlap scoring (no LLM call needed).
    """
    if not warm_entries:
        return []

    query_words = set(query.lower().split())
    scored = []

    for entry in warm_entries:
        content = entry.get("content", "")
        if not content:
            continue
        content_words = set(content.lower().split())
        overlap = len(query_words & content_words)
        if overlap > 0:
            scored.append((overlap, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [e for _, e in scored[:max_entries]]


# ---------------------------------------------------------------------------
# Sliding-window turn-summarization
# ---------------------------------------------------------------------------

def summarize_turns(warm_entries: List[Dict], window_size: int = 20) -> List[Dict]:
    """Summarize older warm entries into condensed form.

    Entries beyond the window are collapsed: consecutive user/assistant pairs
    become a single summary line. Entries within the window are kept verbatim.
    """
    if len(warm_entries) <= window_size:
        return warm_entries

    recent = warm_entries[-window_size:]
    older = warm_entries[:-window_size]

    # Collapse older entries into summary pairs
    summaries = []
    i = 0
    while i < len(older):
        entry = older[i]
        role = entry.get("role", "user")
        content = entry.get("content", "")
        # Truncate long content
        content = truncate_verbose(content, 200)
        if i + 1 < len(older) and older[i + 1].get("role") != role:
            next_content = truncate_verbose(older[i + 1].get("content", ""), 200)
            summaries.append({
                "role": "summary",
                "content": f"[{role}: {content[:100]}... → {older[i+1].get('role', '')}: {next_content[:100]}...]"
            })
            i += 2
        else:
            summaries.append({
                "role": "summary",
                "content": f"[{role}: {content[:150]}...]"
            })
            i += 1

    return summaries + recent


# ---------------------------------------------------------------------------
# Main pruning pipeline
# ---------------------------------------------------------------------------

class PruneResult:
    """Result of the context pruning pipeline."""

    def __init__(self, cold_text: str, warm_text: str, stats: dict):
        self.cold_text = cold_text
        self.warm_text = warm_text
        self.token_count = estimate_tokens(cold_text) + estimate_tokens(warm_text)
        self.stats = stats

    def to_prompt_block(self) -> str:
        """Format as a prompt block for injection into the primary model."""
        parts = []
        if self.cold_text:
            parts.append(f"<cold_memory>\n{self.cold_text}\n</cold_memory>")
        if self.warm_text:
            parts.append(f"<recent_context>\n{self.warm_text}\n</recent_context>")
        return "\n\n".join(parts)


def prune_context(cold_data: dict, warm_entries: List[Dict],
                  query: str = "", max_tokens: int = 2000) -> PruneResult:
    """Run the full context pruning pipeline.

    Steps:
    1. Strip low-value tokens from cold memory
    2. RAG-retrieve relevant warm entries
    3. Sliding-window summarize older turns
    4. Strip metadata from all entries
    5. Enforce token budget
    """
    stats = {
        "cold_entries_before": 0,
        "cold_entries_after": 0,
        "warm_entries_before": len(warm_entries),
        "warm_entries_after": 0,
        "tokens_before": 0,
        "tokens_after": 0,
    }

    # --- Cold memory pruning ---
    cold_text = ""
    cold_entry_count = 0
    cold_entry_texts = []  # tracks processed text per entry for accurate truncation
    if cold_data:
        stats["cold_entries_before"] = sum(len(v) for v in cold_data.values())
        # Collapse cold dict to text, stripping metadata
        for name, entries in sorted(cold_data.items()):
            for e in entries:
                cold_entry_count += 1
                if isinstance(e, dict):
                    entry_lines = []
                    for k, v in e.items():
                        if k in STRIP_METADATA_KEYS:
                            continue
                        if isinstance(v, str) and len(v) > 300:
                            v = v[:300] + "..."
                        entry_lines.append(f"{k}: {v}")
                    entry_text = "\n".join(entry_lines)
                else:
                    entry_text = str(e)[:200]
                entry_text = strip_low_value(entry_text)
                entry_text = collapse_whitespace(entry_text)
                if entry_text:
                    cold_entry_texts.append(entry_text)
        cold_text = "\n\n".join(cold_entry_texts)
        stats["cold_entries_after"] = cold_entry_count

    # --- Warm memory pruning ---
    if query:
        warm_entries = retrieve_relevant_warm(query, warm_entries)
    warm_entries = summarize_turns(warm_entries)

    # Strip metadata from warm entries
    pruned_warm = []
    for entry in warm_entries:
        pruned = {k: v for k, v in entry.items() if k not in STRIP_METADATA_KEYS}
        content = pruned.get("content", "")
        content = strip_low_value(content)
        content = collapse_whitespace(content)
        if content:
            pruned["content"] = content
            pruned_warm.append(pruned)

    stats["warm_entries_after"] = len(pruned_warm)
    warm_text = "\n".join(
        f"{e.get('role', 'user')}: {e.get('content', '')}"
        for e in pruned_warm
    )

    # --- Token budget enforcement ---
    stats["tokens_before"] = estimate_tokens(cold_text) + estimate_tokens(warm_text)
    if stats["tokens_before"] > max_tokens:
        # Truncate warm first, then cold
        warm_tokens = estimate_tokens(warm_text)
        cold_tokens = estimate_tokens(cold_text)
        total_tokens = warm_tokens + cold_tokens
        if total_tokens > 0:
            warm_ratio = warm_tokens / total_tokens
            budget_for_warm = int(max_tokens * warm_ratio)
        else:
            budget_for_warm = max_tokens // 2
        budget_for_cold = max_tokens - budget_for_warm

        if warm_tokens > budget_for_warm:
            # Token-aware truncation: keep entries until budget is exhausted
            cumulative = 0
            keep = 0
            for entry in pruned_warm:
                entry_text = f"{entry.get('role', 'user')}: {entry.get('content', '')}"
                entry_tokens = estimate_tokens(entry_text)
                if cumulative + entry_tokens > budget_for_warm:
                    break
                cumulative += entry_tokens
                keep += 1
            keep = max(1, keep)
            truncated = len(pruned_warm) - keep
            warm_text = "\n".join(
                f"{pruned_warm[i].get('role', 'user')}: {pruned_warm[i].get('content', '')}"
                for i in range(keep)
            )
            if truncated > 0:
                warm_text += f"\n... ({truncated} more entries truncated)"

        if cold_tokens > budget_for_cold:
            # Token-aware truncation: keep entries until budget is exhausted
            cumulative = 0
            keep = 0
            for entry_text in cold_entry_texts:
                entry_tokens = estimate_tokens(entry_text)
                if cumulative + entry_tokens > budget_for_cold:
                    break
                cumulative += entry_tokens
                keep += 1
            keep = max(1, keep)
            truncated = cold_entry_count - keep
            cold_text = "\n\n".join(cold_entry_texts[:keep])
            if truncated > 0:
                cold_text += f"\n... ({truncated} more entries truncated)"

    stats["tokens_after"] = estimate_tokens(cold_text) + estimate_tokens(warm_text)

    return PruneResult(cold_text, warm_text, stats)
