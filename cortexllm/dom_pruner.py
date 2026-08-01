#!/usr/bin/env python3
"""
DOM Pruner — session-aware DOM structure pruning for browser/tool-use contexts.

Strips irrelevant DOM structure before it reaches the model. Does NOT persist
DOM structure across unrelated tasks; if the same task/session repeats in
sequence, reuses the already-pruned structure within that session only.

Fully local — no calls beyond the local Ollama instance.
"""

import json
import re
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# ---------------------------------------------------------------------------
# Session-aware cache: pruned DOM is cached per session_id within a task
# ---------------------------------------------------------------------------

class DOMPruneCache:
    """In-memory cache for pruned DOM structures, keyed by (session_id, task_id).

    Cleared on task boundary (call clear() when a new task starts).
    Evicts oldest entries when MAX_ENTRIES is reached (LRU eviction).
    """

    MAX_ENTRIES = 100

    def __init__(self):
        self._cache: OrderedDict[str, str] = OrderedDict()
        self._current_session: Optional[str] = None

    def _make_key(self, session_id: str, task_id: Optional[str] = None) -> str:
        """Build a composite cache key from session_id and task_id."""
        if task_id:
            return f"{session_id}::{task_id}"
        return session_id

    def get(self, session_id: str, task_id: Optional[str] = None) -> Optional[str]:
        """Get cached pruned DOM for a session and optional task_id."""
        key = self._make_key(session_id, task_id)
        value = self._cache.get(key)
        if value is not None:
            # Move to end (most recently used) for LRU tracking
            self._cache.move_to_end(key)
        return value

    def set(self, session_id: str, pruned_dom: str, task_id: Optional[str] = None):
        """Cache pruned DOM for a session and optional task_id."""
        key = self._make_key(session_id, task_id)
        # Evict oldest entry if at capacity
        if len(self._cache) >= self.MAX_ENTRIES:
            self._cache.popitem(last=False)
        self._cache[key] = pruned_dom
        self._cache.move_to_end(key)
        self._current_session = session_id

    def clear(self):
        """Clear all cached DOM (call on task boundary)."""
        self._cache.clear()
        self._current_session = None

    @property
    def current_session(self) -> Optional[str]:
        return self._current_session


# Global cache instance
_dom_cache = DOMPruneCache()


# ---------------------------------------------------------------------------
# DOM stripping patterns
# ---------------------------------------------------------------------------

# HTML tags that carry no semantic value for the model
STRIP_TAGS = {
    "script", "style", "noscript", "meta", "link", "svg",
    "path", "circle", "rect", "line", "polyline", "polygon",
    "defs", "clipPath", "mask", "use", "symbol",
}

# Attributes to strip from remaining tags
STRIP_ATTRS = {
    "style", "class", "id", "data-*", "aria-*", "onclick",
    "onload", "onerror", "onmouseover", "onmouseout",
    "tabindex", "role", "aria-*",
}

# Elements that are likely navigation/menus/chrome (low value)
LOW_VALUE_SELECTORS = [
    r'<nav[^>]*>.*?</nav>',
    r'<footer[^>]*>.*?</footer>',
    r'<header[^>]*>.*?</header>',
    r'<aside[^>]*>.*?</aside>',
    # Match full element by class — backreference captures the tag name
    r'<(\w+)[^>]*class="[^"]*(?:nav|menu|footer|header|sidebar|advert|cookie|modal|overlay)[^"]*"[^>]*>.*?</\1>',
]


def strip_tags(html: str) -> str:
    """Remove specified HTML tags and their content."""
    for tag in STRIP_TAGS:
        html = re.sub(
            rf'<{tag}[^>]*>.*?</{tag}>',
            '',
            html,
            flags=re.DOTALL | re.IGNORECASE
        )
        # Also strip self-closing variants
        html = re.sub(rf'<{tag}[^>]*/>', '', html, flags=re.IGNORECASE)
    return html


def strip_low_value_sections(html: str) -> str:
    """Remove low-value sections like nav, footer, sidebar."""
    for pattern in LOW_VALUE_SELECTORS:
        html = re.sub(pattern, '', html, flags=re.DOTALL | re.IGNORECASE)
    return html


def strip_attributes(html: str) -> str:
    """Strip non-semantic attributes from remaining tags."""
    # Remove all data-* and aria-* attributes
    html = re.sub(r'\s+(?:data|aria)-[a-zA-Z_-]+="[^"]*"', '', html)
    # Remove attributes listed in STRIP_ATTRS (skip wildcard entries handled above)
    for attr in STRIP_ATTRS:
        if attr.endswith("-*"):
            continue  # wildcard entries handled by the regex above
        html = re.sub(rf'\s+{attr}="[^"]*"', '', html)
    return html


def collapse_text(html: str) -> str:
    """Extract visible text from HTML, preserving structure."""
    # Replace block-level tags with newlines
    for tag in ['div', 'p', 'br', 'li', 'h[1-6]', 'tr', 'section', 'article']:
        html = re.sub(rf'</?{tag}[^>]*>', '\n', html, flags=re.IGNORECASE)
    # Replace inline tags with space
    for tag in ['span', 'a', 'strong', 'em', 'b', 'i', 'u', 'code']:
        html = re.sub(rf'</?{tag}[^>]*>', ' ', html, flags=re.IGNORECASE)
    # Decode common entities
    html = html.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    html = html.replace('&nbsp;', ' ').replace('&quot;', '"')
    # Collapse whitespace
    html = re.sub(r'\n{3,}', '\n\n', html)
    html = re.sub(r'[ \t]{2,}', ' ', html)
    return html.strip()


# ---------------------------------------------------------------------------
# Main pruning pipeline
# ---------------------------------------------------------------------------

MAX_HTML_SIZE = 100 * 1024 * 1024  # 100 MB


def prune_dom(raw_html: str, session_id: str, task_id: str = None) -> str:
    """Prune DOM structure for model consumption.

    Session-aware: if the same session_id is seen again within the same task,
    returns the cached pruned version. Call clear_dom_cache() on task boundary.

    Pipeline:
    1. Input validation
    2. Check cache (session + task aware)
    3. Strip non-semantic tags (script, style, svg, etc.)
    4. Strip low-value sections (nav, footer, sidebar)
    5. Strip non-semantic attributes
    6. Collapse to visible text
    7. Cache result for this session
    """
    # Input validation
    if not isinstance(raw_html, str):
        raise TypeError(f"raw_html must be str, got {type(raw_html).__name__}")
    if not isinstance(session_id, str):
        raise TypeError(f"session_id must be str, got {type(session_id).__name__}")
    if task_id is not None and not isinstance(task_id, str):
        raise TypeError(f"task_id must be str or None, got {type(task_id).__name__}")
    if len(raw_html) > MAX_HTML_SIZE:
        raise ValueError(
            f"raw_html exceeds maximum size of {MAX_HTML_SIZE} bytes "
            f"({len(raw_html)} bytes)"
        )

    # Check cache (includes task_id in key)
    cached = _dom_cache.get(session_id, task_id)
    if cached is not None:
        return cached

    # Prune
    result = strip_tags(raw_html)
    result = strip_low_value_sections(result)
    result = strip_attributes(result)
    result = collapse_text(result)

    # Truncate if still too large (max 8000 chars for DOM)
    if len(result) > 8000:
        # Keep first 4000 and last 2000
        result = result[:4000] + "\n... [truncated] ...\n" + result[-2000:]

    # Cache (includes task_id in key)
    _dom_cache.set(session_id, result, task_id)

    return result


def clear_dom_cache():
    """Clear the DOM prune cache. Call on task boundary."""
    _dom_cache.clear()
