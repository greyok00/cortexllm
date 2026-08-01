#!/usr/bin/env python3
"""
OpenClaw Memory Hook - Direct CortexLLM Integration
No gateway required for session management
Writes directly to ~/.config/cortexllm/memory/
"""
import sys
import json
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Import CortexLLM Memory Manager with fallback
# ---------------------------------------------------------------------------
_manager = None

def _load_manager() -> Any:
    """Lazy-load the CortexLLM memory manager, returning None on failure."""
    global _manager
    if _manager is not None:
        return _manager

    search_paths = [
        Path.home() / ".openclaw" / "cortexllm",
        Path.home() / ".openclaw",
        Path.home() / ".local" / "bin",
    ]
    for p in search_paths:
        resolved = str(p.resolve())
        if resolved not in sys.path:
            sys.path.insert(0, resolved)

    try:
        from memory_manager import manager as mm  # type: ignore[import-untyped]
        _manager = mm
        logger.info("CortexLLM memory manager loaded")
    except ImportError as exc:
        logger.warning("CortexLLM memory manager not available: %s", exc)
        _manager = None
    return _manager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _word_boundary_pattern(term: str) -> re.Pattern:
    """Build a case-insensitive regex that matches *whole words* only."""
    escaped = re.escape(term)
    return re.compile(rf"\b{escaped}\b", re.IGNORECASE)


# Pre-compile banned-term patterns for performance
BANNED_TERMS_RAW = [
    "freecash", "quickrewards", "taskpulse", "2captcha",
    "freecash.com", "quickrewards.net", "taskpul.se",
]
BANNED_PATTERNS = [_word_boundary_pattern(t) for t in BANNED_TERMS_RAW]


# ---------------------------------------------------------------------------
# MemoryHook
# ---------------------------------------------------------------------------
class MemoryHook:
    """Direct CortexLLM integration - no gateway needed.

    Writes commands/responses to hot memory and auto-discovers patterns
    for cold storage.  All public methods are safe to call even when the
    underlying memory manager is unavailable (they degrade gracefully).
    """

    def __init__(self, platform: str = "openclaw") -> None:
        self.platform = platform
        self._manager = _load_manager()

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _is_banned(content: str) -> bool:
        """Return True if *content* references a banned site (whole-word match)."""
        return any(p.search(content) for p in BANNED_PATTERNS)

    @staticmethod
    def _validate_tokens(val: int, label: str) -> int:
        """Clamp token counts to non-negative integers."""
        if not isinstance(val, int):
            logger.warning("%s is not an int (%r); coercing to 0", label, val)
            return 0
        if val < 0:
            logger.warning("%s is negative (%d); coercing to 0", label, val)
            return 0
        return val

    # -- public API -------------------------------------------------------

    def on_command(self, command: str, context: Optional[dict] = None) -> str:
        """Save *command* to CortexLLM hot memory and scan for cold patterns."""
        if self._is_banned(command):
            return command

        if self._manager is None:
            return command

        try:
            self._manager.add_to_hot(
                platform=self.platform,
                content=command,
                role="user",
                metadata={"context": context or {}, "type": "command"},
            )
        except Exception:
            logger.exception("Failed to save command to hot memory")

        self._analyze_for_cold(command, context)
        return command

    def on_response(
        self,
        response: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
    ) -> str:
        """Save *response* to CortexLLM hot memory."""
        if self._is_banned(response):
            return response

        if self._manager is None:
            return response

        try:
            self._manager.add_to_hot(
                platform=self.platform,
                content=response,
                role="assistant",
                tokens_in=self._validate_tokens(tokens_in, "tokens_in"),
                tokens_out=self._validate_tokens(tokens_out, "tokens_out"),
                metadata={"type": "response"},
            )
        except Exception:
            logger.exception("Failed to save response to hot memory")
        return response

    def on_knowledge_discovered(self, category: str, knowledge: dict) -> dict:
        """Save immediately to CortexLLM cold storage.

        This is a non-critical operation; failures are logged but not
        propagated to the caller.
        """
        if self._manager is None:
            return knowledge

        if not isinstance(category, str) or not category.strip():
            logger.warning("Invalid category %r; skipping cold save", category)
            return knowledge

        try:
            self._manager.save_to_cold(category, knowledge, immediate=True)
        except Exception:
            logger.exception(
                "Failed to save knowledge to cold storage (category=%r)", category
            )
        return knowledge

    def get_context(self, limit: int = 50) -> list:
        """Return recent context from CortexLLM warm memory."""
        if self._manager is None:
            return []
        try:
            return self._manager.get_warm_messages(limit=limit)
        except Exception:
            logger.exception("Failed to retrieve warm context")
            return []

    def get_resume(self) -> Optional[Any]:
        """Return the last command for session resume."""
        if self._manager is None:
            return None
        try:
            return self._manager.get_session_resume(self.platform)
        except Exception:
            logger.exception("Failed to retrieve session resume")
            return None

    # -- internal ---------------------------------------------------------

    def _analyze_for_cold(self, command: str, context: Optional[dict] = None) -> None:
        """Auto-save useful patterns to cold storage.

        Scans *command* against known pattern categories and persists
        every match (not just the first).
        """
        if self._manager is None:
            return

        patterns = {
            "workflow": ["workflow", "process", "steps"],
            "configuration": ["config", "setting", "setup"],
            "api_endpoint": ["endpoint", "api", "url"],
            "error_solution": ["error", "fix", "solution"],
        }

        command_lower = command.lower()
        for category, keywords in patterns.items():
            if any(kw in command_lower for kw in keywords):
                try:
                    self._manager.save_to_cold(
                        category,
                        {
                            "command": command,
                            "context": context or {},
                            "discovered_at": datetime.now().isoformat(),
                        },
                        immediate=True,
                    )
                except Exception:
                    logger.exception(
                        "Failed to save cold pattern (category=%r)", category
                    )
                # Continue checking other categories instead of breaking


# ---------------------------------------------------------------------------
# Module-level convenience instance (lazy — no side effects on import)
# ---------------------------------------------------------------------------
_hook: Optional[MemoryHook] = None


def get_hook(platform: str = "openclaw") -> MemoryHook:
    """Return a singleton MemoryHook instance.

    The first call triggers manager loading; subsequent calls reuse the
    same instance (ignoring *platform* after the first call).
    """
    global _hook
    if _hook is None:
        _hook = MemoryHook(platform=platform)
    return _hook
