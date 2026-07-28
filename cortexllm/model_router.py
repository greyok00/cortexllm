#!/usr/bin/env python3
"""
Model Router — routes memory_search, memory_read, and ranking/filtering
operations to a small local Ollama model (1B-3B class) while the primary
conversational model stays reserved for actual reasoning.

Configuration:
  CORTEXLLM_SMALL_MODEL — env var for the small model name (default: "qwen3.6:1.5b")
  CORTEXLLM_SMALL_MODEL_URL — env var for Ollama endpoint (default: "http://127.0.0.1:11434/api/generate")

Fallback: if the small model is unavailable, falls back to the primary model
with a logged warning. Never blocks the primary model for memory ops.
"""

import json
import os
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

SMALL_MODEL = os.environ.get("CORTEXLLM_SMALL_MODEL", "qwen3.6:1.5b")
OLLAMA_URL = os.environ.get(
    "CORTEXLLM_SMALL_MODEL_URL",
    "http://127.0.0.1:11434/api/generate"
)
FALLBACK_WARNING = "small_model_unavailable"


def _call_ollama(prompt: str, model: str = None) -> Optional[str]:
    """Call the local Ollama instance with a prompt. Returns text or None on failure."""
    model_name = model or SMALL_MODEL
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 512,
        }
    }
    try:
        req = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            return result.get("response", "").strip()
    except (urllib.error.URLError, urllib.error.HTTPError,
            json.JSONDecodeError, OSError, TimeoutError) as e:
        print(f"ModelRouter: small model '{model_name}' unavailable: {e}")
        return None


def route_memory_search(query: str, limit: int, memory_instance) -> List[Dict]:
    """Route memory_search to small model for ranking/filtering.

    The small model receives the raw search results and returns a relevance-ranked
    subset. Falls back to simple substring matching if the small model is unavailable.
    """
    # Get raw results from memory
    raw_results = memory_instance.search(query, limit * 3)  # Get more for ranking

    if not raw_results:
        return []

    # Try small model for ranking
    ranked = _rank_with_small_model(query, raw_results, limit)
    if ranked is not None:
        return ranked[:limit]

    # Fallback: return raw results sorted by relevance
    print("ModelRouter: falling back to primary model for search ranking")
    raw_results.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    return raw_results[:limit]


def route_memory_read(tier: str, platform: str, category: str,
                      memory_instance) -> Optional[Dict]:
    """Route memory_read to small model for summarization/filtering.

    For cold memory with many entries, the small model can summarize or filter
    before returning. Falls back to returning all data if unavailable.
    """
    if tier == "hot":
        data = memory_instance.get_hot(platform)
    elif tier == "warm":
        data = memory_instance.get_warm()
    elif tier == "cold":
        data = memory_instance.get_cold(category)
    else:
        return None

    # Only route to small model if there's substantial data to process
    if isinstance(data, list) and len(data) > 50:
        summary = _summarize_with_small_model(tier, data)
        if summary is not None:
            return {"summary": summary, "total_entries": len(data)}

    return data


def _rank_with_small_model(query: str, results: List[Dict],
                           top_n: int) -> Optional[List[Dict]]:
    """Use small model to rank results by relevance to query."""
    # Build a compact representation for the small model
    items = []
    for i, r in enumerate(results):
        items.append(f"[{i}] {r.get('source', 'unknown')}: {r.get('content', '')[:150]}")

    prompt = (
        f"Given the search query: \"{query}\"\n\n"
        f"Rank these results by relevance (0=irrelevant, 5=perfect match). "
        f"Return only the index numbers of the top {top_n} most relevant, "
        f"one per line, ordered by relevance (most relevant first):\n\n"
        + "\n".join(items)
    )

    response = _call_ollama(prompt)
    if not response:
        return None

    # Parse response: extract index numbers
    ranked = []
    for line in response.strip().split("\n"):
        line = line.strip()
        try:
            idx = int(line.split()[0].strip("[]"))
            if 0 <= idx < len(results):
                ranked.append(results[idx])
        except (ValueError, IndexError):
            continue

    # If parsing failed, return None to trigger fallback
    return ranked if ranked else None


def _summarize_with_small_model(tier: str, data: List) -> Optional[str]:
    """Use small model to summarize memory contents."""
    # Take a sample for summarization
    sample = data[:20]
    sample_text = "\n".join(
        f"- {m.get('role', '?')}: {m.get('content', '')[:200]}"
        for m in sample if isinstance(m, dict)
    )

    prompt = (
        f"Summarize the key topics in this {tier} memory sample "
        f"(first 20 of {len(data)} entries). "
        f"List only the main themes, 2-3 sentences:\n\n{sample_text}"
    )

    return _call_ollama(prompt)
