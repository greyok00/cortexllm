#!/bin/bash
# CortexLLM Config Sync
# Syncs source configs to runtime and vice versa

set -e

SOURCE_DIR="$HOME/.openclaw/cortexllm"
RUNTIME_DIR="$HOME/.config/cortexllm"

echo "Syncing CortexLLM configs..."

# Sync docs from source to runtime
echo "\u2192 Copying documentation..."
cp "$SOURCE_DIR/AGENTS.md"     "$RUNTIME_DIR/"
cp "$SOURCE_DIR/INSTALL.md"    "$RUNTIME_DIR/"
cp "$SOURCE_DIR/TODO.md"       "$RUNTIME_DIR/"
cp "$SOURCE_DIR/WALKTHROUGH.md" "$RUNTIME_DIR/"
cp "$SOURCE_DIR/README.md"     "$RUNTIME_DIR/"

# Sync configs from runtime to source (runtime is source of truth)
echo "\u2192 Syncing configs..."
cp "$RUNTIME_DIR/config.json"    "$SOURCE_DIR/" 2>/dev/null || true
cp "$RUNTIME_DIR/USER_STYLE.md" "$SOURCE_DIR/" 2>/dev/null || true

# Verify files that are actually copied above
echo "\u2192 Verifying..."
test -f "$RUNTIME_DIR/config.json"  && echo "\u2713 config.json"  || echo "\u26a0 config.json missing"
test -f "$RUNTIME_DIR/USER_STYLE.md" && echo "\u2713 USER_STYLE.md" || echo "\u26a0 USER_STYLE.md missing"
test -f "$RUNTIME_DIR/AGENTS.md"    && echo "\u2713 AGENTS.md"    || echo "\u26a0 AGENTS.md missing"
test -f "$RUNTIME_DIR/INSTALL.md"   && echo "\u2713 INSTALL.md"   || echo "\u26a0 INSTALL.md missing"

echo ""
echo "\u2713 Sync complete"
echo ""
echo "Runtime config: $RUNTIME_DIR"
echo "Source code:    $SOURCE_DIR"
