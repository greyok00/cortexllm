#!/usr/bin/env python3
"""
CortexLLM Profile System — isolated workspaces with per-profile memory.

Each profile:
  - Isolated workspace directory
  - Own instruction file (AGENT.md, SOUL.md)
  - Own sandbox directory
  - Memory scope: isolated (default) or shared (explicit opt-in)
  - Auto-numbered duplicate profile names until renamed
  - Independently tracked token/cost budget

Usage:
    registry = ProfileRegistry()
    profile = registry.get_or_create("default")
    profile.set_instruction("You are a helpful assistant.")
    profile.record_usage(tokens_in=100, tokens_out=200)
"""

import json
import shutil
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from cortexllm_db import db


# ---------------------------------------------------------------------------
# Profile Data
# ---------------------------------------------------------------------------

@dataclass
class Profile:
    """A single profile with isolated workspace and memory scope."""
    name: str
    display_name: str
    workspace_dir: Path
    sandbox_dir: Path
    instruction_file: Path
    memory_scope: str = "isolated"  # "isolated" or "shared"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    tokens_in_total: int = 0
    tokens_out_total: int = 0
    cost_total: float = 0.0
    task_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def set_instruction(self, content: str):
        """Write instruction content to the profile's instruction file."""
        self.instruction_file.parent.mkdir(parents=True, exist_ok=True)
        self.instruction_file.write_text(content)

    def get_instruction(self) -> str:
        """Read instruction content from the profile's instruction file."""
        if self.instruction_file.exists():
            return self.instruction_file.read_text()
        return ""

    def record_usage(self, tokens_in: int = 0, tokens_out: int = 0,
                     cost: float = 0.0):
        """Record token/cost usage for this profile."""
        self.tokens_in_total += tokens_in
        self.tokens_out_total += tokens_out
        self.cost_total += cost
        self.task_count += 1

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "workspace_dir": str(self.workspace_dir),
            "sandbox_dir": str(self.sandbox_dir),
            "instruction_file": str(self.instruction_file),
            "memory_scope": self.memory_scope,
            "created_at": self.created_at,
            "tokens_in_total": self.tokens_in_total,
            "tokens_out_total": self.tokens_out_total,
            "cost_total": self.cost_total,
            "task_count": self.task_count,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Profile Registry
# ---------------------------------------------------------------------------

