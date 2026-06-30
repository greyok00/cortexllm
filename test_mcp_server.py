#!/usr/bin/env python3
"""Test CortexLLM MCP Server"""

import subprocess
import json

# Test writing to memory
print("Testing CortexLLM MCP Server\n")

# Write a test message
result = subprocess.run(
    ['python3', '/home/grey/.config/cortexllm/cortexllm_mcp_server.py'],
    input=json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "memory_write",
            "arguments": {
                "tier": "hot",
                "platform": "test",
                "content": "MCP server test message",
                "role": "user"
            }
        }
    }).encode(),
    capture_output=True,
    timeout=5
)

if result.returncode == 0:
    print("✅ MCP server responded")
    try:
        response = json.loads(result.stdout)
        print(f"Response: {json.dumps(response, indent=2)}")
    except:
        print(f"Raw output: {result.stdout[:200]}")
else:
    print(f"❌ MCP server error: {result.stderr[:200]}")

# Check if memory was written
import pathlib
test_file = pathlib.Path.home() / ".config/cortexllm/memory/hot/test.json"
if test_file.exists():
    print(f"\n✅ Memory file created: {test_file}")
    print(f"Content: {test_file.read_text()[:200]}")
else:
    print(f"\n❌ Memory file not created")
