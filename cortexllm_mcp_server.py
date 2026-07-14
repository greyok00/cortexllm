#!/usr/bin/env python3
"""
CortexLLM MCP Server
Universal per-profile memory system for any MCP-compatible AI agent.

Provides:
- Memory resources (hot/warm/cold tiers)
- Tools (read, write, search memory)
- Cross-platform sync (OpenClaw, OpenCode, Claude Desktop, etc.)
"""

import json
import os
import sys
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, Tool, TextContent

# CortexLLM paths — override via CORTEXLLM_DIR env var
CORTEXLLM_DIR = Path(os.environ.get("CORTEXLLM_DIR", str(Path.home() / ".config/cortexllm")))
HOT_DIR = CORTEXLLM_DIR / "memory/hot"
WARM_DIR = CORTEXLLM_DIR / "memory/warm"
COLD_DIR = CORTEXLLM_DIR / "memory/cold"

# Initialize MCP server
app = Server("cortexllm")


class CortexLLMMemory:
    """Per-profile memory system with hot/warm/cold tiers"""
    
    def __init__(self):
        HOT_DIR.mkdir(parents=True, exist_ok=True)
        WARM_DIR.mkdir(parents=True, exist_ok=True)
        COLD_DIR.mkdir(parents=True, exist_ok=True)
    
    def get_hot(self, platform: str = "default") -> list:
        """Get hot memory messages for a platform. Returns list of messages."""
        hot_file = HOT_DIR / f"{platform}.json"
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
        hot_file = HOT_DIR / f"{platform}.json"
        hot_file.write_text(json.dumps({
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
        except:
            return []
    
    def get_warm_data(self) -> dict:
        """Get full warm memory dict."""
        return {
            "messages": self.get_warm()
        }
    
    def set_warm(self, messages: list):
        """Set warm memory. Always writes dict format."""
        warm_file = WARM_DIR / "per_profile.json"
        warm_file.write_text(json.dumps({
            "messages": messages
        }, indent=2))
    
    def set_warm_data(self, data: dict):
        """Set warm memory from full dict."""
        warm_file = WARM_DIR / "per_profile.json"
        warm_file.write_text(json.dumps(data, indent=2))
    
    def get_cold(self, category: str = None) -> dict:
        """Get cold storage (permanent knowledge)"""
        if category:
            cold_file = COLD_DIR / f"{category}.json"
            if cold_file.exists():
                try:
                    return json.loads(cold_file.read_text())
                except:
                    return {}
            return {}
        
        # List all categories
        categories = {}
        for f in COLD_DIR.glob("*.json"):
            try:
                categories[f.stem] = json.loads(f.read_text())
            except:
                pass
        return categories
    
    def set_cold(self, category: str, data: dict):
        """Save to cold storage"""
        cold_file = COLD_DIR / f"{category}.json"
        cold_file.write_text(json.dumps(data, indent=2))
    
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
            except:
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
            except:
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
            description="Permanent knowledge storage",
            mimeType="application/json"
        ),
    ]


@app.read_resource()
async def read_resource(uri: str) -> str:
    """Read memory resource"""
    if uri == "cortexllm://memory/hot":
        # Return all hot memories
        all_hot = {}
        for hot_file in HOT_DIR.glob("*.json"):
            try:
                data = json.loads(hot_file.read_text())
                if isinstance(data, dict):
                    all_hot[hot_file.stem] = data.get("messages", [])
                else:
                    all_hot[hot_file.stem] = data
            except:
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
            description="Search across all CortexLLM memory tiers",
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
            except:
                knowledge = {"content": content}
            
            data = memory.get_cold(category)
            if not data:
                data = {"category": category, "entries": []}
            
            data["entries"].append({
                "timestamp": datetime.now().isoformat(),
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
        results = memory.search(query, limit)
        return [TextContent(type="text", text=json.dumps(results, indent=2))]
    
    elif name == "memory_clear":
        tier = arguments.get("tier", "all")
        
        if tier == "hot":
            platform = arguments.get("platform")
            if platform:
                hot_file = HOT_DIR / f"{platform}.json"
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
            result = {"status": "cleared", "tier": "all"}
        
        else:
            result = {"error": "Invalid tier"}
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
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
