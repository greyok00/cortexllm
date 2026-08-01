#!/usr/bin/env python3
"""
CortexLLM MCP Server
Universal per-profile memory system for any MCP-compatible AI agent.

Provides:
- Memory resources (hot/warm/cold tiers)
- Tools (read, write, search memory)
- Wiki layer (structured facts with provenance, conflict resolution, freshness tracking)
- Cross-platform sync (OpenClaw, Claude Code, etc.)
- Model routing: memory_search/read routed to small local Ollama model
"""

import json
import asyncio
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, Tool, TextContent

# CortexLLM paths
CORTEXLLM_DIR = Path.home() / ".config/cortexllm"
HOT_DIR = CORTEXLLM_DIR / "memory/hot"
WARM_DIR = CORTEXLLM_DIR / "memory/warm"
COLD_DIR = CORTEXLLM_DIR / "memory/cold"

# Import database layer for wiki operations
try:
    from cortexllm_db import db
except ImportError:
    db = None

# Import model router for memory ops
try:
    from model_router import route_memory_search, route_memory_read
except ImportError:
    route_memory_search = None
    route_memory_read = None

# Initialize MCP server
app = Server("cortexllm")


def _sanitize_name(name: str) -> str:
    """Restrict names to safe characters [a-zA-Z0-9_-]"""
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', name)
    if not sanitized:
        raise ValueError(f"Name '{name}' contains no valid characters")
    return sanitized


def _safe_path(base_dir: Path, name: str, suffix: str = ".json") -> Path:
    """Resolve a path and verify it stays under the base directory"""
    safe_name = _sanitize_name(name)
    path = (base_dir / f"{safe_name}{suffix}").resolve()
    base_resolved = base_dir.resolve()
    if not str(path).startswith(str(base_resolved)):
        raise ValueError(f"Path traversal detected: {name}")
    return path


def _atomic_write(filepath: Path, data: str):
    """Write data atomically using temp file + rename (TOCTOU-safe)"""
    tmp = tempfile.NamedTemporaryFile(
        mode='w',
        dir=filepath.parent,
        suffix='.tmp',
        delete=False
    )
    try:
        tmp.write(data)
        tmp.close()
        Path(tmp.name).rename(filepath)
    except Exception:
        Path(tmp.name).unlink(missing_ok=True)
        raise


