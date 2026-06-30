#!/bin/bash
# CortexLLM Production Config Installer for OpenClaw

set -e

OPENCLAW_DIR="${HOME}/.openclaw"

echo "=== CortexLLM Production Config Installer ==="
echo ""

# Check if OpenClaw is installed
if [ ! -d "$OPENCLAW_DIR" ]; then
    echo "Error: OpenClaw not found at $OPENCLAW_DIR"
    echo "Please install OpenClaw first."
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing to: $OPENCLAW_DIR"
echo ""

# Install workspace configs
echo "1. Installing workspace configs (SOUL.md, AGENTS.md)..."
cp -v "$SCRIPT_DIR/workspace/SOUL.md" "$OPENCLAW_DIR/workspace/SOUL.md"
cp -v "$SCRIPT_DIR/workspace/AGENTS.md" "$OPENCLAW_DIR/workspace/AGENTS.md"

# Install production platform configs
echo ""
echo "2. Installing production platform configs..."
mkdir -p "$OPENCLAW_DIR/production/platforms"
cp -rv "$SCRIPT_DIR/production/platforms/"* "$OPENCLAW_DIR/production/platforms/"

# Install config template
echo ""
echo "3. Installing config template..."
if [ ! -f "$OPENCLAW_DIR/openclaw.json.bak" ]; then
    cp -v "$OPENCLAW_DIR/openclaw.json" "$OPENCLAW_DIR/openclaw.json.bak" 2>/dev/null || true
fi
cp -v "$SCRIPT_DIR/openclaw.json.config" "$OPENCLAW_DIR/openclaw.json"

echo ""
echo "=== Installation Complete ==="
echo ""
echo "IMPORTANT: Edit ~/.openclaw/openclaw.json and set your auth token!"
echo ""
echo "Then restart OpenClaw gateway:"
echo "  pkill -f 'openclaw.*gateway'"
echo "  openclaw gateway --port 18789"