class ProfileRegistry:
    """Manages profile creation, lookup, and persistence."""

    def __init__(self, base_dir: Path = None):
        self._base_dir = base_dir or Path.home() / ".cortexclaw" / "profiles"
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._registry_file = self._base_dir / "registry.json"
        self._profiles: Dict[str, Profile] = {}
        self._name_counts: Dict[str, int] = {}
        self._load_registry()

    # ------------------------------------------------------------------
    # Profile CRUD
    # ------------------------------------------------------------------

    def get_or_create(self, name: str, memory_scope: str = "isolated") -> Profile:
        """Get existing profile or create a new one with auto-numbered names."""
        # Check if profile exists
        if name in self._profiles:
            return self._profiles[name]

        # Auto-number duplicate display names
        display_name = name
        base_name = name
        if base_name in self._name_counts:
            self._name_counts[base_name] += 1
            display_name = f"{base_name}_{self._name_counts[base_name]}"
        else:
            self._name_counts[base_name] = 1

        # Create directories
        safe_name = name.replace(":", "_").replace("/", "_").replace(" ", "_")
        workspace_dir = self._base_dir / safe_name / "workspace"
        sandbox_dir = self._base_dir / safe_name / "sandbox"
        instruction_file = self._base_dir / safe_name / "instructions.md"

        workspace_dir.mkdir(parents=True, exist_ok=True)
        sandbox_dir.mkdir(parents=True, exist_ok=True)

        profile = Profile(
            name=name,
            display_name=display_name,
            workspace_dir=workspace_dir,
            sandbox_dir=sandbox_dir,
            instruction_file=instruction_file,
            memory_scope=memory_scope,
        )

        self._profiles[name] = profile
        self._save_registry()
        return profile

    def get(self, name: str) -> Optional[Profile]:
        """Get a profile by name."""
        return self._profiles.get(name)

    def delete(self, name: str):
        """Delete a profile and its directories."""
        if name not in self._profiles:
            return
        profile = self._profiles[name]
        # Remove directories
        profile_dir = profile.workspace_dir.parent
        if profile_dir.exists():
            shutil.rmtree(profile_dir)
        del self._profiles[name]
        self._save_registry()

    def rename(self, old_name: str, new_name: str) -> Optional[Profile]:
        """Rename a profile."""
        if old_name not in self._profiles:
            return None
        profile = self._profiles.pop(old_name)
        profile.name = new_name
        profile.display_name = new_name
        self._profiles[new_name] = profile
        self._save_registry()
        return profile

    def list_profiles(self) -> List[Profile]:
        """List all profiles."""
        return list(self._profiles.values())

    def get_active_profiles(self) -> List[Profile]:
        """Get profiles with recent activity (last 24h)."""
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        active = []
        for profile in self._profiles.values():
            # Check if profile has recent Memory_Hot entries
            rows = db.reader().execute(
                "SELECT COUNT(*) FROM Memory_Hot "
                "WHERE profile = ? AND timestamp > ? LIMIT 1",
                (f"profile:{profile.name}", cutoff)
            ).fetchall()
            if rows and rows[0][0] > 0:
                active.append(profile)
        return active

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_registry(self):
        """Save profile registry to disk."""
        data = {
            "profiles": {name: p.to_dict() for name, p in self._profiles.items()},
            "name_counts": self._name_counts,
            "updated": datetime.now().isoformat(),
        }
        self._registry_file.write_text(json.dumps(data, indent=2))

    def _load_registry(self):
        """Load profile registry from disk."""
        if not self._registry_file.exists():
            return
        try:
            data = json.loads(self._registry_file.read_text())
            self._name_counts = data.get("name_counts", {})
            for name, pdata in data.get("profiles", {}).items():
                profile = Profile(
                    name=pdata["name"],
                    display_name=pdata.get("display_name", pdata["name"]),
                    workspace_dir=Path(pdata["workspace_dir"]),
                    sandbox_dir=Path(pdata["sandbox_dir"]),
                    instruction_file=Path(pdata["instruction_file"]),
                    memory_scope=pdata.get("memory_scope", "isolated"),
                    created_at=pdata.get("created_at", datetime.now().isoformat()),
                    tokens_in_total=pdata.get("tokens_in_total", 0),
                    tokens_out_total=pdata.get("tokens_out_total", 0),
                    cost_total=pdata.get("cost_total", 0.0),
                    task_count=pdata.get("task_count", 0),
                    metadata=pdata.get("metadata", {}),
                )
                self._profiles[name] = profile
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Budget tracking
    # ------------------------------------------------------------------

    def get_budget(self, profile_name: str) -> Dict:
        """Get budget status for a profile."""
        profile = self.get(profile_name)
        if not profile:
            return {"exists": False}
        return {
            "exists": True,
            "tokens_in": profile.tokens_in_total,
            "tokens_out": profile.tokens_out_total,
            "cost": profile.cost_total,
            "task_count": profile.task_count,
        }

    def reset_budget(self, profile_name: str):
        """Reset budget counters for a profile."""
        profile = self.get(profile_name)
        if profile:
            profile.tokens_in_total = 0
            profile.tokens_out_total = 0
            profile.cost_total = 0.0
            profile.task_count = 0
            self._save_registry()


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_registry: Optional[ProfileRegistry] = None


def get_registry() -> ProfileRegistry:
    """Get or create the global profile registry."""
    global _registry
    if _registry is None:
        _registry = ProfileRegistry()
    return _registry


def get_profile(name: str) -> Optional[Profile]:
    """Convenience: get a profile by name."""
    return get_registry().get(name)


def get_or_create_profile(name: str, memory_scope: str = "isolated") -> Profile:
    """Convenience: get or create a profile."""
    return get_registry().get_or_create(name, memory_scope)