class CortexLLMMemory:
    """Per-profile memory system with hot/warm/cold tiers"""

    def __init__(self):
        HOT_DIR.mkdir(parents=True, exist_ok=True)
        WARM_DIR.mkdir(parents=True, exist_ok=True)
        COLD_DIR.mkdir(parents=True, exist_ok=True)

    def get_hot(self, platform: str = "default") -> list:
        """Get hot memory messages for a platform. Returns list of messages."""
        hot_file = _safe_path(HOT_DIR, platform)
        if not hot_file.exists():
            return []
        try:
            data = json.loads(hot_file.read_text())
            if isinstance(data, dict):
                return data.get("messages", [])
            return data
        except Exception as e:
            print(f"Warning: failed to read hot memory for {platform}: {e}")
            return []

    def get_hot_data(self, platform: str = "default") -> dict:
        """Get full hot memory dict with platform + messages keys."""
        return {
            "platform": platform,
            "messages": self.get_hot(platform)
        }

    def set_hot(self, platform: str, messages: list):
        """Set hot memory for a platform. Always writes dict format."""
        hot_file = _safe_path(HOT_DIR, platform)
        _atomic_write(hot_file, json.dumps({
            "platform": platform,
            "messages": messages
        }, indent=2))

    def append_hot(self, platform: str, content: str, role: str = "user", metadata: dict = None):
        """Append message to hot memory"""
        messages = self.get_hot(platform)
        message = {
            "role": role,
            "content": content,
            "metadata": metadata or {}
        }
        messages.append(message)
        messages = messages[-500:]  # Keep last 500
        self.set_hot(platform, messages)
        return message

    def get_warm(self) -> list:
        """Get warm (per-profile) memory messages. Returns list of messages."""
        warm_file = WARM_DIR / "per_profile.json"
        if not warm_file.exists():
            return []
        try:
            data = json.loads(warm_file.read_text())
            if isinstance(data, dict):
                return data.get("messages", [])
            return data
        except Exception:
            return []

    def get_warm_data(self) -> dict:
        """Get full warm memory dict."""
        return {
            "messages": self.get_warm()
        }

    def set_warm(self, messages: list):
        """Set warm memory. Always writes dict format."""
        warm_file = WARM_DIR / "per_profile.json"
        _atomic_write(warm_file, json.dumps({
            "messages": messages
        }, indent=2))

    def set_warm_data(self, data: dict):
        """Set warm memory from full dict."""
        warm_file = WARM_DIR / "per_profile.json"
        _atomic_write(warm_file, json.dumps(data, indent=2))

    def get_cold(self, category: str = None) -> dict:
        """Get cold storage (permanent knowledge)"""
        if category:
            cold_file = _safe_path(COLD_DIR, category)
            if cold_file.exists():
                try:
                    return json.loads(cold_file.read_text())
                except Exception:
                    return {}
            return {}

        # List all categories
        categories = {}
        for f in COLD_DIR.glob("*.json"):
            try:
                categories[f.stem] = json.loads(f.read_text())
            except Exception:
                pass
        return categories

    def set_cold(self, category: str, data: dict):
        """Save to cold storage"""
        cold_file = _safe_path(COLD_DIR, category)
        _atomic_write(cold_file, json.dumps(data, indent=2))

    def search(self, query: str, limit: int = 10) -> list:
        """Search across all memory tiers"""
        results = []
        query_lower = query.lower()

        # Search hot memory (all platforms)
        for hot_file in HOT_DIR.glob("*.json"):
            try:
                data = json.loads(hot_file.read_text())
                msgs = data.get("messages", []) if isinstance(data, dict) else data
                for msg in msgs[-limit:]:
                    content = msg.get("content", "")
                    if query_lower in content.lower():
                        results.append({
                            "source": f"hot/{hot_file.stem}",
                            "content": content[:200],
                            "relevance": 0.8
                        })
            except Exception:
                pass

        # Search warm memory
        warm_messages = self.get_warm()
        for msg in warm_messages[-limit*2:]:
            content = msg.get("content", "")
            if query_lower in content.lower():
                results.append({
                    "source": "warm/per_profile",
                    "content": content[:200],
                    "relevance": 0.9
                })

        # Search cold storage
        for cold_file in COLD_DIR.glob("*.json"):
            try:
                data = json.loads(cold_file.read_text())
                entries = data.get("entries", [])
                for entry in entries:
                    knowledge = json.dumps(entry.get("knowledge", {}))
                    if query_lower in knowledge.lower():
                        results.append({
                            "source": f"cold/{cold_file.stem}",
                            "content": knowledge[:200],
                            "relevance": 1.0
                        })
            except Exception:
                pass

        # Sort by relevance
        results.sort(key=lambda x: x["relevance"], reverse=True)
        return results[:limit]


# Global memory instance
memory = CortexLLMMemory()


@app.list_resources()
async def list_resources() -> list[Resource]:
    """List available memory resources"""
    return [
        Resource(
            uri="cortexllm://memory/hot",
            name="Hot Memory",
            description="Active session memory (per-platform)",
            mimeType="application/json"
        ),
        Resource(
            uri="cortexllm://memory/warm",
            name="Warm Memory",
            description="Unified cross-platform memory",
            mimeType="application/json"
        ),
        Resource(
            uri="cortexllm://memory/cold",
            name="Cold Memory",
            description="Permanent knowledge storage + wiki layer",
            mimeType="application/json"
        ),
    ]


