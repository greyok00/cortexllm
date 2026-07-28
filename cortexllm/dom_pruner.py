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
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# ---------------------------------------------------------------------------
# Session-aware cache: pruned DOM is cached per session_id within a task
# ---------------------------------------------------------------------------

class DOMPruneCache:
    """In-memory cache for pruned DOM structures, keyed by session_id.

    Cleared on task boundary (call clear() when a new task starts).
    """

    def __init__(self):
        self._cache: Dict[str, str] = {}
        self._current_session: Optional[str] = None

    def get(self, session_id: str) -> Optional[str]:
        """Get cached pruned DOM for a session."""
        return self._cache.get(session_id)

    def set(self, session_id: str, pruned_dom: str):
        """Cache pruned DOM for a session."""
        self._cache[session_id] = pruned_dom
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
    r'class="[^"]*(?:nav|menu|footer|header|sidebar|advert|cookie|modal|overlay)[^"]*"',
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
    # Remove style, class, id, event handlers
    for attr in ['style', 'class', 'id', 'onclick', 'onload', 'onerror',
                 'onmouseover', 'onmouseout', 'tabindex', 'role']:
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

def prune_dom(raw_html: str, session_id: str, task_id: str = None) -> str:
    """Prune DOM structure for model consumption.

    Session-aware: if the same session_id is seen again within the same task,
    returns the cached pruned version. Call clear_dom_cache() on task boundary.

    Pipeline:
    1. Check cache (session-aware)
    2. Strip non-semantic tags (script, style, svg, etc.)
    3. Strip low-value sections (nav, footer, sidebar)
    4. Strip non-semantic attributes
    5. Collapse to visible text
    6. Cache result for this session
    """
    # Check cache
    cached = _dom_cache.get(session_id)
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

    # Cache
    _dom_cache.set(session_id, result)

    return result


def clear_dom_cache():
    """Clear the DOM prune cache. Call on task boundary."""
    _dom_cache.clear()


def set_current_session(session_id: str):
    """Set the current session for cache reuse tracking."""
    _dom_cache._current_session = session_id
