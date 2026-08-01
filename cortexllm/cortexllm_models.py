#!/usr/bin/env python3
"""
CortexLLM Pydantic Models — typed message objects for all agent communication.

Enforced by the PreFlightGate before any LLM call and by the PostResponseVerifier
after every LLM call. No raw strings pass between agents.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_and_check(v: str) -> str:
    """Strip whitespace and reject empty/whitespace-only strings."""
    stripped = v.strip()
    if not stripped:
        raise ValueError("Value cannot be empty or whitespace-only")
    return stripped


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EventType(str, Enum):
    AGENT_STARTED = "agent_started"
    AGENT_FINISHED = "agent_finished"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    THOUGHT_GENERATED = "thought_generated"
    TASK_COMPLETE = "task_complete"
    ERROR = "error"
    LLM_CALL = "llm_call"
    LLM_RESPONSE = "llm_response"
    PRE_FLIGHT = "pre_flight"
    POST_VERIFY = "post_verify"


# ---------------------------------------------------------------------------
# Message Models
# ---------------------------------------------------------------------------

class MemoryMessage(BaseModel):
    """A single message stored in memory (hot/warm)."""
    model_config = {"extra": "forbid"}

    profile: str = Field(default="default", description="Profile scope")
    role: MessageRole = Field(default=MessageRole.USER)
    content: str = Field(..., min_length=1, description="Message content")
    tokens_in: int = Field(default=0, ge=0)
    tokens_out: int = Field(default=0, ge=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    platform: str = Field(default="default")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("content cannot be empty or whitespace-only")
        return v


class ColdFact(BaseModel):
    """A distilled fact stored in cold memory."""
    model_config = {"extra": "forbid"}

    profile: str = Field(default="shared")
    category: str = Field(..., min_length=1)
    fact: str = Field(..., min_length=1)
    source: str = Field(default="unknown", min_length=1)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

    @field_validator("category", "fact", "source")
    @classmethod
    def not_empty(cls, v: str) -> str:
        return _strip_and_check(v)


class WikiFact(BaseModel):
    """A structured wiki fact with provenance and conflict tracking."""
    model_config = {"extra": "forbid"}

    entity: str = Field(..., min_length=1, description="Subject of the fact")
    attribute: str = Field(..., min_length=1, description="Specific attribute")
    claim: str = Field(..., min_length=1, description="The claim/statement")
    profile: str = Field(default="shared")
    category: str = Field(default="wiki")
    evidence: List[str] = Field(default_factory=list, description="Supporting evidence URLs or references")
    provenance: str = Field(default="unknown", description="Platform/session that wrote it: 'openclaw' or 'claude'")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    source: str = Field(default="unknown")
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

    @field_validator("entity", "attribute", "claim")
    @classmethod
    def not_empty(cls, v: str) -> str:
        return _strip_and_check(v)


class WikiSearchResult(BaseModel):
    """A wiki search result with freshness scoring."""
    model_config = {"extra": "forbid"}

    id: int
    entity: str
    attribute: str
    claim: str
    provenance: str
    confidence: float
    freshness_score: float
    stale: bool
    evidence: List[str] = Field(default_factory=list)
    category: str = Field(default="wiki")
    profile: str = Field(default="shared")
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str
    last_verified: Optional[str] = None

    @field_validator("entity", "attribute", "claim")
    @classmethod
    def not_empty(cls, v: str) -> str:
        return _strip_and_check(v)


class Checkpoint(BaseModel):
    """A session restore point."""
    model_config = {"extra": "forbid"}

    profile: str = Field(..., min_length=1)
    last_command: str = Field(..., min_length=1)
    context: Dict[str, Any] = Field(default_factory=dict)
    session_id: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

    @field_validator("profile", "last_command")
    @classmethod
    def not_empty(cls, v: str) -> str:
        return _strip_and_check(v)


class TaskRecord(BaseModel):
    """A tracked task."""
    model_config = {"extra": "forbid"}

    profile: str = Field(..., min_length=1)
    task_id: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    @field_validator("profile", "task_id", "description")
    @classmethod
    def not_empty(cls, v: str) -> str:
        return _strip_and_check(v)


class LogEvent(BaseModel):
    """An observability event."""
    model_config = {"extra": "forbid"}

    profile: str = Field(default="default")
    event_type: EventType
    event_data: Dict[str, Any] = Field(default_factory=dict)
    task_id: Optional[str] = None
    session_id: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# ---------------------------------------------------------------------------
# Pre-Flight / Post-Response Models
# ---------------------------------------------------------------------------

class PreFlightResult(BaseModel):
    """Result of pre-flight gate checks."""
    model_config = {"extra": "forbid"}

    passed: bool = True
    blocked: bool = False
    reason: Optional[str] = None
    reroute_to: Optional[str] = None  # Different model if capability mismatch
    cached_response: Optional[str] = None  # Skip LLM if cached
    budget_remaining: Optional[float] = None
    iterations_remaining: Optional[int] = None
    warnings: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PostVerifyResult(BaseModel):
    """Result of post-response verification."""
    model_config = {"extra": "forbid"}

    passed: bool = True
    needs_retry: bool = False
    retry_reason: Optional[str] = None
    escalate_to_judge: bool = False
    judge_prompt: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Capability Descriptors
# ---------------------------------------------------------------------------

class ModelCapability(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    CODE = "code"
    TOOL_USE = "tool_use"
    FUNCTION_CALLING = "function_calling"


MODEL_CAPABILITIES: Dict[str, List[ModelCapability]] = {
    "ollama": [ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.TOOL_USE],
    "openai": [ModelCapability.TEXT, ModelCapability.IMAGE, ModelCapability.AUDIO, ModelCapability.CODE, ModelCapability.TOOL_USE, ModelCapability.FUNCTION_CALLING],
    "anthropic": [ModelCapability.TEXT, ModelCapability.IMAGE, ModelCapability.CODE, ModelCapability.TOOL_USE],
    "gemini": [ModelCapability.TEXT, ModelCapability.IMAGE, ModelCapability.AUDIO, ModelCapability.VIDEO, ModelCapability.CODE, ModelCapability.TOOL_USE],
}

# Specific model overrides
MODEL_CAPABILITY_OVERRIDES: Dict[str, List[ModelCapability]] = {
    "llava": [ModelCapability.TEXT, ModelCapability.IMAGE],
    "deepseek-v4-flash:cloud": [ModelCapability.TEXT, ModelCapability.CODE, ModelCapability.TOOL_USE],
}