@app.read_resource()
async def read_resource(uri: str) -> str:
    """Read memory resource"""
    if uri == "cortexllm://memory/hot":
        all_hot = {}
        for hot_file in HOT_DIR.glob("*.json"):
            try:
                data = json.loads(hot_file.read_text())
                if isinstance(data, dict):
                    all_hot[hot_file.stem] = data.get("messages", [])
                else:
                    all_hot[hot_file.stem] = data
            except Exception:
                pass
        return json.dumps(all_hot, indent=2)

    elif uri == "cortexllm://memory/warm":
        return json.dumps(memory.get_warm_data(), indent=2)

    elif uri == "cortexllm://memory/cold":
        return json.dumps(memory.get_cold(), indent=2)

    else:
        raise ValueError(f"Unknown resource: {uri}")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available memory tools"""
    return [
        Tool(
            name="memory_read",
            description="Read from CortexLLM per-profile memory",
            inputSchema={
                "type": "object",
                "properties": {
                    "tier": {
                        "type": "string",
                        "enum": ["hot", "warm", "cold"],
                        "description": "Memory tier to read from"
                    },
                    "platform": {
                        "type": "string",
                        "description": "Platform name (for hot memory)"
                    },
                    "category": {
                        "type": "string",
                        "description": "Category name (for cold memory)"
                    }
                },
                "required": ["tier"]
            }
        ),
        Tool(
            name="memory_write",
            description="Write to CortexLLM per-profile memory",
            inputSchema={
                "type": "object",
                "properties": {
                    "tier": {
                        "type": "string",
                        "enum": ["hot", "warm", "cold"],
                        "description": "Memory tier to write to"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write"
                    },
                    "platform": {
                        "type": "string",
                        "description": "Platform name (for hot memory)"
                    },
                    "category": {
                        "type": "string",
                        "description": "Category name (for cold memory)"
                    },
                    "role": {
                        "type": "string",
                        "enum": ["user", "assistant", "system"],
                        "description": "Message role"
                    }
                },
                "required": ["tier", "content"]
            }
        ),
        Tool(
            name="memory_search",
            description="Search across all CortexLLM memory tiers (routed to small local Ollama model)",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default: 10)"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="memory_clear",
            description="Clear CortexLLM memory (use with caution)",
            inputSchema={
                "type": "object",
                "properties": {
                    "tier": {
                        "type": "string",
                        "enum": ["hot", "warm", "all"],
                        "description": "Which memory to clear"
                    },
                    "platform": {
                        "type": "string",
                        "description": "Platform to clear (for hot memory)"
                    }
                },
                "required": ["tier"]
            }
        ),
        # Wiki layer tools
        Tool(
            name="wiki_add",
            description="Add a structured wiki fact with UPSERT conflict resolution",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "description": "Subject of the fact (e.g., 'user_preference', 'system_config')"
                    },
                    "attribute": {
                        "type": "string",
                        "description": "Specific attribute (e.g., 'theme', 'model')"
                    },
                    "claim": {
                        "type": "string",
                        "description": "The claim/statement"
                    },
                    "evidence": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Supporting evidence URLs or references"
                    },
                    "provenance": {
                        "type": "string",
                        "enum": ["openclaw", "claude"],
                        "description": "Which platform/session wrote this"
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Confidence score (0-1)"
                    }
                },
                "required": ["entity", "attribute", "claim", "provenance"]
            }
        ),
        Tool(
            name="wiki_get",
            description="Get the current wiki fact for an entity/attribute",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "description": "Subject of the fact"
                    },
                    "attribute": {
                        "type": "string",
                        "description": "Specific attribute"
                    },
                    "provenance": {
                        "type": "string",
                        "description": "Optional platform filter"
                    }
                },
                "required": ["entity", "attribute"]
            }
        ),
        Tool(
            name="wiki_search",
            description="Search wiki facts with freshness-weighted ranking",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default: 20)"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="wiki_reconcile",
            description="Resolve a contradiction chain for an entity/attribute",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "description": "Subject of the fact"
                    },
                    "attribute": {
                        "type": "string",
                        "description": "Specific attribute"
                    },
                    "winning_id": {
                        "type": "integer",
                        "description": "ID of the winning fact row"
                    },
                    "provenance": {
                        "type": "string",
                        "description": "Optional platform filter"
                    }
                },
                "required": ["entity", "attribute", "winning_id"]
            }
        ),
        Tool(
            name="wiki_verify",
            description="Mark a fact as verified (updates last_verified timestamp)",
            inputSchema={
                "type": "object",
                "properties": {
                    "fact_id": {
                        "type": "integer",
                        "description": "ID of the fact to verify"
                    }
                },
                "required": ["fact_id"]
            }
        ),
        Tool(
            name="wiki_stale",
            description="List facts that haven't been verified within the freshness window",
            inputSchema={
                "type": "object",
                "properties": {
                    "window_days": {
                        "type": "integer",
                        "description": "Freshness window in days (default: 30)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default: 100)"
                    }
                },
                "required": []
            }
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute memory tool"""

    if name == "memory_read":
        tier = arguments.get("tier", "warm")

        if tier == "hot":
            platform = arguments.get("platform", "default")
            data = memory.get_hot(platform)

        elif tier == "warm":
            data = memory.get_warm()

        elif tier == "cold":
            category = arguments.get("category")
            data = memory.get_cold(category)

        else:
            data = {"error": "Invalid tier"}

        return [TextContent(type="text", text=json.dumps(data, indent=2))]

    elif name == "memory_write":
        tier = arguments.get("tier", "warm")
        content = arguments.get("content", "")
        role = arguments.get("role", "user")

        if tier == "hot":
            platform = arguments.get("platform", "default")
            result = memory.append_hot(platform, content, role)

        elif tier == "warm":
            messages = memory.get_warm()
            messages.append({"role": role, "content": content})
            messages = messages[-2000:]
            memory.set_warm(messages)
            result = {"status": "written", "tier": "warm"}

        elif tier == "cold":
            category = arguments.get("category", "general")
            try:
                knowledge = json.loads(content)
            except Exception:
                knowledge = {"content": content}

            data = memory.get_cold(category)
            if not data:
                data = {"category": category, "entries": []}

            data["entries"].append({
                "timestamp": datetime.utcnow().isoformat(),
                "knowledge": knowledge
            })
            memory.set_cold(category, data)
            result = {"status": "written", "tier": "cold", "category": category}

        else:
            result = {"error": "Invalid tier"}

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "memory_search":
        query = arguments.get("query", "")
        limit = arguments.get("limit", 10)
        # Route to small local Ollama model for ranking/filtering
        if route_memory_search is not None:
            results = route_memory_search(query, limit, memory)
        else:
            results = memory.search(query, limit)
        return [TextContent(type="text", text=json.dumps(results, indent=2))]

    elif name == "memory_clear":
        tier = arguments.get("tier", "all")

        if tier == "hot":
            platform = arguments.get("platform")
            if platform:
                hot_file = _safe_path(HOT_DIR, platform)
                if hot_file.exists():
                    hot_file.unlink()
                result = {"status": "cleared", "platform": platform}
            else:
                for f in HOT_DIR.glob("*.json"):
                    f.unlink()
                result = {"status": "cleared", "tier": "hot"}

        elif tier == "warm":
            warm_file = WARM_DIR / "per_profile.json"
            if warm_file.exists():
                warm_file.unlink()
            result = {"status": "cleared", "tier": "warm"}

        elif tier == "all":
            for f in HOT_DIR.glob("*.json"):
                f.unlink()
            warm_file = WARM_DIR / "per_profile.json"
            if warm_file.exists():
                warm_file.unlink()
            for f in COLD_DIR.glob("*.json"):
                f.unlink()
            result = {"status": "cleared", "tier": "all"}

        else:
            result = {"error": "Invalid tier"}

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # Wiki layer tools
    elif name == "wiki_add":
        if db is None:
            return [TextContent(type="text", text=json.dumps({"error": "Database layer not available"}, indent=2))]
        entity = arguments["entity"]
        attribute = arguments["attribute"]
        claim = arguments["claim"]
        provenance = arguments["provenance"]
        evidence = arguments.get("evidence", [])
        confidence = arguments.get("confidence", 0.5)

        new_id = db.add_wiki_fact(
            entity=entity, attribute=attribute, claim=claim,
            provenance=provenance, evidence=evidence,
            confidence=confidence
        )
        return [TextContent(type="text", text=json.dumps({
            "status": "written",
            "id": new_id,
            "entity": entity,
            "attribute": attribute,
            "provenance": provenance
        }, indent=2))]

    elif name == "wiki_get":
        if db is None:
            return [TextContent(type="text", text=json.dumps({"error": "Database layer not available"}, indent=2))]
        entity = arguments["entity"]
        attribute = arguments["attribute"]
        provenance = arguments.get("provenance")
        fact = db.get_wiki_fact(entity, attribute, provenance)
        if fact:
            return [TextContent(type="text", text=json.dumps(fact, indent=2, default=str))]
        return [TextContent(type="text", text=json.dumps({"error": "Not found"}, indent=2))]

    elif name == "wiki_search":
        if db is None:
            return [TextContent(type="text", text=json.dumps({"error": "Database layer not available"}, indent=2))]
        query = arguments.get("query", "")
        limit = arguments.get("limit", 20)
        results = db.search_wiki(query, limit)
        return [TextContent(type="text", text=json.dumps(results, indent=2, default=str))]

    elif name == "wiki_reconcile":
        if db is None:
            return [TextContent(type="text", text=json.dumps({"error": "Database layer not available"}, indent=2))]
        entity = arguments["entity"]
        attribute = arguments["attribute"]
        winning_id = arguments["winning_id"]
        provenance = arguments.get("provenance")
        db.reconcile_contradiction(entity, attribute, winning_id, provenance)
        return [TextContent(type="text", text=json.dumps({
            "status": "reconciled",
            "entity": entity,
            "attribute": attribute,
            "winning_id": winning_id
        }, indent=2))]

    elif name == "wiki_verify":
        if db is None:
            return [TextContent(type="text", text=json.dumps({"error": "Database layer not available"}, indent=2))]
        fact_id = arguments["fact_id"]
        updated = db.verify_fact(fact_id)
        return [TextContent(type="text", text=json.dumps({
            "status": "verified" if updated else "not_found",
            "fact_id": fact_id
        }, indent=2))]

    elif name == "wiki_stale":
        if db is None:
            return [TextContent(type="text", text=json.dumps({"error": "Database layer not available"}, indent=2))]
        window_days = arguments.get("window_days", 30)
        limit = arguments.get("limit", 100)
        facts = db.get_stale_facts(window_days, limit)
        return [TextContent(type="text", text=json.dumps(facts, indent=2, default=str))]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Run MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
