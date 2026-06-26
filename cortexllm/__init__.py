"""CortexLLM - Unified AI Control for Your Terminal

A beautiful, fast terminal UI for managing AI conversations with persistent
memory and agent orchestration. Works with OpenClaw, OpenCode, or any
Ollama-compatible backend.
"""

__version__ = "2.0.0"
__author__ = "greyok00"

from .core.brain import Brain
from .core.memory import Memory
from .core.config import Config

__all__ = ["Brain", "Memory", "Config"]
