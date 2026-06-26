#!/bin/bash
# CortexLLM Config Sync
# Syncs source configs to runtime and vice versa

set -e

SOURCE_DIR="$HOME/.openclaw/cortexllm"
RUNTIME_DIR="$HOME/.config/cortexllm"

echo "Syncing CortexLLM configs..."

# Sync docs from source to runtime
echo "→ Copying documentation..."
cp "$SOURCE_DIR/AGENTS.md" "$RUNTIME_DIR/"
cp "$SOURCE_DIR/INSTALL.md" "$RUNTIME_DIR/"
cp "$SOURCE_DIR/TODO.md" "$RUNTIME_DIR/"
cp "$SOURCE_DIR/WALKTHROUGH.md" "$RUNTIME_DIR/"
cp "$SOURCE_DIR/README.md" "$RUNTIME_DIR/"

# Sync configs from runtime to source (runtime is source of truth)
echo "→ Syncing configs..."
cp "$RUNTIME_DIR/config.json" "$SOURCE_DIR/" 2>/dev/null || true
cp "$RUNTIME_DIR/USER_STYLE.md" "$SOURCE_DIR/" 2>/dev/null || true

# Verify sync
echo "→ Verifying..."
test -f "$RUNTIME_DIR/config.json" && echo "✓ config.json"
test -f "$RUNTIME_DIR/USER_STYLE.md" && echo "✓ USER_STYLE.md"
test -f "$RUNTIME_DIR/AGENTS.md" && echo "✓ AGENTS.md"
test -f "$RUNTIME_DIR/DEFAULTS.md" && echo "✓ DEFAULTS.md"

echo ""
echo "✓ Sync complete"
echo ""
echo "Runtime config: $RUNTIME_DIR"
echo "Source code:    $SOURCE_DIR"
